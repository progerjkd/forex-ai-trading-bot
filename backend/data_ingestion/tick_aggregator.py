"""
Tick aggregator for converting tick-level price data into OHLCV candles.
Subscribes to Redis tick stream and aggregates into M1 and M5 timeframes.
"""

import json
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from shared.config import settings
from shared.database import SessionLocal
from shared.models import MarketData
from shared.redis_client import (
    RedisChannels,
    get_redis_client,
    publish_message,
)

logger = logging.getLogger(__name__)


class TimeWindow:
    """
    Time-based window for aggregating ticks into OHLCV candles.

    Maintains a buffer of ticks and calculates OHLCV when the window closes.
    """

    def __init__(self, instrument: str, timeframe: str):
        """
        Initialize time window.

        Args:
            instrument: Trading instrument (e.g., "EUR_USD")
            timeframe: Timeframe (e.g., "M1", "M5")
        """
        self.instrument = instrument
        self.timeframe = timeframe
        self.ticks: List[Dict] = []
        self.window_start: Optional[datetime] = None

    def add_tick(self, tick: Dict):
        """
        Add tick to window.

        Args:
            tick: Tick data with timestamp, bid, ask, mid
        """
        tick_time = datetime.fromisoformat(tick["timestamp"])

        # Initialize window start on first tick
        if self.window_start is None:
            self.window_start = self.floor_to_timeframe(tick_time)

        self.ticks.append(tick)

    def should_close(self, current_time: datetime) -> bool:
        """
        Check if window should close based on current time.

        Args:
            current_time: Current timestamp

        Returns:
            True if window should close, False otherwise
        """
        if not self.window_start or not self.ticks:
            return False

        # Get timeframe duration in minutes
        minutes = int(self.timeframe[1:])  # "M1" -> 1, "M5" -> 5
        window_end = self.window_start + timedelta(minutes=minutes)

        # Close if current time is past window end
        return current_time >= window_end

    def get_ohlcv(self) -> Dict:
        """
        Calculate OHLCV from ticks in window.

        Returns:
            Dict with OHLCV data
        """
        if not self.ticks:
            return None

        # Extract mid prices from all ticks
        mid_prices = [tick["mid"] for tick in self.ticks if tick.get("mid")]

        if not mid_prices:
            return None

        return {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "timestamp": self.window_start,
            "open": mid_prices[0],
            "high": max(mid_prices),
            "low": min(mid_prices),
            "close": mid_prices[-1],
            "volume": len(self.ticks),  # Tick count as volume
        }

    def reset(self):
        """Reset window for next period."""
        self.ticks = []
        self.window_start = None

    def floor_to_timeframe(self, dt: datetime) -> datetime:
        """
        Floor datetime to timeframe boundary.

        Examples:
            M1: 10:30:45 -> 10:30:00
            M5: 10:32:45 -> 10:30:00 (floor to nearest 5-minute mark)

        Args:
            dt: Datetime to floor

        Returns:
            Floored datetime
        """
        minutes = int(self.timeframe[1:])

        # Floor to minute boundary
        floored = dt.replace(second=0, microsecond=0)

        # For M5, floor to nearest 5-minute mark
        if minutes > 1:
            floored_minute = (floored.minute // minutes) * minutes
            floored = floored.replace(minute=floored_minute)

        return floored


class TickAggregator:
    """
    Aggregates tick-level data into OHLCV candles.

    Subscribes to Redis tick stream, maintains time windows for each
    instrument and timeframe, and stores completed candles in TimescaleDB.
    """

    def __init__(self):
        """Initialize tick aggregator."""
        self.redis_client = get_redis_client()
        self.db: Session = SessionLocal()
        self.running = False

        # Parse timeframes from config
        timeframes = settings.tick_aggregation_timeframes.split(",")
        self.timeframes = [tf.strip() for tf in timeframes]

        # Initialize windows: {instrument: {timeframe: TimeWindow}}
        self.windows: Dict[str, Dict[str, TimeWindow]] = {}

        # Stats
        self.ticks_processed = 0
        self.candles_stored = 0

        logger.info(f"Initialized tick aggregator for timeframes: {self.timeframes}")

    def start(self):
        """
        Start aggregating ticks.

        Subscribes to Redis tick stream and processes messages indefinitely.
        """
        self.running = True
        logger.info("Starting tick aggregation...")

        try:
            # Subscribe to all tick channels
            pubsub = self.redis_client.pubsub()
            pattern = RedisChannels.all_ticks()
            pubsub.psubscribe(pattern)

            logger.info(f"Subscribed to pattern: {pattern}")

            for message in pubsub.listen():
                if not self.running:
                    logger.info("Aggregation stopped by user")
                    break

                # Skip subscription confirmation
                if message["type"] == "psubscribe":
                    continue

                # Process tick message
                if message["type"] == "pmessage":
                    try:
                        tick = json.loads(message["data"])
                        self.handle_tick(tick)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode tick message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing tick: {e}")

        except KeyboardInterrupt:
            logger.info("Aggregation interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in aggregation: {e}")
            raise
        finally:
            self.cleanup()

    def stop(self):
        """Stop aggregation gracefully."""
        logger.info("Stopping tick aggregator...")
        self.running = False

    def handle_tick(self, tick: Dict):
        """
        Process incoming tick and update windows.

        Args:
            tick: Tick data from Redis
        """
        try:
            instrument = tick.get("instrument")
            if not instrument:
                logger.warning("Tick missing instrument field")
                return

            tick_time = datetime.fromisoformat(tick["timestamp"])

            # Process each timeframe
            for timeframe in self.timeframes:
                # Get or create window
                window = self.get_or_create_window(instrument, timeframe)

                # Check if window should close before adding new tick
                if window.should_close(tick_time):
                    # Close current window and create candle
                    candle = window.get_ohlcv()
                    if candle:
                        self.store_candle(candle)
                        self.publish_candle(candle)

                    # Reset window for next period
                    window.reset()

                # Add tick to window
                window.add_tick(tick)

            self.ticks_processed += 1

            # Log progress
            if self.ticks_processed % 500 == 0:
                logger.info(
                    f"Processed {self.ticks_processed} ticks | "
                    f"Stored {self.candles_stored} candles"
                )

        except Exception as e:
            logger.error(f"Error handling tick: {e}")
            logger.debug(f"Tick data: {tick}")

    def get_or_create_window(self, instrument: str, timeframe: str) -> TimeWindow:
        """
        Get existing window or create new one.

        Args:
            instrument: Trading instrument
            timeframe: Candle timeframe

        Returns:
            TimeWindow instance
        """
        if instrument not in self.windows:
            self.windows[instrument] = {}

        if timeframe not in self.windows[instrument]:
            self.windows[instrument][timeframe] = TimeWindow(instrument, timeframe)

        return self.windows[instrument][timeframe]

    def store_candle(self, candle: Dict):
        """
        Store completed candle in TimescaleDB.

        Args:
            candle: Candle data with OHLCV
        """
        try:
            # Create MarketData record
            market_data = MarketData(
                instrument=candle["instrument"],
                timeframe=candle["timeframe"],
                timestamp=candle["timestamp"],
                open=candle["open"],
                high=candle["high"],
                low=candle["low"],
                close=candle["close"],
                volume=candle["volume"],
            )

            # Add and commit (with duplicate handling)
            self.db.add(market_data)

            try:
                self.db.commit()
                self.candles_stored += 1

                logger.debug(
                    f"Stored candle: {candle['instrument']} {candle['timeframe']} "
                    f"@ {candle['timestamp']} | OHLC: {candle['open']:.5f} "
                    f"{candle['high']:.5f} {candle['low']:.5f} {candle['close']:.5f}"
                )

            except Exception as e:
                self.db.rollback()
                # Check if it's a duplicate (unique constraint violation)
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    logger.debug(f"Candle already exists (duplicate): {candle['timestamp']}")
                else:
                    logger.error(f"Failed to store candle: {e}")

        except Exception as e:
            logger.error(f"Error creating candle record: {e}")

    def publish_candle(self, candle: Dict):
        """
        Publish completed candle event to Redis.

        Args:
            candle: Candle data
        """
        try:
            channel = RedisChannels.candles(candle["instrument"], candle["timeframe"])

            # Format candle for publishing (convert timestamp to string)
            candle_event = {
                **candle,
                "timestamp": candle["timestamp"].isoformat(),
                "type": "candle",
            }

            publish_message(channel, candle_event)

            logger.debug(f"Published candle to {channel}")

        except Exception as e:
            logger.error(f"Failed to publish candle: {e}")
            # Don't raise - publishing failure shouldn't break aggregation

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up aggregator resources...")

        # Close any remaining windows and store final candles
        for instrument in self.windows:
            for timeframe in self.windows[instrument]:
                window = self.windows[instrument][timeframe]
                if window.ticks:
                    candle = window.get_ohlcv()
                    if candle:
                        logger.info(f"Storing final candle for {instrument} {timeframe}")
                        self.store_candle(candle)

        # Close database session
        if self.db:
            self.db.close()

        logger.info(
            f"Aggregation complete. Processed {self.ticks_processed} ticks, "
            f"stored {self.candles_stored} candles"
        )


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point for tick aggregator service."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("=" * 70)
    logger.info("TICK AGGREGATOR SERVICE")
    logger.info("=" * 70)

    logger.info(f"Timeframes: {settings.tick_aggregation_timeframes}")
    logger.info("")

    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create and start aggregator
    aggregator = TickAggregator()

    try:
        logger.info("Starting aggregation... (Press Ctrl+C to stop)")
        aggregator.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        aggregator.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
