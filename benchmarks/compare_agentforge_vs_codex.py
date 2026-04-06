#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any



def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))



def index_results(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["run_id"]: item for item in payload.get("results", [])}



def index_case_aggregates(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["case_id"]: item for item in payload.get("case_aggregates", [])}



def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)



def print_summary(label: str, payload: dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    print(f"[{label}]")
    for key in [
        "runs",
        "run_success_rate",
        "case_pass_rate",
        "avg_quality_score",
        "avg_efficiency_score",
        "avg_duration_seconds",
    ]:
        print(f"  {key}: {fmt(summary.get(key))}")
    pass_at = summary.get("pass_at_k") or {}
    if pass_at:
        print("  pass_at_k: " + ", ".join(f"{k}={float(v):.3f}" for k, v in sorted(pass_at.items(), key=lambda kv: int(kv[0]))))
    print()



def main() -> int:
    parser = argparse.ArgumentParser(description="Compare AgentForge and single Codex benchmark result JSONs")
    parser.add_argument("--agentforge", required=True)
    parser.add_argument("--codex", required=True)
    args = parser.parse_args()

    af = load(args.agentforge)
    cx = load(args.codex)
    af_case = index_case_aggregates(af)
    cx_case = index_case_aggregates(cx)
    case_ids = sorted(set(af_case) | set(cx_case))

    print("=== AgentForge vs Single Codex ===")
    print_summary("AgentForge", af)
    print_summary("Single Codex", cx)

    print("Per-case aggregate:")
    for cid in case_ids:
        a = af_case.get(cid, {})
        c = cx_case.get(cid, {})
        print(
            f"- {cid}: "
            f"AF(pass@1={fmt((a.get('pass_at_k') or {}).get('1'), 3)}, best_q={fmt(a.get('best_quality_score'))}, avg_eff={fmt(a.get('avg_efficiency_score'))}, avg_t={fmt(a.get('avg_duration_seconds'))}s) | "
            f"CX(pass@1={fmt((c.get('pass_at_k') or {}).get('1'), 3)}, best_q={fmt(c.get('best_quality_score'))}, avg_eff={fmt(c.get('avg_efficiency_score'))}, avg_t={fmt(c.get('avg_duration_seconds'))}s)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
