"""
Real-time signal generation service.

Subscribes to Redis candle events, runs ML inference, and publishes signals.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional

from shared.config import settings
from shared.database import SessionLocal
from shared.redis_client import get_redis_client, subscribe_to_channel
from strategy_engine.features import FeatureService
from strategy_engine.models import Predictor

logger = logging.getLogger(__name__)


class SignalGenerationService:
    """
    Real-time signal generation from candle events.

    Subscribes to Redis candle channels, generates features,
    runs ML prediction, and publishes signals.
    """

    def __init__(
        self,
        instruments: list[str] = None,
        timeframe: str = "M5",
        model_version: str = "v1",
    ):
        """
        Initialize signal generation service.

        Args:
            instruments: List of instruments to monitor (default from settings)
            timeframe: Timeframe to subscribe to (default M5)
            model_version: ML model version to use (default v1)
        """
        self.instruments = instruments or settings.get_trading_pairs_list()
        self.timeframe = timeframe
        self.model_version = model_version

        self.running = False
        self.redis_client = get_redis_client()

        # Initialize services
        self.feature_service = FeatureService()
        self.predictors = {}  # {instrument: Predictor}

        # Stats
        self.candles_processed = 0
        self.signals_generated = 0
        self.errors = 0

        logger.info(
            f"Initialized SignalGenerationService for {len(self.instruments)} instruments "
            f"on {timeframe} timeframe"
        )

    def _load_predictors(self):
        """Load ML models for all instruments."""
        for instrument in self.instruments:
            try:
                predictor = Predictor(
                    instrument=instrument, model_version=self.model_version
                )
                self.predictors[instrument] = predictor
                logger.info(f"Loaded model for {instrument}")
            except Exception as e:
                logger.error(f"Failed to load model for {instrument}: {e}")
                # Continue with other instruments

    def _handle_candle_event(self, message: Dict):
        """
        Process a candle event and generate signal if needed.

        Args:
            message: Candle data from Redis
        """
        try:
            # Extract candle data
            instrument = message.get("instrument")
            timeframe = message.get("timeframe")
            timestamp_str = message.get("timestamp")
            close_price = float(message.get("close"))

            if not all([instrument, timeframe, timestamp_str, close_price]):
                logger.warning(f"Incomplete candle data: {message}")
                return

            # Only process our target timeframe
            if timeframe != self.timeframe:
                return

            # Check if we have a predictor for this instrument
            if instrument not in self.predictors:
                logger.debug(f"No predictor for {instrument}, skipping")
                return

            self.candles_processed += 1

            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            logger.info(
                f"Processing candle: {instrument} {timeframe} "
                f"at {timestamp} (close={close_price})"
            )

            # Generate features
            features = self.feature_service.get_latest_features(
                instrument, timeframes=["M1", "M5"]  # Use available timeframes
            )

            if features.empty:
                logger.warning(f"No features generated for {instrument}")
                return

            # Get predictor
            predictor = self.predictors[instrument]

            # Run prediction
            prediction = predictor.predict(
                features=features, entry_price=close_price, timestamp=timestamp
            )

            logger.info(
                f"Prediction for {instrument}: {prediction['signal']} "
                f"(confidence={prediction['confidence']:.3f}, "
                f"threshold={predictor.confidence_threshold})"
            )

            # Create signal if confidence threshold met
            if prediction["meets_threshold"]:
                # Store in database
                signal = predictor.create_signal(
                    prediction, indicators_snapshot=features.to_dict("records")[0]
                )

                self.signals_generated += 1

                logger.info(
                    f"✅ Signal created: {signal.signal_type} for {instrument} "
                    f"at {signal.entry_price} (confidence={signal.confidence:.3f})"
                )

                # Publish to Redis for WebSocket broadcast
                self._publish_signal(signal)

            # Log progress
            if self.candles_processed % 10 == 0:
                logger.info(
                    f"Stats: Processed {self.candles_processed} candles | "
                    f"Generated {self.signals_generated} signals | "
                    f"Errors {self.errors}"
                )

        except Exception as e:
            self.errors += 1
            logger.error(f"Error processing candle: {e}")
            import traceback

            traceback.print_exc()

    def _publish_signal(self, signal):
        """
        Publish signal to Redis for WebSocket broadcast.

        Args:
            signal: Signal model instance
        """
        try:
            message = {
                "type": "signal",
                "instrument": signal.instrument,
                "timestamp": signal.timestamp.isoformat(),
                "signal_type": signal.signal_type.value,
                "confidence": signal.confidence,
                "entry_price": signal.entry_price,
                "source": signal.source,
                "model_version": signal.model_version,
            }

            channel = f"forex:signals:{signal.instrument}"
            self.redis_client.publish(channel, json.dumps(message))

            logger.debug(f"Published signal to {channel}")

        except Exception as e:
            logger.error(f"Failed to publish signal to Redis: {e}")
            # Don't raise - this is not critical

    def start(self):
        """Start the signal generation service."""
        logger.info("Starting Signal Generation Service...")

        # Load ML models
        self._load_predictors()

        if not self.predictors:
            logger.error("No predictors loaded - cannot start service")
            return

        self.running = True

        # Subscribe to candle events (pattern subscription for all instruments)
        channel_pattern = "forex:candles:*"

        logger.info(f"Subscribing to Redis channel pattern: {channel_pattern}")

        try:
            subscribe_to_channel(
                channel_pattern, callback=self._handle_candle_event, pattern=True
            )
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error in subscription loop: {e}")
            raise
        finally:
            self.stop()

    def stop(self):
        """Stop the signal generation service."""
        if not self.running:
            return

        logger.info("Stopping Signal Generation Service...")
        self.running = False

        # Log final stats
        logger.info(
            f"Final stats: Processed {self.candles_processed} candles | "
            f"Generated {self.signals_generated} signals | "
            f"Errors {self.errors}"
        )

        logger.info("Signal Generation Service stopped")

    def get_stats(self) -> Dict:
        """Get service statistics."""
        return {
            "running": self.running,
            "instruments": self.instruments,
            "timeframe": self.timeframe,
            "candles_processed": self.candles_processed,
            "signals_generated": self.signals_generated,
            "errors": self.errors,
            "models_loaded": len(self.predictors),
        }
