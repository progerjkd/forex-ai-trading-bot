#!/usr/bin/env python3
"""
Test script to verify OANDA API connection.
Run this to ensure your API credentials are working correctly.

Usage:
    python backend/test_oanda_connection.py
"""

import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from data_ingestion.oanda_client import OANDAClient
from shared.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run OANDA connection tests."""
    print("=" * 70)
    print("OANDA API CONNECTION TEST")
    print("=" * 70)
    print()

    # Display configuration
    print(f"Environment: {settings.oanda_environment}")
    print(f"Account ID: {settings.oanda_account_id}")
    print(f"API Base URL: {settings.oanda_base_url}")
    print(f"Trading Pairs: {settings.get_trading_pairs_list()}")
    print()

    try:
        # Initialize client
        print("Initializing OANDA client...")
        client = OANDAClient()
        print("✓ Client initialized successfully")
        print()

        # Test 1: Connection and account info
        print("Test 1: Testing connection and fetching account info...")
        print("-" * 70)
        account_info = client.test_connection()

        print(f"✓ Connection successful!")
        print(f"  Account ID: {account_info['account_id']}")
        print(f"  Balance: {account_info['balance']:.2f} {account_info['currency']}")
        print(f"  Unrealized P/L: {account_info['unrealized_pl']:.2f}")
        print(f"  Open Positions: {account_info['open_positions']}")
        print(f"  Open Trades: {account_info['open_trades']}")
        print()

        # Test 2: Fetch current prices
        print("Test 2: Fetching current prices for trading pairs...")
        print("-" * 70)

        for pair in settings.get_trading_pairs_list():
            # Convert pair format: EUR/USD -> EUR_USD
            oanda_pair = pair.replace("/", "_")

            try:
                price_data = client.get_current_price(oanda_pair)
                print(f"✓ {pair}:")
                print(f"  Bid: {price_data['bid']:.5f}")
                print(f"  Ask: {price_data['ask']:.5f}")
                print(f"  Mid: {price_data['mid']:.5f}")
                print(f"  Spread: {price_data['spread']:.5f}")
                print(f"  Status: {price_data['status']}")
                print()
            except Exception as e:
                print(f"✗ {pair}: Failed - {e}")
                print()

        # Test 3: Fetch historical candles
        print("Test 3: Fetching historical candle data...")
        print("-" * 70)

        candles = client.get_candles("EUR_USD", granularity="M5", count=10)
        print(f"✓ Fetched {len(candles)} candles for EUR/USD (5-minute)")
        if candles:
            latest = candles[-1]
            print(f"  Latest candle:")
            print(f"    Time: {latest['time']}")
            print(f"    Open: {latest['open']:.5f}")
            print(f"    High: {latest['high']:.5f}")
            print(f"    Low: {latest['low']:.5f}")
            print(f"    Close: {latest['close']:.5f}")
            print(f"    Volume: {latest['volume']}")
        print()

        # Test 4: Get tradeable instruments
        print("Test 4: Fetching tradeable instruments...")
        print("-" * 70)

        instruments = client.get_tradeable_instruments()
        print(f"✓ Found {len(instruments)} tradeable currency pairs")
        print(f"  Sample pairs: {', '.join(instruments[:10])}")
        print()

        # Summary
        print("=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
        print()
        print("Your OANDA API connection is working correctly.")
        print("You can now proceed with building the data ingestion pipeline.")
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
        print("Troubleshooting steps:")
        print("1. Check that your .env file has the correct OANDA_API_KEY")
        print("2. Verify your OANDA_ACCOUNT_ID is correct")
        print("3. Ensure you're using a practice account (OANDA_ENVIRONMENT=practice)")
        print("4. Check that your OANDA account is active and funded")
        print()

        return 1


if __name__ == "__main__":
    sys.exit(main())
