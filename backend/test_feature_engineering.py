#!/usr/bin/env python3
"""
Test feature engineering pipeline.

Tests:
1. Indicator calculation on historical data
2. Feature vector assembly
3. Multi-timeframe aggregation
4. Performance benchmarks
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from shared.database import SessionLocal
from strategy_engine.features import FeatureService, IndicatorCalculator


def test_indicator_calculation():
    """Test basic indicator calculation."""
    print("\n" + "=" * 70)
    print("TEST 1: Indicator Calculation")
    print("=" * 70)

    service = FeatureService()

    # Fetch 250 M1 candles for EUR_USD
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=5)  # ~300 minutes of M1 data

    print(f"\nFetching M1 candles from {start_time} to {end_time}...")

    df = service.get_candles("EUR_USD", "M1", start_time, end_time)

    if df.empty:
        print("❌ No candles found!")
        return False

    print(f"✓ Fetched {len(df)} candles")

    # Calculate indicators
    print("\nCalculating indicators...")
    df_indicators = service.indicator_calculator.calculate_all(df)

    # Validate indicators
    print("\nValidating indicators...")

    # Check RSI range
    rsi = df_indicators["rsi_14"].dropna()
    if not rsi.empty:
        if rsi.min() < 0 or rsi.max() > 100:
            print(f"❌ RSI out of range: {rsi.min():.2f} - {rsi.max():.2f}")
            return False
        print(f"✓ RSI in valid range [0, 100]: {rsi.min():.2f} - {rsi.max():.2f}")

    # Check MACD exists
    if "macd" in df_indicators.columns and not df_indicators["macd"].dropna().empty:
        print("✓ MACD calculated")

    # Check Bollinger Bands ordering
    bb_upper = df_indicators["bb_upper"].dropna()
    bb_lower = df_indicators["bb_lower"].dropna()
    if not bb_upper.empty and not bb_lower.empty:
        if (bb_upper >= bb_lower).all():
            print("✓ Bollinger Bands correctly ordered (upper >= lower)")
        else:
            print("❌ Bollinger Bands ordering invalid")
            return False

    # Check ATR is positive
    atr = df_indicators["atr_14"].dropna()
    if not atr.empty:
        if (atr > 0).all():
            print(f"✓ ATR positive: {atr.mean():.6f}")
        else:
            print("❌ ATR has non-positive values")
            return False

    print("\n✅ All indicator validations passed!")
    return True


def test_feature_vector_generation():
    """Test complete feature vector generation."""
    print("\n" + "=" * 70)
    print("TEST 2: Feature Vector Generation")
    print("=" * 70)

    service = FeatureService()

    # Get latest features
    print("\nGenerating features for latest timestamp...")

    features = service.get_latest_features("EUR_USD", timeframes=["M1", "M5"])

    if features.empty:
        print("❌ Failed to generate features!")
        return False

    print(f"✓ Generated feature vector with shape: {features.shape}")
    print(f"  Columns: {features.shape[1]}")
    print(f"  Rows: {features.shape[0]}")

    # Check for NaN values
    nan_count = features.isna().sum().sum()
    if nan_count > 0:
        print(f"⚠ Warning: {nan_count} NaN values found")
        print("\nColumns with NaN:")
        nan_cols = features.columns[features.isna().any()].tolist()
        for col in nan_cols[:10]:  # Show first 10
            print(f"  - {col}")
    else:
        print("✓ No NaN values")

    # Show some example features
    print("\nSample features:")
    sample_cols = [col for col in features.columns if "rsi" in col.lower()][:3]
    if sample_cols:
        print(features[sample_cols].to_string(index=False))

    print("\n✅ Feature vector generation passed!")
    return True


def test_multi_timeframe_features():
    """Test multi-timeframe aggregation."""
    print("\n" + "=" * 70)
    print("TEST 3: Multi-Timeframe Aggregation")
    print("=" * 70)

    service = FeatureService()

    # Generate features with multiple timeframes
    print("\nGenerating features for M1, M5, M15, H1...")

    features = service.get_latest_features(
        "EUR_USD", timeframes=["M1", "M5", "M15", "H1"]
    )

    if features.empty:
        print("❌ Failed to generate multi-timeframe features!")
        return False

    print(f"✓ Generated {features.shape[1]} features")

    # Check for timeframe prefixes
    timeframes = ["M1", "M5", "M15", "H1"]
    for tf in timeframes:
        tf_features = [col for col in features.columns if col.startswith(f"{tf}_")]
        print(f"  {tf}: {len(tf_features)} features")

        if len(tf_features) == 0:
            print(f"❌ No features found for timeframe {tf}")
            return False

    # Check for time features
    time_features = ["hour", "day_of_week", "forex_session"]
    for feat in time_features:
        if feat in features.columns:
            print(f"✓ Time feature '{feat}' present: {features[feat].values[0]}")

    print("\n✅ Multi-timeframe aggregation passed!")
    return True


def test_performance():
    """Benchmark feature calculation speed."""
    print("\n" + "=" * 70)
    print("TEST 4: Performance Benchmark")
    print("=" * 70)

    service = FeatureService()

    # Get recent timestamps for batch processing
    db = SessionLocal()
    from shared.models import MarketData
    from sqlalchemy import and_

    print("\nFetching recent timestamps...")

    candles = (
        db.query(MarketData.timestamp)
        .filter(
            and_(
                MarketData.instrument == "EUR_USD",
                MarketData.timeframe == "M5",
            )
        )
        .order_by(MarketData.timestamp.desc())
        .limit(10)
        .all()
    )

    timestamps = [c.timestamp for c in candles]

    if len(timestamps) < 5:
        print("⚠ Warning: Not enough timestamps for benchmark")
        db.close()
        return True

    print(f"✓ Testing with {len(timestamps)} timestamps")

    # Benchmark single feature generation
    print("\nBenchmarking single feature generation...")

    start_time = time.time()
    features = service.get_features(timestamps[0], "EUR_USD", timeframes=["M1", "M5"])
    elapsed = time.time() - start_time

    print(f"  Time per feature vector: {elapsed*1000:.1f}ms")

    if elapsed < 1.0:  # Target: <1000ms
        print("✓ Performance within target (<1000ms)")
    else:
        print(f"⚠ Warning: Slower than target (goal: <1000ms, actual: {elapsed*1000:.1f}ms)")

    # Benchmark batch processing
    print("\nBenchmarking batch processing...")

    start_time = time.time()
    batch_features = service.get_batch_features(
        "EUR_USD", timestamps[:5], timeframes=["M1", "M5"]
    )
    elapsed = time.time() - start_time

    if not batch_features.empty:
        per_timestamp = elapsed / len(timestamps[:5])
        print(f"  Batch processing: {elapsed:.2f}s for {len(timestamps[:5])} timestamps")
        print(f"  Time per timestamp: {per_timestamp*1000:.1f}ms")
        print(f"  Throughput: {1/per_timestamp:.1f} timestamps/second")

    db.close()

    print("\n✅ Performance benchmark completed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("FEATURE ENGINEERING PIPELINE TESTS")
    print("=" * 70)

    tests = [
        ("Indicator Calculation", test_indicator_calculation),
        ("Feature Vector Generation", test_feature_vector_generation),
        ("Multi-Timeframe Aggregation", test_multi_timeframe_features),
        ("Performance Benchmark", test_performance),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception:")
            print(f"   {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Feature engineering pipeline is ready.")
        return 0
    else:
        print("\n⚠ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
