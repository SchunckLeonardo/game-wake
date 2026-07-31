# Use AbacatePay for MVP payments

GameWake uses AbacatePay API v2 as the MVP Payment Provider for one-time Wallet Contributions through Pix and card checkout. GameWake verifies signed webhooks, deduplicates provider events, and reconciles completed, refunded, and disputed payments into its own immutable Wallet Ledger; AbacatePay never becomes the Wallet source of truth. Threshold-triggered Auto Recharge remains outside the confirmed provider contract until AbacatePay documents a safe on-demand stored-payment capability.
