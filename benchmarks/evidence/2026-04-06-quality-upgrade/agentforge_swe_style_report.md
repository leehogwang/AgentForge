# AgentForge SWE-style Benchmark Evidence

## Summary

- cases: 2
- runs: 2
- run_success_rate: 1.000
- case_pass_rate: 1.000
- avg_quality_score: 98.00
- avg_efficiency_score: 43.28
- avg_duration_seconds: 65.55
- pass_at_k: 1=1.000

## Case Aggregates

| case_id | repeats | run_success_rate | best_quality | avg_efficiency | avg_duration_s | public_pass_rate | hidden_pass_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| billing-discount-order | 1 | 1.000 | 98.00 | 44.60 | 61.56 | 1.000 | 1.000 |
| inventory-low-stock | 1 | 1.000 | 98.00 | 41.95 | 69.53 | 1.000 | 1.000 |

## Per-run Results

| run_id | success | decision | public | hidden | quality | efficiency | attempts | duration_s | changed_files |
|---|---|---|---|---|---:|---:|---:|---:|---|
| inventory-low-stock | True | DONE | True | True | 98.00 | 41.95 | 2 | 69.53 | src/inventory/service.py, tests/test_public.py |
| billing-discount-order | True | DONE | True | True | 98.00 | 44.60 | 2 | 61.56 | src/billing/calc.py, tests/test_public.py |
