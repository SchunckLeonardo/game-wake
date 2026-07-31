import pytest

from gamewake.accounts import (
    Accounts,
    InMemoryAccountRepository,
    LastOwnerRemovalError,
    PredefinedRole,
)


def test_creating_an_account_makes_the_creator_its_owner():
    accounts = Accounts(InMemoryAccountRepository())

    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")

    memberships = accounts.list_memberships(account.id)
    assert [(membership.user_id, membership.roles) for membership in memberships] == [
        ("user-owner", frozenset({PredefinedRole.OWNER}))
    ]


def test_the_last_owner_cannot_be_removed_from_an_account():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [owner] = accounts.list_memberships(account.id)

    with pytest.raises(LastOwnerRemovalError):
        accounts.remove_membership(account.id, owner.id)

    assert accounts.list_memberships(account.id) == [owner]
