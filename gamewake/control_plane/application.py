from gamewake.accounts import Account, Accounts, Invitation, User
from gamewake.billing import Billing
from gamewake.game_catalog import GameCatalog, GameTemplateDefinition
from gamewake.worlds import ConfigurationRevision, World, WorldOperation, Worlds

from .contracts import ConnectionDetails, ConnectionDetailsProvider


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
    ) -> None:
        self.accounts = accounts
        self.worlds = worlds
        self.billing = billing
        self.game_catalog = game_catalog
        self._connection_details_provider = connection_details_provider

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

    def request_wake(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> WorldOperation:
        return self.worlds.request_wake(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
        )

    def request_sleep(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
        force: bool = False,
    ) -> WorldOperation:
        return self.worlds.request_sleep(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
            force=force,
        )

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
