# Refund wake attempts that never go Online

GameWake records Runtime Usage from the start of infrastructure allocation, but automatically reverses its Wallet debits when a wake attempt never reaches `Online`. Repeated attempts may be rate-limited and the failure cause must be shown to the user. GameWake absorbs failed-start infrastructure cost so customers pay only for sessions they could actually use, accepting that the product must actively control abuse and startup reliability.
