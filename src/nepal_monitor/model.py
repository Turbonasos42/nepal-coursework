from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable

from .features import FEATURE_COLUMNS


MODEL_VERSION = "rules_logreg_v1"


def sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def scale_feature(name: str, value: float) -> float:
    value = float(value or 0.0)
    if name in {"explicit_count", "possible_count"}:
        return min(value, 5.0) / 5.0
    if name in {"weak_count", "topic_social_media_ban", "topic_corruption", "topic_gen_z", "topic_students", "topic_government", "topic_strike"}:
        return min(value, 10.0) / 10.0
    if name in {"max_score", "avg_score"}:
        return min(value, 10.0) / 10.0
    if name in {"has_exact_date", "has_exact_place", "has_call_to_action", "has_organizer"}:
        return 1.0 if value else 0.0
    if name == "independent_sources":
        return min(value, 5.0) / 5.0
    if name == "mention_growth_3d":
        return max(0.0, min((value + 1.0) / 4.0, 1.0))
    if name in {"total_posts", "total_signals"}:
        return min(value, 20.0) / 20.0
    return value


def vectorize(row: dict[str, float]) -> list[float]:
    return [scale_feature(name, float(row.get(name, 0.0) or 0.0)) for name in FEATURE_COLUMNS]


@dataclass
class LogisticRegression:
    weights: list[float]
    bias: float

    @classmethod
    def default(cls) -> "LogisticRegression":
        weights = [0.0 for _ in FEATURE_COLUMNS]
        defaults = {
            "explicit_count": 2.3,
            "possible_count": 1.3,
            "weak_count": 0.35,
            "max_score": 2.0,
            "avg_score": 1.2,
            "has_exact_date": 0.9,
            "has_exact_place": 0.8,
            "has_call_to_action": 0.7,
            "has_organizer": 0.6,
            "independent_sources": 1.0,
            "mention_growth_3d": 0.8,
            "topic_social_media_ban": 0.6,
            "topic_corruption": 0.35,
            "topic_gen_z": 0.35,
            "topic_students": 0.25,
            "topic_government": 0.2,
            "topic_strike": 0.45,
            "total_posts": 0.15,
            "total_signals": 0.25,
        }
        for index, name in enumerate(FEATURE_COLUMNS):
            weights[index] = defaults.get(name, 0.0)
        return cls(weights=weights, bias=-2.4)

    def predict_proba(self, row: dict[str, float]) -> float:
        xs = vectorize(row)
        linear = self.bias + sum(weight * value for weight, value in zip(self.weights, xs))
        return sigmoid(linear)

    def fit(
        self,
        rows: Iterable[dict[str, float]],
        labels: Iterable[int],
        epochs: int = 2500,
        learning_rate: float = 0.35,
        l2: float = 0.01,
    ) -> "LogisticRegression":
        xs = [vectorize(row) for row in rows]
        ys = [int(label) for label in labels]
        if not xs or len(set(ys)) < 2:
            return self

        weights = self.weights[:]
        bias = self.bias
        n = float(len(xs))
        for _ in range(epochs):
            grad_w = [0.0 for _ in weights]
            grad_b = 0.0
            for x, y in zip(xs, ys):
                pred = sigmoid(bias + sum(w * value for w, value in zip(weights, x)))
                error = pred - y
                grad_b += error
                for index, value in enumerate(x):
                    grad_w[index] += error * value
            bias -= learning_rate * grad_b / n
            for index in range(len(weights)):
                grad = grad_w[index] / n + l2 * weights[index]
                weights[index] -= learning_rate * grad
        self.weights = weights
        self.bias = bias
        return self


def load_calibration(path: str) -> tuple[list[dict[str, float]], list[int]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return [], []
    rows: list[dict[str, float]] = []
    labels: list[int] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            rows.append({name: float(record.get(name, 0) or 0) for name in FEATURE_COLUMNS})
            labels.append(int(record["label"]))
    return rows, labels
