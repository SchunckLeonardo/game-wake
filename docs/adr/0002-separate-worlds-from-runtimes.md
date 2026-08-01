# Separate Worlds from Runtimes

GameWake models a World as the persistent game resource and a Runtime as the disposable infrastructure that executes it. A Runtime may be created, replaced, or destroyed as part of wake and sleep operations, but no Runtime lifecycle operation may delete the World's progress, settings, or backups. This separation allows GameWake to change infrastructure providers and control compute costs without changing the identity or continuity of a World.
