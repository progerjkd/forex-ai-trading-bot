"""
Data ingestion service for fetching and storing OHLCV data from OANDA.
Handles bulk historical data downloads and real-time data streaming.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from data_ingestion.oanda_client import OANDAClient
from shared.config import settings
from shared.database import SessionLocal
from shared.models import MarketData

logger = logging.getLogger(__name__)


class DataIngestionService:
    """
    Service for ingesting market data from OANDA and storing in TimescaleDB.
    """

    def __init__(self):
        """Initialize data ingestion service."""
        self.oanda_client = OANDAClient()
        logger.info("Data ingestion service initialized")

    def fetch_and_store_candles(
        self,
        instrument: str,
        timeframe: str = "M5",
        count: int = 100,
        db: Optional[Session] = None
    ) -> int:
        """
        Fetch candles from OANDA and store in database.

        Args:
            instrument: Trading pair in OANDA format (e.g., "EUR_USD")
            timeframe: Candle timeframe (M1, M5, M15, H1, H4, D)
            count: Number of candles to fetch
            db: Database session (creates new one if not provided)

        Returns:
            Number of candles stored
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # Fetch candles from OANDA
            logger.info(f"Fetching {count} {timeframe} candles for {instrument}")
            candles = self.oanda_client.get_candles(
                instrument=instrument,
                granularity=timeframe,
                count=count
            )

            if not candles:
                logger.warning(f"No candles returned for {instrument}")
                return 0

            # Store candles in database
            stored_count = 0
            for candle in candles:
                # Check if candle already exists (avoid duplicates)
                existing = db.query(MarketData).filter(
                    MarketData.instrument == instrument,
                    MarketData.timeframe == timeframe,
                    MarketData.timestamp == datetime.fromisoformat(
                        candle['time'].replace('Z', '+00:00')
                    )
                ).first()

                if existing:
                    continue  # Skip duplicate

                # Create new market data record
                market_data = MarketData(
                    instrument=instrument,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(
                        candle['time'].replace('Z', '+00:00')
                    ),
                    open=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    volume=candle['volume']
                )

                db.add(market_data)
                stored_count += 1

            # Commit all changes
            db.commit()
            logger.info(f"Stored {stored_count} new candles for {instrument} ({timeframe})")

            return stored_count

        except Exception as e:
            logger.error(f"Error fetching/storing candles for {instrument}: {e}")
            db.rollback()
            raise

        finally:
            if close_db:
                db.close()

    def fetch_historical_data(
        self,
        instruments: Optional[List[str]] = None,
        timeframe: str = "M5",
        days_back: int = 30
    ) -> dict:
        """
        Fetch historical data for multiple instruments.

        Args:
            instruments: List of instruments (uses config if None)
            timeframe: Candle timeframe
            days_back: Number of days of historical data to fetch

        Returns:
            Dictionary with instrument: candles_stored
        """
        if instruments is None:
            # Convert EUR/USD to EUR_USD format
            instruments = [
                pair.replace("/", "_")
                for pair in settings.get_trading_pairs_list()
            ]

        # Calculate number of candles based on timeframe and days
        timeframe_minutes = {
            'M1': 1,
            'M5': 5,
            'M15': 15,
            'H1': 60,
            'H4': 240,
            'D': 1440
        }

        minutes = timeframe_minutes.get(timeframe, 5)
        candles_per_day = (24 * 60) / minutes
        total_candles = min(int(candles_per_day * days_back), 5000)  # OANDA max

        results = {}
        db = SessionLocal()

        try:
            for instrument in instruments:
                try:
                    count = self.fetch_and_store_candles(
                        instrument=instrument,
                        timeframe=timeframe,
                        count=total_candles,
                        db=db
                    )
                    results[instrument] = count
                except Exception as e:
                    logger.error(f"Failed to fetch {instrument}: {e}")
                    results[instrument] = 0

            return results

        finally:
            db.close()

    def get_latest_timestamp(
        self,
        instrument: str,
        timeframe: str,
        db: Optional[Session] = None
    ) -> Optional[datetime]:
        """
        Get the timestamp of the most recent candle in database.

        Args:
            instrument: Trading pair
            timeframe: Candle timeframe
            db: Database session

        Returns:
            Latest timestamp or None if no data exists
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            latest = db.query(MarketData).filter(
                MarketData.instrument == instrument,
                MarketData.timeframe == timeframe
            ).order_by(MarketData.timestamp.desc()).first()

            return latest.timestamp if latest else None

        finally:
            if close_db:
                db.close()

    def backfill_missing_data(
        self,
        instrument: str,
        timeframe: str = "M5",
        max_candles: int = 5000
    ) -> int:
        """
        Backfill missing historical data for an instrument.

        Args:
            instrument: Trading pair
            timeframe: Candle timeframe
            max_candles: Maximum candles to fetch

        Returns:
            Number of candles stored
        """
        db = SessionLocal()

        try:
            # Get latest timestamp in database
            latest_ts = self.get_latest_timestamp(instrument, timeframe, db)

            if latest_ts:
                # Calculate how many candles we're missing
                now = datetime.utcnow()
                time_diff = now - latest_ts

                timeframe_minutes = {
                    'M1': 1, 'M5': 5, 'M15': 15,
                    'H1': 60, 'H4': 240, 'D': 1440
                }
                minutes = timeframe_minutes.get(timeframe, 5)
                estimated_missing = int(time_diff.total_seconds() / (minutes * 60))

                count = min(estimated_missing, max_candles)
                logger.info(
                    f"Backfilling {count} candles for {instrument} "
                    f"from {latest_ts} to now"
                )
            else:
                # No data exists, fetch maximum
                count = max_candles
                logger.info(f"No existing data for {instrument}, fetching {count} candles")

            return self.fetch_and_store_candles(
                instrument=instrument,
                timeframe=timeframe,
                count=count,
                db=db
            )

        finally:
            db.close()
