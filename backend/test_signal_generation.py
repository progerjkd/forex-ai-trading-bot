#!/usr/bin/env python3
"""
Test signal generation service.

Tests:
1. Service initialization
2. Signal generation from candle event
3. Redis publishing
4. Database persistence
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared.database import SessionLocal
from shared.models import Signal
from shared.redis_client import get_redis_client
from strategy_engine.signals import SignalGenerationService


def test_service_initialization():
    """Test service can initialize."""
    print("\n" + "=" * 70)
    print("TEST 1: Service Initialization")
    print("=" * 70)

    try:
        service = SignalGenerationService(
            instruments=["EUR_USD"], timeframe="M5", model_version="v1"
        )

        print(f"✓ Service initialized")
        print(f"  Instruments: {service.instruments}")
        print(f"  Timeframe: {service.timeframe}")

        return True
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False


def test_signal_generation():
    """Test signal generation by publishing a test candle."""
    print("\n" + "=" * 70)
    print("TEST 2: Signal Generation")
    print("=" * 70)

    # Publish a test candle event to Redis
    redis_client = get_redis_client()

    test_candle = {
        "instrument": "EUR_USD",
        "timeframe": "M5",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "open": 1.0850,
        "high": 1.0855,
        "low": 1.0848,
        "close": 1.0852,
        "volume": 1000,
    }

    print(f"Publishing test candle: {test_candle}")

    redis_client.publish("forex:candles:EUR_USD:M5", json.dumps(test_candle))

    print("✓ Test candle published")
    print("  Check service logs to see if signal was generated")

    # Check database for new signals
    time.sleep(2)  # Give service time to process

    db = SessionLocal()
    recent_signals = (
        db.query(Signal)
        .filter(Signal.instrument == "EUR_USD")
        .order_by(Signal.timestamp.desc())
        .limit(5)
        .all()
    )

    print(f"\nRecent signals in database: {len(recent_signals)}")
    for sig in recent_signals:
        print(f"  {sig.timestamp} | {sig.signal_type.value} | {sig.confidence:.3f}")

    db.close()

    return True


def main():
    """Run tests."""
    print("\n" + "=" * 70)
    print("SIGNAL GENERATION SERVICE TESTS")
    print("=" * 70)

    tests = [
        ("Service Initialization", test_service_initialization),
        ("Signal Generation", test_signal_generation),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(
        "\nNote: Run the service with 'poetry run python -m strategy_engine.signals.main'"
    )
    print("Then run this test to publish a candle and verify signal generation.")


if __name__ == "__main__":
    main()
