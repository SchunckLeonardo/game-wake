from dataclasses import replace
from uuid import uuid4

from .model import (
    Account,
    Invitation,
    InvitationStatus,
    LastOwnerRemovalError,
    Membership,
    PermissionDeniedError,
    PredefinedRole,
)
from .policy import Permission, permissions_for
from .repository import AccountRepository, AccountSnapshot


class Accounts:
    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    def create_account(self, *, name: str, owner_user_id: str) -> Account:
        account = Account(id=str(uuid4()), name=name)
        owner = Membership(
            id=str(uuid4()),
            account_id=account.id,
            user_id=owner_user_id,
            roles=frozenset({PredefinedRole.OWNER}),
        )
        self._repository.create(account, owner)
        return account

    def list_memberships(self, account_id: str) -> list[Membership]:
        return list(self._repository.get(account_id).memberships)

    def list_invitations(self, account_id: str) -> list[Invitation]:
        return list(self._repository.get(account_id).invitations)

    def authorize(
        self,
        account_id: str,
        *,
        user_id: str,
        permission: Permission,
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
        return membership is not None and permission in permissions_for(membership.roles)

    def assign_predefined_role(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        membership_id: str,
        role: PredefinedRole,
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
        updated = replace(membership, roles=membership.roles | {role})
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
        if not any(
            membership.user_id == inviter_user_id
            and PredefinedRole.OWNER in membership.roles
            for membership in snapshot.memberships
        ):
            raise PermissionDeniedError("inviting members requires the Owner role")
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
            AccountSnapshot(
                account=snapshot.account,
                memberships=snapshot.memberships,
                invitations=(*snapshot.invitations, *invitations),
                version=snapshot.version,
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
            roles=frozenset({PredefinedRole.PLAYER}),
        )
        invitations = tuple(
            accepted if item.id == invitation.id else item
            for item in snapshot.invitations
        )
        self._repository.save(
            AccountSnapshot(
                account=snapshot.account,
                memberships=(*snapshot.memberships, membership),
                invitations=invitations,
                version=snapshot.version,
            ),
            expected_version=snapshot.version,
        )
        return membership

    def remove_membership(self, account_id: str, membership_id: str) -> None:
        snapshot = self._repository.get(account_id)
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
        self._repository.save(
            AccountSnapshot(
                account=snapshot.account,
                memberships=remaining,
                invitations=snapshot.invitations,
                version=snapshot.version,
            ),
            expected_version=snapshot.version,
        )

    @staticmethod
    def _owner_count(snapshot: AccountSnapshot) -> int:
        return sum(
            PredefinedRole.OWNER in membership.roles
            for membership in snapshot.memberships
        )
