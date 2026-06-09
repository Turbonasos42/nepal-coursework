from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from .constants import (
    DEFAULT_CALIBRATION_CSV,
    DEFAULT_DB_PATH,
    DEFAULT_GROUND_TRUTH_CSV,
    DEFAULT_POSTS_CSV,
    DEFAULT_REPORT_PATH,
    DEFAULT_SOURCES_CSV,
)
from .connectors.web import collect_web_targets
from .db import connect, init_db
from .evaluation import evaluate
from .extractors import extract_signals
from .forecast_mvp import run_mvp_forecast
from .forecasting import make_forecasts
from .importers import import_ground_truth, import_posts, import_sources
from .reporting import write_report
from .scoring import score_signals


def _add_db(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path.")


def cmd_init_db(args: argparse.Namespace) -> None:
    init_db(args.db)
    print(f"initialized database: {args.db}")


def cmd_import_sources(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        count = import_sources(conn, args.csv, replace=not args.append)
    print(f"imported sources: {count}")


def cmd_import_posts(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        count = import_posts(
            conn,
            args.csv,
            replace=not args.append,
            strict_cutoff=not args.allow_post_cutoff,
        )
    print(f"imported posts: {count}")


def cmd_collect_web(args: argparse.Namespace) -> None:
    count = collect_web_targets(
        targets_csv=args.targets,
        output_csv=args.output,
        user_agent=args.user_agent,
        delay_seconds=args.delay_seconds,
        timeout=args.timeout,
        max_chars=args.max_chars,
    )
    print(f"collected web posts: {count}")
    print(f"wrote normalized CSV: {args.output}")


def cmd_extract_signals(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        count = extract_signals(conn)
    print(f"extracted signals: {count}")


def cmd_score_signals(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        count = score_signals(conn)
    print(f"scored signals: {count}")


def cmd_make_forecasts(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        count = make_forecasts(
            conn,
            calibration_path=args.calibration,
            threshold=args.threshold,
            horizon_days=args.horizon_days,
            lookback_days=args.lookback_days,
        )
    print(f"created forecasts: {count}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        metrics = evaluate(conn, ground_truth_csv=args.ground_truth, output_csv=args.output)
    for key, value in metrics.items():
        print(f"{key}: {value}")


def cmd_report(args: argparse.Namespace) -> None:
    init_db(args.db)
    with connect(args.db) as conn:
        output = write_report(conn, args.output)
    print(f"wrote report: {output}")


def cmd_forecast_mvp(args: argparse.Namespace) -> None:
    forecast_start = args.forecast_start
    if isinstance(forecast_start, str):
        forecast_start = date.fromisoformat(forecast_start)
    forecast_end = args.forecast_end
    if isinstance(forecast_end, str):
        forecast_end = date.fromisoformat(forecast_end)
    input_cutoff = args.input_cutoff
    if isinstance(input_cutoff, str):
        input_cutoff = datetime.fromisoformat(input_cutoff)
    result = run_mvp_forecast(
        posts_csv=args.posts,
        comments_csv=args.comments,
        lexicon_csv=args.lexicon,
        ground_truth_csv=args.ground_truth,
        output_dir=args.output_dir,
        forecast_start=forecast_start,
        forecast_end=forecast_end,
        input_cutoff=input_cutoff,
        horizon_days=args.horizon_days,
        extra_posts=args.extra_posts,
    )
    print(f"posts used: {result['posts_used']}")
    print(f"forecast rows: {result['forecast_rows']}")
    print(f"summary: {result['summary']}")


def cmd_run_demo(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    if db_path.exists() and args.reset:
        db_path.unlink()
    init_db(args.db)
    with connect(args.db) as conn:
        print(f"imported sources: {import_sources(conn, args.sources, replace=True)}")
        print(f"imported posts: {import_posts(conn, args.posts, replace=True, strict_cutoff=True)}")
        print(f"extracted signals: {extract_signals(conn)}")
        print(f"scored signals: {score_signals(conn)}")
        print(
            "created forecasts: "
            + str(
                make_forecasts(
                    conn,
                    calibration_path=args.calibration,
                    threshold=args.threshold,
                    horizon_days=args.horizon_days,
                    lookback_days=args.lookback_days,
                )
            )
        )
        print(f"imported ground truth: {import_ground_truth(conn, args.ground_truth, replace=True)}")
        metrics = evaluate(conn, ground_truth_csv=None, output_csv="reports/evaluation_summary.csv")
        for key, value in metrics.items():
            print(f"{key}: {value}")
        output = write_report(conn, args.report)
        print(f"wrote report: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nepal_backtest",
        description="Historical replay MVP for Nepal September 2025 protest signal forecasting.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Create the SQLite schema.")
    _add_db(init_parser)
    init_parser.set_defaults(func=cmd_init_db)

    sources_parser = subparsers.add_parser("import-sources", help="Import source registry CSV.")
    _add_db(sources_parser)
    sources_parser.add_argument("--csv", default=DEFAULT_SOURCES_CSV)
    sources_parser.add_argument("--append", action="store_true")
    sources_parser.set_defaults(func=cmd_import_sources)

    posts_parser = subparsers.add_parser("import-posts", help="Import historical raw posts CSV.")
    _add_db(posts_parser)
    posts_parser.add_argument("--csv", default=DEFAULT_POSTS_CSV)
    posts_parser.add_argument("--append", action="store_true")
    posts_parser.add_argument("--allow-post-cutoff", action="store_true")
    posts_parser.set_defaults(func=cmd_import_posts)

    web_parser = subparsers.add_parser(
        "collect-web",
        help="Fetch permitted public HTML URLs into normalized raw_posts CSV.",
    )
    web_parser.add_argument("--targets", required=True, help="CSV with url and published_at columns.")
    web_parser.add_argument("--output", default="data/web_collected_posts.csv")
    web_parser.add_argument(
        "--user-agent",
        default="NepalBacktestMVP/0.1 public research contact=local",
    )
    web_parser.add_argument("--delay-seconds", type=float, default=2.0)
    web_parser.add_argument("--timeout", type=int, default=20)
    web_parser.add_argument("--max-chars", type=int, default=4000)
    web_parser.set_defaults(func=cmd_collect_web)

    extract_parser = subparsers.add_parser("extract-signals", help="Extract structured signals.")
    _add_db(extract_parser)
    extract_parser.set_defaults(func=cmd_extract_signals)

    score_parser = subparsers.add_parser("score-signals", help="Score extracted signals.")
    _add_db(score_parser)
    score_parser.set_defaults(func=cmd_score_signals)

    forecast_parser = subparsers.add_parser("make-forecasts", help="Build rolling city forecasts.")
    _add_db(forecast_parser)
    forecast_parser.add_argument("--calibration", default=DEFAULT_CALIBRATION_CSV)
    forecast_parser.add_argument("--threshold", type=float, default=0.60)
    forecast_parser.add_argument("--horizon-days", type=int, default=3)
    forecast_parser.add_argument("--lookback-days", type=int, default=3)
    forecast_parser.set_defaults(func=cmd_make_forecasts)

    eval_parser = subparsers.add_parser("evaluate", help="Evaluate forecasts against ground truth.")
    _add_db(eval_parser)
    eval_parser.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH_CSV)
    eval_parser.add_argument("--output", default="reports/evaluation_summary.csv")
    eval_parser.set_defaults(func=cmd_evaluate)

    report_parser = subparsers.add_parser("report", help="Write Markdown and CSV report artifacts.")
    _add_db(report_parser)
    report_parser.add_argument("--output", default=DEFAULT_REPORT_PATH)
    report_parser.set_defaults(func=cmd_report)

    mvp_parser = subparsers.add_parser(
        "forecast-mvp",
        help="Build explainable L4-L0 forecast MVP reports from collected CSVs.",
    )
    mvp_parser.add_argument("--posts", default="data/platform_posts.csv")
    mvp_parser.add_argument("--comments", default="data/platform_comments.csv")
    mvp_parser.add_argument("--lexicon", default="data/nepal_trigger_lexicon.csv")
    mvp_parser.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH_CSV)
    mvp_parser.add_argument("--output-dir", default="reports/forecast_mvp")
    mvp_parser.add_argument("--forecast-start", type=date.fromisoformat, default=date(2025, 7, 1))
    mvp_parser.add_argument("--forecast-end", type=date.fromisoformat, default=date(2025, 9, 7))
    mvp_parser.add_argument("--input-cutoff", type=datetime.fromisoformat, default=datetime(2025, 9, 8))
    mvp_parser.add_argument("--horizon-days", type=int, default=3)
    mvp_parser.add_argument("--extra-posts", action="append", default=[])
    mvp_parser.set_defaults(func=cmd_forecast_mvp)

    demo_parser = subparsers.add_parser("run-demo", help="Run the full replay pipeline on sample data.")
    _add_db(demo_parser)
    demo_parser.add_argument("--sources", default=DEFAULT_SOURCES_CSV)
    demo_parser.add_argument("--posts", default=DEFAULT_POSTS_CSV)
    demo_parser.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH_CSV)
    demo_parser.add_argument("--calibration", default=DEFAULT_CALIBRATION_CSV)
    demo_parser.add_argument("--report", default=DEFAULT_REPORT_PATH)
    demo_parser.add_argument("--threshold", type=float, default=0.60)
    demo_parser.add_argument("--horizon-days", type=int, default=3)
    demo_parser.add_argument("--lookback-days", type=int, default=3)
    demo_parser.add_argument("--reset", action=argparse.BooleanOptionalAction, default=True)
    demo_parser.set_defaults(func=cmd_run_demo)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
