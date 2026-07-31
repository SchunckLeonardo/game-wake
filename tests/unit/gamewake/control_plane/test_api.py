from decimal import Decimal

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.billing import (
    Billing,
    ContributionPackage,
    InMemoryBillingRepository,
    PaymentCheckout,
)
from gamewake.control_plane import (
    ApiRequest,
    ConnectionDetails,
    GameWakeApi,
    GameWakeApplication,
)
from gamewake.game_catalog import GameCatalog
from gamewake.worlds import InMemoryWorldRepository, Worlds


class RecordingOperationDispatcher:
    def __init__(self):
        self.calls = []

    def start(self, account_id, operation_id):
        self.calls.append((account_id, operation_id))


class CheckoutProvider:
    def create_checkout(self, request):
        return PaymentCheckout(
            id="bill_123",
            external_id=request.external_id,
            url="https://pay.abacatepay.com/bill_123",
            amount=request.expected_amount,
        )


class StubConnectionDetailsProvider:
    def issue(self, world, *, viewer_user_id):
        assert viewer_user_id == "owner"
        return ConnectionDetails(host="203.0.113.10", port=8211, password="grupo-secreto")


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
    effective = api.handle(
        ApiRequest(
            method="GET",
            path=f"/api/v1/accounts/{account_id}/worlds/{world_id}/configuration",
            user_id="owner",
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
    assert (
        configured.body["world"]["pendingConfigurationRevisionId"]
        == configured.body["revision"]["id"]
    )
    assert effective.body["revision"]["number"] == 2


def test_world_queries_and_wake_dispatch_use_the_same_persisted_operation():
    accounts = Accounts(InMemoryAccountRepository())
    owner = accounts.sign_in_with_discord(discord_user_id="discord-owner", display_name="Leonardo")
    account = accounts.create_account(name="Grupo", owner_user_id=owner.id)
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog)
    world = worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    dispatcher = RecordingOperationDispatcher()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
            operation_dispatcher=dispatcher,
        )
    )

    listed = api.handle(ApiRequest("GET", f"/api/v1/accounts/{account.id}/worlds", owner.id))
    started = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/wake",
            owner.id,
            {"idempotencyKey": "web:wake:1"},
        )
    )
    repeated = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/wake",
            owner.id,
            {"idempotencyKey": "web:wake:1"},
        )
    )
    operation_id = started.body["operation"]["id"]
    progress = api.handle(
        ApiRequest(
            "GET",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/operations",
            owner.id,
        )
    )

    assert listed.status == 200
    assert listed.body["worlds"][0]["id"] == world.id
    assert started.status == 202
    assert repeated.body == started.body
    assert dispatcher.calls == [(account.id, operation_id), (account.id, operation_id)]
    assert progress.body["operations"][0]["phase"] == "requested"


def test_wallet_endpoint_exposes_safe_ledger_values_as_decimal_strings():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    billing = Billing(InMemoryBillingRepository())
    billing.credit_wallet(
        account.id,
        amount=Decimal("25.00"),
        reference="beta-credit",
        idempotency_key="credit-1",
    )
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=billing,
            game_catalog=catalog,
        )
    )

    response = api.handle(ApiRequest("GET", f"/api/v1/accounts/{account.id}/wallet", "owner"))

    assert response.status == 200
    assert response.body["wallet"]["currency"] == "BRL"
    assert response.body["wallet"]["availableBalance"] == "25.00"
    assert response.body["wallet"]["statement"][0]["amount"] == "25.00"


def test_any_account_member_can_create_only_an_allowlisted_credit_package():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=CheckoutProvider(),
        contribution_packages=(ContributionPackage("credits-25", Decimal("25.00"), "prod_25"),),
    )
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=billing,
            game_catalog=catalog,
        )
    )

    response = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/wallet/contributions",
            "owner",
            {
                "packageId": "credits-25",
                "returnUrl": "https://app.gamewake.example/wallet",
                "completionUrl": "https://app.gamewake.example/wallet?paid=1",
                "idempotencyKey": "web:contribution:1",
            },
        )
    )

    assert response.status == 201
    assert response.body["contribution"]["amount"] == "25.00"
    assert response.body["contribution"]["checkoutUrl"].startswith("https://pay.")


def test_connection_details_endpoint_keeps_the_shared_secret_in_an_authenticated_response():
    class OnlineWorlds:
        def get_world(self, account_id, world_id, *, viewer_user_id):
            from gamewake.worlds import World, WorldStatus

            return World(
                id=world_id,
                account_id=account_id,
                name="Palpagos",
                game_template_id="palworld:1",
                region="sa-east-1",
                runtime_profile_id="palworld-small",
                status=WorldStatus.ONLINE,
                runtime_id="i-123",
                runtime_provider_reference="i-123",
                configuration_revision_id="configuration-1",
                pending_configuration_revision_id=None,
                stored_state_id=None,
                stored_state_checksum=None,
                version=1,
            )

    application = GameWakeApplication(
        accounts=object(),
        worlds=OnlineWorlds(),
        billing=object(),
        game_catalog=GameCatalog.with_palworld(),
        connection_details_provider=StubConnectionDetailsProvider(),
    )

    response = GameWakeApi(application).handle(
        ApiRequest(
            "GET",
            "/api/v1/accounts/account-1/worlds/world-1/connection",
            "owner",
        )
    )

    assert response.status == 200
    assert response.body == {
        "connection": {
            "host": "203.0.113.10",
            "port": 8211,
            "password": "grupo-secreto",
        }
    }


def test_authenticated_user_can_discover_only_their_accounts_for_console_routing():
    repository = InMemoryAccountRepository()
    accounts = Accounts(repository)
    mine = accounts.create_account(name="Meu grupo", owner_user_id="owner")
    accounts.create_account(name="Outro grupo", owner_user_id="someone-else")
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    response = api.handle(ApiRequest("GET", "/api/v1/me/accounts", "owner"))

    assert response.status == 200
    assert response.body == {
        "accounts": [{"id": mine.id, "name": "Meu grupo", "discordGuildId": None}]
    }
