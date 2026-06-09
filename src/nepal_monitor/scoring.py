from __future__ import annotations

from collections import defaultdict
import sqlite3

from .constants import SOURCE_PRIORITY_SCORE


def _primary_topic(topic_text: str | None) -> str:
    if not topic_text:
        return ""
    return topic_text.split(",", 1)[0]


def score_signals(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT s.signal_id, s.source_id, s.city, s.action_date, s.topic,
               s.has_exact_date, s.has_exact_place, s.has_call_to_action,
               s.organizer, s.lead_time_hours, s.signal_type,
               COALESCE(src.priority, 'medium') AS priority
        FROM signals s
        LEFT JOIN sources src ON src.source_id = s.source_id
        """
    ).fetchall()

    groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        if row["action_date"]:
            key = (row["city"], row["action_date"], _primary_topic(row["topic"]))
            groups[key].add(row["source_id"] or f"signal:{row['signal_id']}")

    count = 0
    for row in rows:
        independent = 0
        if row["action_date"]:
            key = (row["city"], row["action_date"], _primary_topic(row["topic"]))
            independent = 1 if len(groups[key]) >= 2 else 0

        reliability = SOURCE_PRIORITY_SCORE.get((row["priority"] or "medium").lower(), 1)
        score = 0
        if row["has_exact_date"]:
            score += 2
        if row["has_exact_place"]:
            score += 2
        score += reliability
        if row["has_call_to_action"]:
            score += 1
        if row["organizer"]:
            score += 1
        if independent:
            score += 1
        if row["lead_time_hours"] is not None and row["lead_time_hours"] >= 24:
            score += 1

        if row["signal_type"] == 0:
            score = min(score, 3)

        conn.execute(
            """
            UPDATE signals
            SET reliability_score = ?,
                independent_confirmation = ?,
                score = ?
            WHERE signal_id = ?
            """,
            (reliability, independent, min(score, 10), row["signal_id"]),
        )
        count += 1
    conn.commit()
    return count
