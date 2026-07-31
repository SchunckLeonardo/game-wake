CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    discord_guild_id TEXT UNIQUE,
    aggregate JSONB NOT NULL,
    version BIGINT NOT NULL CHECK (version >= 1),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- gamewake:statement
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    aggregate JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- gamewake:statement
CREATE TABLE linked_identities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    aggregate JSONB NOT NULL,
    UNIQUE (provider, provider_user_id),
    UNIQUE (user_id, provider)
);

-- gamewake:statement
CREATE TABLE activity_events (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);

-- gamewake:statement
CREATE INDEX activity_events_account_timeline
ON activity_events (account_id, occurred_at, id);

-- gamewake:statement
CREATE TABLE worlds (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    status TEXT NOT NULL,
    aggregate JSONB NOT NULL,
    version BIGINT NOT NULL CHECK (version >= 1),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id, id)
);

-- gamewake:statement
CREATE TABLE configuration_revisions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    world_id TEXT NOT NULL,
    number BIGINT NOT NULL CHECK (number >= 1),
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    FOREIGN KEY (account_id, world_id) REFERENCES worlds(account_id, id) ON DELETE CASCADE,
    UNIQUE (account_id, idempotency_key),
    UNIQUE (account_id, world_id, number)
);

-- gamewake:statement
CREATE TABLE world_operations (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    world_id TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    version BIGINT NOT NULL CHECK (version >= 1),
    FOREIGN KEY (account_id, world_id) REFERENCES worlds(account_id, id) ON DELETE CASCADE,
    UNIQUE (account_id, idempotency_key)
);

-- gamewake:statement
CREATE UNIQUE INDEX world_operations_one_active_per_world
ON world_operations (account_id, world_id)
WHERE status IN ('pending', 'running');

-- gamewake:statement
CREATE INDEX world_operations_timeline
ON world_operations (account_id, world_id, created_at, id);

-- gamewake:statement
CREATE TABLE wallet_snapshots (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    aggregate JSONB NOT NULL,
    version BIGINT NOT NULL CHECK (version >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- gamewake:statement
CREATE TABLE wallet_ledger_entries (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    entry_type TEXT NOT NULL,
    amount NUMERIC(20, 6) NOT NULL,
    reference TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (account_id, idempotency_key)
);

-- gamewake:statement
CREATE INDEX wallet_ledger_account_timeline
ON wallet_ledger_entries (account_id, occurred_at, id);

-- gamewake:statement
CREATE TABLE wallet_contributions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (account_id, idempotency_key)
);

-- gamewake:statement
CREATE TABLE storage_grace_states (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    version BIGINT NOT NULL CHECK (version >= 1),
    payload JSONB NOT NULL
);

-- gamewake:statement
CREATE TABLE storage_statuses (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- gamewake:statement
CREATE OR REPLACE FUNCTION reject_immutable_row_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'GameWake immutable records cannot be updated or deleted';
END;
$$ LANGUAGE plpgsql;

-- gamewake:statement
CREATE TRIGGER wallet_ledger_entries_are_immutable
BEFORE UPDATE OR DELETE ON wallet_ledger_entries
FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

-- gamewake:statement
CREATE TRIGGER activity_events_are_immutable
BEFORE UPDATE OR DELETE ON activity_events
FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
