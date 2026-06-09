from __future__ import annotations

from collections import Counter
from datetime import timedelta
import sqlite3

from .constants import (
    DEFAULT_HORIZON_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    FORECAST_CITIES,
    NATIONAL_CITY,
    REPLAY_END,
    REPLAY_START,
)
from .extractors import detect_topics, extract_city_and_place
from .timeutils import date_range, day_end, day_start, parse_date, parse_datetime


FEATURE_COLUMNS = [
    "explicit_count",
    "possible_count",
    "weak_count",
    "max_score",
    "avg_score",
    "has_exact_date",
    "has_exact_place",
    "has_call_to_action",
    "has_organizer",
    "independent_sources",
    "mention_growth_3d",
    "topic_social_media_ban",
    "topic_corruption",
    "topic_gen_z",
    "topic_students",
    "topic_government",
    "topic_strike",
    "total_posts",
    "total_signals",
]


def _city_matches(signal_city: str, city: str) -> bool:
    return signal_city in {city, NATIONAL_CITY}


def _signal_relevant_to_horizon(row: sqlite3.Row, target_start: str, target_end: str) -> bool:
    action_date = row["action_date"]
    if not action_date:
        return True
    return target_start <= action_date <= target_end


def _count_topic_posts(rows: list[sqlite3.Row], city: str, start_date, end_date) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        published = parse_datetime(row["published_at"]).date()
        if not (start_date <= published <= end_date):
            continue
        row_city, _ = extract_city_and_place(row["text"], row["city_hint"])
        if not _city_matches(row_city, city):
            continue
        for topic in detect_topics(row["text"]):
            counts[topic] += 1
    return counts


def _count_matching_posts(rows: list[sqlite3.Row], city: str, start_date, end_date) -> int:
    count = 0
    for row in rows:
        published = parse_datetime(row["published_at"]).date()
        if not (start_date <= published <= end_date):
            continue
        row_city, _ = extract_city_and_place(row["text"], row["city_hint"])
        if _city_matches(row_city, city):
            count += 1
    return count


def build_daily_city_features(
    conn: sqlite3.Connection,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> int:
    conn.execute("DELETE FROM daily_city_features")
    signals = conn.execute("SELECT * FROM signals ORDER BY published_at").fetchall()
    posts = conn.execute("SELECT * FROM raw_posts ORDER BY published_at").fetchall()
    count = 0

    for forecast_date in date_range(REPLAY_START, REPLAY_END):
        window_start = forecast_date - timedelta(days=lookback_days - 1)
        window_start_dt = day_start(window_start)
        window_end_dt = day_end(forecast_date)
        target_start = forecast_date + timedelta(days=1)
        target_end = forecast_date + timedelta(days=horizon_days)
        target_start_text = target_start.isoformat()
        target_end_text = target_end.isoformat()

        previous_start = forecast_date - timedelta(days=5)
        previous_end = forecast_date - timedelta(days=3)
        latest_start = forecast_date - timedelta(days=2)

        for city in FORECAST_CITIES:
            window_signals = []
            for signal in signals:
                published = parse_datetime(signal["published_at"])
                if not (window_start_dt <= published <= window_end_dt):
                    continue
                if not _city_matches(signal["city"], city):
                    continue
                if signal["signal_type"] >= 3 and not _signal_relevant_to_horizon(
                    signal, target_start_text, target_end_text
                ):
                    continue
                window_signals.append(signal)

            explicit = [row for row in window_signals if row["signal_type"] >= 4]
            possible = [row for row in window_signals if row["signal_type"] == 3]
            weak = [row for row in window_signals if row["signal_type"] in {1, 2}]
            scored = [row["score"] for row in window_signals if row["signal_type"] > 0]
            sources = {
                row["source_id"] or f"signal:{row['signal_id']}"
                for row in window_signals
                if row["signal_type"] > 0
            }

            topic_counts = _count_topic_posts(posts, city, window_start, forecast_date)
            latest_counts = sum(_count_topic_posts(posts, city, latest_start, forecast_date).values())
            previous_counts = sum(_count_topic_posts(posts, city, previous_start, previous_end).values())
            mention_growth = (latest_counts + 1.0) / (previous_counts + 1.0) - 1.0

            top_signals = sorted(window_signals, key=lambda row: row["score"], reverse=True)[:3]
            primary_topics = ",".join(topic for topic, _ in topic_counts.most_common(3))
            total_posts = _count_matching_posts(posts, city, window_start, forecast_date)

            conn.execute(
                """
                INSERT OR REPLACE INTO daily_city_features
                (forecast_date, city, horizon_days, explicit_count, possible_count,
                 weak_count, max_score, avg_score, has_exact_date, has_exact_place,
                 has_call_to_action, has_organizer, independent_sources,
                 mention_growth_3d, topic_social_media_ban, topic_corruption,
                 topic_gen_z, topic_students, topic_government, topic_strike,
                 total_posts, total_signals, top_signal_ids, primary_topics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    forecast_date.isoformat(),
                    city,
                    horizon_days,
                    len(explicit),
                    len(possible),
                    len(weak),
                    max(scored) if scored else 0.0,
                    sum(scored) / len(scored) if scored else 0.0,
                    1 if any(row["has_exact_date"] for row in window_signals) else 0,
                    1 if any(row["has_exact_place"] for row in window_signals) else 0,
                    1 if any(row["has_call_to_action"] for row in window_signals) else 0,
                    1 if any(row["organizer"] for row in window_signals) else 0,
                    len(sources),
                    mention_growth,
                    topic_counts["social_media_ban"],
                    topic_counts["corruption"],
                    topic_counts["gen_z"],
                    topic_counts["students"],
                    topic_counts["government"],
                    topic_counts["strike"],
                    total_posts,
                    len(window_signals),
                    ",".join(str(row["signal_id"]) for row in top_signals),
                    primary_topics,
                ),
            )
            count += 1
    conn.commit()
    return count
