# Coursework Charts Built From Valid Datasets

These charts were built only from validated working datasets and derived reports tied to them through `reports/forecast_mvp/manifest.json`.

## Files
- `01_signal_components_area.png/svg`: topic-component stackplot from model diagnostics.
- `02_sources_vs_specificity.png/svg`: source diversity against explicit event detail counts.
- `03_comment_coverage.png/svg`: comment coverage in the collected Facebook dataset.
- `04_external_source_audit.png/svg`: included/excluded external-source audit and top included domains.
- `05_top_evidence_contributions.png/svg`: top evidence rows used in the coursework forecast.

## Key Numbers
- `2025-09-04`: social-media-ban signals `132`, unique sources `87`.
- `2025-09-07`: mobilization `310`, explicit event details `9`, unique sources `160`.
- Comment-coverage peak: `2025-09-08` with `1265` posts with parsed comments.
- External audit: `68` included rows and `1469` excluded rows after cutoff filtering.
- Coursework evidence rows: `5`.

## Provenance
- `model_diagnostics/criteria_growth_timeseries.csv` is derived from `data/platform_posts.csv`, `data/platform_comments.csv`, and `data/derived/external_pre_event_posts.csv`.
- `comment_activity/posts_with_comments_daily.csv` is derived from `data/platform_posts.csv` and `data/platform_comments.csv`.
- `course_top_evidence.csv` is written by `src/nepal_monitor/forecast_mvp.py` from the same raw inputs used for the forecast run.
- `external_pre_event_sources_audit.csv` is the real audit table for included and excluded external pre-event source rows.
