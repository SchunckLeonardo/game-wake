from gamewake.accounts import Membership, PredefinedRole, ResourceScope, RoleAssignment


def assignment(identifier: str, role: PredefinedRole) -> RoleAssignment:
    return RoleAssignment(
        id=identifier,
        scope=ResourceScope(account_id="account-1"),
        predefined_role=role,
    )


def test_legacy_additive_membership_projects_the_newest_non_owner_role() -> None:
    membership = Membership(
        id="membership-1",
        account_id="account-1",
        user_id="user-1",
        assignments=(
            assignment("assignment-player", PredefinedRole.PLAYER),
            assignment("assignment-manager", PredefinedRole.MANAGER),
        ),
    )

    assert membership.role_assignment == membership.assignments[-1]
    assert membership.roles == frozenset({PredefinedRole.MANAGER})


def test_legacy_additive_membership_preserves_account_ownership_during_transition() -> None:
    membership = Membership(
        id="membership-owner",
        account_id="account-1",
        user_id="owner",
        assignments=(
            assignment("assignment-owner", PredefinedRole.OWNER),
            assignment("assignment-player", PredefinedRole.PLAYER),
        ),
    )

    assert membership.role_assignment == membership.assignments[0]
    assert membership.roles == frozenset({PredefinedRole.OWNER})
