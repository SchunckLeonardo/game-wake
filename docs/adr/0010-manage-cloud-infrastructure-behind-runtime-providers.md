# Manage cloud infrastructure behind Runtime Providers

GameWake owns and operates the cloud accounts used to provision customer Runtimes, presenting customers with a final price, region, and Runtime Profile rather than provider credentials or billing. AWS is the only provider in the MVP, implemented behind a Runtime Provider contract for allocation, networking, observation, recovery, and release. GameWake deliberately excludes BYOC and provider selection from the MVP to remove setup bureaucracy while preserving an internal seam for future providers.
