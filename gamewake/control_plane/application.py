from gamewake.accounts import Account, Accounts, Invitation
from gamewake.billing import Billing
from gamewake.game_catalog import GameCatalog, GameTemplateDefinition
from gamewake.worlds import ConfigurationRevision, World, Worlds


class GameWakeApplication:
    """Shared use cases consumed by HTTP, Discord commands, and Discord Activity."""

    def __init__(
        self,
        *,
        accounts: Accounts,
        worlds: Worlds,
        billing: Billing,
        game_catalog: GameCatalog,
    ) -> None:
        self.accounts = accounts
        self.worlds = worlds
        self.billing = billing
        self.game_catalog = game_catalog

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
