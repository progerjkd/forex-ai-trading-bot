"""
Redis subscriber that broadcasts candle events to WebSocket clients.

Subscribes to Redis candle channels and forwards updates to all
connected WebSocket clients via the connection manager.
"""

import asyncio
import json
import logging
from typing import Dict

from api.websocket_manager import manager
from shared.redis_client import RedisChannels, get_redis_client

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    """
    Background service that subscribes to Redis and broadcasts to WebSocket clients.

    Runs as an asyncio background task, listening for candle events from Redis
    and forwarding them to WebSocket clients based on their subscriptions.
    """

    def __init__(self):
        """Initialize broadcaster."""
        self.redis_client = get_redis_client()
        self.running = False
        self.task = None
        self.loop = None  # Store event loop reference

        # Stats
        self.messages_received = 0
        self.messages_broadcast = 0

    async def start(self):
        """
        Start the broadcaster background task.

        Creates an asyncio task that runs the Redis subscription loop.
        """
        if self.running:
            logger.warning("Broadcaster already running")
            return

        self.running = True
        self.loop = asyncio.get_event_loop()  # Store loop reference
        self.task = asyncio.create_task(self._subscribe_loop())
        logger.info("WebSocket broadcaster started")

    async def stop(self):
        """Stop the broadcaster gracefully."""
        if not self.running:
            return

        logger.info("Stopping WebSocket broadcaster...")
        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("Broadcaster task cancelled")

    async def _subscribe_loop(self):
        """
        Main subscription loop (runs in background).

        Subscribes to Redis candle channels and processes incoming messages.
        This runs in a separate thread pool executor since redis-py is synchronous.
        """
        try:
            # Run Redis subscription in thread pool (it's blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._redis_subscribe)

        except asyncio.CancelledError:
            logger.info("Subscription loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in subscription loop: {e}")
            import traceback

            traceback.print_exc()

    def _redis_subscribe(self):
        """
        Synchronous Redis subscription (runs in thread pool).

        Subscribes to forex:candles:* and forex:signals:* patterns.
        """
        try:
            pubsub = self.redis_client.pubsub()
            candles_pattern = RedisChannels.all_candles()
            signals_pattern = "forex:signals:*"

            pubsub.psubscribe(candles_pattern)
            pubsub.psubscribe(signals_pattern)

            logger.info(f"Subscribed to Redis patterns: {candles_pattern}, {signals_pattern}")

            for message in pubsub.listen():
                if not self.running:
                    logger.info("Subscription stopped by broadcaster")
                    break

                # Skip subscription confirmation
                if message["type"] == "psubscribe":
                    continue

                # Process messages (candles or signals)
                if message["type"] == "pmessage":
                    try:
                        # Parse message data
                        data = json.loads(message["data"])
                        channel = message["channel"].decode("utf-8")
                        self.messages_received += 1

                        # Determine message type from channel
                        if "candles" in channel:
                            # Schedule candle broadcast
                            asyncio.run_coroutine_threadsafe(
                                self._broadcast_candle(data), self.loop
                            )
                        elif "signals" in channel:
                            # Schedule signal broadcast
                            asyncio.run_coroutine_threadsafe(
                                self._broadcast_signal(data), self.loop
                            )

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

        except Exception as e:
            logger.error(f"Redis subscription error: {e}")
            raise
        finally:
            pubsub.close()

    async def _broadcast_candle(self, candle: Dict):
        """
        Broadcast candle to subscribed WebSocket clients.

        Args:
            candle: Candle data from Redis
        """
        try:
            instrument = candle.get("instrument")
            if not instrument:
                logger.warning("Candle missing instrument field")
                return

            # Broadcast to clients subscribed to this instrument
            await manager.broadcast_to_subscribers(instrument, candle)
            self.messages_broadcast += 1

            # Log every 10th broadcast
            if self.messages_broadcast % 10 == 0:
                logger.info(
                    f"Broadcast {self.messages_broadcast} candles | "
                    f"Received: {self.messages_received} | "
                    f"Active connections: {len(manager.active_connections)}"
                )

        except Exception as e:
            logger.error(f"Error broadcasting candle: {e}")

    async def _broadcast_signal(self, signal_data: Dict):
        """
        Broadcast signal to subscribed WebSocket clients.

        Args:
            signal_data: Signal data from Redis

        """
        try:
            instrument = signal_data.get("instrument")
            if not instrument:
                logger.warning("Signal missing instrument field")
                return

            # Wrap signal data with type
            message = {"type": "signal", "data": signal_data}

            # Broadcast to clients subscribed to this instrument
            await manager.broadcast_to_subscribers(instrument, message)

            logger.info(
                f"Broadcast signal: {signal_data.get('signal_type')} "
                f"for {instrument} (confidence={signal_data.get('confidence', 0):.3f})"
            )

        except Exception as e:
            logger.error(f"Error broadcasting signal: {e}")

    def get_stats(self) -> dict:
        """
        Get broadcaster statistics.

        Returns:
            Dict with broadcaster stats
        """
        return {
            "running": self.running,
            "messages_received": self.messages_received,
            "messages_broadcast": self.messages_broadcast,
        }


# Global broadcaster instance
broadcaster = WebSocketBroadcaster()
