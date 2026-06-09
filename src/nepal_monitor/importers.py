from __future__ import annotations

import csv
from hashlib import sha1
from pathlib import Path
import sqlite3
from typing import Iterable

from .constants import INPUT_CUTOFF
from .timeutils import parse_datetime


def _read_csv(path: str) -> Iterable[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {key: (value or "").strip() for key, value in row.items()}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha1("|".join(parts).encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _first_text(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name, "").strip()
        if value:
            return value
    return ""


def _parse_post_datetime(row: dict[str, str]):
    errors: list[Exception] = []
    for name in ("published_at", "created_at", "timestamp", "date", "scraped_at"):
        value = row.get(name, "").strip()
        if not value:
            continue
        try:
            return parse_datetime(value)
        except ValueError as exc:
            errors.append(exc)
    raise ValueError(f"could not parse post datetime from row: {row.get('post_id') or row.get('url') or row}")


def _normalize_post_row(row: dict[str, str]) -> dict[str, str]:
    text = _first_text(row, "text", "content", "message", "caption", "description", "body")
    platform = _first_text(row, "platform") or "unknown"
    source_name = _first_text(row, "source_name", "page_name", "account_name", "name") or "unknown"
    source_id = _first_text(row, "source_id", "page_id", "account_id")
    if not source_id and source_name != "unknown":
        source_id = _stable_id("source", platform, source_name)
    post_id = _first_text(row, "post_id", "id")
    if not post_id:
        post_id = _stable_id("post", platform, row.get("url", ""), source_name, text[:120])
    source_type = _first_text(row, "source_type")
    if not source_type and platform.lower() == "facebook":
        source_type = "public_page"
    return {
        **row,
        "post_id": post_id,
        "platform": platform,
        "source_id": source_id,
        "source_name": source_name,
        "source_type": source_type or "unknown",
        "language": _first_text(row, "language", "lang"),
        "city_hint": _first_text(row, "city_hint", "city", "place") or "Nepal",
        "text": text,
    }


def import_sources(conn: sqlite3.Connection, csv_path: str, replace: bool = True) -> int:
    if replace:
        conn.execute("DELETE FROM sources")
    count = 0
    for row in _read_csv(csv_path):
        conn.execute(
            """
            INSERT OR REPLACE INTO sources
            (source_id, platform, name, source_type, url, public, region, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["source_id"],
                row["platform"],
                row["name"],
                row["source_type"],
                row["url"],
                1 if row.get("public", "yes").lower() in {"yes", "true", "1"} else 0,
                row.get("region") or "Nepal",
                row.get("priority") or "medium",
            ),
        )
        count += 1
    conn.commit()
    return count


def import_posts(
    conn: sqlite3.Connection,
    csv_path: str,
    replace: bool = True,
    strict_cutoff: bool = True,
) -> int:
    if replace:
        conn.execute("DELETE FROM raw_posts")
    sources = {
        row["source_id"]: row
        for row in conn.execute("SELECT source_id, name, source_type, platform FROM sources")
    }
    count = 0
    for row in _read_csv(csv_path):
        row = _normalize_post_row(row)
        if not row["text"]:
            continue
        published_at = _parse_post_datetime(row)
        if strict_cutoff and published_at >= INPUT_CUTOFF:
            raise ValueError(
                f"input post {row.get('post_id')} is after cutoff {INPUT_CUTOFF.isoformat()}"
            )
        source = sources.get(row.get("source_id", ""))
        source_name = row.get("source_name") or (source["name"] if source else "unknown")
        source_type = row.get("source_type") or (source["source_type"] if source else "unknown")
        platform = row.get("platform") or (source["platform"] if source else "unknown")
        conn.execute(
            """
            INSERT OR REPLACE INTO raw_posts
            (post_id, platform, source_id, source_name, source_type, url, published_at,
             language, city_hint, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["post_id"],
                platform,
                row.get("source_id") or None,
                source_name,
                source_type,
                row.get("url") or "",
                published_at.isoformat(sep=" "),
                row.get("language") or "",
                row.get("city_hint") or "",
                row["text"],
            ),
        )
        count += 1
    conn.commit()
    return count


def import_ground_truth(conn: sqlite3.Connection, csv_path: str, replace: bool = True) -> int:
    if replace:
        conn.execute("DELETE FROM ground_truth_events")
    count = 0
    for row in _read_csv(csv_path):
        conn.execute(
            """
            INSERT OR REPLACE INTO ground_truth_events
            (event_id, event_date, city, event_type, description, source_url, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["event_id"],
                row["event_date"],
                row["city"],
                row["event_type"],
                row["description"],
                row["source_url"],
                1 if row.get("verified", "yes").lower() in {"yes", "true", "1"} else 0,
            ),
        )
        count += 1
    conn.commit()
    return count
