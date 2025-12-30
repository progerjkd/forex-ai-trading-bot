"""
Real-time prediction service for forex signals.

Loads trained models and generates predictions with confidence scoring.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from sqlalchemy.orm import Session

from shared.config import settings
from shared.database import SessionLocal
from shared.models import Signal

from .model_store import ModelStore

logger = logging.getLogger(__name__)


class Predictor:
    """
    Real-time prediction service for forex signal generation.

    Loads trained models and generates predictions with confidence scores.
    """

    # Map numeric predictions to signal types
    SIGNAL_MAP = {
        1: "BUY",
        0: "HOLD",
        -1: "SELL",
    }

    def __init__(
        self,
        instrument: str,
        model_version: str = "v1",
        confidence_threshold: Optional[float] = None,
        db: Optional[Session] = None,
    ):
        """
        Initialize predictor.

        Args:
            instrument: Trading pair (e.g., "EUR_USD")
            model_version: Model version to load (default "v1")
            confidence_threshold: Min confidence for signals (default from settings)
            db: Optional database session
        """
        self.instrument = instrument
        self.model_version = model_version
        self.confidence_threshold = (
            confidence_threshold or settings.ml_confidence_threshold
        )
        self.db = db or SessionLocal()
        self._owns_session = db is None

        # Load model
        self.model_store = ModelStore()
        model_path = self.model_store.get_latest_model(instrument, model_version)

        if not model_path:
            raise ValueError(
                f"No model found for {instrument} version {model_version}"
            )

        self.model, self.metadata = self.model_store.load(model_path)
        self.feature_columns = self.metadata.get("feature_columns", [])

        logger.info(
            f"Loaded model for {instrument} (version {model_version}, "
            f"{len(self.feature_columns)} features)"
        )

    def __del__(self):
        """Clean up database session."""
        if self._owns_session and self.db:
            self.db.close()

    def predict(
        self,
        features: pd.DataFrame,
        entry_price: float,
        timestamp: Optional[datetime] = None,
    ) -> Dict:
        """
        Generate prediction from features.

        Args:
            features: Feature vector (1 × N DataFrame)
            entry_price: Current market price
            timestamp: Prediction timestamp (default: now)

        Returns:
            Dictionary with prediction results
        """
        timestamp = timestamp or datetime.utcnow()

        # Ensure features match training columns
        features = features[self.feature_columns]

        # Get prediction and probabilities
        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]

        # Map probabilities to class labels
        class_labels = self.model.classes_  # [-1, 0, 1]
        prob_dict = {
            self.SIGNAL_MAP[int(label)]: float(prob)
            for label, prob in zip(class_labels, probabilities)
        }

        # Get confidence (max probability)
        confidence = float(probabilities.max())

        signal_type = self.SIGNAL_MAP[int(prediction)]

        result = {
            "signal": signal_type,
            "confidence": confidence,
            "probabilities": prob_dict,
            "prediction_raw": int(prediction),
            "timestamp": timestamp,
            "entry_price": entry_price,
            "meets_threshold": confidence >= self.confidence_threshold,
        }

        logger.info(
            f"Prediction: {signal_type} (confidence={confidence:.3f}, "
            f"threshold={self.confidence_threshold})"
        )

        return result

    def create_signal(
        self,
        prediction_result: Dict,
        indicators_snapshot: Optional[Dict] = None,
    ) -> Optional[Signal]:
        """
        Create Signal record if confidence meets threshold.

        Args:
            prediction_result: Result from predict()
            indicators_snapshot: JSONB snapshot of features

        Returns:
            Signal object if created, None otherwise
        """
        if not prediction_result["meets_threshold"]:
            logger.info(
                "Prediction does not meet confidence threshold, skipping signal"
            )
            return None

        signal = Signal(
            instrument=self.instrument,
            timestamp=prediction_result["timestamp"],
            signal_type=prediction_result["signal"],
            confidence=prediction_result["confidence"],
            source=f"ml_random_forest_{self.model_version}",
            entry_price=prediction_result["entry_price"],
            indicators=indicators_snapshot or {},
            model_version=self.model_version,
            executed=False,
        )

        self.db.add(signal)
        self.db.commit()

        logger.info(f"Signal created: {signal.signal_type} at {signal.entry_price}")

        return signal
