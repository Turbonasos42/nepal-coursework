from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
import sqlite3

from .importers import import_ground_truth


def _auc(probabilities: list[float], labels: list[int]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    pairs = sorted(zip(probabilities, labels), key=lambda item: item[0])
    ranks = [0.0 for _ in pairs]
    index = 0
    while index < len(pairs):
        end = index + 1
        while end < len(pairs) and pairs[end][0] == pairs[index][0]:
            end += 1
        avg_rank = (index + 1 + end) / 2.0
        for rank_index in range(index, end):
            ranks[rank_index] = avg_rank
        index = end
    rank_sum_pos = sum(rank for rank, (_, label) in zip(ranks, pairs) if label == 1)
    return (rank_sum_pos - positives * (positives + 1) / 2.0) / (positives * negatives)


def evaluate(
    conn: sqlite3.Connection,
    ground_truth_csv: str | None = None,
    output_csv: str = "reports/evaluation_summary.csv",
) -> dict[str, float | int | None]:
    if ground_truth_csv:
        import_ground_truth(conn, ground_truth_csv, replace=True)

    forecasts = conn.execute("SELECT * FROM forecasts ORDER BY forecast_date, city").fetchall()
    truths = conn.execute("SELECT * FROM ground_truth_events WHERE verified = 1").fetchall()

    tp = fp = fn = tn = 0
    probabilities: list[float] = []
    labels: list[int] = []
    lead_times: list[int] = []

    for forecast in forecasts:
        actual_events = [
            truth
            for truth in truths
            if truth["city"] == forecast["city"]
            and forecast["target_start_date"] <= truth["event_date"] <= forecast["target_end_date"]
        ]
        actual = 1 if actual_events else 0
        predicted = 1 if forecast["binary_prediction"] == "yes" else 0
        probabilities.append(float(forecast["event_probability"]))
        labels.append(actual)
        if predicted and actual:
            tp += 1
            event_date = min(event["event_date"] for event in actual_events)
            lead_times.append((date.fromisoformat(event_date) - date.fromisoformat(forecast["forecast_date"])).days)
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1

    detected_events = 0
    first_warning_leads: list[int] = []
    for truth in truths:
        event_date = date.fromisoformat(truth["event_date"])
        matching_yes = [
            forecast
            for forecast in forecasts
            if forecast["city"] == truth["city"]
            and forecast["binary_prediction"] == "yes"
            and forecast["forecast_date"] < truth["event_date"]
            and forecast["target_start_date"] <= truth["event_date"] <= forecast["target_end_date"]
        ]
        if matching_yes:
            detected_events += 1
            earliest = min(date.fromisoformat(forecast["forecast_date"]) for forecast in matching_yes)
            first_warning_leads.append((event_date - earliest).days)

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    brier = (
        sum((probability - label) ** 2 for probability, label in zip(probabilities, labels))
        / len(labels)
        if labels
        else 0.0
    )
    metrics: dict[str, float | int | None] = {
        "forecasts": total,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "brier_score": brier,
        "roc_auc": _auc(probabilities, labels),
        "average_lead_time_days": sum(lead_times) / len(lead_times) if lead_times else None,
        "ground_truth_events": len(truths),
        "events_detected": detected_events,
        "event_recall": detected_events / len(truths) if truths else 0.0,
        "average_first_warning_lead_days": (
            sum(first_warning_leads) / len(first_warning_leads) if first_warning_leads else None
        ),
    }

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            writer.writerow([key, "" if value is None else value])
    return metrics
