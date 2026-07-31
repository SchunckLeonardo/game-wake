CREATE TABLE owner_recovery_profiles (
    owner_user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    verified_email TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- gamewake:statement
CREATE TABLE owner_recovery_codes (
    owner_user_id TEXT NOT NULL REFERENCES owner_recovery_profiles(owner_user_id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (owner_user_id, code_hash)
);
