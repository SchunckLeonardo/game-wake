from threading import RLock

from .model import ConcurrentBillingUpdate, WalletSnapshot


class InMemoryBillingRepository:
    def __init__(self) -> None:
        self._wallets: dict[str, WalletSnapshot] = {}
        self._lock = RLock()

    def get(self, account_id: str) -> WalletSnapshot:
        return self._wallets.get(
            account_id,
            WalletSnapshot(
                account_id,
                entries=(),
                reservations=(),
                quotes=(),
                usages=(),
                contributions=(),
                payment_events=(),
                balance_guards=(),
                world_budgets=(),
                world_budget_alerts=(),
                version=0,
            ),
        )

    def save(self, snapshot: WalletSnapshot, *, expected_version: int) -> None:
        with self._lock:
            current = self.get(snapshot.account_id)
            if current.version != expected_version:
                raise ConcurrentBillingUpdate("Wallet was changed concurrently")
            self._wallets[snapshot.account_id] = WalletSnapshot(
                account_id=snapshot.account_id,
                entries=snapshot.entries,
                reservations=snapshot.reservations,
                quotes=snapshot.quotes,
                usages=snapshot.usages,
                contributions=snapshot.contributions,
                payment_events=snapshot.payment_events,
                balance_guards=snapshot.balance_guards,
                world_budgets=snapshot.world_budgets,
                world_budget_alerts=snapshot.world_budget_alerts,
                version=expected_version + 1,
            )

    def find_contribution(self, contribution_id: str):
        with self._lock:
            return next(
                (
                    contribution
                    for snapshot in self._wallets.values()
                    for contribution in snapshot.contributions
                    if contribution.id == contribution_id
                ),
                None,
            )
