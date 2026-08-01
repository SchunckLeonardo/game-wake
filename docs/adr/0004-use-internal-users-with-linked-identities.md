# Use internal Users with Linked Identities

GameWake represents each person with an internal User and authenticates that User through Linked Identities. Discord is the only sign-in provider in the MVP, but Discord identifiers do not become the primary identity or ownership key for GameWake resources. This adds a small indirection now so future sign-in providers can be added without migrating Memberships, Worlds, Wallet activity, or ownership.
