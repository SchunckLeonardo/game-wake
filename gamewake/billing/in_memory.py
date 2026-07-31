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
                version=expected_version + 1,
            )
