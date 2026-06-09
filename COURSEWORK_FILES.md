# Coursework Files

Only the files below are needed for the coursework package.

## Core Code
- `nepal_backtest.py`
- `pyproject.toml`
- `src/nepal_monitor/cli.py`
- `src/nepal_monitor/constants.py`
- `src/nepal_monitor/evaluation.py`
- `src/nepal_monitor/extractors.py`
- `src/nepal_monitor/features.py`
- `src/nepal_monitor/forecast_mvp.py`
- `src/nepal_monitor/importers.py`
- `src/nepal_monitor/model.py`
- `src/nepal_monitor/scoring.py`
- `src/nepal_monitor/timeutils.py`

## Data Used In The Final Run
- `data/platform_posts.csv`
- `data/platform_comments.csv`
- `data/nepal_trigger_lexicon.csv`
- `data/ground_truth_events.csv`
- `data/derived/external_pre_event_posts.csv`
- `data/derived/external_pre_event_sources_audit.csv`

## Final Coursework Outputs
- `reports/forecast_mvp/manifest.json`
- `reports/forecast_mvp/course_summary.md`
- `reports/forecast_mvp/course_forecast_daily.csv`
- `reports/forecast_mvp/course_backtest_metrics.csv`
- `reports/forecast_mvp/course_top_evidence.csv`

## Coursework Charts
- `reports/forecast_mvp/course_valid_charts/01_signal_components_area.png`
- `reports/forecast_mvp/course_valid_charts/02_sources_vs_specificity.png`
- `reports/forecast_mvp/course_valid_charts/03_comment_coverage.png`
- `reports/forecast_mvp/course_valid_charts/04_external_source_audit.png`
- `reports/forecast_mvp/course_valid_charts/05_top_evidence_contributions.png`
- `reports/forecast_mvp/course_valid_charts/summary.md`

## Chart Source Files For Rebuild
- `scripts/build_coursework_valid_charts.py`
- `reports/forecast_mvp/model_diagnostics/criteria_growth_timeseries.csv`
- `reports/forecast_mvp/comment_activity/posts_with_comments_daily.csv`

## Not Needed
- any `README.md`
- any file with `example` in the name
- any file with `sample` in the name
- `reports/forecast_mvp/_saved_snapshots/`
- `reports/debug_*`
- `reports/facebook_runs/`
- `data/facebook_playwright_profile/`
- `data/fb_playwright_profile/`
- `data/external_raw/`
- `data/derived/external_datasets/`
- `__pycache__/`
