"""
Feature engineering for multi-timeframe aggregation.

Combines indicators from multiple timeframes (M1, M5, M15, H1) and adds
time-based and price action features for ML model input.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import pytz

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Assemble feature vectors from indicators across multiple timeframes.

    Combines M1, M5, M15, H1 indicators into a single feature vector
    for ML model input.
    """

    def __init__(self, timeframes: List[str] = ["M1", "M5", "M15", "H1"]):
        """
        Initialize with target timeframes.

        Args:
            timeframes: List of timeframes to include (default: M1, M5, M15, H1)
        """
        self.timeframes = timeframes

    @staticmethod
    def get_forex_session(dt: datetime) -> int:
        """
        Determine forex trading session.

        Args:
            dt: Datetime (timezone-aware)

        Returns:
            Session code:
            0 = Off hours
            1 = Tokyo (00:00-09:00 UTC)
            2 = London (08:00-17:00 UTC)
            3 = New York (13:00-22:00 UTC)
            4 = London/NY overlap (13:00-17:00 UTC)
        """
        # Convert to UTC if not already
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        else:
            dt = dt.astimezone(pytz.UTC)

        hour = dt.hour

        # London/NY overlap (most liquid)
        if 13 <= hour < 17:
            return 4

        # Tokyo session
        if 0 <= hour < 9:
            return 1

        # London session
        if 8 <= hour < 17:
            return 2

        # New York session
        if 13 <= hour < 22:
            return 3

        # Off hours
        return 0

    @staticmethod
    def is_london_open(dt: datetime) -> bool:
        """Check if London session is open."""
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        else:
            dt = dt.astimezone(pytz.UTC)

        hour = dt.hour
        return 8 <= hour < 17

    @staticmethod
    def is_ny_open(dt: datetime) -> bool:
        """Check if New York session is open."""
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        else:
            dt = dt.astimezone(pytz.UTC)

        hour = dt.hour
        return 13 <= hour < 22

    def add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add time-based features.

        Features:
        - hour (0-23)
        - day_of_week (0-6, Monday=0)
        - forex_session (0-4)
        - is_major_session (1 if London/NY overlap)
        - is_london_open, is_ny_open

        Args:
            df: DataFrame with timestamp column

        Returns:
            DataFrame with time features added
        """
        df = df.copy()

        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Hour of day
        df["hour"] = df["timestamp"].dt.hour

        # Day of week (0=Monday, 6=Sunday)
        df["day_of_week"] = df["timestamp"].dt.dayofweek

        # Forex session
        df["forex_session"] = df["timestamp"].apply(self.get_forex_session)

        # Major session (London/NY overlap)
        df["is_major_session"] = (df["forex_session"] == 4).astype(int)

        # Individual sessions
        df["is_london_open"] = df["timestamp"].apply(self.is_london_open).astype(int)
        df["is_ny_open"] = df["timestamp"].apply(self.is_ny_open).astype(int)

        return df

    @staticmethod
    def add_price_action_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add price action features from OHLC data.

        Features:
        - candle_body (close - open)
        - candle_range (high - low)
        - upper_wick, lower_wick
        - body_to_range_ratio
        - wick_balance

        Args:
            df: DataFrame with OHLC columns

        Returns:
            DataFrame with price action features added
        """
        df = df.copy()

        open_price = df["open"]
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Candle body (positive for bullish, negative for bearish)
        df["candle_body"] = close - open_price

        # Candle range
        df["candle_range"] = high - low

        # Avoid division by zero
        candle_range_safe = df["candle_range"].replace(0, 1e-10)

        # Body to range ratio (0-1)
        df["body_to_range_ratio"] = df["candle_body"].abs() / candle_range_safe

        # Wicks
        df["upper_wick"] = high - pd.concat([open_price, close], axis=1).max(axis=1)
        df["lower_wick"] = pd.concat([open_price, close], axis=1).min(axis=1) - low

        # Wick balance (-1 to 1, negative = more lower wick, positive = more upper wick)
        total_wick = df["upper_wick"] + df["lower_wick"]
        total_wick_safe = total_wick.replace(0, 1e-10)
        df["wick_balance"] = (df["upper_wick"] - df["lower_wick"]) / total_wick_safe

        return df

    def build_vector(
        self,
        indicators_by_timeframe: Dict[str, pd.DataFrame],
        target_timestamp: datetime,
    ) -> pd.DataFrame:
        """
        Build feature vector from multi-timeframe indicators.

        Args:
            indicators_by_timeframe: Dictionary mapping timeframe to DataFrame
                Example: {
                    "M1": DataFrame with indicators for M1,
                    "M5": DataFrame with indicators for M5,
                    ...
                }
            target_timestamp: Timestamp to extract features for

        Returns:
            Single-row DataFrame with all features (1 × N columns)
        """
        features = {}

        # Extract latest row from each timeframe
        for timeframe in self.timeframes:
            if timeframe not in indicators_by_timeframe:
                logger.warning(f"Timeframe {timeframe} not in indicators dict")
                continue

            df = indicators_by_timeframe[timeframe]

            if df.empty:
                logger.warning(f"Empty DataFrame for timeframe {timeframe}")
                continue

            # Get the row closest to target timestamp (should be exact match or latest)
            if "timestamp" in df.columns:
                df = df.set_index("timestamp")

            # Get latest row
            latest_row = df.iloc[-1]

            # Prefix all columns with timeframe
            for col in latest_row.index:
                if col != "timestamp":  # Don't duplicate timestamp
                    feature_name = f"{timeframe}_{col}"
                    features[feature_name] = latest_row[col]

        # Create DataFrame from features
        feature_df = pd.DataFrame([features])

        # Add time features (from M1 timeframe or target_timestamp)
        time_data = pd.DataFrame({"timestamp": [target_timestamp]})
        time_features = self.add_time_features(time_data)

        # Add time features to result
        for col in time_features.columns:
            if col != "timestamp":
                feature_df[col] = time_features[col].values[0]

        # Add price action features (from M1 timeframe)
        if "M1" in indicators_by_timeframe and not indicators_by_timeframe["M1"].empty:
            m1_df = indicators_by_timeframe["M1"]
            if "timestamp" in m1_df.columns:
                m1_df = m1_df.set_index("timestamp")

            latest_m1 = m1_df.iloc[[-1]].reset_index(drop=True)

            # Add OHLC columns if not present
            if all(
                col in latest_m1.columns for col in ["open", "high", "low", "close"]
            ):
                price_features = self.add_price_action_features(latest_m1)

                for col in price_features.columns:
                    if col not in ["open", "high", "low", "close", "volume", "timestamp"]:
                        feature_df[col] = price_features[col].values[0]

        logger.info(f"Built feature vector with {len(feature_df.columns)} features")

        return feature_df

    def get_feature_names(self) -> List[str]:
        """
        Get expected feature names based on configured timeframes.

        Returns:
            List of feature names
        """
        # This is a placeholder - actual names depend on indicators calculated
        # Used for validation and ML model training
        base_indicators = [
            "sma_10",
            "sma_20",
            "sma_50",
            "sma_200",
            "ema_9",
            "ema_21",
            "ema_50",
            "price_vs_sma20",
            "price_vs_ema21",
            "sma20_slope",
            "rsi_14",
            "rsi_21",
            "macd",
            "macd_signal",
            "macd_hist",
            "roc_1",
            "roc_5",
            "roc_10",
            "rsi_overbought",
            "rsi_oversold",
            "macd_crossover",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_width",
            "bb_percent",
            "atr_14",
            "volatility_ratio",
            "price_position",
            "obv",
            "volume_roc_5",
            "volume_roc_10",
            "volume_sma_20",
            "volume_vs_sma",
            "volume_trend",
        ]

        # Prefix with timeframes
        features = []
        for timeframe in self.timeframes:
            for indicator in base_indicators:
                features.append(f"{timeframe}_{indicator}")

        # Add time features
        time_features = [
            "hour",
            "day_of_week",
            "forex_session",
            "is_major_session",
            "is_london_open",
            "is_ny_open",
        ]
        features.extend(time_features)

        # Add price action features
        price_features = [
            "candle_body",
            "candle_range",
            "body_to_range_ratio",
            "upper_wick",
            "lower_wick",
            "wick_balance",
        ]
        features.extend(price_features)

        return features
