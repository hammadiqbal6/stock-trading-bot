# Skill: Add a data or news source

## Market data
1. Implement `MarketDataProvider` in `trading_bot/data/` (`get_bars`, `health_check`).
2. Wire into `get_data_provider()` with clear live vs backtest purpose.
3. Add rate limiting + actionable `DataError` guidance.
4. Unit-test normalization with fixture frames (no network).

## News
1. Implement `NewsSource` in `trading_bot/news/`.
2. Register in `NewsAggregator._default_sources` with graceful skip on missing creds.
3. Document signup + env var in README accounts table and `.env.example`.
4. Respect rate limits; never crash the engine if one source fails.
