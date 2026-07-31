CREATE TABLE account_memberships (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    membership_id TEXT NOT NULL,
    PRIMARY KEY (account_id, user_id),
    UNIQUE (membership_id)
);

-- gamewake:statement
INSERT INTO account_memberships (account_id, user_id, membership_id)
SELECT
    accounts.id,
    membership -> 'fields' ->> 'user_id',
    membership -> 'fields' ->> 'id'
FROM accounts
CROSS JOIN LATERAL jsonb_array_elements(
    accounts.aggregate #> '{fields,memberships,__tuple__}'
) AS membership
ON CONFLICT (account_id, user_id) DO NOTHING;

-- gamewake:statement
CREATE INDEX account_memberships_user_accounts
ON account_memberships (user_id, account_id);
