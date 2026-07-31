# Reserve Wallet credit before provisioning

GameWake creates a Usage Reservation before allocating paid Runtime infrastructure. The reservation covers startup, at least fifteen minutes Online, and safe shutdown; concurrent wake attempts may use only unreserved Wallet credit. Reservations are not charges and unused amounts are released immediately. This introduces temporary holds into billing so multiple Worlds cannot overcommit one shared Wallet or create postpaid debt.
