---
version: 1
slug: "web-app-page-tsx"
primary_target: "web/app/page.tsx"
related_targets: ["web/app/console/ConsoleDashboard.tsx","web/app/onboarding/OnboardingFlow.tsx","web/app/activity/DiscordActivityExperience.tsx","web/app/auth/callback/AuthCallback.tsx"]
---

# GameWake site system

## Scope and visitor modes

- Landing: **Persuade** a small group of friends to enter with Discord and understand pay-as-you-go without learning infrastructure.
- Console, onboarding, auth and Discord Activity: **Operate** the selected World, shared Wallet, members, backups, activity and configuration with immediate state clarity.

## Job, action and proof

- The visitor must understand that the World persists while infrastructure sleeps.
- Primary landing action: `Entrar com Discord`.
- Primary Console action: wake or safely sleep the selected World.
- Proof comes from the visible wake lifecycle, locked session price, friend presence and protected backup state already supported by the product.

## Chosen direction

**Mesa Central do World.** The World is the visual and operational center. Friends, Discord, cost and protection occupy anchored stations around it. Inside the Console, the same table becomes a scannable workspace with a concise status band and action dock instead of a KPI wall.

- Approved comp: `.impeccable/mocks/world-table.png`
- Memorable moment: the sleeping World sits safely at the center and the single Wake Green action visibly changes its state.
- Preserve the GameWake design system, product copy and all working behavior.

## Fidelity inventory

| Visible ingredient | Commitment | Implementation medium |
| --- | --- | --- |
| Slim navigation | Brand, two anchors and one Discord action | Semantic HTML and CSS |
| Central circular World | Dominant first-viewport focal point with calm depth | Generated raster world artwork plus semantic HTML overlay |
| Four connected stations | Friends, Discord, price and backup remain anchored to the World | Semantic HTML, CSS lines and authored inline SVG icons |
| Primary action | One tactile Wake Green button with hard offset shadow | Semantic link/button and CSS |
| Landing second fold | Three-step explanation begins inside the first desktop viewport | Semantic section and CSS grid |
| Console status band | World state, Wallet and backup read in one pass | Semantic HTML and CSS |
| Console World table | Selected World remains central; information supports it rather than competing | Generated raster artwork, HTML and CSS |
| Friend presence | Names, presence and invitation stay close to the World | Semantic lists and status text |
| Action dock | Wake, sleep and contextual actions remain familiar controls | Semantic buttons and CSS |
| Mobile adaptation | World leads, stations become a vertical sequence, navigation becomes bottom dock | Responsive CSS; no squeezed desktop layout |

## Constraints

- No generic cloud dashboard, fictional testimonials, invented customers or unsupported claims.
- The generated World is illustrative and must not imply an exact in-game map.
- Essential text, focus, keyboard navigation, reduced motion and WCAG 2.2 AA remain mandatory.
- Existing API calls, permissions, lifecycle rules and test selectors remain functional.

## Unresolved decisions

None. The user approved the Mesa Central composition and its Console translation.
