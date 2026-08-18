from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gamewake.accounts import (
    Accounts,
    InMemoryAccountRepository,
    InMemoryRecoverySecretStore,
    Permission,
    SensitiveActionConfirmation,
)
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
    WorldPasswordSettings,
)
from gamewake.game_catalog import GameCatalog
from gamewake.worlds import (
    InMemoryWorldArchiveStore,
    InMemoryWorldRepository,
    WorldData,
    Worlds,
)


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


class StubWorldPasswordManager:
    def __init__(self):
        self.calls = []

    def get(self, world):
        self.calls.append(("get", world.id))
        return WorldPasswordSettings(mode="fixed")

    def configure(self, world, *, mode, password):
        self.calls.append(("configure", world.id, mode, password))
        return WorldPasswordSettings(mode=mode)


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


def test_web_onboarding_enables_recovery_for_a_sole_owner_with_verified_discord_email():
    accounts = Accounts(
        InMemoryAccountRepository(),
        recovery_secret_store=InMemoryRecoverySecretStore(),
    )
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    response = api.handle(
        ApiRequest(
            "POST",
            "/api/v1/accounts",
            "owner",
            {"name": "Grupo"},
            verified_email="owner@example.com",
        )
    )

    assert response.status == 201
    assert response.body["ownerRecovery"]["verifiedEmail"] == "owner@example.com"
    assert len(response.body["ownerRecovery"]["codes"]) == 8
    assert accounts.owner_recovery_ready(response.body["account"]["id"]) is True


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


def test_owner_sets_and_reads_the_monthly_world_budget_through_the_api():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    configured = api.handle(
        ApiRequest(
            "PUT",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/budget",
            "owner",
            {"monthlyLimit": "75.00", "idempotencyKey": "web:budget:1"},
        )
    )
    status = api.handle(
        ApiRequest(
            "GET",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/budget",
            "owner",
        )
    )

    assert configured.status == 200
    assert configured.body["budget"] == {
        "worldId": world.id,
        "period": configured.body["budget"]["period"],
        "monthlyLimit": "75.00",
        "spent": "0.00",
        "reserved": "0.00",
        "committed": "0.00",
        "percentage": "0.00",
        "wakeAllowed": True,
    }
    assert status == configured


def test_manager_configures_per_world_auto_sleep_from_supported_choices():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    configured = api.handle(
        ApiRequest(
            "PATCH",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/settings",
            "owner",
            {"autoSleepMinutes": 60},
        )
    )
    disabled = api.handle(
        ApiRequest(
            "PATCH",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/settings",
            "owner",
            {"autoSleepMinutes": None},
        )
    )
    invalid = api.handle(
        ApiRequest(
            "PATCH",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/settings",
            "owner",
            {"autoSleepMinutes": 15},
        )
    )

    assert configured.status == 200
    assert configured.body["world"]["autoSleepMinutes"] == 60
    assert disabled.body["world"]["autoSleepMinutes"] is None
    assert invalid.status == 400


def test_owner_revokes_a_membership_through_a_step_up_authenticated_api_request():
    now = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    invitation = accounts.invite_members(
        account.id,
        inviter_user_id="owner",
        invited_user_ids=["friend"],
    )[0]
    membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    response = api.handle(
        ApiRequest(
            "DELETE",
            f"/api/v1/accounts/{account.id}/memberships/{membership.id}",
            "owner",
            {"confirmedResourceName": "Grupo"},
            authenticated_at=now,
        )
    )

    assert response.status == 200
    assert response.body == {"removed": True}
    assert accounts.list_memberships(account.id, viewer_user_id="owner")[0].user_id == "owner"


def test_any_account_member_can_create_only_an_allowlisted_credit_package():
    accounts = Accounts(
        InMemoryAccountRepository(),
        recovery_secret_store=InMemoryRecoverySecretStore(),
    )
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    accounts.enable_owner_recovery(
        account.id,
        owner_user_id="owner",
        verified_email="owner@example.com",
    )
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


def test_checkout_receives_the_verified_discord_payer_information():
    class RecordingCheckoutProvider(CheckoutProvider):
        def __init__(self):
            self.request = None

        def create_checkout(self, request):
            self.request = request
            return super().create_checkout(request)

    repository = InMemoryAccountRepository()
    accounts = Accounts(
        repository,
        recovery_secret_store=InMemoryRecoverySecretStore(),
    )
    user = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(name="Grupo", owner_user_id=user.id)
    accounts.enable_owner_recovery(
        account.id,
        owner_user_id=user.id,
        verified_email="leo@example.com",
    )
    provider = RecordingCheckoutProvider()
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(
                InMemoryBillingRepository(),
                payment_provider=provider,
                contribution_packages=(
                    ContributionPackage("credits-25", Decimal("25.00"), "prod_25"),
                ),
            ),
            game_catalog=catalog,
        )
    )

    response = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/wallet/contributions",
            user.id,
            {
                "packageId": "credits-25",
                "returnUrl": "https://app.gamewake.example/wallet",
                "completionUrl": "https://app.gamewake.example/wallet?payment=complete",
                "idempotencyKey": "web:contribution:payer",
            },
            verified_email="leo@example.com",
        )
    )

    assert response.status == 201
    assert provider.request.payer_name == "Leonardo"
    assert provider.request.payer_email == "leo@example.com"


def test_paid_checkout_can_be_reconciled_when_the_webhook_did_not_credit_the_wallet():
    class PaidCheckoutProvider(CheckoutProvider):
        def find_checkout(self, external_id):
            return PaymentCheckout(
                id="bill_123",
                external_id=external_id,
                url="https://pay.abacatepay.com/bill_123",
                amount=Decimal("25.00"),
                status="PAID",
                paid_amount=Decimal("25.00"),
            )

    accounts = Accounts(
        InMemoryAccountRepository(),
        recovery_secret_store=InMemoryRecoverySecretStore(),
    )
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    accounts.enable_owner_recovery(
        account.id,
        owner_user_id="owner",
        verified_email="owner@example.com",
    )
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=PaidCheckoutProvider(),
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
    created = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/wallet/contributions",
            "owner",
            {
                "packageId": "credits-25",
                "returnUrl": "https://app.gamewake.example/wallet",
                "completionUrl": "https://app.gamewake.example/wallet?payment=complete",
                "idempotencyKey": "web:contribution:reconcile",
            },
        )
    )
    contribution_id = created.body["contribution"]["id"]

    reconciled = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/wallet/contributions/{contribution_id}/reconcile",
            "owner",
        )
    )

    assert reconciled.status == 200
    assert reconciled.body["contribution"]["status"] == "completed"
    assert billing.get_wallet(account.id).available_balance == Decimal("25.00")


def test_first_payment_is_blocked_until_a_sole_owner_has_recovery_ready():
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
                "idempotencyKey": "web:contribution:without-recovery",
            },
        )
    )

    assert response.status == 403
    assert "recovery" in response.body["error"]["message"].casefold()


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
        "accounts": [
            {
                "id": mine.id,
                "name": "Meu grupo",
                "discordGuildId": None,
                "discordChannelConfigured": False,
                "access": {
                    "roles": ["owner"],
                    "permissions": sorted(permission.value for permission in Permission),
                },
            }
        ]
    }


def test_account_projection_reports_discord_channel_readiness_without_exposing_channel_id():
    repository = InMemoryAccountRepository()
    accounts = Accounts(repository)
    mine = accounts.create_account(
        name="Meu grupo",
        owner_user_id="owner",
        discord_guild_id="123456789012345678",
        discord_channel_id="987654321098765432",
    )
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

    [account] = response.body["accounts"]
    assert account["id"] == mine.id
    assert account["discordGuildId"] == "123456789012345678"
    assert account["discordChannelConfigured"] is True
    assert "discordChannelId" not in account


def test_manager_configures_world_password_policy_without_returning_the_secret():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog)
    target = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    invitation = accounts.invite_members(
        account.id,
        inviter_user_id="owner",
        invited_user_ids=["player"],
    )[0]
    accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="player",
    )
    passwords = StubWorldPasswordManager()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
            world_password_manager=passwords,
        )
    )

    updated = api.handle(
        ApiRequest(
            "PATCH",
            f"/api/v1/accounts/{account.id}/worlds/{target.id}/access/password",
            "owner",
            {"mode": "fixed", "password": "meu-segredo-123"},
        )
    )
    loaded = api.handle(
        ApiRequest(
            "GET",
            f"/api/v1/accounts/{account.id}/worlds/{target.id}/access/password",
            "owner",
        )
    )
    forbidden = api.handle(
        ApiRequest(
            "PATCH",
            f"/api/v1/accounts/{account.id}/worlds/{target.id}/access/password",
            "player",
            {"mode": "random_each_run"},
        )
    )

    assert updated.status == 200
    assert updated.body == {"password": {"mode": "fixed"}}
    assert loaded.body == {"password": {"mode": "fixed"}}
    assert forbidden.status == 403
    assert "meu-segredo-123" not in repr(updated.body)
    assert passwords.calls == [
        ("configure", target.id, "fixed", "meu-segredo-123"),
        ("get", target.id),
    ]


def test_owner_creates_separate_play_and_console_invitation_links():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    custom_role = accounts.create_custom_role(
        account.id,
        actor_user_id="owner",
        name="Guardião dos saves",
        permissions={Permission.VIEW_WORLD, Permission.CREATE_BACKUP},
        confirmation=SensitiveActionConfirmation(
            actor_user_id="owner",
            reauthenticated_at=now,
            confirmed_resource_name="Grupo",
        ),
    )
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    play = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/invitation-links",
            "owner",
            {"access": "play"},
            authenticated_at=now,
        )
    )
    manage = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/invitation-links",
            "owner",
            {"access": "console", "predefinedRole": "manager"},
            authenticated_at=now,
        )
    )
    custom_manage = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/invitation-links",
            "owner",
            {"access": "console", "customRoleId": custom_role.id},
            authenticated_at=now,
        )
    )
    invalid_manage = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/invitation-links",
            "owner",
            {"access": "console", "predefinedRole": "player"},
            authenticated_at=now,
        )
    )
    invitation_id = manage.body["invitation"]["id"]
    preview = api.handle(
        ApiRequest(
            "GET",
            f"/api/v1/accounts/{account.id}/invitations/{invitation_id}",
            "friend",
        )
    )
    accepted = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/invitations/{invitation_id}/accept",
            "friend",
        )
    )
    custom_accepted = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/invitations/{custom_manage.body['invitation']['id']}/accept",
            "custom-friend",
        )
    )
    custom_accounts = api.handle(ApiRequest("GET", "/api/v1/me/accounts", "custom-friend"))

    assert play.status == 201
    assert play.body["invitation"]["access"] == "play"
    assert play.body["invitation"]["predefinedRole"] == "player"
    assert manage.status == 201
    assert manage.body["invitation"]["access"] == "console"
    assert invalid_manage.status == 400
    assert invalid_manage.body["error"]["message"] == (
        "console access requires a Moderator or custom Role"
    )
    assert preview.body["invitation"]["accountName"] == "Grupo"
    assert accepted.body["membership"]["roles"][0]["role"] == "manager"
    assert custom_accepted.body["membership"]["roles"][0]["role"] == custom_role.id
    assert custom_accounts.body["accounts"][0]["access"] == {
        "roles": [custom_role.id],
        "permissions": ["backup:create", "world:view"],
    }


def test_owner_reads_members_and_creates_a_scoped_custom_role_with_recent_authentication():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="owner",
        invited_user_ids=["friend"],
    )
    accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )

    members = api.handle(ApiRequest("GET", f"/api/v1/accounts/{account.id}/memberships", "owner"))
    created = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/roles",
            "owner",
            {
                "name": "Guardião dos saves",
                "permissions": ["world:view", "backup:create", "backup:restore"],
                "confirmedResourceName": "Grupo",
            },
            authenticated_at=now,
        )
    )
    assigned = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/memberships/{members.body['memberships'][1]['id']}/roles",
            "owner",
            {
                "customRoleId": created.body["role"]["id"],
                "confirmedResourceName": "Grupo",
            },
            authenticated_at=now,
        )
    )
    roles = api.handle(ApiRequest("GET", f"/api/v1/accounts/{account.id}/roles", "owner"))

    assert members.status == 200
    assert members.body["memberships"][0]["roles"][0]["role"] == "owner"
    assert created.status == 201
    assert created.body["role"]["name"] == "Guardião dos saves"
    assert created.body["role"]["permissions"] == [
        "backup:create",
        "backup:restore",
        "world:view",
    ]
    assert assigned.status == 200
    assert assigned.body["membership"]["roles"] == [
        {
            "id": assigned.body["membership"]["roles"][0]["id"],
            "role": created.body["role"]["id"],
            "kind": "custom",
            "worldId": None,
        }
    ]
    assert roles.body["predefinedRoles"] == ["owner", "manager", "player"]
    assert roles.body["customRoles"][0]["id"] == created.body["role"]["id"]


def test_custom_role_creation_explains_when_recent_authentication_expired():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    response = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/roles",
            "owner",
            {
                "name": "Guardiao dos saves",
                "permissions": ["world:view", "backup:create"],
                "confirmedResourceName": "Grupo",
            },
            authenticated_at=now - timedelta(minutes=6),
        )
    )

    assert response.status == 403
    assert response.body["error"]["code"] == "recent_authentication_required"
    assert "Renove seu login Discord" in response.body["error"]["message"]


def test_owner_can_remove_the_players_only_role_through_the_api():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="owner",
        invited_user_ids=["friend"],
    )
    membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )
    role_assignment_id = membership.role_assignment.id
    catalog = GameCatalog.with_palworld()
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    response = api.handle(
        ApiRequest(
            "DELETE",
            (
                f"/api/v1/accounts/{account.id}/memberships/{membership.id}"
                f"/roles/{role_assignment_id}"
            ),
            "owner",
            {"confirmedResourceName": "Grupo"},
            authenticated_at=now,
        )
    )

    assert response.status == 200
    assert response.body["membership"]["roles"] == []
    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.VIEW_WORLD,
    )


def test_world_backup_restore_and_portable_export_are_available_through_the_api():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(repository, access=accounts, game_catalog=catalog, clock=lambda: now)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    persisted = replace(
        world,
        stored_state_id="state-1",
        stored_state_checksum="sha256:state-1",
        version=world.version + 1,
    )
    repository.save(persisted, expected_version=world.version)
    data = WorldData(
        repository,
        access=accounts,
        archive_store=InMemoryWorldArchiveStore(clock=lambda: now),
        clock=lambda: now,
    )
    api = GameWakeApi(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            world_data=data,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        )
    )

    created = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/backups",
            "owner",
            {"idempotencyKey": "backup-1"},
        )
    )
    listed = api.handle(
        ApiRequest("GET", f"/api/v1/accounts/{account.id}/worlds/{world.id}/backups", "owner")
    )
    restored = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/backups/{created.body['backup']['id']}/restore",
            "owner",
            {"idempotencyKey": "restore-1"},
        )
    )
    exported = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/exports",
            "owner",
            {"idempotencyKey": "export-1"},
        )
    )
    deletion = api.handle(
        ApiRequest(
            "DELETE",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}",
            "owner",
            {
                "confirmedResourceName": "Palpagos",
                "idempotencyKey": "delete-1",
            },
            authenticated_at=now,
        )
    )
    cancelled = api.handle(
        ApiRequest(
            "POST",
            f"/api/v1/accounts/{account.id}/worlds/{world.id}/deletion/cancel",
            "owner",
        )
    )

    assert created.status == 201
    assert listed.body["backups"][0]["kind"] == "manual"
    assert restored.status == 200
    assert restored.body["world"]["storedStateId"] == "state-1"
    assert exported.status == 201
    assert exported.body["export"]["downloadUrl"].startswith("memory://")
    assert deletion.body["world"]["status"] == "pending_deletion"
    assert deletion.body["world"]["deletionScheduledFor"] is not None
    assert cancelled.body["world"]["status"] == "sleeping"
