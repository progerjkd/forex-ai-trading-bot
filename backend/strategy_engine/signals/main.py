#!/usr/bin/env python3
"""
Signal Generation Service - Entry Point

Runs the real-time ML signal generation service.

Usage:
    poetry run python -m strategy_engine.signals.main
"""

import logging
import signal
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.config import settings
from strategy_engine.signals import SignalGenerationService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Global service instance for signal handlers
service = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}")
    if service:
        service.stop()
    sys.exit(0)


def main():
    """Run the signal generation service."""
    global service

    logger.info("=" * 70)
    logger.info("SIGNAL GENERATION SERVICE")
    logger.info("=" * 70)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Get configuration
    instruments = settings.get_trading_pairs_list()
    timeframe = "M5"  # Primary timeframe
    model_version = "v1"

    logger.info(f"Configuration:")
    logger.info(f"  Instruments: {instruments}")
    logger.info(f"  Timeframe: {timeframe}")
    logger.info(f"  Model version: {model_version}")
    logger.info(f"  Confidence threshold: {settings.ml_confidence_threshold}")

    # Initialize service
    service = SignalGenerationService(
        instruments=instruments, timeframe=timeframe, model_version=model_version
    )

    # Start service (blocks until stopped)
    logger.info("Starting service...")
    service.start()

    logger.info("Service exited")


if __name__ == "__main__":
    main()
