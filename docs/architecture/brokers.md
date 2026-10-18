# Brokers

## Alpaca (default)

- Paper API: `https://paper-api.alpaca.markets` via `alpaca-py` `TradingClient(paper=True)`.
- Market data Basic: IEX feed.
- Paper accounts: open worldwide (including Pakistan) with email signup.

## paper_sim

In-memory broker for local demos and CI without credentials. Instant fills at last set price.

## IBKR (stub)

`IBKRBrokerStub` documents the future live path (IBKR accepts Pakistan for real money). Not implemented — health check returns guidance to use Alpaca/paper_sim.

To implement: new `ibkr_broker.py` against `Broker` ABC, register in `factory.py`, add ADR.
