from decimal import Decimal

from gamewake.accounts import Account, Accounts, Invitation, User
from gamewake.billing import Billing, Wallet, WalletContribution
from gamewake.game_catalog import GameCatalog, GameTemplateDefinition
from gamewake.worlds import ConfigurationRevision, World, WorldOperation, Worlds

from .contracts import ConnectionDetails, ConnectionDetailsProvider, OperationDispatcher


class GameWakeApplication:
    """Shared use cases consumed by HTTP, Discord commands, and Discord Activity."""

    def __init__(
        self,
        *,
        accounts: Accounts,
        worlds: Worlds,
        billing: Billing,
        game_catalog: GameCatalog,
        connection_details_provider: ConnectionDetailsProvider | None = None,
        operation_dispatcher: OperationDispatcher | None = None,
        runtime_profile_hourly_rates: dict[str, Decimal] | None = None,
    ) -> None:
        self.accounts = accounts
        self.worlds = worlds
        self.billing = billing
        self.game_catalog = game_catalog
        self._connection_details_provider = connection_details_provider
        self._operation_dispatcher = operation_dispatcher
        self._runtime_profile_hourly_rates = dict(runtime_profile_hourly_rates or {})

    def resolve_discord_principal(
        self,
        *,
        discord_guild_id: str,
        discord_user_id: str,
        display_name: str,
    ) -> tuple[Account, User]:
        user = self.accounts.sign_in_with_discord(
            discord_user_id=discord_user_id,
            display_name=display_name,
        )
        account = self.accounts.find_account_by_discord_guild(discord_guild_id)
        if account is None:
            raise KeyError(discord_guild_id)
        return account, user

    def invite_discord_friends(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        friends: list[tuple[str, str]],
    ) -> list[Invitation]:
        invited_user_ids = [
            self.accounts.sign_in_with_discord(
                discord_user_id=discord_user_id,
                display_name=display_name,
            ).id
            for discord_user_id, display_name in friends
        ]
        return self.invite_friends(
            account_id,
            actor_user_id=actor_user_id,
            invited_user_ids=invited_user_ids,
        )

    def create_account(
        self,
        *,
        actor_user_id: str,
        name: str,
        discord_guild_id: str | None,
    ) -> Account:
        return self.accounts.create_account(
            name=name,
            owner_user_id=actor_user_id,
            discord_guild_id=discord_guild_id,
        )

    def invite_friends(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        invited_user_ids: list[str],
    ) -> list[Invitation]:
        return self.accounts.invite_members(
            account_id,
            inviter_user_id=actor_user_id,
            invited_user_ids=invited_user_ids,
        )

    def create_world(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        name: str,
        game_template_id: str,
        region: str,
        runtime_profile_id: str,
    ) -> World:
        return self.worlds.create_world(
            account_id,
            actor_user_id=actor_user_id,
            name=name,
            game_template_id=game_template_id,
            region=region,
            runtime_profile_id=runtime_profile_id,
        )

    def list_worlds(
        self,
        account_id: str,
        *,
        viewer_user_id: str,
    ) -> list[World]:
        return self.worlds.list_worlds(
            account_id,
            viewer_user_id=viewer_user_id,
        )

    def get_wallet(self, account_id: str, *, viewer_user_id: str) -> Wallet:
        self.accounts.list_memberships(account_id, viewer_user_id=viewer_user_id)
        return self.billing.get_wallet(account_id)

    def create_contribution(
        self,
        account_id: str,
        *,
        payer_user_id: str,
        package_id: str,
        return_url: str,
        completion_url: str,
        idempotency_key: str,
    ) -> WalletContribution:
        self.accounts.list_memberships(account_id, viewer_user_id=payer_user_id)
        return self.billing.create_contribution(
            account_id,
            payer_user_id=payer_user_id,
            package_id=package_id,
            return_url=return_url,
            completion_url=completion_url,
            idempotency_key=idempotency_key,
        )

    def request_wake(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> WorldOperation:
        operation = self.worlds.request_wake(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
        )
        rate = self._runtime_profile_hourly_rates.get(
            self.worlds.get_world(
                account_id,
                world_id,
                viewer_user_id=actor_user_id,
            ).runtime_profile_id
        )
        if (
            rate is not None
            and operation.idempotency_key != idempotency_key
            and operation.session_quote_id is None
        ):
            return operation
        if (
            rate is not None
            and operation.idempotency_key == idempotency_key
            and operation.session_quote_id is None
        ):
            reservation = None
            try:
                world = self.worlds.get_world(
                    account_id,
                    world_id,
                    viewer_user_id=actor_user_id,
                )
                quote = self.billing.create_session_quote(
                    account_id,
                    world_id=world.id,
                    runtime_profile_id=world.runtime_profile_id,
                    hourly_rate=rate,
                    idempotency_key=f"{idempotency_key}:quote",
                )
                reservation = self.billing.reserve_for_wake(
                    account_id,
                    quote.id,
                    idempotency_key=f"{idempotency_key}:reservation",
                )
                operation = self.worlds.attach_billing_session(
                    account_id,
                    operation.id,
                    session_quote_id=quote.id,
                    usage_reservation_id=reservation.id,
                )
            except Exception:
                if reservation is not None:
                    self.billing.release_reservation(account_id, reservation.id)
                self.worlds.fail_wake_preflight(account_id, operation.id)
                raise
        if self._operation_dispatcher is not None:
            self._operation_dispatcher.start(account_id, operation.id)
        return operation

    def request_sleep(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
        force: bool = False,
    ) -> WorldOperation:
        operation = self.worlds.request_sleep(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
            force=force,
        )
        if self._operation_dispatcher is not None:
            self._operation_dispatcher.start(account_id, operation.id)
        return operation

    def connection_details(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> ConnectionDetails:
        world = self.worlds.get_world(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )
        if world.status.value != "online":
            raise ValueError("Connection Details are available only while the World is Online")
        if self._connection_details_provider is None:
            raise ValueError("Connection Details are not configured")
        return self._connection_details_provider.issue(
            world,
            viewer_user_id=viewer_user_id,
        )

    def configuration_schema(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> GameTemplateDefinition:
        world = self.worlds.get_world(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )
        return self.game_catalog.resolve(world.game_template_id)

    def update_configuration(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        changes: object,
        idempotency_key: str,
        origin: str,
    ) -> tuple[World, ConfigurationRevision]:
        revision = self.worlds.update_configuration(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            changes=changes,
            idempotency_key=idempotency_key,
            origin=origin,
        )
        world = self.worlds.get_world(
            account_id,
            world_id,
            viewer_user_id=actor_user_id,
        )
        return world, revision
