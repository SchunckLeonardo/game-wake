# Derive Wallet balance from an immutable ledger

GameWake derives every Wallet balance from an append-only Wallet Ledger. Contributions, reservations, releases, Runtime Charges, storage charges, refunds, and support corrections create entries; corrections compensate earlier entries instead of editing or deleting them. This increases billing implementation discipline while preserving a complete, reconcilable history for customers, payment processing, and support.
