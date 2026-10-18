"""Sentiment analysis (FinBERT + pluggable LLM)."""

from trading_bot.sentiment.pipeline import SentimentPipeline, SentimentResult

__all__ = ["SentimentPipeline", "SentimentResult"]
