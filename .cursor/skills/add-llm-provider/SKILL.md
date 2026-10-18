# Skill: Add an LLM provider

1. Implement `LLMSentimentProvider` in `trading_bot/sentiment/llm.py`.
2. Add enum value to `LLMProvider` in settings + `.env.example` + README table.
3. Always anonymise entity names before prompts (`anonymise_text`).
4. Rate-limit; on failure raise `LLMProviderError` and let pipeline fall back to FinBERT/neutral.
5. Advisory layer may reuse the provider but must remain order-free.
6. Add a mocked unit/integration test — do not call paid APIs in CI.
