"""
Feature service for fetching candle data and calculating features.

Integrates with TimescaleDB to fetch historical candles,
calculates indicators, and builds feature vectors for ML inference.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import and_
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from shared.models import MarketData

from .feature_engineer import FeatureEngineer
from .indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


class FeatureService:
    """
    Service for fetching candle data and calculating features.

    Integrates with TimescaleDB to fetch historical candles,
    calculates indicators, and builds feature vectors.
    """

    # Timeframe to minutes mapping
    TIMEFRAME_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D": 1440,
    }

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize with optional database session.

        Args:
            db: SQLAlchemy session (creates new if not provided)
        """
        self.db = db or SessionLocal()
        self.indicator_calculator = IndicatorCalculator()
        self.feature_engineer = FeatureEngineer()

        # Track if we own the session (for cleanup)
        self._owns_session = db is None

    def __del__(self):
        """Clean up database session if we own it."""
        if self._owns_session and self.db:
            self.db.close()

    def get_candles(
        self,
        instrument: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """
        Fetch candle data from database.

        Args:
            instrument: Trading pair (e.g., "EUR_USD")
            timeframe: Timeframe (e.g., "M1", "M5", "H1")
            start_time: Start of time range
            end_time: End of time range

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        try:
            # Query MarketData table
            candles = (
                self.db.query(MarketData)
                .filter(
                    and_(
                        MarketData.instrument == instrument,
                        MarketData.timeframe == timeframe,
                        MarketData.timestamp >= start_time,
                        MarketData.timestamp <= end_time,
                    )
                )
                .order_by(MarketData.timestamp)
                .all()
            )

            if not candles:
                logger.warning(
                    f"No candles found for {instrument} {timeframe} "
                    f"from {start_time} to {end_time}"
                )
                return pd.DataFrame()

            # Convert to DataFrame
            data = {
                "timestamp": [c.timestamp for c in candles],
                "open": [float(c.open) for c in candles],
                "high": [float(c.high) for c in candles],
                "low": [float(c.low) for c in candles],
                "close": [float(c.close) for c in candles],
                "volume": [int(c.volume) for c in candles],
            }

            df = pd.DataFrame(data)

            logger.info(
                f"Fetched {len(df)} candles for {instrument} {timeframe} "
                f"from {start_time} to {end_time}"
            )

            return df

        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            return pd.DataFrame()

    def calculate_start_time(
        self, target_time: datetime, timeframe: str, lookback_periods: int
    ) -> datetime:
        """
        Calculate start time based on lookback periods.

        Args:
            target_time: Target timestamp
            timeframe: Timeframe (e.g., "M1", "M5")
            lookback_periods: Number of periods to look back

        Returns:
            Start time
        """
        if timeframe not in self.TIMEFRAME_MINUTES:
            raise ValueError(f"Unknown timeframe: {timeframe}")

        minutes_per_period = self.TIMEFRAME_MINUTES[timeframe]
        lookback_minutes = lookback_periods * minutes_per_period

        start_time = target_time - timedelta(minutes=lookback_minutes)

        return start_time

    def calculate_indicators_for_timeframe(
        self,
        instrument: str,
        timeframe: str,
        target_time: datetime,
        lookback_periods: int = 250,
    ) -> pd.DataFrame:
        """
        Calculate indicators for single timeframe.

        Fetches enough historical data (lookback_periods) to calculate
        all indicators accurately (e.g., SMA-200 needs 200+ bars).

        Args:
            instrument: Trading pair (e.g., "EUR_USD")
            timeframe: Timeframe (e.g., "M1", "M5")
            target_time: Target timestamp
            lookback_periods: Number of periods to fetch (default 250)

        Returns:
            DataFrame with indicators calculated
        """
        # Calculate start time
        start_time = self.calculate_start_time(target_time, timeframe, lookback_periods)

        # Fetch candles
        df = self.get_candles(instrument, timeframe, start_time, target_time)

        if df.empty:
            logger.warning(
                f"No candles available for {instrument} {timeframe}, "
                "cannot calculate indicators"
            )
            return pd.DataFrame()

        # Validate sufficient data
        if len(df) < 200:
            logger.warning(
                f"Insufficient data for {instrument} {timeframe}: "
                f"{len(df)} candles (need 200+)"
            )

        # Calculate indicators
        df_with_indicators = self.indicator_calculator.calculate_all(df)

        return df_with_indicators

    def get_features(
        self,
        instrument: str,
        target_time: datetime,
        timeframes: List[str] = ["M1", "M5", "M15", "H1"],
        lookback_periods: int = 250,
    ) -> pd.DataFrame:
        """
        Get complete feature vector for ML inference.

        Args:
            instrument: Trading pair (e.g., "EUR_USD")
            target_time: Timestamp to generate features for
            timeframes: List of timeframes to include
            lookback_periods: Historical data to fetch per timeframe

        Returns:
            Single-row DataFrame with all features (1 × N columns)

        Example:
            >>> service = FeatureService()
            >>> features = service.get_features(
            ...     "EUR_USD",
            ...     datetime(2024, 1, 15, 10, 30, 0),
            ...     timeframes=["M1", "M5", "M15", "H1"]
            ... )
            >>> print(features.shape)
            (1, 150)  # 1 row, ~150 features
        """
        try:
            # Calculate indicators for each timeframe
            indicators_by_timeframe = {}

            for timeframe in timeframes:
                logger.info(
                    f"Calculating indicators for {instrument} {timeframe} "
                    f"at {target_time}"
                )

                df_indicators = self.calculate_indicators_for_timeframe(
                    instrument, timeframe, target_time, lookback_periods
                )

                if not df_indicators.empty:
                    indicators_by_timeframe[timeframe] = df_indicators
                else:
                    logger.warning(
                        f"Failed to calculate indicators for {timeframe}, skipping"
                    )

            # Check if we have at least one timeframe
            if not indicators_by_timeframe:
                logger.error("No indicators calculated for any timeframe")
                return pd.DataFrame()

            # Build feature vector
            feature_vector = self.feature_engineer.build_vector(
                indicators_by_timeframe, target_time
            )

            logger.info(
                f"Generated feature vector with {len(feature_vector.columns)} features"
            )

            return feature_vector

        except Exception as e:
            logger.error(f"Error generating features: {e}")
            import traceback

            traceback.print_exc()
            return pd.DataFrame()

    def get_batch_features(
        self,
        instrument: str,
        timestamps: List[datetime],
        timeframes: List[str] = ["M1", "M5", "M15", "H1"],
        lookback_periods: int = 250,
    ) -> pd.DataFrame:
        """
        Get features for multiple timestamps (for training/backtesting).

        Args:
            instrument: Trading pair (e.g., "EUR_USD")
            timestamps: List of timestamps to generate features for
            timeframes: List of timeframes to include
            lookback_periods: Historical data per timeframe

        Returns:
            DataFrame with shape (N × features) where N = len(timestamps)

        Example:
            >>> service = FeatureService()
            >>> timestamps = [
            ...     datetime(2024, 1, 15, 10, 0, 0),
            ...     datetime(2024, 1, 15, 10, 5, 0),
            ...     datetime(2024, 1, 15, 10, 10, 0),
            ... ]
            >>> features = service.get_batch_features("EUR_USD", timestamps)
            >>> print(features.shape)
            (3, 150)  # 3 rows, ~150 features each
        """
        all_features = []

        logger.info(f"Generating features for {len(timestamps)} timestamps")

        for i, timestamp in enumerate(timestamps):
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(timestamps)} timestamps")

            features = self.get_features(
                instrument, timestamp, timeframes, lookback_periods
            )

            if not features.empty:
                # Add timestamp column for reference
                features["target_timestamp"] = timestamp
                all_features.append(features)

        if not all_features:
            logger.error("No features generated for any timestamp")
            return pd.DataFrame()

        # Concatenate all feature vectors
        batch_features = pd.concat(all_features, ignore_index=True)

        logger.info(
            f"Generated batch features: {batch_features.shape[0]} rows × "
            f"{batch_features.shape[1]} columns"
        )

        return batch_features

    def get_latest_features(
        self,
        instrument: str,
        timeframes: List[str] = ["M1", "M5", "M15", "H1"],
    ) -> pd.DataFrame:
        """
        Get features for the most recent timestamp available.

        Useful for real-time inference.

        Args:
            instrument: Trading pair
            timeframes: List of timeframes

        Returns:
            Single-row DataFrame with latest features
        """
        # Get latest candle from M1 timeframe to determine latest timestamp
        latest_candle = (
            self.db.query(MarketData)
            .filter(
                and_(
                    MarketData.instrument == instrument,
                    MarketData.timeframe == "M1",
                )
            )
            .order_by(MarketData.timestamp.desc())
            .first()
        )

        if not latest_candle:
            logger.error(f"No candles found for {instrument}")
            return pd.DataFrame()

        target_time = latest_candle.timestamp

        logger.info(f"Generating features for latest timestamp: {target_time}")

        return self.get_features(instrument, target_time, timeframes)
