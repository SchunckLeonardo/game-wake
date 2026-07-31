# Lock the retail rate for each Runtime session

GameWake creates a Session Quote when a wake attempt begins and keeps that final hourly rate for the entire successful Runtime session. Catalog changes never reprice an active Runtime; they are communicated in advance and apply only to future wake confirmations. This makes customer charges predictable and ledger reconciliation stable while GameWake accepts provider-cost movement during an active session.
