# Course Forecast Summary

Selected analysis level: `L4_city_event_forecast`.
Selection rule: selected as the highest forecast level with active medium/high risk rows.

This report uses one fixed working level for the coursework presentation. Diagnostic model-selection details are kept out of this course summary.

## Risk Distribution
- high: 1
- medium: 0
- low: 0
- none: 0

## First Medium/High Warning
- 2025-09-07 Kathmandu risk=73.08 target=2025-09-08..2025-09-10

## Backtest Metrics
- forecast_rows_total: 1
- forecast_rows_evaluated: 1
- ground_truth_events: 3
- true_positive: 1
- false_positive: 0
- false_negative: 0
- true_negative: 0
- precision: 1.0
- recall: 1.0
- f1: 1.0
- brier_score: 0.0854
- events_detected: 2
- events_missed: 1
- event_recall: 0.6667
- average_first_warning_lead_days: 1.5

## Highest Risk Rows
- 2025-09-07 Kathmandu: risk=73.08 level=high terms=Maitighar:13; Gen Z:9; parliament:8; youth:6; corruption:6

## Course Files
- course_forecast_daily: reports\forecast_mvp\course_forecast_daily.csv
- course_top_evidence: reports\forecast_mvp\course_top_evidence.csv
- course_backtest_metrics: reports\forecast_mvp\course_backtest_metrics.csv
- course_summary: reports\forecast_mvp\course_summary.md
- data_needed: reports\forecast_mvp\data_needed.md
