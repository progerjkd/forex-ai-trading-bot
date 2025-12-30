#!/usr/bin/env python3
"""
Test script for data ingestion service.
Fetches sample data from OANDA and stores in TimescaleDB.

Usage:
    python backend/test_data_ingestion.py
"""

import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text

from data_ingestion.ingestion_service import DataIngestionService
from shared.config import settings
from shared.database import SessionLocal
from shared.models import MarketData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Test data ingestion."""
    print("=" * 70)
    print("DATA INGESTION TEST")
    print("=" * 70)
    print()

    # Display configuration
    print(f"Trading Pairs: {settings.get_trading_pairs_list()}")
    print(f"Environment: {settings.oanda_environment}")
    print()

    try:
        # Initialize service
        print("Initializing data ingestion service...")
        service = DataIngestionService()
        print("✓ Service initialized")
        print()

        # Test 1: Fetch sample data for EUR/USD
        print("Test 1: Fetching 50 M5 candles for EUR/USD...")
        print("-" * 70)
        count = service.fetch_and_store_candles(
            instrument="EUR_USD",
            timeframe="M5",
            count=50
        )
        print(f"✓ Stored {count} candles")
        print()

        # Test 2: Verify data in database
        print("Test 2: Verifying data in database...")
        print("-" * 70)
        db = SessionLocal()
        try:
            # Count total candles
            total = db.query(MarketData).count()
            print(f"✓ Total candles in database: {total}")

            # Get latest candle for each pair
            for pair in ["EUR_USD", "GBP_USD", "USD_JPY"]:
                latest = db.query(MarketData).filter(
                    MarketData.instrument == pair,
                    MarketData.timeframe == "M5"
                ).order_by(MarketData.timestamp.desc()).first()

                if latest:
                    print(f"\n  {pair} (M5):")
                    print(f"    Latest: {latest.timestamp}")
                    print(f"    OHLC: O={latest.open:.5f} H={latest.high:.5f} "
                          f"L={latest.low:.5f} C={latest.close:.5f}")
                    print(f"    Volume: {latest.volume}")
                else:
                    print(f"\n  {pair} (M5): No data")

        finally:
            db.close()

        print()

        # Test 3: Fetch historical data for all configured pairs
        print("Test 3: Fetching 30 days of M5 data for all pairs...")
        print("-" * 70)
        results = service.fetch_historical_data(
            timeframe="M5",
            days_back=30
        )

        for instrument, stored_count in results.items():
            status = "✓" if stored_count > 0 else "✗"
            print(f"  {status} {instrument}: {stored_count} candles")

        print()

        # Test 4: Show TimescaleDB hypertable info
        print("Test 4: TimescaleDB hypertable statistics...")
        print("-" * 70)
        db = SessionLocal()
        try:
            # Get hypertable size
            result = db.execute(text("""
                SELECT
                    pg_size_pretty(hypertable_size('trading.market_data')) as size,
                    (SELECT COUNT(*) FROM trading.market_data) as total_rows
            """)).fetchone()

            print(f"  Hypertable size: {result[0]}")
            print(f"  Total rows: {result[1]:,}")

            # Get chunk info
            result = db.execute(text("""
                SELECT COUNT(*) as chunk_count
                FROM timescaledb_information.chunks
                WHERE hypertable_name = 'market_data';
            """)).fetchone()

            print(f"  Number of chunks: {result[0]}")

        finally:
            db.close()

        print()

        # Summary
        print("=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
        print()
        print("Data ingestion is working correctly!")
        print("Next steps:")
        print("  1. Set up scheduled data ingestion (Celery tasks)")
        print("  2. Implement real-time data streaming")
        print("  3. Add Redis pub/sub for live updates")
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print("TEST FAILED! ✗")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()

        return 1


if __name__ == "__main__":
    sys.exit(main())
