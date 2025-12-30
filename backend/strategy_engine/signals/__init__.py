"""
Real-time signal generation module.

Subscribes to Redis candle events and generates ML-based trading signals.
"""

from .signal_generation_service import SignalGenerationService

__all__ = ["SignalGenerationService"]
