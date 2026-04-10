"""
QuantVision Pro — Shared provider instances.

Centralises all service provider singletons so that routers can
import them without circular dependency issues.
"""

from alert_engine import AlertEngine
from data_fetcher import DataFetcher
from database import db
from external_notifications import ExternalNotificationDispatcher
from fundamentals_provider import FundamentalsProvider
from market_intelligence import MacroSnapshotProvider, MarketEventProvider, NewsProvider
from quote_provider import YahooFinanceQuoteProvider
from screener_engine import ScreenerEngine
from taiwan_chip_provider import TaiwanChipProvider
from ws_manager import ConnectionManager

fetcher = DataFetcher()
quote_provider = YahooFinanceQuoteProvider(fetcher)
external_notifier = ExternalNotificationDispatcher.from_env()
alert_engine = AlertEngine(db, quote_provider, external_notifier=external_notifier)
market_event_provider = MarketEventProvider()
news_provider = NewsProvider()
macro_snapshot_provider = MacroSnapshotProvider(fetcher)
fundamentals_provider = FundamentalsProvider()
taiwan_chip_provider = TaiwanChipProvider(fetcher)
screener_engine = ScreenerEngine()
ws_manager = ConnectionManager()
