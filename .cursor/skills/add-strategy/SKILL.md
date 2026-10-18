# Skill: Add a strategy

1. Implement `Strategy` in `trading_bot/strategies/` with `generate_targets(close, ...)`.
2. Register/select via `config/settings.yaml` `strategy.name` and factory hook in engine if needed.
3. Add unit tests with synthetic OHLCV (no network).
4. Run `make sample-validation` or synthetic walk-forward; document honest metrics in `docs/strategies/`.
5. Ensure risk engine still sizes/ caps orders — strategy only proposes weights.
6. Update AGENTS.md architecture table if layering changes.
