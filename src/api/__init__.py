"""
API clients for external data sources.

This package provides clients for:
- The Odds API (Vegas lines, spreads, totals)
- MySportsFeeds/SportsDataIO (injury reports, player news)
"""

from .base_client import BaseAPIClient, APIError, RateLimitError, TimeoutError
from .odds_api import OddsAPIClient
from .mysportsfeeds_api import MySportsFeedsClient

__all__ = [
    'BaseAPIClient',
    'APIError',
    'RateLimitError',
    'TimeoutError',
    'OddsAPIClient',
    'MySportsFeedsClient',
]

