#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any



def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)



def render_summary(summary: dict[str, Any]) -> list[str]:
    lines = [
        "## Summary",
        "",
        f"- cases: {summary.get('cases')}",
        f"- runs: {summary.get('runs')}",
        f"- run_success_rate: {fmt(summary.get('run_success_rate'), 3)}",
        f"- case_pass_rate: {fmt(summary.get('case_pass_rate'), 3)}",
        f"- avg_quality_score: {fmt(summary.get('avg_quality_score'))}",
        f"- avg_efficiency_score: {fmt(summary.get('avg_efficiency_score'))}",
        f"- avg_duration_seconds: {fmt(summary.get('avg_duration_seconds'))}",
    ]
    pass_at = summary.get("pass_at_k") or {}
    if pass_at:
        lines.append("- pass_at_k: " + ", ".join(f"{k}={float(v):.3f}" for k, v in sorted(pass_at.items(), key=lambda kv: int(kv[0]))))
    lines.append("")
    return lines



def render_case_table(case_aggregates: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Case Aggregates",
        "",
        "| case_id | repeats | run_success_rate | best_quality | avg_efficiency | avg_duration_s | public_pass_rate | hidden_pass_rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in case_aggregates:
        lines.append(
            "| {case_id} | {repeats} | {run_success_rate} | {best_quality_score} | {avg_efficiency_score} | {avg_duration_seconds} | {public_verify_pass_rate} | {hidden_verify_pass_rate} |".format(
                case_id=item.get("case_id"),
                repeats=item.get("repeats"),
                run_success_rate=fmt(item.get("run_success_rate"), 3),
                best_quality_score=fmt(item.get("best_quality_score")),
                avg_efficiency_score=fmt(item.get("avg_efficiency_score")),
                avg_duration_seconds=fmt(item.get("avg_duration_seconds")),
                public_verify_pass_rate=fmt(item.get("public_verify_pass_rate"), 3),
                hidden_verify_pass_rate=fmt(item.get("hidden_verify_pass_rate"), 3),
            )
        )
    lines.append("")
    return lines



def render_run_table(results: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Per-run Results",
        "",
        "| run_id | success | decision | public | hidden | quality | efficiency | attempts | duration_s | changed_files |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in results:
        changed = ", ".join(item.get("changed_files") or [])
        lines.append(
            "| {run_id} | {success} | {decision} | {public} | {hidden} | {quality} | {efficiency} | {attempts} | {duration} | {changed} |".format(
                run_id=item.get("run_id"),
                success=item.get("success"),
                decision=item.get("final_decision", item.get("exit_code")),
                public=item.get("public_verify_passed"),
                hidden=item.get("hidden_verify_passed"),
                quality=fmt(item.get("quality_score")),
                efficiency=fmt(item.get("efficiency_score")),
                attempts=item.get("attempts", item.get("command_executions", "n/a")),
                duration=fmt(item.get("duration_seconds")),
                changed=changed,
            )
        )
    lines.append("")
    return lines



def main() -> int:
    parser = argparse.ArgumentParser(description="Render benchmark JSON into a markdown report")
    parser.add_argument("--input", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    lines = [f"# {args.title}", ""]
    lines.extend(render_summary(payload.get("summary", {})))
    lines.extend(render_case_table(payload.get("case_aggregates", [])))
    lines.extend(render_run_table(payload.get("results", [])))
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
