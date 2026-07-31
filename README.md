# GameWake Web

Landing page, Web Console and Discord Activity for GameWake. The experience lets
a group of friends create a shared account, contribute to its Wallet, invite
members, wake or safely sleep a game World, edit guided settings and inspect
backups and redacted activity.

## Prerequisites

- Node.js `>=22.13.0`

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. Demo routes do not call external services:

- `/onboarding?demo=1`
- `/accounts/demo?demo=1`
- `/activity`

## Validation

```bash
npm run lint
npm test
npm run test:e2e
npm audit --omit=dev
```

The Playwright suite covers desktop and mobile onboarding, Wallet contribution,
invitations, World wake/connect/safe-sleep, guided configuration and the shared
Discord Activity surface.

## Runtime configuration

- `NEXT_PUBLIC_GAMEWAKE_API_URL`: HTTPS origin of the GameWake Control Plane.
- `NEXT_PUBLIC_DISCORD_APPLICATION_ID`: Discord application ID used by the
  Embedded App SDK.

Discord is the product identity provider. Sites access control is used only to
keep preview deployments private; it is not a substitute for GameWake account
authorization.

The production Control Plane, ledger and World state live in Aurora PostgreSQL;
the site intentionally has no separate application database.
