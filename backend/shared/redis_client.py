"""
Redis client utilities for pub/sub messaging and caching.
Provides connection management, channel publishing/subscribing, and cache operations.
"""

import json
import logging
from typing import Any, Callable, Dict, Optional

import redis

from shared.config import settings

logger = logging.getLogger(__name__)

# Global connection pool singleton
_redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_client() -> redis.Redis:
    """
    Get Redis client with connection pooling.

    Uses singleton pattern for connection pool to reuse connections
    across the application.

    Returns:
        Redis client instance
    """
    global _redis_pool

    if _redis_pool is None:
        logger.info(f"Initializing Redis connection pool to {settings.redis_url}")
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,  # Automatically decode bytes to strings
            max_connections=20
        )

    return redis.Redis(connection_pool=_redis_pool)


# Channel naming conventions
class RedisChannels:
    """Redis channel naming conventions for pub/sub."""

    @staticmethod
    def ticks(instrument: str) -> str:
        """Channel for tick-level price updates."""
        return f"forex:ticks:{instrument}"

    @staticmethod
    def candles(instrument: str, timeframe: str) -> str:
        """Channel for completed candle events."""
        return f"forex:candles:{instrument}:{timeframe}"

    @staticmethod
    def signals(instrument: str) -> str:
        """Channel for trading signals."""
        return f"forex:signals:{instrument}"

    @staticmethod
    def all_ticks() -> str:
        """Pattern to subscribe to all tick channels."""
        return "forex:ticks:*"

    @staticmethod
    def all_candles() -> str:
        """Pattern to subscribe to all candle channels."""
        return "forex:candles:*"


# Cache key naming conventions
class RedisCacheKeys:
    """Redis cache key naming conventions."""

    @staticmethod
    def latest_price(instrument: str) -> str:
        """Cache key for latest price data."""
        return f"forex:price:{instrument}"

    @staticmethod
    def stream_status() -> str:
        """Cache key for streaming health status."""
        return "forex:stream:status"

    @staticmethod
    def stream_heartbeat(instrument: str) -> str:
        """Cache key for last heartbeat timestamp."""
        return f"forex:stream:heartbeat:{instrument}"


def publish_message(channel: str, data: Dict[str, Any]) -> None:
    """
    Publish message to Redis pub/sub channel.

    Automatically serializes data to JSON before publishing.

    Args:
        channel: Redis channel name
        data: Message data (will be JSON serialized)

    Example:
        publish_message(
            RedisChannels.ticks("EUR_USD"),
            {"timestamp": "2024-12-29T10:30:00Z", "bid": 1.10523, "ask": 1.10525}
        )
    """
    try:
        client = get_redis_client()
        message_json = json.dumps(data)
        client.publish(channel, message_json)
        logger.debug(f"Published to {channel}: {data}")
    except Exception as e:
        logger.error(f"Failed to publish to {channel}: {e}")
        raise


def subscribe_to_channel(
    channel: str,
    callback: Callable[[Dict[str, Any]], None],
    pattern: bool = False
) -> None:
    """
    Subscribe to Redis channel and process messages with callback.

    This is a blocking operation that listens for messages indefinitely.

    Args:
        channel: Channel name or pattern (if pattern=True)
        callback: Function to call for each message (receives parsed JSON dict)
        pattern: If True, treat channel as a pattern (use psubscribe)

    Example:
        def handle_tick(tick_data):
            print(f"Received tick: {tick_data}")

        subscribe_to_channel("forex:ticks:EUR_USD", handle_tick)
    """
    client = get_redis_client()
    pubsub = client.pubsub()

    try:
        if pattern:
            pubsub.psubscribe(channel)
            logger.info(f"Subscribed to pattern: {channel}")
        else:
            pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")

        for message in pubsub.listen():
            # Skip subscription confirmation messages
            if message['type'] in ['subscribe', 'psubscribe']:
                continue

            # Process actual messages
            if message['type'] in ['message', 'pmessage']:
                try:
                    data = json.loads(message['data'])
                    callback(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message from {channel}: {e}")
                except Exception as e:
                    logger.error(f"Error in callback for {channel}: {e}")

    except KeyboardInterrupt:
        logger.info("Subscription interrupted by user")
    except Exception as e:
        logger.error(f"Error in subscription to {channel}: {e}")
        raise
    finally:
        pubsub.close()


def cache_latest_price(instrument: str, price_data: Dict[str, Any], ttl: int = 300) -> None:
    """
    Cache latest price data in Redis.

    Uses SET with TTL (time-to-live) to automatically expire stale data.

    Args:
        instrument: Trading instrument (e.g., "EUR_USD")
        price_data: Price data to cache (will be JSON serialized)
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)

    Example:
        cache_latest_price("EUR_USD", {
            "timestamp": "2024-12-29T10:30:00Z",
            "bid": 1.10523,
            "ask": 1.10525,
            "mid": 1.10524
        })
    """
    try:
        client = get_redis_client()
        key = RedisCacheKeys.latest_price(instrument)
        value = json.dumps(price_data)
        client.setex(key, ttl, value)
        logger.debug(f"Cached latest price for {instrument} (TTL={ttl}s)")
    except Exception as e:
        logger.error(f"Failed to cache price for {instrument}: {e}")
        # Don't raise - caching failure should not break the system


def get_cached_price(instrument: str) -> Optional[Dict[str, Any]]:
    """
    Get cached price data from Redis.

    Args:
        instrument: Trading instrument (e.g., "EUR_USD")

    Returns:
        Price data dict if found, None if not found or expired
    """
    try:
        client = get_redis_client()
        key = RedisCacheKeys.latest_price(instrument)
        value = client.get(key)

        if value is None:
            return None

        return json.loads(value)
    except Exception as e:
        logger.error(f"Failed to get cached price for {instrument}: {e}")
        return None


def update_stream_status(status: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Update streaming service status in Redis.

    Args:
        status: Status string ("connected", "disconnected", "error")
        details: Optional additional details
    """
    try:
        client = get_redis_client()
        key = RedisCacheKeys.stream_status()

        status_data = {
            "status": status,
            "timestamp": None,  # Will be set by caller
            "details": details or {}
        }

        client.setex(key, 3600, json.dumps(status_data))  # 1-hour TTL
        logger.info(f"Updated stream status: {status}")
    except Exception as e:
        logger.error(f"Failed to update stream status: {e}")


def test_pubsub():
    """
    Test Redis pub/sub functionality.

    Publishes a test message and verifies it can be received.
    """
    import threading
    import time

    test_channel = "test:channel"
    test_message = {"test": "message", "timestamp": str(time.time())}

    # Flag to track if message was received
    received = []

    def subscriber():
        def callback(data):
            print(f"✓ Received: {data}")
            received.append(data)

        subscribe_to_channel(test_channel, callback)

    # Start subscriber in background thread
    sub_thread = threading.Thread(target=subscriber, daemon=True)
    sub_thread.start()

    # Give subscriber time to connect
    time.sleep(1)

    # Publish test message
    print(f"Publishing test message to {test_channel}")
    publish_message(test_channel, test_message)

    # Wait for message
    time.sleep(1)

    if received:
        print("✓ Pub/sub test passed!")
        return True
    else:
        print("✗ Pub/sub test failed - message not received")
        return False


if __name__ == "__main__":
    # Run test if executed directly
    logging.basicConfig(level=logging.INFO)
    test_pubsub()
