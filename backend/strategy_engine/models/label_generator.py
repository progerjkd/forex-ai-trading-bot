"""
Label generator for forex trading signals.

Generates BUY/SELL/HOLD labels from historical price movements using
forward returns method.
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from shared.database import SessionLocal

logger = logging.getLogger(__name__)


class LabelGenerator:
    """
    Generate trading labels from price movements.

    Uses forward returns method:
    - BUY: Price increases ≥ threshold% within next N candles
    - SELL: Price decreases ≤ -threshold% within next N candles
    - HOLD: Price movement within ±threshold% range
    """

    def __init__(
        self,
        price_threshold: float = 0.5,  # 0.5% movement
        lookahead_periods: int = 5,  # 5 candles forward
        db: Optional[Session] = None,
    ):
        """
        Initialize label generator.

        Args:
            price_threshold: Percentage price movement to trigger BUY/SELL (default 0.5%)
            lookahead_periods: Number of candles to look forward (default 5)
            db: Optional database session
        """
        self.price_threshold = price_threshold / 100  # Convert to decimal
        self.lookahead_periods = lookahead_periods
        self.db = db or SessionLocal()
        self._owns_session = db is None

    def __del__(self):
        """Clean up database session."""
        if self._owns_session and self.db:
            self.db.close()

    def generate_labels(
        self, candle_data: pd.DataFrame, price_column: str = "close"
    ) -> pd.Series:
        """
        Generate labels from candle data.

        Args:
            candle_data: DataFrame with OHLCV data and timestamp
            price_column: Column to use for labeling (default "close")

        Returns:
            Series with labels: 1 (BUY), -1 (SELL), 0 (HOLD)
        """
        # Calculate forward returns
        prices = candle_data[price_column]
        forward_returns = prices.shift(-self.lookahead_periods) / prices - 1

        # Generate labels based on threshold
        labels = pd.Series(0, index=candle_data.index, name="label")

        # BUY: Price increases by threshold or more
        labels[forward_returns >= self.price_threshold] = 1

        # SELL: Price decreases by threshold or more
        labels[forward_returns <= -self.price_threshold] = -1

        # HOLD: Everything else (already set to 0)

        # Drop the last N rows that don't have lookahead data
        labels.iloc[-self.lookahead_periods :] = np.nan

        logger.info(
            f"Generated {len(labels)} labels: "
            f"BUY={sum(labels == 1)}, "
            f"SELL={sum(labels == -1)}, "
            f"HOLD={sum(labels == 0)}"
        )

        return labels

    def get_label_distribution(self, labels: pd.Series) -> Dict:
        """
        Get distribution of labels.

        Args:
            labels: Label series

        Returns:
            Dictionary with label counts and percentages
        """
        total = len(labels)
        buy_count = sum(labels == 1)
        sell_count = sum(labels == -1)
        hold_count = sum(labels == 0)

        return {
            "total": total,
            "buy": buy_count,
            "sell": sell_count,
            "hold": hold_count,
            "buy_pct": buy_count / total * 100 if total > 0 else 0,
            "sell_pct": sell_count / total * 100 if total > 0 else 0,
            "hold_pct": hold_count / total * 100 if total > 0 else 0,
        }
