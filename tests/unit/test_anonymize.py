from trading_bot.sentiment.anonymize import anonymise_text


def test_anonymise_strips_ticker_and_name() -> None:
    text = "Apple Inc (AAPL) beats estimates while Microsoft lags"
    out = anonymise_text(text, "AAPL")
    assert "AAPL" not in out
    assert "Apple" not in out
    assert "TICKER" in out or "COMPANY" in out
