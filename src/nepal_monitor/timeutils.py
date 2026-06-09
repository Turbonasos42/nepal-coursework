from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterator


def parse_datetime(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        raise ValueError("empty datetime")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "T" not in text and len(text) == 10:
        return datetime.combine(date.fromisoformat(text), time.min)
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def parse_date(value: str) -> date:
    return date.fromisoformat((value or "").strip())


def date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def day_end(value: date) -> datetime:
    return datetime.combine(value, time(23, 59, 59))


def day_start(value: date) -> datetime:
    return datetime.combine(value, time.min)


def iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None
