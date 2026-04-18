from .core import DatabaseCore, DEFAULT_OWNER_ID

from repositories.assets import AssetMixin
from repositories.alert import AlertMixin
from repositories.auth import AuthMixin
from repositories.backtest import BacktestMixin
from repositories.intelligence import IntelligenceMixin
from repositories.journal import JournalMixin
from repositories.market_data import MarketDataMixin
from repositories.notification import NotificationMixin
from repositories.sync import SyncMixin
from repositories.taiwan_chip import TaiwanChipMixin
from repositories.watchlist import WatchlistMixin
from repositories.workspace import WorkspaceMixin

class Database(
    DatabaseCore,
    AssetMixin,
    AlertMixin,
    AuthMixin,
    BacktestMixin,
    IntelligenceMixin,
    JournalMixin,
    MarketDataMixin,
    NotificationMixin,
    SyncMixin,
    TaiwanChipMixin,
    WatchlistMixin,
    WorkspaceMixin
):
    pass

db = Database()

import logging
log = logging.getLogger(__name__)
from .core import MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE
from models.schema import (
    CREATE_TABLE_STATEMENTS,
    REQUIRED_COLUMN_MIGRATIONS,
    REQUIRED_INDEX_MIGRATIONS,
    build_schema_plan,
)

async def init_db():
    await db.connect()
    await db.create_tables()
    log.info(
        "MySQL initialized: %s@%s:%s/%s",
        MYSQL_USER,
        MYSQL_HOST,
        MYSQL_PORT,
        MYSQL_DATABASE,
    )
