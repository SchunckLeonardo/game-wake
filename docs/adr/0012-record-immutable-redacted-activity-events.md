# Record immutable redacted Activity Events

GameWake records security-, operation-, and billing-relevant actions as immutable Activity Events containing actor, resource, Discord or Web origin, timestamp, outcome, and a safe diff. Secrets and payment methods are redacted before persistence. This adds storage and schema discipline but provides one trustworthy basis for customer history, authorization review, billing support, and incident investigation.
