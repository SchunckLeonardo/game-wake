# Encapsulate game support in versioned Game Templates

GameWake supports each game through a versioned Game Template that owns installation and updates, networking and health checks, player detection, safe save and shutdown behavior, progress and backup rules, typed documented settings, and compatible Runtime Profiles. Every World is permanently associated with exactly one Game Template. This concentrates game-specific behavior behind one contract so the product can add games without scattering conditionals across lifecycle, billing, Discord, and Web UI code.
