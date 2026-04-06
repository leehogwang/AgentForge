# AgentForge Quality Benchmark Evidence

## Summary

- cases: 3
- runs: 6
- run_success_rate: 0.667
- case_pass_rate: 0.667
- avg_quality_score: 88.00
- avg_efficiency_score: 29.46
- avg_duration_seconds: 87.48
- pass_at_k: 1=0.667, 2=0.667

## Case Aggregates

| case_id | repeats | run_success_rate | best_quality | avg_efficiency | avg_duration_s | public_pass_rate | hidden_pass_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| config-loader-invalid-env | 2 | 0.000 | 65.00 | 24.20 | 79.92 | 1.000 | 0.000 |
| report-summary-regression | 2 | 1.000 | 100.00 | 28.70 | 103.19 | 1.000 | 1.000 |
| slugify-edge-cases | 2 | 1.000 | 100.00 | 35.49 | 79.34 | 1.000 | 1.000 |

## Per-run Results

| run_id | success | decision | public | hidden | quality | efficiency | attempts | duration_s | changed_files |
|---|---|---|---|---|---:|---:|---:|---:|---|
| config-loader-invalid-env#run1 | False | DONE | True | False | 65.00 | 19.75 | 3 | 105.85 | config_loader.py |
| config-loader-invalid-env#run2 | False | DONE | True | False | 65.00 | 28.64 | 2 | 53.98 | config_loader.py |
| report-summary-regression#run1 | True | DONE | True | True | 100.00 | 21.71 | 5 | 138.00 | report.py |
| report-summary-regression#run2 | True | DONE | True | True | 100.00 | 35.68 | 3 | 68.39 | report.py |
| slugify-edge-cases#run1 | True | DONE | True | True | 100.00 | 48.27 | 2 | 40.23 | utils.py |
| slugify-edge-cases#run2 | True | DONE | True | True | 98.00 | 22.71 | 5 | 118.44 | test_slugify_additional.py, utils.py |
