#!/usr/bin/env python3
"""
Entry point for OANDA streaming service.
Starts real-time price streaming and publishes to Redis.

Usage:
    python backend/data_ingestion/main.py
"""

from streaming_client import main

if __name__ == "__main__":
    main()
