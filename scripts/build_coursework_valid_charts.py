from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "forecast_mvp" / "course_valid_charts"
CRITERIA_CSV = ROOT / "reports" / "forecast_mvp" / "model_diagnostics" / "criteria_growth_timeseries.csv"
COMMENTS_CSV = ROOT / "reports" / "forecast_mvp" / "comment_activity" / "posts_with_comments_daily.csv"
AUDIT_CSV = ROOT / "data" / "derived" / "external_pre_event_sources_audit.csv"
EVIDENCE_CSV = ROOT / "reports" / "forecast_mvp" / "course_top_evidence.csv"


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titlesize": 18,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.dpi": 150,
            "savefig.dpi": 220,
        }
    )


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{stem}.png", bbox_inches="tight")
    fig.savefig(output_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def load_criteria(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["day"] = pd.to_datetime(df["day"])
    return df


def load_comments(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["day"] = pd.to_datetime(df["day"])
    return df


def load_audit(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_evidence(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def add_key_markers(ax: plt.Axes) -> None:
    markers = [
        (pd.Timestamp("2025-08-21"), "Aug peak", "#6b7280"),
        (pd.Timestamp("2025-09-04"), "4 Sep", "#ea580c"),
        (pd.Timestamp("2025-09-07"), "7 Sep", "#dc2626"),
        (pd.Timestamp("2025-09-08"), "8 Sep", "#111827"),
    ]
    ylim = ax.get_ylim()
    for day, label, color in markers:
        ax.axvline(day, color=color, linewidth=1.3, linestyle="--", alpha=0.7)
        ax.text(day, ylim[1] * 0.97, label, rotation=90, va="top", ha="right", fontsize=9, color=color)


def format_dates(ax: plt.Axes) -> None:
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.tick_params(axis="x", rotation=35)


def build_signal_components(criteria: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    components = [
        ("social_media_ban", "Social media ban", "#ef4444"),
        ("grievance", "Grievance", "#f59e0b"),
        ("mobilization", "Mobilization", "#2563eb"),
        ("government", "Government", "#10b981"),
    ]
    ax.stackplot(
        criteria["day"],
        *[criteria[column] for column, _label, _color in components],
        labels=[label for _column, label, _color in components],
        colors=[color for _column, _label, color in components],
        alpha=0.85,
    )
    ax.set_title("Signal Components in Pre-Event Data")
    ax.set_ylabel("3-day signal count")
    ax.set_xlabel("Date")
    add_key_markers(ax)
    format_dates(ax)
    ax.legend(loc="upper left", ncol=2, frameon=True)
    ax.text(
        0.01,
        -0.22,
        "Built from reports/forecast_mvp/model_diagnostics/criteria_growth_timeseries.csv, which is derived from data/platform_posts.csv, data/platform_comments.csv and data/derived/external_pre_event_posts.csv.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475467",
    )
    save_figure(fig, output_dir, "01_signal_components_area")


def build_sources_vs_specificity(criteria: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    ax.bar(criteria["day"], criteria["unique_sources"], width=0.9, color="#cbd5e1", label="Unique sources")
    ax.set_ylabel("Unique sources in 3-day window")
    ax.set_xlabel("Date")
    ax2 = ax.twinx()
    ax2.plot(criteria["day"], criteria["explicit_event_details"], color="#dc2626", linewidth=2.6, label="Explicit event details")
    ax2.plot(criteria["day"], criteria["exact_date_mentions"], color="#7c3aed", linewidth=2.0, linestyle="--", label="Exact date mentions")
    ax2.plot(criteria["day"], criteria["exact_place_mentions"], color="#0f766e", linewidth=2.0, linestyle=":", label="Exact place mentions")
    ax2.set_ylabel("Specific evidence count")
    add_key_markers(ax)
    format_dates(ax)
    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left", ncol=2, frameon=True)
    ax.set_title("Source Diversity vs Event Specificity")
    ax.text(
        0.01,
        -0.22,
        "This chart separates two different questions: how many distinct sources were present, and when the data started to contain exact place/date/event details.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475467",
    )
    save_figure(fig, output_dir, "02_sources_vs_specificity")


def build_comment_coverage(comments: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    ax.fill_between(
        comments["day"],
        comments["posts_with_parsed_comments"],
        color="#dbeafe",
        alpha=0.8,
        label="Posts with parsed comments",
    )
    ax.plot(comments["day"], comments["posts_with_parsed_comments"], color="#2563eb", linewidth=2.4)
    ax.set_ylabel("Posts with parsed comments")
    ax.set_xlabel("Date")
    ax2 = ax.twinx()
    ax2.plot(
        comments["day"],
        comments["commented_post_share"] * 100.0,
        color="#dc2626",
        linewidth=2.5,
        label="Commented-post share, %",
    )
    ax2.set_ylabel("Commented-post share, %")
    add_key_markers(ax)
    format_dates(ax)
    ax.set_title("Comment Coverage in Collected Facebook Data")
    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left", frameon=True)
    ax.text(
        0.01,
        -0.22,
        "Built directly from reports/forecast_mvp/comment_activity/posts_with_comments_daily.csv, which is derived from the raw data/platform_posts.csv and data/platform_comments.csv files.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475467",
    )
    save_figure(fig, output_dir, "03_comment_coverage")


def build_external_audit(audit: pd.DataFrame, output_dir: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.2, 6.1), gridspec_kw={"width_ratios": [1.0, 1.35]})
    status_counts = audit["status"].value_counts().rename_axis("status").reset_index(name="count")
    ax1.pie(
        status_counts["count"],
        labels=status_counts["status"],
        colors=["#2563eb", "#cbd5e1"],
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 11},
    )
    ax1.set_title("External Source Audit")

    included = audit.loc[audit["status"] == "included"].copy()
    domains = (
        included["domain"]
        .fillna("unknown")
        .value_counts()
        .head(10)
        .sort_values(ascending=True)
        .rename_axis("domain")
        .reset_index(name="count")
    )
    ax2.barh(domains["domain"], domains["count"], color="#0f766e")
    ax2.set_title("Top Included Pre-Event Domains")
    ax2.set_xlabel("Included rows")
    for index, value in enumerate(domains["count"]):
        ax2.text(value + 0.15, index, str(value), va="center", fontsize=10, color="#0f172a")
    fig.text(
        0.02,
        0.02,
        "Built from data/derived/external_pre_event_sources_audit.csv. The chart shows the real included/excluded split after cutoff filtering and the domains that actually entered the pre-event dataset.",
        fontsize=9,
        color="#475467",
    )
    save_figure(fig, output_dir, "04_external_source_audit")


def build_top_evidence(evidence: pd.DataFrame, output_dir: Path) -> None:
    evidence = evidence.copy().sort_values("risk_contribution", ascending=True)
    evidence["display_label"] = evidence.apply(
        lambda row: f"{row['source_name']} [{str(row['post_id'])[:6]}]",
        axis=1,
    )
    fig, ax = plt.subplots(figsize=(13.2, 6.4))
    bars = ax.barh(evidence["display_label"], evidence["risk_contribution"], color="#7c3aed")
    ax.set_title("Top Evidence Posts for the 7 Sep Kathmandu Forecast")
    ax.set_xlabel("Risk contribution")
    ax.set_ylabel("Source")
    for bar, post_id in zip(bars, evidence["post_id"]):
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height() / 2, f"{width:.2f}", va="center", fontsize=10, color="#111827")
        ax.text(0.4, bar.get_y() + bar.get_height() / 2, post_id[:8], va="center", fontsize=9, color="#fafafa")
    ax.text(
        0.01,
        -0.22,
        "All five bars come from reports/forecast_mvp/course_top_evidence.csv and map back to real post_id rows in data/platform_posts.csv.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475467",
    )
    save_figure(fig, output_dir, "05_top_evidence_contributions")


def write_summary(criteria: pd.DataFrame, comments: pd.DataFrame, audit: pd.DataFrame, evidence: pd.DataFrame, output_dir: Path) -> None:
    sep7 = criteria.loc[criteria["day"] == pd.Timestamp("2025-09-07")].iloc[0]
    sep4 = criteria.loc[criteria["day"] == pd.Timestamp("2025-09-04")].iloc[0]
    comment_peak = comments.loc[comments["posts_with_parsed_comments"].idxmax()]
    status_counts = audit["status"].value_counts()
    included = int(status_counts.get("included", 0))
    excluded = int(status_counts.get("excluded", 0))
    lines = [
        "# Coursework Charts Built From Valid Datasets",
        "",
        "These charts were built only from validated working datasets and derived reports tied to them through `reports/forecast_mvp/manifest.json`.",
        "",
        "## Files",
        "- `01_signal_components_area.png/svg`: topic-component stackplot from model diagnostics.",
        "- `02_sources_vs_specificity.png/svg`: source diversity against explicit event detail counts.",
        "- `03_comment_coverage.png/svg`: comment coverage in the collected Facebook dataset.",
        "- `04_external_source_audit.png/svg`: included/excluded external-source audit and top included domains.",
        "- `05_top_evidence_contributions.png/svg`: top evidence rows used in the coursework forecast.",
        "",
        "## Key Numbers",
        f"- `2025-09-04`: social-media-ban signals `{int(sep4['social_media_ban'])}`, unique sources `{int(sep4['unique_sources'])}`.",
        f"- `2025-09-07`: mobilization `{int(sep7['mobilization'])}`, explicit event details `{int(sep7['explicit_event_details'])}`, unique sources `{int(sep7['unique_sources'])}`.",
        f"- Comment-coverage peak: `{comment_peak['day'].date().isoformat()}` with `{int(comment_peak['posts_with_parsed_comments'])}` posts with parsed comments.",
        f"- External audit: `{included}` included rows and `{excluded}` excluded rows after cutoff filtering.",
        f"- Coursework evidence rows: `{len(evidence)}`.",
        "",
        "## Provenance",
        "- `model_diagnostics/criteria_growth_timeseries.csv` is derived from `data/platform_posts.csv`, `data/platform_comments.csv`, and `data/derived/external_pre_event_posts.csv`.",
        "- `comment_activity/posts_with_comments_daily.csv` is derived from `data/platform_posts.csv` and `data/platform_comments.csv`.",
        "- `course_top_evidence.csv` is written by `src/nepal_monitor/forecast_mvp.py` from the same raw inputs used for the forecast run.",
        "- `external_pre_event_sources_audit.csv` is the real audit table for included and excluded external pre-event source rows.",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build coursework charts from validated project datasets.")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    setup_style()
    criteria = load_criteria(CRITERIA_CSV)
    comments = load_comments(COMMENTS_CSV)
    audit = load_audit(AUDIT_CSV)
    evidence = load_evidence(EVIDENCE_CSV)

    build_signal_components(criteria, output_dir)
    build_sources_vs_specificity(criteria, output_dir)
    build_comment_coverage(comments, output_dir)
    build_external_audit(audit, output_dir)
    build_top_evidence(evidence, output_dir)
    write_summary(criteria, comments, audit, evidence, output_dir)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
