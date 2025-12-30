"""
Real-time OANDA price streaming client with Redis pub/sub broadcasting.
Establishes HTTP streaming connection and publishes tick updates to Redis.
"""

import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_ingestion.oanda_client import OANDAClient
from shared.config import settings
from shared.redis_client import (
    RedisChannels,
    RedisCacheKeys,
    cache_latest_price,
    publish_message,
    update_stream_status,
)

logger = logging.getLogger(__name__)


class StreamingClient:
    """
    Real-time OANDA price streaming client.

    Establishes persistent HTTP streaming connection to OANDA and publishes
    tick-level price updates to Redis pub/sub channels for downstream processing.
    """

    def __init__(self, instruments: List[str]):
        """
        Initialize streaming client.

        Args:
            instruments: List of instruments to stream (OANDA format: EUR_USD)
        """
        self.instruments = instruments
        self.oanda_client = OANDAClient()
        self.running = False
        self.tick_count = 0
        self.heartbeat_count = 0

        logger.info(f"Initialized streaming client for {len(instruments)} instruments")

    def start(self):
        """
        Start streaming price updates.

        This is a blocking call that runs until interrupted or an error occurs.
        Publishes each tick to Redis and caches the latest price.
        """
        self.running = True
        logger.info(f"Starting price stream for: {', '.join(self.instruments)}")

        # Update stream status to connected
        update_stream_status("connecting", {"instruments": self.instruments})

        try:
            # Start streaming - this is a blocking iterator
            for message in self.oanda_client.stream_pricing(self.instruments):
                if not self.running:
                    logger.info("Streaming stopped by user")
                    break

                # Process message based on type
                if message.get("type") == "PRICE":
                    self.process_tick(message)
                elif message.get("type") == "HEARTBEAT":
                    self.handle_heartbeat(message)

        except KeyboardInterrupt:
            logger.info("Streaming interrupted by user (Ctrl+C)")
            self.stop()
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            update_stream_status("error", {"error": str(e)})
            raise
        finally:
            logger.info(f"Stream ended. Processed {self.tick_count} ticks, {self.heartbeat_count} heartbeats")
            update_stream_status("disconnected")

    def stop(self):
        """Stop streaming gracefully."""
        logger.info("Stopping streaming client...")
        self.running = False

    def process_tick(self, tick_data: Dict):
        """
        Process incoming tick (price update) and publish to Redis.

        Args:
            tick_data: Raw tick data from OANDA
        """
        try:
            # Normalize tick to our format
            tick = self.normalize_tick(tick_data)

            # Publish to Redis channel
            channel = RedisChannels.ticks(tick["instrument"])
            publish_message(channel, tick)

            # Cache latest price
            cache_latest_price(tick["instrument"], tick)

            # Increment counter
            self.tick_count += 1

            # Log every 100 ticks
            if self.tick_count % 100 == 0:
                logger.info(
                    f"Processed {self.tick_count} ticks | "
                    f"Latest: {tick['instrument']} @ {tick['mid']:.5f}"
                )

            # Update stream status periodically
            if self.tick_count == 1 or self.tick_count % 500 == 0:
                update_stream_status("connected", {
                    "instruments": self.instruments,
                    "ticks_processed": self.tick_count,
                    "heartbeats_received": self.heartbeat_count
                })

        except Exception as e:
            logger.error(f"Error processing tick: {e}")
            logger.debug(f"Tick data: {tick_data}")

    def handle_heartbeat(self, heartbeat_data: Dict):
        """
        Handle heartbeat message (keep-alive signal).

        Args:
            heartbeat_data: Heartbeat message from OANDA
        """
        self.heartbeat_count += 1

        # Log heartbeats less frequently
        if self.heartbeat_count % 10 == 0:
            logger.debug(f"Heartbeat received ({self.heartbeat_count} total)")

    def normalize_tick(self, tick_data: Dict) -> Dict:
        """
        Normalize OANDA tick data to our standard format.

        Args:
            tick_data: Raw OANDA tick message

        Returns:
            Normalized tick dictionary

        Example OANDA tick format:
        {
            "type": "PRICE",
            "time": "2024-12-29T10:30:15.234567890Z",
            "bids": [{"price": "1.10523", "liquidity": 10000000}],
            "asks": [{"price": "1.10525", "liquidity": 10000000}],
            "closeoutBid": "1.10523",
            "closeoutAsk": "1.10525",
            "status": "tradeable",
            "tradeable": true,
            "instrument": "EUR_USD"
        }
        """
        # Extract bid/ask prices
        bids = tick_data.get("bids", [])
        asks = tick_data.get("asks", [])

        bid = float(bids[0]["price"]) if bids else 0.0
        ask = float(asks[0]["price"]) if asks else 0.0
        mid = (bid + ask) / 2 if (bid and ask) else 0.0
        spread = ask - bid if (bid and ask) else 0.0

        # Parse timestamp
        timestamp_str = tick_data.get("time", "")
        timestamp = self.parse_oanda_timestamp(timestamp_str)

        return {
            "type": "tick",
            "instrument": tick_data.get("instrument"),
            "timestamp": timestamp.isoformat() if timestamp else None,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread": spread,
            "status": tick_data.get("status"),
            "tradeable": tick_data.get("tradeable", False),
        }

    @staticmethod
    def parse_oanda_timestamp(timestamp_str: str) -> datetime:
        """
        Parse OANDA timestamp to datetime object.

        OANDA uses RFC3339 format with nanosecond precision.

        Args:
            timestamp_str: Timestamp string (e.g., "2024-12-29T10:30:15.234567890Z")

        Returns:
            datetime object
        """
        # OANDA timestamps have nanosecond precision, but Python datetime only supports microseconds
        # Truncate to microseconds: "2024-12-29T10:30:15.234567890Z" -> "2024-12-29T10:30:15.234567Z"
        if "." in timestamp_str:
            parts = timestamp_str.split(".")
            fractional = parts[1].rstrip("Z")[:6]  # Take first 6 digits (microseconds)
            timestamp_str = f"{parts[0]}.{fractional}Z"

        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point for streaming service."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("=" * 70)
    logger.info("OANDA STREAMING CLIENT")
    logger.info("=" * 70)

    # Get instruments from settings
    instruments = settings.get_trading_pairs_list()
    instruments = [pair.replace("/", "_") for pair in instruments]

    logger.info(f"Configured instruments: {', '.join(instruments)}")
    logger.info(f"Environment: {settings.oanda_environment}")
    logger.info(f"Streaming enabled: {settings.streaming_enabled}")
    logger.info("")

    if not settings.streaming_enabled:
        logger.warning("Streaming is disabled in configuration. Exiting.")
        return

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create and start streaming client
    client = StreamingClient(instruments)

    try:
        logger.info("Starting streaming... (Press Ctrl+C to stop)")
        client.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        client.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
