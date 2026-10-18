# Runbook: Incidents

## Broker outage
1. Confirm Alpaca status / network.
2. Engine should surface `BrokerError` guidance; no silent retries that hammer the API.
3. Switch temporarily to `paper_sim` only for UI demos — not for reconciling real paper fills.

## Unexpected live orders
1. Halt process; set `TRADING_MODE=paper`.
2. Verify live gate env vars were not set.
3. Rotate keys if exposed.

## Risk breach
1. Kill switch should already halt new orders.
2. Flatten via broker UI if needed.
3. Post-mortem: was stop-loss/daily cap calibrated?
