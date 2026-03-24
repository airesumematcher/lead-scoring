#!/usr/bin/env python3
"""Train and compare the local 25-feature lead scoring models."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    BaggingRegressor,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor


DATA_DIR = Path("data_processed")
MODELS_DIR = Path("models")
RANDOM_STATE = 42
TEST_SIZE = 0.2


@dataclass
class TrainedDataset:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    X_train_scaled: np.ndarray
    X_test_scaled: np.ndarray


class MultiModelComparison:
    """Train, evaluate, and persist the local model suite."""

    def __init__(self):
        self.models = {}
        self.results = {}
        self.scaler = StandardScaler()
        self.feature_names = []

    def load_data(self) -> tuple[pd.DataFrame, pd.Series]:
        """Load the checked-in 25-feature dataset."""
        X = pd.read_csv(DATA_DIR / "features_enhanced.csv")
        y = pd.read_csv(DATA_DIR / "targets.csv")["lead_score"]
        self.feature_names = X.columns.tolist()
        print(f"✅ Loaded dataset: {X.shape[0]} samples × {X.shape[1]} features")
        return X, y

    def split_data(self, X: pd.DataFrame, y: pd.Series) -> TrainedDataset:
        """Create train/test splits and scale where required."""
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
        )
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        return TrainedDataset(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            X_train_scaled=X_train_scaled,
            X_test_scaled=X_test_scaled,
        )

    def train_models(self, dataset: TrainedDataset):
        """Train all single-model estimators."""
        configs = {
            "RandomForest": (
                RandomForestRegressor(
                    n_estimators=200,
                    max_depth=15,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
                dataset.X_train,
                dataset.X_test,
            ),
            "GradientBoosting": (
                GradientBoostingRegressor(
                    n_estimators=150,
                    max_depth=6,
                    learning_rate=0.1,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=RANDOM_STATE,
                    subsample=0.8,
                    loss="huber",
                ),
                dataset.X_train,
                dataset.X_test,
            ),
            "ExtraTrees": (
                ExtraTreesRegressor(
                    n_estimators=200,
                    max_depth=15,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
                dataset.X_train,
                dataset.X_test,
            ),
            "Bagging": (
                BaggingRegressor(
                    n_estimators=100,
                    max_features=0.7,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
                dataset.X_train,
                dataset.X_test,
            ),
            "SVR": (
                SVR(kernel="rbf", C=100, epsilon=1, gamma="scale"),
                dataset.X_train_scaled,
                dataset.X_test_scaled,
            ),
            "NeuralNetwork": (
                MLPRegressor(
                    hidden_layer_sizes=(128, 64, 32),
                    activation="relu",
                    learning_rate_init=0.001,
                    max_iter=500,
                    random_state=RANDOM_STATE,
                    early_stopping=True,
                    validation_fraction=0.1,
                    n_iter_no_change=20,
                ),
                dataset.X_train_scaled,
                dataset.X_test_scaled,
            ),
            "XGBoost": (
                XGBRegressor(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.9,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                    objective="reg:squarederror",
                    verbosity=0,
                ),
                dataset.X_train,
                dataset.X_test,
            ),
        }

        for name, (model, X_train, X_test) in configs.items():
            print(f"🚀 Training {name}...")
            model.fit(X_train, dataset.y_train)
            self.models[name] = model
            self.results[name] = self._evaluate_model(
                name=name,
                model=model,
                X_train=X_train,
                X_test=X_test,
                y_train=dataset.y_train,
                y_test=dataset.y_test,
            )

    def create_ensemble(self, dataset: TrainedDataset):
        """Train the ensemble on the training split, not the test split."""
        print("🚀 Training Ensemble...")
        ensemble = VotingRegressor(
            estimators=[
                ("rf", self.models["RandomForest"]),
                ("gb", self.models["GradientBoosting"]),
                ("et", self.models["ExtraTrees"]),
                ("bag", self.models["Bagging"]),
            ]
        )
        ensemble.fit(dataset.X_train, dataset.y_train)
        self.models["Ensemble"] = ensemble
        self.results["Ensemble"] = self._evaluate_model(
            name="Ensemble",
            model=ensemble,
            X_train=dataset.X_train,
            X_test=dataset.X_test,
            y_train=dataset.y_train,
            y_test=dataset.y_test,
            run_cv=False,
        )

    @staticmethod
    def _evaluate_model(name, model, X_train, X_test, y_train, y_test, run_cv=True):
        """Evaluate a single model and return serializable metrics."""
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)

        r2_train = r2_score(y_train, y_pred_train)
        r2_test = r2_score(y_test, y_pred_test)
        mae_test = mean_absolute_error(y_test, y_pred_test)
        rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))

        if run_cv:
            cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="r2")
            cv_mean = float(cv_scores.mean())
            cv_std = float(cv_scores.std())
        else:
            cv_mean = float(r2_test)
            cv_std = 0.0

        print(
            f"   {name}: R²={r2_test:.4f} | MAE=±{mae_test:.2f} | RMSE={rmse_test:.2f}"
        )
        return {
            "r2_train": float(r2_train),
            "r2_test": float(r2_test),
            "mae_test": float(mae_test),
            "rmse_test": float(rmse_test),
            "cv_mean": cv_mean,
            "cv_std": cv_std,
        }

    def save_all_models(self):
        """Persist models, scaler, and comparison results."""
        MODELS_DIR.mkdir(exist_ok=True)

        for name, model in self.models.items():
            path = MODELS_DIR / f"model_{name.lower()}.pkl"
            with open(path, "wb") as f:
                pickle.dump(model, f)
            print(f"💾 Saved {path}")

        with open(MODELS_DIR / "scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)
        print(f"💾 Saved {MODELS_DIR / 'scaler.pkl'}")

        summary = {
            "timestamp": datetime.now().isoformat(),
            "models": self.results,
            "feature_names": self.feature_names,
        }
        with open(MODELS_DIR / "model_comparison_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(f"💾 Saved {MODELS_DIR / 'model_comparison_results.json'}")

    def print_ranking(self):
        """Print a small leaderboard for the trained models."""
        print("\n🏆 Model ranking")
        ranked = sorted(
            self.results.items(),
            key=lambda item: item[1]["r2_test"],
            reverse=True,
        )
        for idx, (name, metrics) in enumerate(ranked, start=1):
            print(
                f"{idx}. {name:<18} R²={metrics['r2_test']:.4f} "
                f"MAE=±{metrics['mae_test']:.2f}"
            )


def main():
    comparison = MultiModelComparison()
    X, y = comparison.load_data()
    dataset = comparison.split_data(X, y)
    comparison.train_models(dataset)
    comparison.create_ensemble(dataset)
    comparison.save_all_models()
    comparison.print_ranking()
    print("\n✅ Multi-model training complete")


if __name__ == "__main__":
    main()
