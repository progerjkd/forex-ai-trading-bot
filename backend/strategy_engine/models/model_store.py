"""
Model persistence and versioning.

Handles saving and loading trained models with metadata tracking.
"""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ModelStore:
    """
    Manage model persistence and versioning.

    Saves models to local filesystem with metadata for tracking.
    """

    def __init__(self, models_dir: str = "backend/models/saved"):
        """
        Initialize model store.

        Args:
            models_dir: Directory for saved models (default: backend/models/saved)
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        model,
        instrument: str,
        version: str,
        metadata: Dict,
        feature_columns: list,
    ) -> str:
        """
        Save model and metadata to disk.

        Args:
            model: Trained scikit-learn model
            instrument: Trading pair (e.g., "EUR_USD")
            version: Model version (e.g., "v1")
            metadata: Training metrics and configuration
            feature_columns: List of feature column names

        Returns:
            Path to saved model file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"{instrument}_{version}_{timestamp}.pkl"
        metadata_filename = f"{instrument}_{version}_{timestamp}_metadata.json"

        model_path = self.models_dir / model_filename
        metadata_path = self.models_dir / metadata_filename

        # Save model with pickle
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # Save metadata
        metadata_full = {
            "instrument": instrument,
            "version": version,
            "timestamp": timestamp,
            "feature_columns": feature_columns,
            "n_features": len(feature_columns),
            **metadata,
        }

        with open(metadata_path, "w") as f:
            json.dump(metadata_full, f, indent=2, default=str)

        logger.info(f"Model saved to {model_path}")
        logger.info(f"Metadata saved to {metadata_path}")

        return str(model_path)

    def load(self, model_path: str) -> Tuple:
        """
        Load model and metadata from disk.

        Args:
            model_path: Path to model file

        Returns:
            Tuple of (model, metadata)
        """
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Load model
        with open(model_path, "rb") as f:
            model = pickle.load(f)

        # Load metadata
        metadata_path = model_path.with_name(model_path.stem + "_metadata.json")

        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {}

        logger.info(f"Model loaded from {model_path}")

        return model, metadata

    def get_latest_model(self, instrument: str, version: str = "v1") -> Optional[str]:
        """
        Get path to latest model for instrument.

        Args:
            instrument: Trading pair (e.g., "EUR_USD")
            version: Model version (default "v1")

        Returns:
            Path to latest model file, or None if not found
        """
        pattern = f"{instrument}_{version}_*.pkl"
        model_files = sorted(self.models_dir.glob(pattern), reverse=True)

        if model_files:
            return str(model_files[0])

        return None
