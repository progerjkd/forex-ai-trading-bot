"""
Model trainer for Random Forest classifier.

Handles training, evaluation, and performance metrics for forex signal generation.
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


class ModelTrainer:
    """
    Train Random Forest classifier for forex signal generation.

    Handles train/test split, training, evaluation, and model persistence.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 10,
        min_samples_split: int = 10,
        random_state: int = 42,
    ):
        """
        Initialize model trainer.

        Args:
            n_estimators: Number of trees in forest (default 100)
            max_depth: Maximum tree depth (default 10)
            min_samples_split: Minimum samples to split node (default 10)
            random_state: Random seed for reproducibility
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.random_state = random_state

        self.model = None
        self.feature_columns = None
        self.training_metrics = {}

    def train(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        test_size: float = 0.2,
        class_weight: str = "balanced",
    ) -> Dict:
        """
        Train Random Forest model.

        Args:
            features: Feature matrix (N × features)
            labels: Target labels (N × 1) with values -1, 0, 1
            test_size: Fraction of data for testing (default 0.2)
            class_weight: Class weighting strategy (default "balanced")

        Returns:
            Dictionary with training metrics
        """
        logger.info(
            f"Training on {len(features)} samples with {features.shape[1]} features"
        )

        # Remove NaN labels (from lookahead period)
        valid_idx = ~labels.isna()
        features = features[valid_idx]
        labels = labels[valid_idx]

        # Drop non-numeric columns (timestamps, strings, etc.)
        numeric_columns = features.select_dtypes(include=[np.number]).columns
        features = features[numeric_columns]

        # Convert all features to float64 to avoid dtype issues
        features = features.astype(np.float64)

        logger.info(f"After removing NaN labels: {len(features)} samples with {len(numeric_columns)} numeric features")

        # Check if we have all three classes
        unique_labels = labels.unique()
        if len(unique_labels) < 2:
            logger.warning(
                f"Only {len(unique_labels)} unique label(s) found: {unique_labels}. "
                "Need at least 2 classes for classification."
            )
            # Proceed anyway but note this will affect stratification

        # Train/test split with stratification if possible
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                features,
                labels,
                test_size=test_size,
                random_state=self.random_state,
                stratify=labels,
            )
        except ValueError:
            # Fall back to non-stratified split if stratification fails
            logger.warning("Stratification failed, using regular train/test split")
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=test_size, random_state=self.random_state
            )

        logger.info(f"Train set: {len(X_train)}, Test set: {len(X_test)}")

        # Initialize and train model
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            class_weight=class_weight,
            random_state=self.random_state,
            n_jobs=-1,  # Use all CPU cores
        )

        self.model.fit(X_train, y_train)
        self.feature_columns = list(features.columns)

        # Evaluate
        train_metrics = self._evaluate(X_train, y_train, "train")
        test_metrics = self._evaluate(X_test, y_test, "test")

        # Feature importance
        feature_importance = pd.DataFrame(
            {"feature": self.feature_columns, "importance": self.model.feature_importances_}
        ).sort_values("importance", ascending=False)

        self.training_metrics = {
            "train": train_metrics,
            "test": test_metrics,
            "feature_importance": feature_importance.head(20).to_dict("records"),
            "total_samples": len(features),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "n_features": len(self.feature_columns),
        }

        logger.info(f"Training complete. Test accuracy: {test_metrics['accuracy']:.3f}")

        return self.training_metrics

    def _evaluate(self, X: pd.DataFrame, y: pd.Series, dataset_name: str) -> Dict:
        """
        Evaluate model on dataset.

        Args:
            X: Feature matrix
            y: True labels
            dataset_name: Name of dataset (for logging)

        Returns:
            Dictionary with evaluation metrics
        """
        y_pred = self.model.predict(X)

        return {
            "accuracy": accuracy_score(y, y_pred),
            "f1_score": f1_score(y, y_pred, average="weighted", zero_division=0),
            "confusion_matrix": confusion_matrix(y, y_pred).tolist(),
            "classification_report": classification_report(y, y_pred, output_dict=True, zero_division=0),
        }
