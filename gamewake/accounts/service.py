from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from .model import (
    Account,
    DiscordGuildAlreadyLinkedError,
    IdentityProvider,
    Invitation,
    InvitationAccess,
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
from .recovery import (
    InvalidRecoveryCodeError,
    NoOpRecoverySecretStore,
    RecoverySecretStore,
)
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
        recovery_secret_store: RecoverySecretStore | None = None,
    ) -> None:
        self._repository = repository
        self._identities = identity_repository or repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._security_notifier = security_notifier or NoOpSecurityNotifier()
        self._recovery_secrets = recovery_secret_store or NoOpRecoverySecretStore()

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

    def get_user(self, user_id: str) -> User | None:
        return self._identities.get_user(user_id)

    def list_linked_identities(
        self,
        user_id: str,
        *,
        viewer_user_id: str,
    ) -> list[LinkedIdentity]:
        if viewer_user_id != user_id:
            raise PermissionDeniedError("Linked Identities are private to their User")
        return list(self._identities.list_linked_identities(user_id))

    def enable_owner_recovery(
        self,
        account_id: str,
        *,
        owner_user_id: str,
        verified_email: str,
    ) -> tuple[str, ...]:
        snapshot = self._repository.get(account_id)
        if not self._is_account_owner(snapshot, owner_user_id):
            raise PermissionDeniedError("Owner Recovery can be enabled only by an Owner")
        recovery_codes = tuple(token_urlsafe(12) for _ in range(8))
        self._recovery_secrets.put(
            owner_user_id,
            verified_email,
            frozenset(self._hash_recovery_code(code) for code in recovery_codes),
        )
        return recovery_codes

    def owner_recovery_ready(self, account_id: str) -> bool:
        snapshot = self._repository.get(account_id)
        owner_user_ids = self._owner_user_ids(snapshot)
        return len(owner_user_ids) > 1 or (
            len(owner_user_ids) == 1
            and self._recovery_secrets.is_enabled(next(iter(owner_user_ids)))
        )

    def recover_owner_discord_identity(
        self,
        account_id: str,
        *,
        owner_user_id: str,
        recovery_code: str,
        new_discord_user_id: str,
    ) -> None:
        snapshot = self._repository.get(account_id)
        if not self._is_account_owner(snapshot, owner_user_id):
            raise PermissionDeniedError("Owner Recovery applies only to an Owner")
        if not self._recovery_secrets.consume(
            owner_user_id,
            self._hash_recovery_code(recovery_code),
        ):
            raise InvalidRecoveryCodeError("the recovery code is invalid or was already used")

        self._replace_owner_discord_identity(
            snapshot,
            actor_user_id=owner_user_id,
            owner_user_id=owner_user_id,
            new_discord_user_id=new_discord_user_id,
        )

    def recover_owner_discord_identity_by_co_owner(
        self,
        account_id: str,
        *,
        actor_owner_user_id: str,
        lost_owner_user_id: str,
        new_discord_user_id: str,
        confirmation: SensitiveActionConfirmation,
    ) -> None:
        snapshot = self._repository.get(account_id)
        if (
            actor_owner_user_id == lost_owner_user_id
            or not self._is_account_owner(snapshot, actor_owner_user_id)
            or not self._is_account_owner(snapshot, lost_owner_user_id)
        ):
            raise PermissionDeniedError("a different current Owner must authorize this recovery")
        self._verify_sensitive_confirmation(
            actor_user_id=actor_owner_user_id,
            expected_resource_name=snapshot.account.name,
            confirmation=confirmation,
        )
        self._replace_owner_discord_identity(
            snapshot,
            actor_user_id=actor_owner_user_id,
            owner_user_id=lost_owner_user_id,
            new_discord_user_id=new_discord_user_id,
        )

    def _replace_owner_discord_identity(
        self,
        snapshot: AccountSnapshot,
        *,
        actor_user_id: str,
        owner_user_id: str,
        new_discord_user_id: str,
    ) -> None:

        identity = LinkedIdentity(
            id=str(uuid4()),
            user_id=owner_user_id,
            provider=IdentityProvider.DISCORD,
            provider_user_id=new_discord_user_id,
        )
        self._identities.replace_identity(identity)
        event = ActivityEvent(
            id=str(uuid4()),
            account_id=snapshot.account.id,
            actor_user_id=actor_user_id,
            action=ActivityAction.OWNER_RECOVERED,
            subject_id=owner_user_id,
            occurred_at=self._clock(),
        )
        self._repository.save(
            replace(snapshot, activity_events=(*snapshot.activity_events, event)),
            expected_version=snapshot.version,
        )
        self._security_notifier.notify_owners(
            self._owner_user_ids(snapshot),
            ActivityAction.OWNER_RECOVERED,
            owner_user_id,
        )

    def create_account(
        self,
        *,
        name: str,
        owner_user_id: str,
        discord_guild_id: str | None = None,
        discord_channel_id: str | None = None,
    ) -> Account:
        account = Account(
            id=str(uuid4()),
            name=name,
            discord_guild_id=discord_guild_id,
            discord_channel_id=discord_channel_id,
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

    def configure_discord_guild(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        discord_guild_id: str,
    ) -> Account:
        if not discord_guild_id or not discord_guild_id.isdigit():
            raise ValueError("Discord Guild ID must contain only digits")
        snapshot = self._repository.get(account_id)
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_INTEGRATIONS,
        ):
            raise PermissionDeniedError(
                "configuring Discord requires integration management permission"
            )
        linked = self._repository.find_by_discord_guild(discord_guild_id)
        if linked is not None and linked.account.id != account_id:
            raise DiscordGuildAlreadyLinkedError(
                "the Discord Guild is already linked to a GameWake Account"
            )
        if snapshot.account.discord_guild_id == discord_guild_id:
            return snapshot.account
        account = replace(snapshot.account, discord_guild_id=discord_guild_id)
        self._repository.save(
            replace(snapshot, account=account),
            expected_version=snapshot.version,
        )
        return account

    def configure_discord_notification_channel(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        channel_id: str,
    ) -> Account:
        if not channel_id:
            raise ValueError("Discord notification channel is required")
        snapshot = self._repository.get(account_id)
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_INTEGRATIONS,
        ):
            raise PermissionDeniedError(
                "configuring Discord notifications requires integration management permission"
            )
        if snapshot.account.discord_channel_id == channel_id:
            return snapshot.account
        account = replace(snapshot.account, discord_channel_id=channel_id)
        self._repository.save(
            replace(snapshot, account=account),
            expected_version=snapshot.version,
        )
        return account

    def list_accounts(self, user_id: str) -> list[Account]:
        return [snapshot.account for snapshot in self._repository.list_for_user(user_id)]

    def list_memberships(
        self,
        account_id: str,
        *,
        viewer_user_id: str,
    ) -> list[Membership]:
        snapshot = self._repository.get(account_id)
        if not any(membership.user_id == viewer_user_id for membership in snapshot.memberships):
            raise PermissionDeniedError("memberships are visible only inside their account")
        return list(snapshot.memberships)

    def list_invitations(
        self,
        account_id: str,
        *,
        viewer_user_id: str,
    ) -> list[Invitation]:
        if not self.authorize(
            account_id,
            user_id=viewer_user_id,
            permission=Permission.MANAGE_MEMBERSHIPS,
        ):
            raise PermissionDeniedError("invitations require membership management permission")
        return list(self._repository.get(account_id).invitations)

    def list_activity_events(
        self,
        account_id: str,
        *,
        viewer_user_id: str,
    ) -> list[ActivityEvent]:
        snapshot = self._repository.get(account_id)
        if not any(membership.user_id == viewer_user_id for membership in snapshot.memberships):
            raise PermissionDeniedError("activity is visible only to account members")
        return list(snapshot.activity_events)

    def list_custom_roles(
        self,
        account_id: str,
        *,
        viewer_user_id: str,
    ) -> list[CustomRole]:
        snapshot = self._repository.get(account_id)
        if not any(membership.user_id == viewer_user_id for membership in snapshot.memberships):
            raise PermissionDeniedError("roles are visible only inside their account")
        return list(snapshot.custom_roles)

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
            (membership for membership in snapshot.memberships if membership.user_id == user_id),
            None,
        )
        return membership is not None and permission in permissions_for(
            membership.assignments,
            custom_roles=snapshot.custom_roles,
            world_id=world_id,
        )

    def access_for(
        self,
        account_id: str,
        *,
        user_id: str,
        world_id: str | None = None,
    ) -> tuple[Membership, frozenset[Permission]]:
        snapshot = self._repository.get(account_id)
        membership = next(
            (membership for membership in snapshot.memberships if membership.user_id == user_id),
            None,
        )
        if membership is None:
            raise PermissionDeniedError("access is visible only inside the account")
        return membership, permissions_for(
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
        confirmation: SensitiveActionConfirmation | None = None,
    ) -> CustomRole:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("creating roles requires role management permission")

        snapshot = self._repository.get(account_id)
        self._verify_sensitive_confirmation(
            actor_user_id=actor_user_id,
            expected_resource_name=snapshot.account.name,
            confirmation=confirmation,
        )
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
        confirmation: SensitiveActionConfirmation | None = None,
    ) -> Membership:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("assigning roles requires role management permission")

        snapshot = self._repository.get(account_id)
        self._verify_sensitive_confirmation(
            actor_user_id=actor_user_id,
            expected_resource_name=snapshot.account.name,
            confirmation=confirmation,
        )
        custom_role = next(role for role in snapshot.custom_roles if role.id == custom_role_id)
        membership = next(
            membership for membership in snapshot.memberships if membership.id == membership_id
        )
        assignment = RoleAssignment(
            id=str(uuid4()),
            scope=ResourceScope(account_id=custom_role.account_id, world_id=world_id),
            custom_role_id=custom_role.id,
        )
        self._ensure_role_replacement_preserves_owner(snapshot, membership, assignment)
        updated = replace(
            membership,
            assignments=(assignment,),
        )
        memberships = tuple(
            updated if item.id == membership_id else item for item in snapshot.memberships
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
        confirmation: SensitiveActionConfirmation | None = None,
    ) -> Membership:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("assigning roles requires role management permission")

        snapshot = self._repository.get(account_id)
        self._verify_sensitive_confirmation(
            actor_user_id=actor_user_id,
            expected_resource_name=snapshot.account.name,
            confirmation=confirmation,
        )
        membership = next(
            membership for membership in snapshot.memberships if membership.id == membership_id
        )
        assignment = RoleAssignment(
            id=str(uuid4()),
            scope=ResourceScope(account_id=account_id, world_id=world_id),
            predefined_role=role,
        )
        self._ensure_role_replacement_preserves_owner(snapshot, membership, assignment)
        updated = replace(
            membership,
            assignments=(assignment,),
        )
        memberships = tuple(
            updated if item.id == membership_id else item for item in snapshot.memberships
        )
        self._repository.save(
            replace(snapshot, memberships=memberships),
            expected_version=snapshot.version,
        )
        return updated

    def remove_role_assignment(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        role_assignment_id: str,
        confirmation: SensitiveActionConfirmation | None = None,
    ) -> Membership:
        if not self.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError("removing roles requires role management permission")
        snapshot = self._repository.get(account_id)
        self._verify_sensitive_confirmation(
            actor_user_id=actor_user_id,
            expected_resource_name=snapshot.account.name,
            confirmation=confirmation,
        )
        membership = next(item for item in snapshot.memberships if item.id == membership_id)
        assignment = next(item for item in membership.assignments if item.id == role_assignment_id)
        if membership.role_assignment != assignment:
            raise ValueError("the Role Assignment is no longer active")
        if (
            assignment.predefined_role is PredefinedRole.OWNER
            and assignment.scope.world_id is None
            and self._owner_count(snapshot) == 1
        ):
            raise LastOwnerRemovalError("an account must retain at least one Owner")

        updated = replace(
            membership,
            assignments=(),
        )
        memberships = tuple(
            updated if item.id == membership_id else item for item in snapshot.memberships
        )
        event = ActivityEvent(
            id=str(uuid4()),
            account_id=account_id,
            actor_user_id=actor_user_id,
            action=ActivityAction.ROLE_ASSIGNMENT_REVOKED,
            subject_id=role_assignment_id,
            occurred_at=self._clock(),
        )
        self._repository.save(
            replace(
                snapshot,
                memberships=memberships,
                activity_events=(*snapshot.activity_events, event),
            ),
            expected_version=snapshot.version,
        )
        self._security_notifier.notify_owners(
            self._owner_user_ids(snapshot),
            ActivityAction.ROLE_ASSIGNMENT_REVOKED,
            role_assignment_id,
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

    def create_invitation_link(
        self,
        account_id: str,
        *,
        inviter_user_id: str,
        role: PredefinedRole | None = PredefinedRole.PLAYER,
        custom_role_id: str | None = None,
        world_id: str | None = None,
        expires_in: timedelta = timedelta(days=7),
    ) -> Invitation:
        snapshot = self._repository.get(account_id)
        if not self.authorize(
            account_id,
            user_id=inviter_user_id,
            permission=Permission.MANAGE_MEMBERSHIPS,
        ):
            raise PermissionDeniedError(
                "creating invitation links requires membership management permission"
            )
        if (role is None) == (custom_role_id is None):
            raise ValueError("choose exactly one predefined or custom Role")
        if role is PredefinedRole.OWNER:
            raise ValueError("Owner access cannot be granted through an Invitation link")
        access = (
            InvitationAccess.PLAY
            if role is PredefinedRole.PLAYER and custom_role_id is None
            else InvitationAccess.CONSOLE
        )
        if access is InvitationAccess.CONSOLE and not self.authorize(
            account_id,
            user_id=inviter_user_id,
            permission=Permission.MANAGE_ROLES,
        ):
            raise PermissionDeniedError(
                "console invitation links require role management permission"
            )
        if custom_role_id is not None and not any(
            item.id == custom_role_id for item in snapshot.custom_roles
        ):
            raise ValueError("the custom Role does not exist")
        if expires_in <= timedelta(0) or expires_in > timedelta(days=30):
            raise ValueError("Invitation expiry must be between one second and 30 days")

        invitation = Invitation(
            id=str(uuid4()),
            account_id=account_id,
            inviter_user_id=inviter_user_id,
            invited_user_id=None,
            status=InvitationStatus.PENDING,
            access=access,
            predefined_role=role,
            custom_role_id=custom_role_id,
            world_id=world_id,
            expires_at=self._clock() + expires_in,
        )
        self._repository.save(
            replace(snapshot, invitations=(*snapshot.invitations, invitation)),
            expected_version=snapshot.version,
        )
        return invitation

    def get_invitation(
        self,
        account_id: str,
        invitation_id: str,
        *,
        viewer_user_id: str,
    ) -> tuple[Account, Invitation]:
        snapshot = self._repository.get(account_id)
        invitation = next(item for item in snapshot.invitations if item.id == invitation_id)
        if invitation.invited_user_id is not None and invitation.invited_user_id != viewer_user_id:
            raise PermissionDeniedError("only the invited User can view this Invitation")
        return snapshot.account, invitation

    def accept_invitation(
        self,
        account_id: str,
        invitation_id: str,
        *,
        invited_user_id: str,
    ) -> Membership:
        snapshot = self._repository.get(account_id)
        invitation = next(
            invitation for invitation in snapshot.invitations if invitation.id == invitation_id
        )
        if invitation.invited_user_id != invited_user_id and invitation.invited_user_id is not None:
            raise PermissionDeniedError("only the invited User can accept this Invitation")
        if invitation.status is not InvitationStatus.PENDING:
            raise ValueError("the Invitation is no longer pending")
        if invitation.expires_at is not None and self._clock() >= invitation.expires_at:
            raise ValueError("the Invitation has expired")
        accepted = replace(invitation, status=InvitationStatus.ACCEPTED)
        assignment = RoleAssignment(
            id=str(uuid4()),
            scope=ResourceScope(account_id=account_id, world_id=invitation.world_id),
            predefined_role=invitation.predefined_role,
            custom_role_id=invitation.custom_role_id,
        )
        existing = next(
            (item for item in snapshot.memberships if item.user_id == invited_user_id),
            None,
        )
        if existing is None:
            membership = Membership(
                id=str(uuid4()),
                account_id=account_id,
                user_id=invited_user_id,
                assignments=(assignment,),
            )
            memberships = (*snapshot.memberships, membership)
        else:
            raise ValueError("the User already has a Membership in this account")
        invitations = tuple(
            accepted if item.id == invitation.id else item for item in snapshot.invitations
        )
        self._repository.save(
            replace(
                snapshot,
                memberships=memberships,
                invitations=invitations,
            ),
            expected_version=snapshot.version,
        )
        return membership

    def accept_pending_invitation(
        self,
        account_id: str,
        *,
        invited_user_id: str,
    ) -> Membership:
        snapshot = self._repository.get(account_id)
        invitation = next(
            (
                item
                for item in snapshot.invitations
                if item.invited_user_id == invited_user_id
                and item.status is InvitationStatus.PENDING
            ),
            None,
        )
        if invitation is None:
            raise ValueError("não existe convite pendente para você neste servidor")
        return self.accept_invitation(
            account_id,
            invitation.id,
            invited_user_id=invited_user_id,
        )

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
            membership for membership in snapshot.memberships if membership.id == membership_id
        )
        if PredefinedRole.OWNER in membership.roles and self._owner_count(snapshot) == 1:
            raise LastOwnerRemovalError("an account must retain at least one Owner")

        remaining = tuple(
            membership for membership in snapshot.memberships if membership.id != membership_id
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
            item.user_id for item in snapshot.memberships if PredefinedRole.OWNER in item.roles
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
        confirmation: SensitiveActionConfirmation | None,
    ) -> None:
        if confirmation is None:
            raise SensitiveActionConfirmationError(
                "the action requires recent reauthentication and exact resource confirmation"
            )
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
            membership.role_assignment is not None
            and membership.role_assignment.predefined_role is PredefinedRole.OWNER
            and membership.role_assignment.scope.world_id is None
            for membership in snapshot.memberships
        )

    @staticmethod
    def _owner_user_ids(snapshot: AccountSnapshot) -> frozenset[str]:
        return frozenset(
            membership.user_id
            for membership in snapshot.memberships
            if membership.role_assignment is not None
            and membership.role_assignment.predefined_role is PredefinedRole.OWNER
            and membership.role_assignment.scope.world_id is None
        )

    @classmethod
    def _ensure_role_replacement_preserves_owner(
        cls,
        snapshot: AccountSnapshot,
        membership: Membership,
        replacement: RoleAssignment,
    ) -> None:
        current = membership.role_assignment
        replacing_account_owner = (
            current is not None
            and current.predefined_role is PredefinedRole.OWNER
            and current.scope.world_id is None
        )
        replacement_is_account_owner = (
            replacement.predefined_role is PredefinedRole.OWNER
            and replacement.scope.world_id is None
        )
        if (
            replacing_account_owner
            and not replacement_is_account_owner
            and cls._owner_count(snapshot) == 1
        ):
            raise LastOwnerRemovalError("an account must retain at least one Owner")

    @classmethod
    def _is_account_owner(cls, snapshot: AccountSnapshot, user_id: str) -> bool:
        return user_id in cls._owner_user_ids(snapshot)

    @staticmethod
    def _hash_recovery_code(recovery_code: str) -> str:
        return sha256(recovery_code.encode("utf-8")).hexdigest()
