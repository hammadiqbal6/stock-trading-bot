"""News aggregators."""

from trading_bot.news.base import NewsArticle, NewsSource
from trading_bot.news.finnhub_source import FinnhubNewsSource
from trading_bot.news.gdelt_source import GDELTNewsSource
from trading_bot.news.aggregator import NewsAggregator

__all__ = [
    "FinnhubNewsSource",
    "GDELTNewsSource",
    "NewsAggregator",
    "NewsArticle",
    "NewsSource",
]
