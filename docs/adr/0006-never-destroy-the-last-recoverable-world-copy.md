# Never destroy the last recoverable World copy

GameWake never destroys the last recoverable copy of a World. A World reaches `Dormindo` only after its progress is durably persisted outside the Runtime and validated. If final persistence fails, GameWake preserves recoverable storage, releases expensive compute only when safe, and moves the World to `Precisa de atenção`; every Runtime provider adapter must support this Recovery Guarantee.
