from decimal import ROUND_UP, Decimal

from gamewake.accounts import (
    Account,
    Accounts,
    ActivityEvent,
    CustomRole,
    Invitation,
    Membership,
    Permission,
    PredefinedRole,
    SensitiveActionConfirmation,
    User,
)
from gamewake.billing import Billing, Wallet, WalletContribution, WorldBudgetStatus
from gamewake.game_catalog import GameCatalog, GameTemplateDefinition
from gamewake.worlds import (
    Backup,
    ConfigurationRevision,
    World,
    WorldData,
    WorldExport,
    WorldOperation,
    Worlds,
)

from .contracts import ConnectionDetails, ConnectionDetailsProvider, OperationDispatcher


class GameWakeApplication:
    """Shared use cases consumed by HTTP, Discord commands, and Discord Activity."""

    def __init__(
        self,
        *,
        accounts: Accounts,
        worlds: Worlds,
        world_data: WorldData | None = None,
        billing: Billing,
        game_catalog: GameCatalog,
        connection_details_provider: ConnectionDetailsProvider | None = None,
        operation_dispatcher: OperationDispatcher | None = None,
        runtime_profile_hourly_rates: dict[str, Decimal] | None = None,
    ) -> None:
        self.accounts = accounts
        self.worlds = worlds
        self.world_data = world_data
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

    def start_discord_account(
        self,
        *,
        discord_guild_id: str,
        discord_user_id: str,
        display_name: str,
        discord_channel_id: str | None = None,
    ) -> tuple[Account, User]:
        user = self.accounts.sign_in_with_discord(
            discord_user_id=discord_user_id,
            display_name=display_name,
        )
        account = self.accounts.find_account_by_discord_guild(discord_guild_id)
        if account is None:
            account = self.accounts.create_account(
                name=f"Grupo de {display_name}",
                owner_user_id=user.id,
                discord_guild_id=discord_guild_id,
                discord_channel_id=discord_channel_id,
            )
        elif discord_channel_id is not None:
            account = self.accounts.configure_discord_notification_channel(
                account.id,
                actor_user_id=user.id,
                channel_id=discord_channel_id,
            )
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

    def configure_discord_guild(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        discord_guild_id: str,
    ) -> Account:
        return self.accounts.configure_discord_guild(
            account_id,
            actor_user_id=actor_user_id,
            discord_guild_id=discord_guild_id,
        )

    def enable_owner_recovery(
        self,
        account_id: str,
        *,
        owner_user_id: str,
        verified_email: str,
    ) -> tuple[str, ...]:
        return self.accounts.enable_owner_recovery(
            account_id,
            owner_user_id=owner_user_id,
            verified_email=verified_email,
        )

    def list_accounts(self, *, viewer_user_id: str) -> list[Account]:
        return self.accounts.list_accounts(viewer_user_id)

    def list_memberships(self, account_id: str, *, viewer_user_id: str) -> list[Membership]:
        return self.accounts.list_memberships(account_id, viewer_user_id=viewer_user_id)

    def list_custom_roles(self, account_id: str, *, viewer_user_id: str) -> list[CustomRole]:
        return self.accounts.list_custom_roles(account_id, viewer_user_id=viewer_user_id)

    def create_custom_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        name: str,
        permissions: set[Permission],
        confirmation: SensitiveActionConfirmation,
    ) -> CustomRole:
        return self.accounts.create_custom_role(
            account_id,
            actor_user_id=actor_user_id,
            name=name,
            permissions=permissions,
            confirmation=confirmation,
        )

    def assign_custom_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        custom_role_id: str,
        world_id: str | None,
        confirmation: SensitiveActionConfirmation,
    ) -> Membership:
        return self.accounts.assign_custom_role(
            account_id,
            actor_user_id=actor_user_id,
            membership_id=membership_id,
            custom_role_id=custom_role_id,
            world_id=world_id,
            confirmation=confirmation,
        )

    def assign_predefined_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        role: PredefinedRole,
        world_id: str | None,
        confirmation: SensitiveActionConfirmation,
    ) -> Membership:
        return self.accounts.assign_predefined_role(
            account_id,
            actor_user_id=actor_user_id,
            membership_id=membership_id,
            role=role,
            world_id=world_id,
            confirmation=confirmation,
        )

    def remove_role_assignment(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        role_assignment_id: str,
        confirmation: SensitiveActionConfirmation,
    ) -> Membership:
        return self.accounts.remove_role_assignment(
            account_id,
            actor_user_id=actor_user_id,
            membership_id=membership_id,
            role_assignment_id=role_assignment_id,
            confirmation=confirmation,
        )

    def remove_membership(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        confirmation: SensitiveActionConfirmation,
    ) -> None:
        self.accounts.remove_membership(
            account_id,
            membership_id,
            actor_user_id=actor_user_id,
            confirmation=confirmation,
        )

    def list_activity(self, account_id: str, *, viewer_user_id: str) -> list[ActivityEvent]:
        return self.accounts.list_activity_events(
            account_id,
            viewer_user_id=viewer_user_id,
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

    def accept_invitation(
        self,
        account_id: str,
        invitation_id: str,
        *,
        invited_user_id: str,
    ) -> Membership:
        return self.accounts.accept_invitation(
            account_id,
            invitation_id,
            invited_user_id=invited_user_id,
        )

    def accept_pending_invitation(
        self,
        account_id: str,
        *,
        invited_user_id: str,
    ) -> Membership:
        return self.accounts.accept_pending_invitation(
            account_id,
            invited_user_id=invited_user_id,
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

    def update_world_settings(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        auto_sleep_minutes: int | None,
    ) -> World:
        return self.worlds.update_runtime_settings(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            auto_sleep_minutes=auto_sleep_minutes,
        )

    def get_wallet(self, account_id: str, *, viewer_user_id: str) -> Wallet:
        self.accounts.list_memberships(account_id, viewer_user_id=viewer_user_id)
        return self.billing.get_wallet(account_id)

    def get_world_budget(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> WorldBudgetStatus | None:
        self.worlds.get_world(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )
        return self.billing.get_world_budget_status(account_id, world_id)

    def set_world_budget(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        monthly_limit: Decimal,
        idempotency_key: str,
    ) -> WorldBudgetStatus:
        self.worlds.get_world(
            account_id,
            world_id,
            viewer_user_id=actor_user_id,
        )
        if not self.accounts.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_WORLD_BUDGET,
            world_id=world_id,
        ):
            raise PermissionError("changing a World Budget requires Owner permission")
        self.billing.set_world_budget(
            account_id,
            world_id=world_id,
            monthly_limit=monthly_limit,
            idempotency_key=idempotency_key,
        )
        status = self.billing.get_world_budget_status(account_id, world_id)
        if status is None:
            raise RuntimeError("World Budget was not persisted")
        return status

    def create_contribution(
        self,
        account_id: str,
        *,
        payer_user_id: str,
        package_id: str,
        return_url: str,
        completion_url: str,
        idempotency_key: str,
        payer_email: str | None = None,
    ) -> WalletContribution:
        self.accounts.list_memberships(account_id, viewer_user_id=payer_user_id)
        if not self.accounts.owner_recovery_ready(account_id):
            raise PermissionError(
                "Owner Recovery must be ready before the account can accept payments"
            )
        payer = self.accounts.get_user(payer_user_id)
        return self.billing.create_contribution(
            account_id,
            payer_user_id=payer_user_id,
            package_id=package_id,
            return_url=return_url,
            completion_url=completion_url,
            idempotency_key=idempotency_key,
            payer_name=payer.display_name if payer is not None else None,
            payer_email=payer_email,
        )

    def reconcile_contribution(
        self,
        account_id: str,
        contribution_id: str,
        *,
        payer_user_id: str,
    ) -> WalletContribution:
        self.accounts.list_memberships(account_id, viewer_user_id=payer_user_id)
        contribution = self.billing.get_contribution(
            account_id,
            contribution_id,
            requesting_user_id=payer_user_id,
        )
        if contribution.payer_user_id != payer_user_id:
            raise PermissionError("only the payer can reconcile this contribution")
        return self.billing.reconcile_contribution(account_id, contribution_id)

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

    def wake_estimate(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> dict[str, str | int]:
        world = self.worlds.get_world(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )
        rate = self._runtime_profile_hourly_rates.get(world.runtime_profile_id)
        if rate is None:
            raise ValueError("Runtime Profile pricing is not configured")
        reserved_minutes = 25
        minimum = (rate * Decimal(reserved_minutes) / Decimal(60)).quantize(
            Decimal("0.01"),
            rounding=ROUND_UP,
        )
        return {
            "currency": "BRL",
            "hourlyRate": str(rate.quantize(Decimal("0.01"))),
            "minimumReservation": str(minimum),
            "reservedMinutes": reserved_minutes,
        }

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

    def effective_configuration(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> ConfigurationRevision:
        return self.worlds.get_effective_configuration(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )

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

    def list_backups(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> tuple[Backup, ...]:
        return self._world_data().list_backups(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )

    def create_manual_backup(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> Backup:
        return self._world_data().create_manual_backup(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
        )

    def restore_backup(
        self,
        account_id: str,
        world_id: str,
        backup_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> World:
        return self._world_data().restore_backup(
            account_id,
            world_id,
            backup_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
        )

    def create_world_export(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> WorldExport:
        return self._world_data().create_export(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
        )

    def schedule_world_deletion(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        confirmation: SensitiveActionConfirmation,
        idempotency_key: str,
    ) -> World:
        return self._world_data().schedule_deletion(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            confirmation=confirmation,
            idempotency_key=idempotency_key,
        )

    def cancel_world_deletion(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
    ) -> World:
        return self._world_data().cancel_deletion(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
        )

    def _world_data(self) -> WorldData:
        if self.world_data is None:
            raise ValueError("World data operations are not configured")
        return self.world_data
