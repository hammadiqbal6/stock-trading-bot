# ADR 0002: Broker abstraction

## Status
Accepted

## Context
Need Alpaca now and IBKR later without rewriting the engine.

## Decision
Define `Broker` ABC (`get_account`, positions, submit/cancel/list orders, `health_check`). Factory selects implementation from config.

## Consequences
- Engine stays broker-agnostic.
- New brokers are additive modules + tests + docs.
