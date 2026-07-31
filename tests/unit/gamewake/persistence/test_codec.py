from datetime import UTC, datetime
from decimal import Decimal

from gamewake.accounts import (
    Account,
    ActivityAction,
    ActivityEvent,
    Membership,
    Permission,
    PredefinedRole,
    ResourceScope,
    RoleAssignment,
)
from gamewake.accounts.repository import AccountSnapshot
from gamewake.billing import LedgerEntry, LedgerEntryType
from gamewake.billing.model import WalletSnapshot
from gamewake.persistence import decode_domain, encode_domain


def test_round_trips_nested_account_snapshot_without_importing_types_from_payload() -> None:
    occurred_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    snapshot = AccountSnapshot(
        account=Account("account-1", "Sexta", "guild-1"),
        memberships=(
            Membership(
                "membership-1",
                "account-1",
                "user-1",
                (
                    RoleAssignment(
                        "assignment-1",
                        ResourceScope("account-1"),
                        predefined_role=PredefinedRole.OWNER,
                    ),
                ),
            ),
        ),
        invitations=(),
        custom_roles=(),
        activity_events=(
            ActivityEvent(
                "event-1",
                "account-1",
                "user-1",
                ActivityAction.OWNER_RECOVERED,
                "user-1",
                occurred_at,
            ),
        ),
        version=3,
    )

    encoded = encode_domain(snapshot)

    assert "gamewake.accounts.repository.AccountSnapshot" in encoded
    assert decode_domain(encoded, AccountSnapshot) == snapshot


def test_round_trips_decimal_enum_tuple_and_frozenset_values() -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    wallet = WalletSnapshot(
        account_id="account-1",
        entries=(
            LedgerEntry(
                "entry-1",
                "account-1",
                LedgerEntryType.CONTRIBUTION,
                Decimal("25.00"),
                "payment-1",
                "event-1",
                now,
            ),
        ),
        reservations=(),
        quotes=(),
        usages=(),
        contributions=(),
        payment_events=(),
        balance_guards=(),
        world_budgets=(),
        world_budget_alerts=(),
        version=1,
    )

    assert decode_domain(encode_domain(wallet), WalletSnapshot) == wallet
    assert decode_domain(encode_domain(frozenset({Permission.WAKE_WORLD}))) == frozenset(
        {Permission.WAKE_WORLD}
    )


def test_rejects_unknown_domain_type_instead_of_importing_it() -> None:
    payload = '{"__type__":"os.system","fields":{"command":"echo unsafe"}}'

    try:
        decode_domain(payload)
    except ValueError as error:
        assert "unknown persisted domain type" in str(error)
    else:
        raise AssertionError("unknown persisted types must be rejected")
