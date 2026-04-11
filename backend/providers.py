"""
QuantVision Pro — Shared provider instances.

Centralises all service provider singletons so that routers can
import them without circular dependency issues.
"""

from alert_engine import AlertEngine
from data_fetcher import DataFetcher
from database import db
from fubon_data_fetcher import HybridDataFetcher
from fubon_futopt_provider import FubonFutoptProvider
from fubon_symbols import (
    is_exact_futopt_contract,
    supports_fubon_stock_realtime_ticker,
    tw_ticker_to_fubon,
)
from fubon_quote_provider import FubonQuoteProvider, HybridQuoteProvider
from external_notifications import ExternalNotificationDispatcher
from fubon_provider import FubonSDKManager
from fundamentals_provider import FundamentalsProvider
from market_intelligence import MacroSnapshotProvider, MarketEventProvider, NewsProvider
from quote_provider import YahooFinanceQuoteProvider
from screener_engine import ScreenerEngine
from taiwan_chip_provider import TaiwanChipProvider
from ws_manager import ConnectionManager

_yahoo_fetcher = DataFetcher()
fubon_manager = FubonSDKManager()
fetcher = HybridDataFetcher(_yahoo_fetcher, fubon_manager)
yahoo_quote_provider = YahooFinanceQuoteProvider(fetcher)
fubon_quote_provider = FubonQuoteProvider(fubon_manager)
fubon_futopt_provider = FubonFutoptProvider(fubon_manager)
quote_provider = HybridQuoteProvider(fubon_quote_provider, yahoo_quote_provider)
external_notifier = ExternalNotificationDispatcher.from_env()
alert_engine = AlertEngine(db, quote_provider, external_notifier=external_notifier)
market_event_provider = MarketEventProvider()
news_provider = NewsProvider()
macro_snapshot_provider = MacroSnapshotProvider(fetcher)
fundamentals_provider = FundamentalsProvider()
taiwan_chip_provider = TaiwanChipProvider(fetcher)
screener_engine = ScreenerEngine()
ws_manager = ConnectionManager()


def _subscribe_fubon_streams(ticker: str) -> None:
    if not fubon_manager.connected:
        return
    if supports_fubon_stock_realtime_ticker(ticker):
        symbol = tw_ticker_to_fubon(ticker)
        if not symbol:
            return
        for channel in ("aggregates", "books", "candles"):
            fubon_manager.subscribe_stock(symbol, channel)
        return
    if not is_exact_futopt_contract(ticker):
        return
    for channel in ("aggregates", "books", "candles"):
        fubon_manager.subscribe_futopt(ticker, channel)


def _unsubscribe_fubon_streams(ticker: str) -> None:
    if supports_fubon_stock_realtime_ticker(ticker):
        symbol = tw_ticker_to_fubon(ticker)
        if not symbol:
            return
        for channel in ("aggregates", "books", "candles"):
            fubon_manager.unsubscribe_stock(symbol, channel)
        return
    if not is_exact_futopt_contract(ticker):
        return
    for channel in ("aggregates", "books", "candles"):
        fubon_manager.unsubscribe_futopt(ticker, channel)


ws_manager.configure_market_data_hooks(
    on_first_subscribe=_subscribe_fubon_streams,
    on_last_unsubscribe=_unsubscribe_fubon_streams,
)
