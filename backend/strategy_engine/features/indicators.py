"""
Technical indicator calculations using pandas and numpy.

Implements common forex trading indicators:
- Trend: SMA, EMA
- Momentum: RSI, MACD, ROC
- Volatility: Bollinger Bands, ATR
- Volume: OBV, Volume indicators
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """
    Calculate technical indicators from OHLCV data.

    Uses pandas and numpy for efficient vectorized calculations.
    Handles edge cases (NaN, insufficient data).
    """

    @staticmethod
    def validate_data(df: pd.DataFrame, min_periods: int = 200) -> bool:
        """
        Check if sufficient data for indicator calculation.

        Args:
            df: DataFrame with OHLCV data
            min_periods: Minimum required periods (default 200 for SMA-200)

        Returns:
            True if sufficient data, False otherwise
        """
        if df is None or df.empty:
            logger.warning("DataFrame is None or empty")
            return False

        if len(df) < min_periods:
            logger.warning(f"Insufficient data: {len(df)} < {min_periods} periods")
            return False

        required_cols = ["open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"Missing required columns: {missing_cols}")
            return False

        return True

    @staticmethod
    def calculate_sma(series: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average."""
        return series.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=period, adjust=False, min_periods=period).mean()

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index.

        Args:
            series: Price series (typically close)
            period: RSI period (default 14)

        Returns:
            RSI values (0-100)
        """
        # Calculate price changes
        delta = series.diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        # Calculate average gains and losses using EMA
        avg_gains = gains.ewm(span=period, adjust=False, min_periods=period).mean()
        avg_losses = losses.ewm(span=period, adjust=False, min_periods=period).mean()

        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            series: Price series (typically close)
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        # Calculate EMAs
        ema_fast = series.ewm(span=fast, adjust=False, min_periods=fast).mean()
        ema_slow = series.ewm(span=slow, adjust=False, min_periods=slow).mean()

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line
        signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()

        # Histogram
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(
        series: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.

        Args:
            series: Price series (typically close)
            period: Moving average period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        middle_band = series.rolling(window=period, min_periods=period).mean()
        std = series.rolling(window=period, min_periods=period).std()

        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)

        return upper_band, middle_band, lower_band

    @staticmethod
    def calculate_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period (default 14)

        Returns:
            ATR values
        """
        # True Range components
        high_low = high - low
        high_close = (high - close.shift(1)).abs()
        low_close = (low - close.shift(1)).abs()

        # True Range is the maximum of the three
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # ATR is the EMA of True Range
        atr = true_range.ewm(span=period, adjust=False, min_periods=period).mean()

        return atr

    @staticmethod
    def calculate_roc(series: pd.Series, period: int) -> pd.Series:
        """
        Calculate Rate of Change.

        Args:
            series: Price series
            period: Period for ROC calculation

        Returns:
            ROC values as percentage
        """
        roc = ((series - series.shift(period)) / series.shift(period)) * 100
        return roc

    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume.

        Args:
            close: Close prices
            volume: Volume

        Returns:
            OBV values
        """
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return obv

    @classmethod
    def calculate_trend_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate trend indicators.

        Adds columns:
        - sma_10, sma_20, sma_50, sma_200
        - ema_9, ema_21, ema_50
        - price_vs_sma20, price_vs_ema21
        - sma20_slope

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with trend indicator columns added
        """
        df = df.copy()
        close = df["close"]

        # Simple Moving Averages
        df["sma_10"] = cls.calculate_sma(close, 10)
        df["sma_20"] = cls.calculate_sma(close, 20)
        df["sma_50"] = cls.calculate_sma(close, 50)
        df["sma_200"] = cls.calculate_sma(close, 200)

        # Exponential Moving Averages
        df["ema_9"] = cls.calculate_ema(close, 9)
        df["ema_21"] = cls.calculate_ema(close, 21)
        df["ema_50"] = cls.calculate_ema(close, 50)

        # Price relative to moving averages (percentage)
        df["price_vs_sma20"] = ((close - df["sma_20"]) / df["sma_20"]) * 100
        df["price_vs_ema21"] = ((close - df["ema_21"]) / df["ema_21"]) * 100

        # SMA-20 slope (rate of change)
        df["sma20_slope"] = df["sma_20"].diff(5) / df["sma_20"].shift(5) * 100

        return df

    @classmethod
    def calculate_momentum_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate momentum indicators.

        Adds columns:
        - rsi_14, rsi_21
        - macd, macd_signal, macd_hist
        - roc_1, roc_5, roc_10
        - rsi_overbought, rsi_oversold
        - macd_crossover

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with momentum indicator columns added
        """
        df = df.copy()
        close = df["close"]

        # RSI
        df["rsi_14"] = cls.calculate_rsi(close, 14)
        df["rsi_21"] = cls.calculate_rsi(close, 21)

        # RSI signals
        df["rsi_overbought"] = (df["rsi_14"] > 70).astype(int)
        df["rsi_oversold"] = (df["rsi_14"] < 30).astype(int)

        # MACD
        macd_line, signal_line, histogram = cls.calculate_macd(close)
        df["macd"] = macd_line
        df["macd_signal"] = signal_line
        df["macd_hist"] = histogram

        # MACD crossover signal (1 = bullish, -1 = bearish, 0 = no signal)
        macd_above = df["macd"] > df["macd_signal"]
        macd_cross = macd_above.astype(int).diff()
        df["macd_crossover"] = macd_cross

        # Rate of Change
        df["roc_1"] = cls.calculate_roc(close, 1)
        df["roc_5"] = cls.calculate_roc(close, 5)
        df["roc_10"] = cls.calculate_roc(close, 10)

        return df

    @classmethod
    def calculate_volatility_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate volatility indicators.

        Adds columns:
        - bb_upper, bb_middle, bb_lower, bb_width, bb_percent
        - atr_14
        - volatility_ratio
        - price_position

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with volatility indicator columns added
        """
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = cls.calculate_bollinger_bands(close, 20, 2.0)
        df["bb_upper"] = bb_upper
        df["bb_middle"] = bb_middle
        df["bb_lower"] = bb_lower

        # Bollinger Band Width (normalized)
        df["bb_width"] = (bb_upper - bb_lower) / bb_middle * 100

        # %B (price position within bands)
        df["bb_percent"] = (close - bb_lower) / (bb_upper - bb_lower) * 100

        # Price position (0 = at lower band, 1 = at upper band)
        df["price_position"] = df["bb_percent"] / 100

        # Average True Range
        df["atr_14"] = cls.calculate_atr(high, low, close, 14)

        # Volatility ratio (ATR relative to price)
        df["volatility_ratio"] = (df["atr_14"] / close) * 100

        return df

    @classmethod
    def calculate_volume_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate volume indicators.

        Adds columns:
        - obv
        - volume_roc_5, volume_roc_10
        - volume_sma_20
        - volume_vs_sma
        - volume_trend

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with volume indicator columns added
        """
        df = df.copy()
        close = df["close"]
        volume = df["volume"]

        # On-Balance Volume
        df["obv"] = cls.calculate_obv(close, volume)

        # Volume Rate of Change
        df["volume_roc_5"] = cls.calculate_roc(volume, 5)
        df["volume_roc_10"] = cls.calculate_roc(volume, 10)

        # Volume Moving Average
        df["volume_sma_20"] = cls.calculate_sma(volume, 20)

        # Volume relative to average
        df["volume_vs_sma"] = (volume / df["volume_sma_20"]) * 100

        # Volume trend (1 = increasing, -1 = decreasing)
        volume_diff = volume.diff(5)
        df["volume_trend"] = np.sign(volume_diff)

        return df

    @classmethod
    def calculate_all(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators.

        Args:
            df: DataFrame with columns [open, high, low, close, volume, timestamp]

        Returns:
            DataFrame with all indicator columns added
        """
        # Validate input data
        if not cls.validate_data(df, min_periods=200):
            logger.error("Data validation failed")
            return df

        # Make a copy to avoid modifying original
        df = df.copy()

        # Ensure timestamp is datetime
        if "timestamp" in df.columns and not pd.api.types.is_datetime64_any_dtype(
            df["timestamp"]
        ):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Calculate indicators by category
        df = cls.calculate_trend_indicators(df)
        df = cls.calculate_momentum_indicators(df)
        df = cls.calculate_volatility_indicators(df)
        df = cls.calculate_volume_indicators(df)

        # Fill NaN values
        # Use forward fill then backward fill for edge cases
        df = df.fillna(method="ffill").fillna(method="bfill")

        # If still NaN (entire column), fill with 0
        df = df.fillna(0)

        logger.info(f"Calculated indicators for {len(df)} candles")

        return df
