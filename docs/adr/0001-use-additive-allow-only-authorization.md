# Use additive allow-only authorization

GameWake combines the grants from every Role Assignment that applies to a Membership and denies everything not granted. Policies cannot contain explicit denials: removing access requires removing a grant or assigning a narrower Role. This deliberately gives up IAM-style deny precedence so Custom Roles remain understandable, composable, and predictable; product safety invariants remain non-bypassable regardless of granted permissions.
