# Adapt World access to each game

Each Game Template declares a World Access Strategy independent of GameWake Roles. GameWake manages native allowlists through optional linked Game Identities when a title supports them and falls back to a managed shared secret when it does not. This keeps GameWake authorization consistent while acknowledging that actual server-entry controls differ by game and avoids requiring external identity linking where it provides no value.
