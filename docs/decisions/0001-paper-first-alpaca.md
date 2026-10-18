# ADR 0001: Paper-first Alpaca as default broker

## Status
Accepted

## Context
Owner is Pakistan-based. Need a free paper brokerage open worldwide, with a path to live later.

## Decision
Use Alpaca paper trading (`alpaca-py`, paper API) as default. Live requires explicit dual confirmation flags. IBKR reserved as stub for future real-money.

## Consequences
- Works without local broker workstation.
- IEX data limitations on Basic plan.
- Live money may need IBKR depending on Alpaca real-account eligibility.
