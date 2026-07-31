from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.billing import Billing, InMemoryBillingRepository
from gamewake.control_plane import ApiRequest, GameWakeApi, GameWakeApplication
from gamewake.game_catalog import GameCatalog
from gamewake.worlds import InMemoryWorldRepository, Worlds


def test_web_onboarding_invites_friends_and_configures_first_world_through_one_api():
    accounts = Accounts(InMemoryAccountRepository())
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog)
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    created_account = api.handle(
        ApiRequest(
            method="POST",
            path="/api/v1/accounts",
            user_id="owner",
            body={"name": "Sexta com os amigos", "discordGuildId": "guild-1"},
        )
    )
    account_id = created_account.body["account"]["id"]
    invited = api.handle(
        ApiRequest(
            method="POST",
            path=f"/api/v1/accounts/{account_id}/invitations",
            user_id="owner",
            body={"invitedUserIds": ["friend-1", "friend-2", "friend-3"]},
        )
    )
    created_world = api.handle(
        ApiRequest(
            method="POST",
            path=f"/api/v1/accounts/{account_id}/worlds",
            user_id="owner",
            body={
                "name": "Palpagos",
                "gameTemplateId": "palworld:1",
                "region": "br-sao-paulo",
                "runtimeProfileId": "palworld-small",
            },
        )
    )
    world_id = created_world.body["world"]["id"]
    schema = api.handle(
        ApiRequest(
            method="GET",
            path=f"/api/v1/accounts/{account_id}/worlds/{world_id}/configuration/schema",
            user_id="owner",
        )
    )
    configured = api.handle(
        ApiRequest(
            method="PATCH",
            path=f"/api/v1/accounts/{account_id}/worlds/{world_id}/configuration",
            user_id="owner",
            body={
                "changes": {
                    "enemy_drop_item_rate": 3.0,
                    "base_camp_worker_max_num": 25,
                },
                "idempotencyKey": "web-config-1",
            },
        )
    )

    assert created_account.status == 201
    assert invited.status == 201
    assert len(invited.body["invitations"]) == 3
    assert created_world.status == 201
    drop_rate = next(
        field
        for field in schema.body["template"]["configurationFields"]
        if field["key"] == "enemy_drop_item_rate"
    )
    assert drop_rate["acceptedValues"]
    assert drop_rate["officialDocumentationUrl"].startswith("https://")
    assert drop_rate["restartRequired"] is True
    assert configured.status == 200
    assert configured.body["revision"]["number"] == 2
    assert configured.body["revision"]["origin"] == "web"
    assert configured.body["revision"]["actorUserId"] == "owner"
    assert configured.body["world"]["pendingConfigurationRevisionId"] == configured.body[
        "revision"
    ]["id"]
