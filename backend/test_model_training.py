#!/usr/bin/env python3
"""
Test ML model training pipeline.

Tests:
1. Label generation from historical candles
2. Model training and evaluation
3. Model persistence (save/load)
4. Real-time prediction
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from shared.database import SessionLocal
from strategy_engine.features import FeatureService
from strategy_engine.models import LabelGenerator, ModelStore, ModelTrainer, Predictor


def test_label_generation():
    """Test label generation from candles."""
    print("\n" + "=" * 70)
    print("TEST 1: Label Generation")
    print("=" * 70)

    db = SessionLocal()
    service = FeatureService(db)

    # Fetch recent M5 candles
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=10)

    print(f"\nFetching M5 candles from {start_time} to {end_time}...")

    df = service.get_candles("EUR_USD", "M5", start_time, end_time)

    if df.empty:
        print("❌ No candles found!")
        db.close()
        return False

    print(f"✓ Fetched {len(df)} M5 candles")

    # Generate labels
    print("\nGenerating labels...")
    label_gen = LabelGenerator(price_threshold=0.5, lookahead_periods=5)
    labels = label_gen.generate_labels(df)

    # Get distribution
    dist = label_gen.get_label_distribution(labels.dropna())

    print(f"\nLabel distribution:")
    print(f"  BUY:  {dist['buy']} ({dist['buy_pct']:.1f}%)")
    print(f"  SELL: {dist['sell']} ({dist['sell_pct']:.1f}%)")
    print(f"  HOLD: {dist['hold']} ({dist['hold_pct']:.1f}%)")

    # Validate
    if dist["buy"] > 0 and dist["sell"] > 0:
        print("\n✅ Label generation passed!")
        db.close()
        return True
    else:
        print("\n❌ No BUY or SELL labels generated")
        db.close()
        return False


def test_model_training():
    """Test full training pipeline."""
    print("\n" + "=" * 70)
    print("TEST 2: Model Training")
    print("=" * 70)

    db = SessionLocal()
    feature_service = FeatureService(db)
    label_gen = LabelGenerator(price_threshold=0.5, lookahead_periods=5)

    # Get training data
    print("\nFetching training data...")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=10)

    # Get all M5 candles
    candles = feature_service.get_candles("EUR_USD", "M5", start_time, end_time)

    if len(candles) < 50:
        print(f"❌ Insufficient data: {len(candles)} candles")
        db.close()
        return False

    print(f"✓ Fetched {len(candles)} candles")

    # Generate features for each candle
    print(f"\nGenerating features for {len(candles)} timestamps...")
    timestamps = candles["timestamp"].tolist()
    features = feature_service.get_batch_features(
        "EUR_USD", timestamps, timeframes=["M1", "M5"]  # Use available timeframes
    )

    if features.empty:
        print("❌ Failed to generate features")
        db.close()
        return False

    # Generate labels
    labels = label_gen.generate_labels(candles)

    # Align features and labels
    features = features.iloc[: len(labels)]

    print(f"✓ Features shape: {features.shape}")
    print(f"✓ Labels shape: {labels.shape}")

    # Train model
    print("\nTraining Random Forest model...")
    trainer = ModelTrainer(n_estimators=100, max_depth=10)

    try:
        metrics = trainer.train(features, labels, test_size=0.2)

        print(f"\nTraining Results:")
        print(f"  Train accuracy: {metrics['train']['accuracy']:.3f}")
        print(f"  Test accuracy:  {metrics['test']['accuracy']:.3f}")
        print(f"  Test F1 score:  {metrics['test']['f1_score']:.3f}")

        # Save model
        print("\nSaving model...")
        store = ModelStore()
        model_path = store.save(
            model=trainer.model,
            instrument="EUR_USD",
            version="v1",
            metadata=metrics,
            feature_columns=trainer.feature_columns,
        )

        print(f"✓ Model saved to: {model_path}")

        db.close()
        print("\n✅ Model training passed!")
        return True

    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback

        traceback.print_exc()
        db.close()
        return False


def test_prediction():
    """Test real-time prediction."""
    print("\n" + "=" * 70)
    print("TEST 3: Real-Time Prediction")
    print("=" * 70)

    # Check if model exists
    store = ModelStore()
    model_path = store.get_latest_model("EUR_USD", "v1")

    if not model_path:
        print("⚠ No trained model found, skipping prediction test")
        return True

    print(f"✓ Found model: {model_path}")

    try:
        # Initialize predictor
        predictor = Predictor(instrument="EUR_USD", model_version="v1")

        # Get latest features
        feature_service = FeatureService()
        features = feature_service.get_latest_features(
            "EUR_USD", timeframes=["M1", "M5"]
        )

        if features.empty:
            print("❌ No features available")
            return False

        print(f"✓ Generated features: {features.shape}")

        # Make prediction
        result = predictor.predict(
            features=features, entry_price=1.0850, timestamp=datetime.utcnow()  # Example price
        )

        print(f"\nPrediction Result:")
        print(f"  Signal: {result['signal']}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Probabilities:")
        for signal, prob in result["probabilities"].items():
            print(f"    {signal}: {prob:.3f}")
        print(f"  Meets threshold: {result['meets_threshold']}")

        print("\n✅ Prediction test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Prediction failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("ML MODEL TRAINING PIPELINE TESTS")
    print("=" * 70)

    tests = [
        ("Label Generation", test_label_generation),
        ("Model Training", test_model_training),
        ("Real-Time Prediction", test_prediction),
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
        print("\n🎉 All tests passed! ML training pipeline is ready.")
        return 0
    else:
        print("\n⚠ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
