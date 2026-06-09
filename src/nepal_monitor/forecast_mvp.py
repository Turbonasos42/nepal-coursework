from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from hashlib import sha1, sha256
import json
import math
from pathlib import Path
import re
from typing import Iterable

from .constants import (
    CALL_TO_ACTION_KEYWORDS,
    DEFAULT_GROUND_TRUTH_CSV,
    FORECAST_CITIES,
    INPUT_CUTOFF,
    NATIONAL_CITY,
)
from .extractors import (
    classify_signal,
    contains_any,
    detect_topics,
    extract_action_date,
    extract_city_and_place,
    extract_organizer,
)
from .timeutils import date_range, parse_datetime


DEFAULT_POSTS_CSV = "data/platform_posts.csv"
DEFAULT_COMMENTS_CSV = "data/platform_comments.csv"
DEFAULT_LEXICON_CSV = "data/nepal_trigger_lexicon.csv"
DEFAULT_OUTPUT_DIR = "reports/forecast_mvp"
DEFAULT_FORECAST_START = date(2025, 7, 1)
DEFAULT_FORECAST_END = date(2025, 9, 7)

LEVEL_L4 = "L4_city_event_forecast"
LEVEL_L3 = "L3_city_risk_forecast"
LEVEL_L2 = "L2_national_risk_forecast"
LEVEL_L1 = "L1_trend_warning"
LEVEL_L0 = "L0_data_summary"

FORECAST_FIELDS = [
    "forecast_date",
    "city",
    "target_start_date",
    "target_end_date",
    "forecast_level",
    "risk_score_0_100",
    "probability",
    "risk_level",
    "coverage_grade",
    "fallback_reason",
    "predicted_event_type",
    "top_terms",
    "top_sources",
    "evidence_posts",
    "posts_3d",
    "signals_3d",
    "unique_sources_3d",
    "topic_growth_ratio",
    "post_growth_ratio",
    "engagement_sum_3d",
]

EVIDENCE_FIELDS = [
    "forecast_date",
    "city",
    "forecast_level",
    "post_id",
    "published_at",
    "source_name",
    "url",
    "risk_contribution",
    "topics",
    "matched_terms",
    "text_excerpt",
]

TIMELINE_FIELDS = [
    "forecast_date",
    "city",
    "risk_score_0_100",
    "risk_level",
    "forecast_level",
    "coverage_grade",
    "posts_3d",
    "signals_3d",
    "unique_sources_3d",
]

COURSE_LEVEL_ORDER = [LEVEL_L4, LEVEL_L3, LEVEL_L2, LEVEL_L1, LEVEL_L0]

TOPIC_MAP = {
    "censorship_social_media": "social_media_ban",
    "corruption_nepotism": "corruption",
    "youth_jobs_students": "gen_z",
    "government_accountability": "government",
    "mobilization_location": "mobilization",
    "anchored_english": "mobilization",
}

EXTRA_TOPIC_TERMS = {
    "social_media_ban": [
        "ban",
        "banned",
        "censorship",
        "vpn",
        "registration",
        "platform",
        "social media",
        "सामाजिक",
        "सञ्जाल",
        "संजाल",
        "प्रतिबन्ध",
        "پابندی",
        "سوشل میڈیا",
    ],
    "corruption": [
        "bhrashtachar",
        "bhrastachar",
        "natawad",
        "nepo",
        "भ्रष्टाचार",
        "नातावाद",
        "کرپشن",
    ],
    "gen_z": [
        "gen z",
        "genz",
        "youth",
        "yuwa",
        "student",
        "berojgari",
        "जेन जी",
        "युवा",
        "विद्यार्थी",
        "बेरोजगारी",
        "نوجوان",
    ],
    "government": [
        "oli",
        "kp oli",
        "prime minister",
        "resignation",
        "government",
        "ओली",
        "प्रधानमन्त्री",
        "राजीनामा",
        "حکومت",
    ],
    "mobilization": [
        "protest",
        "andolan",
        "aandolan",
        "birodh",
        "pradarshan",
        "julus",
        "maitighar",
        "baneshwor",
        "आन्दोलन",
        "विरोध",
        "प्रदर्शन",
        "احتجاج",
        "مظاہرہ",
    ],
}


@dataclass(frozen=True)
class LexiconTerm:
    topic: str
    term: str
    term_type: str
    normalized: str


@dataclass
class MvpPost:
    post_id: str
    platform: str
    source_name: str
    source_type: str
    url: str
    published_at: datetime
    text: str
    search_term: str
    search_type: str
    reactions: int = 0
    comments: int = 0
    shares: int = 0
    comment_rows: int = 0
    city: str = NATIONAL_CITY
    place: str | None = None
    action_date: date | None = None
    has_exact_date: bool = False
    has_exact_place: bool = False
    has_call_to_action: bool = False
    organizer: str | None = None
    signal_type: int = 0
    topics: set[str] = field(default_factory=set)
    matched_terms: set[str] = field(default_factory=set)

    @property
    def day(self) -> date:
        return self.published_at.date()

    @property
    def engagement(self) -> int:
        return max(0, self.reactions) + max(0, self.comments) + max(0, self.shares)

    @property
    def evidence_score(self) -> float:
        return (
            self.signal_type * 10.0
            + math.log1p(self.engagement)
            + min(self.comment_rows, 20) * 0.5
            + len(self.topics) * 1.5
        )


@dataclass
class Aggregate:
    city: str
    forecast_date: date
    target_start: date
    target_end: date
    posts_3d: list[MvpPost]
    baseline_posts: list[MvpPost]
    explicit_count: int
    possible_count: int
    weak_count: int
    signal_count: int
    unique_sources: int
    engagement_sum: int
    comment_rows_sum: int
    topic_counts: Counter
    term_counts: Counter
    post_growth_ratio: float
    topic_growth_ratio: float
    risk_score: float
    coverage_grade: str
    risk_level: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _first(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = (row.get(name) or "").strip()
        if value:
            return value
    return ""


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha1("|".join(parts).encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def file_fingerprint(path: str | Path) -> dict[str, str | int]:
    csv_path = Path(path)
    if not csv_path.exists():
        return {"path": str(csv_path), "exists": 0, "size_bytes": 0, "sha256": ""}
    digest = sha256()
    with csv_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = csv_path.stat()
    return {
        "path": str(csv_path),
        "exists": 1,
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "sha256": digest.hexdigest(),
    }


def parse_metric(value: str | int | float | None) -> int:
    if value is None:
        return 0
    text = str(value).strip().casefold()
    if not text:
        return 0
    translation = str.maketrans(
        "०१२३४५६७८۹۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "012345678901234567890123456789",
    )
    text = text.translate(translation)
    text = text.replace("\u00a0", "").replace(" ", "").replace(",", "")
    multiplier = 1
    if any(token in text for token in ("тыс", "тысяч", "тис", "हजार")) or "k" in text:
        multiplier = 1_000
    if any(token in text for token in ("млн", "миллион", "million")) or "m" in text:
        multiplier = 1_000_000
    match = re.search(r"(\d+(?:[.]\d+)?)", text)
    if not match:
        return 0
    return int(float(match.group(1)) * multiplier)


def parse_optional_datetime(row: dict[str, str]) -> datetime | None:
    for name in ("published_at_iso", "published_at", "created_at", "timestamp", "date"):
        value = (row.get(name) or "").strip()
        if not value:
            continue
        try:
            return parse_datetime(value)
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def load_lexicon(path: str | Path) -> list[LexiconTerm]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    terms: list[LexiconTerm] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            term = (row.get("term") or "").strip()
            if not term:
                continue
            terms.append(
                LexiconTerm(
                    topic=TOPIC_MAP.get((row.get("topic") or "").strip(), (row.get("topic") or "").strip()),
                    term=term,
                    term_type=(row.get("term_type") or "keyword").strip(),
                    normalized=_normalize(term),
                )
            )
    return terms


def load_comment_counts(path: str | Path) -> Counter:
    csv_path = Path(path)
    counts: Counter = Counter()
    if not csv_path.exists():
        return counts
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            post_id = (row.get("post_id") or "").strip()
            text = (row.get("comment_text") or "").strip()
            if post_id and text:
                counts[post_id] += 1
    return counts


def _detect_extended_topics(text: str, lexicon_terms: list[LexiconTerm]) -> tuple[set[str], set[str]]:
    normalized = _normalize(text)
    topics = set(detect_topics(text))
    matched_terms: set[str] = set()
    for topic, terms in EXTRA_TOPIC_TERMS.items():
        if any(term.casefold() in normalized for term in terms):
            topics.add(topic)
    for item in lexicon_terms:
        if not item.normalized:
            continue
        if item.term_type == "hashtag":
            found = item.normalized in normalized.replace(" ", "")
        else:
            found = item.normalized in normalized
        if found:
            topics.add(item.topic)
            matched_terms.add(item.term)
    return topics, matched_terms


def _make_post(row: dict[str, str], lexicon_terms: list[LexiconTerm], comment_counts: Counter) -> MvpPost | None:
    text = _first(row, "text", "content", "message", "caption", "description", "body")
    if not text:
        return None
    published = parse_optional_datetime(row)
    if not published:
        return None
    platform = _first(row, "platform") or "facebook"
    source_name = _first(row, "source_name", "page_name", "account_name", "name") or "unknown"
    source_type = _first(row, "source_type")
    if not source_type and platform.casefold() == "facebook":
        source_type = "public_page"
    search_term = _first(row, "search_term")
    search_type = _first(row, "search_type")
    url = _first(row, "url", "post_url", "link")
    post_id = _first(row, "post_id", "id") or _stable_id("post", platform, url, source_name, text[:160])
    city_hint = _first(row, "city_hint", "city", "place")
    city, place = extract_city_and_place(text, city_hint)
    action_date, has_exact_date = extract_action_date(text, published)
    topics, matched_terms = _detect_extended_topics(text, lexicon_terms)
    has_call = contains_any(text, CALL_TO_ACTION_KEYWORDS)
    organizer = extract_organizer(text, source_name, source_type or "unknown")
    signal_type = classify_signal(
        text=text,
        action_date=action_date,
        city=city,
        place=place,
        has_call=has_call,
        topics=sorted(topics),
        published_at=published,
    )
    return MvpPost(
        post_id=post_id,
        platform=platform,
        source_name=source_name,
        source_type=source_type or "unknown",
        url=url,
        published_at=published,
        text=text,
        search_term=search_term,
        search_type=search_type,
        reactions=parse_metric(_first(row, "reactions", "likes")),
        comments=parse_metric(_first(row, "comments", "comment_count")),
        shares=parse_metric(_first(row, "shares", "share_count")),
        comment_rows=int(comment_counts.get(post_id, 0)),
        city=city,
        place=place,
        action_date=action_date,
        has_exact_date=has_exact_date,
        has_exact_place=bool(place),
        has_call_to_action=has_call,
        organizer=organizer,
        signal_type=signal_type,
        topics=topics,
        matched_terms=matched_terms,
    )


def load_posts(
    posts_csv: str | Path,
    comments_csv: str | Path = DEFAULT_COMMENTS_CSV,
    lexicon_csv: str | Path = DEFAULT_LEXICON_CSV,
    extra_posts: Iterable[str | Path] = (),
    input_cutoff: datetime = INPUT_CUTOFF,
) -> list[MvpPost]:
    lexicon_terms = load_lexicon(lexicon_csv)
    comment_counts = load_comment_counts(comments_csv)
    paths = [Path(posts_csv), *[Path(path) for path in extra_posts]]
    posts_by_id: dict[str, MvpPost] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                post = _make_post(row, lexicon_terms, comment_counts)
                if not post or post.published_at >= input_cutoff:
                    continue
                if post.post_id not in posts_by_id:
                    posts_by_id[post.post_id] = post
    return sorted(posts_by_id.values(), key=lambda item: (item.published_at, item.post_id))


def _days_inclusive(start: date, end: date) -> int:
    return max(1, (end - start).days + 1)


def _is_horizon_relevant(post: MvpPost, target_start: date, target_end: date) -> bool:
    if not post.action_date:
        return True
    return target_start <= post.action_date <= target_end


def _coverage_grade(posts_3d: list[MvpPost], unique_sources: int, explicit_count: int, possible_count: int) -> str:
    if not posts_3d:
        return "E"
    if unique_sources >= 5 and len(posts_3d) >= 10 and (explicit_count or possible_count):
        return "A"
    if unique_sources >= 3 and len(posts_3d) >= 5:
        return "B"
    if unique_sources >= 1 and len(posts_3d) >= 2:
        return "C"
    return "D"


def _risk_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _aggregate(posts: list[MvpPost], city: str, forecast_date: date, horizon_days: int) -> Aggregate:
    target_start = forecast_date + timedelta(days=1)
    target_end = forecast_date + timedelta(days=horizon_days)
    latest_start = forecast_date - timedelta(days=2)
    baseline_start = forecast_date - timedelta(days=16)
    baseline_end = forecast_date - timedelta(days=3)

    if city == NATIONAL_CITY:
        scoped = [post for post in posts if post.day <= forecast_date]
    else:
        scoped = [post for post in posts if post.day <= forecast_date and post.city == city]

    posts_3d = [post for post in scoped if latest_start <= post.day <= forecast_date]
    baseline_posts = [post for post in scoped if baseline_start <= post.day <= baseline_end]
    signal_posts = [
        post
        for post in posts_3d
        if post.signal_type > 0 and _is_horizon_relevant(post, target_start, target_end)
    ]
    explicit_count = sum(1 for post in signal_posts if post.signal_type >= 4)
    possible_count = sum(1 for post in signal_posts if post.signal_type == 3)
    weak_count = sum(1 for post in signal_posts if post.signal_type in {1, 2})
    topic_counts: Counter = Counter(topic for post in posts_3d for topic in post.topics)
    baseline_topic_count = sum(len(post.topics) for post in baseline_posts)
    latest_topic_count = sum(topic_counts.values())
    term_counts: Counter = Counter(term for post in posts_3d for term in post.matched_terms)
    unique_sources = len({post.source_name for post in posts_3d if post.source_name})
    engagement_sum = sum(post.engagement for post in posts_3d)
    comment_rows_sum = sum(post.comment_rows for post in posts_3d)

    latest_daily = len(posts_3d) / 3.0
    baseline_daily = len(baseline_posts) / _days_inclusive(baseline_start, baseline_end)
    post_growth_ratio = (latest_daily + 0.5) / (baseline_daily + 0.5)
    latest_topic_daily = latest_topic_count / 3.0
    baseline_topic_daily = baseline_topic_count / _days_inclusive(baseline_start, baseline_end)
    topic_growth_ratio = (latest_topic_daily + 0.25) / (baseline_topic_daily + 0.25)

    mobilization_raw = (
        explicit_count * 0.8
        + possible_count * 0.35
        + weak_count * 0.1
        + (0.15 if any(post.has_call_to_action for post in signal_posts) else 0.0)
        + (0.1 if any(post.has_exact_date for post in signal_posts) else 0.0)
        + (0.1 if any(post.has_exact_place for post in signal_posts) else 0.0)
        + (0.1 if any(post.organizer for post in signal_posts) else 0.0)
    )
    mobilization_component = min(1.0, mobilization_raw) * 35.0
    topic_component = min(
        1.0,
        min(latest_topic_count, 10) / 10.0 * 0.5
        + max(0.0, topic_growth_ratio - 1.0) / 4.0 * 0.5,
    ) * 25.0
    anomaly_component = min(1.0, max(0.0, post_growth_ratio - 1.0) / 4.0) * 20.0
    diversity_component = min(1.0, unique_sources / 5.0) * 10.0
    engagement_component = min(
        1.0,
        math.log1p(engagement_sum + comment_rows_sum) / math.log1p(5000),
    ) * 10.0
    risk_score = round(
        mobilization_component
        + topic_component
        + anomaly_component
        + diversity_component
        + engagement_component,
        2,
    )
    coverage_grade = _coverage_grade(posts_3d, unique_sources, explicit_count, possible_count)
    return Aggregate(
        city=city,
        forecast_date=forecast_date,
        target_start=target_start,
        target_end=target_end,
        posts_3d=posts_3d,
        baseline_posts=baseline_posts,
        explicit_count=explicit_count,
        possible_count=possible_count,
        weak_count=weak_count,
        signal_count=len(signal_posts),
        unique_sources=unique_sources,
        engagement_sum=engagement_sum,
        comment_rows_sum=comment_rows_sum,
        topic_counts=topic_counts,
        term_counts=term_counts,
        post_growth_ratio=round(post_growth_ratio, 4),
        topic_growth_ratio=round(topic_growth_ratio, 4),
        risk_score=risk_score,
        coverage_grade=coverage_grade,
        risk_level=_risk_level(risk_score),
    )


def _has_national_forecast(aggregate: Aggregate) -> bool:
    return (
        aggregate.risk_score >= 30.0
        and (
            len(aggregate.posts_3d) >= 5
            or aggregate.signal_count >= 2
            or aggregate.topic_growth_ratio >= 1.5
        )
    )


def _predict_event_type(aggregate: Aggregate) -> str:
    topics = set(aggregate.topic_counts)
    if "strike" in topics:
        return "strike"
    if "government" in topics and ("social_media_ban" in topics or "mobilization" in topics):
        return "political_crisis"
    return "protest"


def _probability(score: float, level: str, coverage_grade: str) -> str:
    if level in {LEVEL_L1, LEVEL_L0} or coverage_grade in {"D", "E"}:
        return ""
    probability = min(0.95, max(0.05, 0.05 + score / 100.0 * 0.9))
    return f"{probability:.4f}"


def _top_csv(counter: Counter, limit: int = 5) -> str:
    return "; ".join(f"{item}:{count}" for item, count in counter.most_common(limit))


def _top_sources(posts: list[MvpPost], limit: int = 5) -> str:
    return _top_csv(Counter(post.source_name for post in posts if post.source_name), limit=limit)


def _evidence_posts(posts: list[MvpPost], limit: int = 5) -> list[MvpPost]:
    return sorted(posts, key=lambda post: (post.evidence_score, post.published_at), reverse=True)[:limit]


def _row_from_aggregate(
    city: str,
    aggregate: Aggregate,
    level: str,
    fallback_reason: str,
    predicted_event_type: str,
) -> dict[str, str | int | float]:
    evidence = _evidence_posts(aggregate.posts_3d)
    return {
        "forecast_date": aggregate.forecast_date.isoformat(),
        "city": city,
        "target_start_date": aggregate.target_start.isoformat(),
        "target_end_date": aggregate.target_end.isoformat(),
        "forecast_level": level,
        "risk_score_0_100": f"{aggregate.risk_score:.2f}",
        "probability": _probability(aggregate.risk_score, level, aggregate.coverage_grade),
        "risk_level": aggregate.risk_level,
        "coverage_grade": aggregate.coverage_grade,
        "fallback_reason": fallback_reason,
        "predicted_event_type": predicted_event_type,
        "top_terms": _top_csv(aggregate.term_counts or aggregate.topic_counts),
        "top_sources": _top_sources(aggregate.posts_3d),
        "evidence_posts": ";".join(post.post_id for post in evidence),
        "posts_3d": len(aggregate.posts_3d),
        "signals_3d": aggregate.signal_count,
        "unique_sources_3d": aggregate.unique_sources,
        "topic_growth_ratio": f"{aggregate.topic_growth_ratio:.4f}",
        "post_growth_ratio": f"{aggregate.post_growth_ratio:.4f}",
        "engagement_sum_3d": aggregate.engagement_sum,
    }


def _choose_forecast(city_aggregate: Aggregate, national_aggregate: Aggregate) -> tuple[Aggregate, str, str, str]:
    if city_aggregate.city != NATIONAL_CITY:
        strong_explicit_posts = [
            post
            for post in city_aggregate.posts_3d
            if post.signal_type >= 4
            and _is_horizon_relevant(post, city_aggregate.target_start, city_aggregate.target_end)
            and post.has_call_to_action
            and {"mobilization", "social_media_ban", "corruption", "government"} & post.topics
        ]
        if (
            city_aggregate.risk_score >= 45.0
            and strong_explicit_posts
            and (city_aggregate.unique_sources >= 2 or city_aggregate.coverage_grade in {"A", "B", "C"})
        ):
            return (
                city_aggregate,
                LEVEL_L4,
                "explicit city event evidence",
                _predict_event_type(city_aggregate),
            )
        if (
            city_aggregate.risk_score >= 25.0
            and (len(city_aggregate.posts_3d) >= 2 or city_aggregate.signal_count >= 1)
        ):
            return (
                city_aggregate,
                LEVEL_L3,
                "city evidence present but event type/date incomplete",
                "",
            )
        if _has_national_forecast(national_aggregate):
            return (
                national_aggregate,
                LEVEL_L2,
                "city evidence below threshold; using national risk",
                "",
            )

    if _has_national_forecast(national_aggregate):
        return (
            national_aggregate,
            LEVEL_L2,
            "national signals without reliable city-level localization",
            "",
        )
    if national_aggregate.risk_score > 0 or national_aggregate.posts_3d:
        return (
            national_aggregate,
            LEVEL_L1,
            "insufficient forecast evidence; reporting trend warning",
            "",
        )
    return (
        national_aggregate,
        LEVEL_L0,
        "insufficient signal volume before forecast date",
        "",
    )


def build_forecasts(
    posts: list[MvpPost],
    forecast_start: date = DEFAULT_FORECAST_START,
    forecast_end: date = DEFAULT_FORECAST_END,
    horizon_days: int = 3,
    cities: Iterable[str] | None = None,
) -> tuple[list[dict[str, str | int | float]], list[dict[str, str | float]]]:
    forecast_rows: list[dict[str, str | int | float]] = []
    evidence_rows: list[dict[str, str | float]] = []
    city_list = list(cities or [*FORECAST_CITIES, NATIONAL_CITY])
    if NATIONAL_CITY not in city_list:
        city_list.append(NATIONAL_CITY)

    for forecast_date in date_range(forecast_start, forecast_end):
        national_aggregate = _aggregate(posts, NATIONAL_CITY, forecast_date, horizon_days)
        for city in city_list:
            city_aggregate = national_aggregate if city == NATIONAL_CITY else _aggregate(
                posts, city, forecast_date, horizon_days
            )
            selected, level, reason, predicted_type = _choose_forecast(city_aggregate, national_aggregate)
            row = _row_from_aggregate(city, selected, level, reason, predicted_type)
            forecast_rows.append(row)
            for post in _evidence_posts(selected.posts_3d):
                evidence_rows.append(
                    {
                        "forecast_date": selected.forecast_date.isoformat(),
                        "city": city,
                        "forecast_level": level,
                        "post_id": post.post_id,
                        "published_at": post.published_at.isoformat(sep=" "),
                        "source_name": post.source_name,
                        "url": post.url,
                        "risk_contribution": f"{post.evidence_score:.2f}",
                        "topics": ",".join(sorted(post.topics)),
                        "matched_terms": ";".join(sorted(post.matched_terms)),
                        "text_excerpt": re.sub(r"\s+", " ", post.text)[:300],
                    }
                )
    return forecast_rows, evidence_rows


def load_ground_truth(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def evaluate_mvp_forecasts(
    forecast_rows: list[dict[str, str | int | float]],
    ground_truth_rows: list[dict[str, str]],
) -> dict[str, str | int | float]:
    truths = [
        row
        for row in ground_truth_rows
        if (row.get("verified") or "yes").casefold() in {"yes", "true", "1"}
    ]
    evaluated = [
        row
        for row in forecast_rows
        if row["forecast_level"] in {LEVEL_L4, LEVEL_L3}
        or (row["forecast_level"] == LEVEL_L2 and row["city"] == NATIONAL_CITY)
    ]
    tp = fp = fn = tn = 0
    brier_values: list[float] = []
    for row in evaluated:
        city = str(row["city"])
        start = str(row["target_start_date"])
        end = str(row["target_end_date"])
        actual = any(
            start <= truth.get("event_date", "") <= end
            and (city == NATIONAL_CITY or truth.get("city") == city)
            for truth in truths
        )
        predicted = str(row["risk_level"]) in {"medium", "high"}
        probability_text = str(row.get("probability") or "")
        if probability_text:
            brier_values.append((float(probability_text) - (1.0 if actual else 0.0)) ** 2)
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1

    detected_events = 0
    first_warning_leads: list[int] = []
    for truth in truths:
        event_date_text = truth.get("event_date", "")
        if not event_date_text:
            continue
        event_day = date.fromisoformat(event_date_text)
        matches = [
            row
            for row in evaluated
            if str(row["risk_level"]) in {"medium", "high"}
            and str(row["forecast_date"]) < event_date_text
            and str(row["target_start_date"]) <= event_date_text <= str(row["target_end_date"])
            and (row["city"] == NATIONAL_CITY or row["city"] == truth.get("city"))
        ]
        if matches:
            detected_events += 1
            earliest = min(date.fromisoformat(str(row["forecast_date"])) for row in matches)
            first_warning_leads.append((event_day - earliest).days)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "forecast_rows_total": len(forecast_rows),
        "forecast_rows_evaluated": len(evaluated),
        "ground_truth_events": len(truths),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "brier_score": round(sum(brier_values) / len(brier_values), 4) if brier_values else "",
        "events_detected": detected_events,
        "events_missed": max(0, len(truths) - detected_events),
        "event_recall": round(detected_events / len(truths), 4) if truths else 0.0,
        "average_first_warning_lead_days": (
            round(sum(first_warning_leads) / len(first_warning_leads), 2)
            if first_warning_leads
            else ""
        ),
    }


def select_course_rows(
    forecast_rows: list[dict[str, str | int | float]],
) -> tuple[str, list[dict[str, str | int | float]], str]:
    for level in COURSE_LEVEL_ORDER:
        if level == LEVEL_L2:
            rows = [
                row
                for row in forecast_rows
                if row["forecast_level"] == level and row["city"] == NATIONAL_CITY
            ]
        else:
            rows = [row for row in forecast_rows if row["forecast_level"] == level]
        active_rows = [row for row in rows if row["risk_level"] in {"medium", "high"}]
        if active_rows:
            reason = "selected as the highest forecast level with active medium/high risk rows"
            return level, rows, reason
    rows = [row for row in forecast_rows if row["city"] == NATIONAL_CITY]
    return LEVEL_L0, rows, "selected national data summary because no active forecast level was available"


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_metrics(path: Path, metrics: dict[str, str | int | float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            writer.writerow([key, value])


def _course_summary_text(
    selected_level: str,
    selected_rows: list[dict[str, str | int | float]],
    selection_reason: str,
    metrics: dict[str, str | int | float],
    output_paths: dict[str, Path],
) -> str:
    risk_levels = Counter(str(row["risk_level"]) for row in selected_rows)
    top_rows = sorted(
        selected_rows,
        key=lambda row: float(row["risk_score_0_100"]),
        reverse=True,
    )[:12]
    first_warning = next(
        (
            row
            for row in sorted(selected_rows, key=lambda item: str(item["forecast_date"]))
            if str(row["risk_level"]) in {"medium", "high"}
        ),
        None,
    )
    lines = [
        "# Course Forecast Summary",
        "",
        f"Selected analysis level: `{selected_level}`.",
        f"Selection rule: {selection_reason}.",
        "",
        "This report uses one fixed working level for the coursework presentation. Diagnostic model-selection details are kept out of this course summary.",
        "",
        "## Risk Distribution",
        f"- high: {risk_levels['high']}",
        f"- medium: {risk_levels['medium']}",
        f"- low: {risk_levels['low']}",
        f"- none: {risk_levels['none']}",
    ]
    if first_warning:
        lines.extend(
            [
                "",
                "## First Medium/High Warning",
                (
                    f"- {first_warning['forecast_date']} {first_warning['city']} "
                    f"risk={first_warning['risk_score_0_100']} "
                    f"target={first_warning['target_start_date']}..{first_warning['target_end_date']}"
                ),
            ]
        )
    lines.extend(["", "## Backtest Metrics"])
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Highest Risk Rows"])
    for row in top_rows:
        lines.append(
            (
                f"- {row['forecast_date']} {row['city']}: "
                f"risk={row['risk_score_0_100']} level={row['risk_level']} "
                f"terms={row['top_terms']}"
            )
        )
    lines.extend(
        [
            "",
            "## Course Files",
            f"- course_forecast_daily: {output_paths['course_forecast_daily']}",
            f"- course_top_evidence: {output_paths['course_top_evidence']}",
            f"- course_backtest_metrics: {output_paths['course_backtest_metrics']}",
            f"- course_summary: {output_paths['course_summary']}",
            f"- data_needed: {output_paths['data_needed']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _data_needed_text(selected_level: str) -> str:
    return (
        "# Data Needed For Stronger Analysis\n\n"
        f"Current working level selected for coursework: `{selected_level}`.\n\n"
        "## Highest Priority\n"
        "- Verified pre-event announcement posts from public pages/groups between 2025-08-25 and 2025-09-07: URL, timestamp, page name, city/place, announced date/time, screenshot or archive.\n"
        "- A city/date ground-truth table for both event and non-event days: Kathmandu, Itahari, Dharan, Pokhara, Biratnagar, Lalitpur, Nepal-level; include source URL and event type.\n"
        "- Negative examples: dates and cities where discussion was high but no protest happened. This is required to reduce false positives.\n"
        "- Local news before 2025-09-08 from Kathmandu Post, Nepali Times, Republica, Onlinekhabar, AP/Reuters where available: social media ban, corruption, Gen Z, police/security, government statements.\n\n"
        "## Useful But Optional\n"
        "- ACLED export for Nepal around 2025-07-01..2025-09-15 to validate protest/riot/strategic-development events.\n"
        "- GDELT/RSS article exports for the same dates, using only items published before the forecast date.\n"
        "- Public Telegram/Reddit/X links only when they are public and timestamped; no private chats or closed groups.\n"
        "- Source metadata: public page type, likely location, language, whether it is media/civil society/student/youth group.\n\n"
        "## Why This Is Needed\n"
        "- The current Facebook search dataset is broad and query-biased. Search terms help collection, but should not be treated as evidence.\n"
        "- City-event forecasting needs explicit location/date calls. Without those, the defensible analysis becomes national risk or trend analysis.\n"
        "- Ground truth needs non-event days, not only protest days, otherwise precision cannot be evaluated honestly.\n"
    )


def _summary_text(
    posts: list[MvpPost],
    forecast_rows: list[dict[str, str | int | float]],
    metrics: dict[str, str | int | float],
    output_paths: dict[str, Path],
    input_cutoff: datetime,
) -> str:
    levels = Counter(str(row["forecast_level"]) for row in forecast_rows)
    risk_levels = Counter(str(row["risk_level"]) for row in forecast_rows)
    date_min = min((post.day for post in posts), default=None)
    date_max = max((post.day for post in posts), default=None)
    top_rows = sorted(
        forecast_rows,
        key=lambda row: float(row["risk_score_0_100"]),
        reverse=True,
    )[:10]
    first_medium = next(
        (
            row
            for row in sorted(forecast_rows, key=lambda item: str(item["forecast_date"]))
            if str(row["risk_level"]) in {"medium", "high"}
        ),
        None,
    )
    lines = [
        "# Facebook Forecast MVP",
        "",
        "## Data",
        f"- Posts used before cutoff: {len(posts)}",
        f"- Input date range: {date_min or ''} .. {date_max or ''}",
        f"- Input cutoff: {input_cutoff.isoformat(sep=' ')}",
        "",
        "## Forecast Levels",
    ]
    for level in (LEVEL_L4, LEVEL_L3, LEVEL_L2, LEVEL_L1, LEVEL_L0):
        lines.append(f"- {level}: {levels[level]}")
    lines.extend(
        [
            "",
            "## Risk Levels",
            f"- high: {risk_levels['high']}",
            f"- medium: {risk_levels['medium']}",
            f"- low: {risk_levels['low']}",
            f"- none: {risk_levels['none']}",
            "",
            "## Backtest Metrics",
        ]
    )
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    if first_medium:
        lines.extend(
            [
                "",
                "## First Medium/High Warning",
                (
                    f"- {first_medium['forecast_date']} {first_medium['city']} "
                    f"{first_medium['forecast_level']} risk={first_medium['risk_score_0_100']} "
                    f"reason={first_medium['fallback_reason']}"
                ),
            ]
        )
    lines.extend(["", "## Top Forecast Rows"])
    for row in top_rows:
        lines.append(
            (
                f"- {row['forecast_date']} {row['city']}: "
                f"{row['forecast_level']} risk={row['risk_score_0_100']} "
                f"terms={row['top_terms']}"
            )
        )
    lines.extend(
        [
            "",
            "## Method Note",
            "- This is an explainable historical replay, not a production-grade protest prediction system.",
            "- L4/L3/L2 are forecast levels. L1/L0 are fallback evidence summaries when forecast confidence is not defensible.",
            "- Posts at or after the input cutoff are excluded from forecast inputs to avoid leakage.",
            "",
            "## Outputs",
        ]
    )
    for name, path in output_paths.items():
        lines.append(f"- {name}: {path}")
    return "\n".join(lines) + "\n"


def run_mvp_forecast(
    posts_csv: str = DEFAULT_POSTS_CSV,
    comments_csv: str = DEFAULT_COMMENTS_CSV,
    lexicon_csv: str = DEFAULT_LEXICON_CSV,
    ground_truth_csv: str = DEFAULT_GROUND_TRUTH_CSV,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    forecast_start: date = DEFAULT_FORECAST_START,
    forecast_end: date = DEFAULT_FORECAST_END,
    input_cutoff: datetime = INPUT_CUTOFF,
    horizon_days: int = 3,
    extra_posts: Iterable[str] = (),
) -> dict[str, Path | int | dict[str, str | int | float]]:
    raw_fingerprints_before = {
        "posts_csv": file_fingerprint(posts_csv),
        "comments_csv": file_fingerprint(comments_csv),
        "lexicon_csv": file_fingerprint(lexicon_csv),
        "ground_truth_csv": file_fingerprint(ground_truth_csv),
        "extra_posts": [file_fingerprint(path) for path in extra_posts],
    }
    posts = load_posts(
        posts_csv=posts_csv,
        comments_csv=comments_csv,
        lexicon_csv=lexicon_csv,
        extra_posts=extra_posts,
        input_cutoff=input_cutoff,
    )
    forecast_rows, evidence_rows = build_forecasts(
        posts=posts,
        forecast_start=forecast_start,
        forecast_end=forecast_end,
        horizon_days=horizon_days,
    )
    ground_truth_rows = load_ground_truth(ground_truth_csv)
    metrics = evaluate_mvp_forecasts(forecast_rows, ground_truth_rows)
    output_path = Path(output_dir)
    output_paths = {
        "forecast_daily": output_path / "forecast_daily.csv",
        "risk_timeline": output_path / "risk_timeline.csv",
        "top_evidence": output_path / "top_evidence.csv",
        "backtest_metrics": output_path / "backtest_metrics.csv",
        "summary": output_path / "summary.md",
        "course_forecast_daily": output_path / "course_forecast_daily.csv",
        "course_top_evidence": output_path / "course_top_evidence.csv",
        "course_backtest_metrics": output_path / "course_backtest_metrics.csv",
        "course_summary": output_path / "course_summary.md",
        "data_needed": output_path / "data_needed.md",
    }
    selected_level, selected_rows, selection_reason = select_course_rows(forecast_rows)
    selected_row_keys = {
        (str(row["forecast_date"]), str(row["city"]), str(row["forecast_level"]))
        for row in selected_rows
    }
    course_evidence_rows = [
        row
        for row in evidence_rows
        if (str(row["forecast_date"]), str(row["city"]), str(row["forecast_level"]))
        in selected_row_keys
    ]
    course_metrics = evaluate_mvp_forecasts(selected_rows, ground_truth_rows)
    _write_csv(output_paths["forecast_daily"], forecast_rows, FORECAST_FIELDS)
    _write_csv(output_paths["course_forecast_daily"], selected_rows, FORECAST_FIELDS)
    _write_csv(
        output_paths["risk_timeline"],
        [{key: row[key] for key in TIMELINE_FIELDS} for row in forecast_rows],
        TIMELINE_FIELDS,
    )
    _write_csv(output_paths["top_evidence"], evidence_rows, EVIDENCE_FIELDS)
    _write_csv(output_paths["course_top_evidence"], course_evidence_rows, EVIDENCE_FIELDS)
    _write_metrics(output_paths["backtest_metrics"], metrics)
    _write_metrics(output_paths["course_backtest_metrics"], course_metrics)
    output_paths["summary"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["summary"].write_text(
        _summary_text(posts, forecast_rows, metrics, output_paths, input_cutoff),
        encoding="utf-8",
    )
    output_paths["course_summary"].write_text(
        _course_summary_text(selected_level, selected_rows, selection_reason, course_metrics, output_paths),
        encoding="utf-8",
    )
    output_paths["data_needed"].write_text(_data_needed_text(selected_level), encoding="utf-8")
    manifest = {
        "posts_used": len(posts),
        "forecast_rows": len(forecast_rows),
        "selected_course_level": selected_level,
        "selected_course_rows": len(selected_rows),
        "metrics": metrics,
        "course_metrics": course_metrics,
        "raw_inputs_before": raw_fingerprints_before,
        "raw_inputs_after": {
            "posts_csv": file_fingerprint(posts_csv),
            "comments_csv": file_fingerprint(comments_csv),
            "lexicon_csv": file_fingerprint(lexicon_csv),
            "ground_truth_csv": file_fingerprint(ground_truth_csv),
            "extra_posts": [file_fingerprint(path) for path in extra_posts],
        },
        "outputs": {key: str(path) for key, path in output_paths.items()},
    }
    (output_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "posts_used": len(posts),
        "forecast_rows": len(forecast_rows),
        "metrics": metrics,
        **output_paths,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an explainable Facebook forecast MVP with confidence downgrade levels.",
    )
    parser.add_argument("--posts", default=DEFAULT_POSTS_CSV)
    parser.add_argument("--comments", default=DEFAULT_COMMENTS_CSV)
    parser.add_argument("--lexicon", default=DEFAULT_LEXICON_CSV)
    parser.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH_CSV)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--forecast-start", default=DEFAULT_FORECAST_START.isoformat())
    parser.add_argument("--forecast-end", default=DEFAULT_FORECAST_END.isoformat())
    parser.add_argument("--input-cutoff", default=INPUT_CUTOFF.isoformat())
    parser.add_argument("--horizon-days", type=int, default=3)
    parser.add_argument("--extra-posts", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_mvp_forecast(
        posts_csv=args.posts,
        comments_csv=args.comments,
        lexicon_csv=args.lexicon,
        ground_truth_csv=args.ground_truth,
        output_dir=args.output_dir,
        forecast_start=date.fromisoformat(args.forecast_start),
        forecast_end=date.fromisoformat(args.forecast_end),
        input_cutoff=parse_datetime(args.input_cutoff),
        horizon_days=args.horizon_days,
        extra_posts=args.extra_posts,
    )
    print(f"posts used: {result['posts_used']}")
    print(f"forecast rows: {result['forecast_rows']}")
    print(f"summary: {result['summary']}")
