from __future__ import annotations

from datetime import date, datetime, timedelta
import re
import sqlite3

from .constants import (
    ACTION_KEYWORDS,
    CALL_TO_ACTION_KEYWORDS,
    CITY_ALIASES,
    DATE_KEYWORDS,
    MONTHS,
    NATIONAL_CITY,
    PLACE_ALIASES,
    TOPIC_KEYWORDS,
    WEEKDAYS,
)
from .timeutils import parse_datetime


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def contains_any(text: str, keywords: list[str]) -> bool:
    normalized = _norm(text)
    return any(keyword.lower() in normalized for keyword in keywords)


def detect_topics(text: str) -> list[str]:
    normalized = _norm(text)
    topics: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            topics.append(topic)
    return topics


def extract_city_and_place(text: str, city_hint: str | None = None) -> tuple[str, str | None]:
    normalized = _norm(text)
    hint = _norm(city_hint or "")
    for alias, (city, place) in PLACE_ALIASES.items():
        if alias in normalized:
            return city, place
    for alias, city in CITY_ALIASES.items():
        if alias in normalized:
            return city, None
    if hint:
        if hint in CITY_ALIASES:
            return CITY_ALIASES[hint], None
        return city_hint or NATIONAL_CITY, None
    return NATIONAL_CITY, None


def extract_action_date(text: str, published_at: datetime) -> tuple[date | None, bool]:
    normalized = _norm(text)

    def safe_date(year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    iso_match = re.search(r"\b(2025|2026)-(\d{1,2})-(\d{1,2})\b", normalized)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        parsed = safe_date(year, month, day)
        if parsed:
            return parsed, True

    month_day = re.search(
        r"\b("
        + "|".join(re.escape(name) for name in MONTHS)
        + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b",
        normalized,
    )
    if month_day:
        month_name, day_text = month_day.groups()
        parsed = safe_date(published_at.year, MONTHS[month_name], int(day_text))
        if parsed:
            return parsed, True

    day_month = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("
        + "|".join(re.escape(name) for name in MONTHS)
        + r")\.?\b",
        normalized,
    )
    if day_month:
        day_text, month_name = day_month.groups()
        parsed = safe_date(published_at.year, MONTHS[month_name], int(day_text))
        if parsed:
            return parsed, True

    for keyword, offset in sorted(DATE_KEYWORDS.items(), key=lambda item: -len(item[0])):
        if keyword in normalized:
            return published_at.date() + timedelta(days=offset), True

    for weekday, index in WEEKDAYS.items():
        if re.search(rf"\b(this\s+|next\s+)?{weekday}\b", normalized):
            delta = index - published_at.weekday()
            if delta <= 0:
                delta += 7
            return published_at.date() + timedelta(days=delta), True

    return None, False


def extract_action_time(text: str) -> str | None:
    normalized = _norm(text)
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.m\.|p\.m\.|am|pm)\b", normalized)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or "0")
        suffix = match.group(3).replace(".", "")
        if suffix == "pm" and hour < 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", normalized)
    if match:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    return None


def extract_organizer(text: str, source_name: str, source_type: str) -> str | None:
    normalized_type = _norm(source_type)
    if normalized_type in {
        "youth group",
        "student organization",
        "civil society",
        "party youth wing",
        "public channel",
    }:
        return source_name

    match = re.search(r"(?:organized by|hosted by|called by)\s+([A-Za-z0-9 .'-]{3,80})", text)
    if match:
        return match.group(1).strip(" .")

    if re.search(r"\bgen[- ]?z\b", _norm(text)):
        return "Gen Z organizers"
    return None


def classify_signal(
    text: str,
    action_date: date | None,
    city: str,
    place: str | None,
    has_call: bool,
    topics: list[str],
    published_at: datetime,
) -> int:
    has_action = contains_any(text, ACTION_KEYWORDS)
    if action_date and action_date < published_at.date():
        return 0
    if action_date and city and (place or city != NATIONAL_CITY) and (has_call or has_action):
        return 4
    if has_call and (city != NATIONAL_CITY or topics):
        return 3
    if has_action and topics:
        return 3
    if topics and (has_action or "social_media_ban" in topics or "corruption" in topics):
        return 2
    if topics:
        return 1
    return 0


def extract_one(row: sqlite3.Row) -> dict[str, object]:
    text = row["text"]
    published_at = parse_datetime(row["published_at"])
    city, place = extract_city_and_place(text, row["city_hint"])
    action_date, has_exact_date = extract_action_date(text, published_at)
    action_time = extract_action_time(text)
    topics = detect_topics(text)
    has_call = contains_any(text, CALL_TO_ACTION_KEYWORDS)
    organizer = extract_organizer(text, row["source_name"], row["source_type"])
    signal_type = classify_signal(
        text=text,
        action_date=action_date,
        city=city,
        place=place,
        has_call=has_call,
        topics=topics,
        published_at=published_at,
    )
    lead_time_hours = None
    if action_date:
        action_dt = datetime.combine(action_date, datetime.min.time())
        if action_time:
            hour, minute = [int(part) for part in action_time.split(":", 1)]
            action_dt = action_dt.replace(hour=hour, minute=minute)
        lead_time_hours = (action_dt - published_at).total_seconds() / 3600.0

    return {
        "post_id": row["post_id"],
        "platform": row["platform"],
        "source_id": row["source_id"],
        "source_name": row["source_name"],
        "published_at": row["published_at"],
        "city": city,
        "place": place,
        "action_date": action_date.isoformat() if action_date else None,
        "action_time": action_time,
        "organizer": organizer,
        "topic": ",".join(topics),
        "target_audience": "students/youth" if {"gen_z", "students"} & set(topics) else "",
        "has_call_to_action": 1 if has_call else 0,
        "has_exact_date": 1 if has_exact_date else 0,
        "has_exact_place": 1 if place else 0,
        "signal_type": signal_type,
        "lead_time_hours": lead_time_hours,
        "evidence": text[:240].replace("\n", " "),
    }


def extract_signals(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM signals")
    rows = conn.execute(
        """
        SELECT post_id, platform, source_id, source_name, source_type, published_at,
               language, city_hint, text
        FROM raw_posts
        ORDER BY published_at, post_id
        """
    ).fetchall()
    count = 0
    for row in rows:
        signal = extract_one(row)
        conn.execute(
            """
            INSERT INTO signals
            (post_id, platform, source_id, source_name, published_at, city, place,
             action_date, action_time, organizer, topic, target_audience,
             has_call_to_action, has_exact_date, has_exact_place, signal_type,
             lead_time_hours, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal["post_id"],
                signal["platform"],
                signal["source_id"],
                signal["source_name"],
                signal["published_at"],
                signal["city"],
                signal["place"],
                signal["action_date"],
                signal["action_time"],
                signal["organizer"],
                signal["topic"],
                signal["target_audience"],
                signal["has_call_to_action"],
                signal["has_exact_date"],
                signal["has_exact_place"],
                signal["signal_type"],
                signal["lead_time_hours"],
                signal["evidence"],
            ),
        )
        count += 1
    conn.commit()
    return count
