#!/usr/bin/env python3
"""
Entry point for tick aggregator service.
Subscribes to Redis tick stream and aggregates into OHLCV candles.

Usage:
    python backend/data_ingestion/aggregator_main.py
"""

from tick_aggregator import main

if __name__ == "__main__":
    main()
