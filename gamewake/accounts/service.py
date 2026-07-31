from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .model import (
    Account,
    IdentityProvider,
    Invitation,
    InvitationStatus,
    LastOwnerRemovalError,
    LinkedIdentity,
    Membership,
    PermissionDeniedError,
    PredefinedRole,
    ResourceScope,
    RoleAssignment,
    User,
)
from .policy import CustomRole, Permission, permissions_for
from .repository import AccountRepository, AccountSnapshot, IdentityRepository
from .security import (
    ActivityAction,
    ActivityEvent,
    NoOpSecurityNotifier,
    SecurityNotifier,
    SensitiveActionConfirmation,
    SensitiveActionConfirmationError,
)


class Accounts:
    def __init__(
        self,
        repository: AccountRepository,
        identity_repository: IdentityRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        security_notifier: SecurityNotifier | None = None,
    ) -> None:
        self._repository = repository
        self._identities = identity_repository or repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._security_notifier = security_notifier or NoOpSecurityNotifier()

    def sign_in_with_discord(self, *, discord_user_id: str, display_name: str) -> User:
        existing = self._identities.find_user_by_identity(
            IdentityProvider.DISCORD,
            discord_user_id,
        )
        if existing is not None:
            return existing

        user = User(id=str(uuid4()), display_name=display_name)
        identity = LinkedIdentity(
            id=str(uuid4()),
            user_id=user.id,
            provider=IdentityProvider.DISCORD,
            provider_user_id=discord_user_id,
        )
        self._identities.create_user(user, identity)
        return user

    def list_linked_identities(self, user_id: str) -> list[LinkedIdentity]:
        return list(self._identities.list_linked_identities(user_id))

    def create_account(
        self,
        *,
        name: str,
        owner_user_id: str,
        discord_guild_id: str | None = None,
    ) -> Account:
        account = Account(
            id=str(uuid4()),
            name=name,
            discord_guild_id=discord_guild_id,
        )
        owner_membership_id = str(uuid4())
        owner = Membership(
            id=owner_membership_id,
            account_id=account.id,
            user_id=owner_user_id,
            assignments=(
                RoleAssignment(
                    id=str(uuid4()),
                    scope=ResourceScope(account_id=account.id),
                    predefined_role=PredefinedRole.OWNER,
                ),
            ),
        )
        self._repository.create(account, owner)
        return account

    def find_account_by_discord_guild(self, discord_guild_id: str) -> Account | None:
        snapshot = self._repository.find_by_discord_guild(discord_guild_id)
        return snapshot.account if snapshot is not None else None

    def list_memberships(self, account_id: str) -> list[Membership]:
        return list(self._repository.get(account_id).memberships)

    def list_invitations(self, account_id: str) -> list[Invitation]:
        return list(self._repository.get(account_id).invitations)

    def list_activity_events(
        self,
        account_id: str,
        *,
        viewer_user_id: str,
    ) -> list[ActivityEvent]:
        snapshot = self._repository.get(account_id)
        if not any(
            membership.user_id == viewer_user_id
            for membership in snapshot.memberships
        ):
            raise PermissionDeniedError("activity is visible only to account members")
        return list(snapshot.activity_events)

    def authorize(
        self,
        account_id: str,
        *,
        user_id: str,
        permission: Permission,
        world_id: str | None = None,
    ) -> bool:
        snapshot = self._repository.get(account_id)
        membership = next(
            (
                membership
                for membership in snapshot.memberships
                if membership.user_id == user_id
            ),
            None,
        )
        return membership is not None and permission in permissions_for(
            membership.assignments,
            custom_roles=snapshot.custom_roles,
            world_id=world_id,
        )

    def create_custom_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        name: str,
        permissions: set[Permission],
    ) -> CustomRole:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("creating roles requires role management permission")

        snapshot = self._repository.get(account_id)
        role = CustomRole(
            id=str(uuid4()),
            account_id=account_id,
            name=name,
            permissions=frozenset(permissions),
        )
        self._repository.save(
            replace(snapshot, custom_roles=(*snapshot.custom_roles, role)),
            expected_version=snapshot.version,
        )
        return role

    def assign_custom_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        custom_role_id: str,
        world_id: str | None = None,
    ) -> Membership:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("assigning roles requires role management permission")

        snapshot = self._repository.get(account_id)
        custom_role = next(role for role in snapshot.custom_roles if role.id == custom_role_id)
        membership = next(
            membership
            for membership in snapshot.memberships
            if membership.id == membership_id
        )
        updated = replace(
            membership,
            assignments=(
                *membership.assignments,
                RoleAssignment(
                    id=str(uuid4()),
                    scope=ResourceScope(account_id=custom_role.account_id, world_id=world_id),
                    custom_role_id=custom_role.id,
                ),
            ),
        )
        memberships = tuple(
            updated if item.id == membership_id else item
            for item in snapshot.memberships
        )
        self._repository.save(
            replace(snapshot, memberships=memberships),
            expected_version=snapshot.version,
        )
        return updated

    def assign_predefined_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        role: PredefinedRole,
        world_id: str | None = None,
    ) -> Membership:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("assigning roles requires role management permission")

        snapshot = self._repository.get(account_id)
        membership = next(
            membership
            for membership in snapshot.memberships
            if membership.id == membership_id
        )
        updated = replace(
            membership,
            assignments=(
                *membership.assignments,
                RoleAssignment(
                    id=str(uuid4()),
                    scope=ResourceScope(account_id=account_id, world_id=world_id),
                    predefined_role=role,
                ),
            ),
        )
        memberships = tuple(
            updated if item.id == membership_id else item
            for item in snapshot.memberships
        )
        self._repository.save(
            replace(snapshot, memberships=memberships),
            expected_version=snapshot.version,
        )
        return updated

    def invite_members(
        self,
        account_id: str,
        *,
        inviter_user_id: str,
        invited_user_ids: list[str],
    ) -> list[Invitation]:
        snapshot = self._repository.get(account_id)
        if not self.authorize(
            account_id,
            user_id=inviter_user_id,
            permission=Permission.MANAGE_MEMBERSHIPS,
        ):
            raise PermissionDeniedError(
                "inviting members requires membership management permission"
            )
        invitations = [
            Invitation(
                id=str(uuid4()),
                account_id=account_id,
                inviter_user_id=inviter_user_id,
                invited_user_id=invited_user_id,
                status=InvitationStatus.PENDING,
            )
            for invited_user_id in invited_user_ids
        ]
        self._repository.save(
            replace(
                snapshot,
                invitations=(*snapshot.invitations, *invitations),
            ),
            expected_version=snapshot.version,
        )
        return invitations

    def accept_invitation(
        self,
        account_id: str,
        invitation_id: str,
        *,
        invited_user_id: str,
    ) -> Membership:
        snapshot = self._repository.get(account_id)
        invitation = next(
            invitation
            for invitation in snapshot.invitations
            if invitation.id == invitation_id
        )
        if invitation.invited_user_id != invited_user_id:
            raise PermissionDeniedError("only the invited User can accept this Invitation")
        if invitation.status is not InvitationStatus.PENDING:
            raise ValueError("the Invitation is no longer pending")
        accepted = Invitation(
            id=invitation.id,
            account_id=invitation.account_id,
            inviter_user_id=invitation.inviter_user_id,
            invited_user_id=invitation.invited_user_id,
            status=InvitationStatus.ACCEPTED,
        )
        membership = Membership(
            id=str(uuid4()),
            account_id=account_id,
            user_id=invited_user_id,
            assignments=(
                RoleAssignment(
                    id=str(uuid4()),
                    scope=ResourceScope(account_id=account_id),
                    predefined_role=PredefinedRole.PLAYER,
                ),
            ),
        )
        invitations = tuple(
            accepted if item.id == invitation.id else item
            for item in snapshot.invitations
        )
        self._repository.save(
            replace(
                snapshot,
                memberships=(*snapshot.memberships, membership),
                invitations=invitations,
            ),
            expected_version=snapshot.version,
        )
        return membership

    def remove_membership(
        self,
        account_id: str,
        membership_id: str,
        *,
        actor_user_id: str,
        confirmation: SensitiveActionConfirmation,
    ) -> None:
        snapshot = self._repository.get(account_id)
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_MEMBERSHIPS,
        ):
            raise PermissionDeniedError(
                "revoking membership requires membership management permission"
            )
        self._verify_sensitive_confirmation(
            actor_user_id=actor_user_id,
            expected_resource_name=snapshot.account.name,
            confirmation=confirmation,
        )
        membership = next(
            membership
            for membership in snapshot.memberships
            if membership.id == membership_id
        )
        if PredefinedRole.OWNER in membership.roles and self._owner_count(snapshot) == 1:
            raise LastOwnerRemovalError("an account must retain at least one Owner")

        remaining = tuple(
            membership
            for membership in snapshot.memberships
            if membership.id != membership_id
        )
        event = ActivityEvent(
            id=str(uuid4()),
            account_id=account_id,
            actor_user_id=actor_user_id,
            action=ActivityAction.MEMBERSHIP_REVOKED,
            subject_id=membership_id,
            occurred_at=self._clock(),
        )
        owner_user_ids = frozenset(
            item.user_id
            for item in snapshot.memberships
            if PredefinedRole.OWNER in item.roles
        )
        self._repository.save(
            replace(
                snapshot,
                memberships=remaining,
                activity_events=(*snapshot.activity_events, event),
            ),
            expected_version=snapshot.version,
        )
        self._security_notifier.notify_owners(
            owner_user_ids,
            ActivityAction.MEMBERSHIP_REVOKED,
            membership_id,
        )

    def _verify_sensitive_confirmation(
        self,
        *,
        actor_user_id: str,
        expected_resource_name: str,
        confirmation: SensitiveActionConfirmation,
    ) -> None:
        age = self._clock() - confirmation.reauthenticated_at
        if (
            confirmation.actor_user_id != actor_user_id
            or confirmation.confirmed_resource_name != expected_resource_name
            or age < timedelta(0)
            or age > timedelta(minutes=5)
        ):
            raise SensitiveActionConfirmationError(
                "the action requires recent reauthentication and exact resource confirmation"
            )

    @staticmethod
    def _owner_count(snapshot: AccountSnapshot) -> int:
        return sum(
            any(
                assignment.predefined_role is PredefinedRole.OWNER
                and assignment.scope.world_id is None
                for assignment in membership.assignments
            )
            for membership in snapshot.memberships
        )
