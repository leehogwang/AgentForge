#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_agentforge_benchmark as common
import benchmark_metrics as metrics
import benchmark_task_utils as task_utils


@dataclass
class CodexCaseResult:
    case_id: str
    run_id: str
    repeat_index: int
    repeats: int
    goal: str
    workdir: str
    hidden_dir: str
    exit_code: int
    duration_seconds: float
    public_verify_cmd: str | None
    public_verify_returncode: int | None
    public_verify_passed: bool | None
    hidden_verify_cmd: str | None
    hidden_verify_returncode: int | None
    hidden_verify_passed: bool | None
    verify_cmd: str | None
    verify_returncode: int | None
    verify_passed: bool | None
    success: bool
    command_executions: int
    file_change_events: int
    changed_files: list[str]
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    edit_precision_score: float | None
    quality_score: float
    efficiency_score: float
    stdout_log: str
    stderr_log: str
    final_message_path: str | None
    final_message_excerpt: str | None
    public_verify_stdout: str | None = None
    public_verify_stderr: str | None = None
    hidden_verify_stdout: str | None = None
    hidden_verify_stderr: str | None = None


@dataclass
class CaseAggregate:
    case_id: str
    repeats: int
    successes: int
    run_success_rate: float
    pass_at_k: dict[int, float]
    avg_quality_score: float
    best_quality_score: float
    avg_efficiency_score: float
    avg_duration_seconds: float
    avg_command_executions: float
    public_verify_pass_rate: float | None
    hidden_verify_pass_rate: float | None
    best_run_id: str | None



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run single Codex baseline on a task suite")
    parser.add_argument("--tasks", required=True, help="Path to JSON or JSONL task suite")
    parser.add_argument("--work-root", default="./.codex_bench_runs", help="Directory to create isolated case workdirs")
    parser.add_argument("--hidden-root", default="./.codex_bench_hidden", help="Directory to create hidden verifier assets")
    parser.add_argument("--output", default="./codex_baseline_results.json", help="Where to save results JSON")
    parser.add_argument("--model", default="gpt-5.4", help="Codex model")
    parser.add_argument("--timeout-seconds", type=int, default=600, help="Per-case timeout")
    parser.add_argument("--repeats", type=int, default=1, help="Default repeat count per task")
    parser.add_argument("--dry-run", action="store_true", help="Prepare task directories without calling Codex")
    return parser.parse_args()



def read_json_lines_loose(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events



def summarize_codex_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    command_count = 0
    file_change_events = 0
    changed_files: list[str] = []
    usage = {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None}

    seen_changed: set[str] = set()
    for ev in events:
        ev_type = ev.get("type")
        item = ev.get("item") or {}
        item_type = item.get("type")
        if ev_type == "item.completed" and item_type == "command_execution":
            command_count += 1
        if ev_type == "item.completed" and item_type == "file_change":
            file_change_events += 1
            for ch in item.get("changes") or []:
                path = str(ch.get("path") or "")
                if path and path not in seen_changed:
                    seen_changed.add(path)
                    changed_files.append(path)
        if ev_type == "turn.completed":
            u = ev.get("usage") or {}
            usage = {
                "input_tokens": u.get("input_tokens"),
                "cached_input_tokens": u.get("cached_input_tokens"),
                "output_tokens": u.get("output_tokens"),
            }
    return {
        "command_executions": command_count,
        "file_change_events": file_change_events,
        "changed_files": changed_files,
        **usage,
    }



def build_prompt(task: dict[str, Any]) -> str:
    goal = common.task_goal(task).strip()
    return (
        "다음 목표를 현재 작업 디렉토리에서 해결해라.\n"
        f"목표: {goal}\n\n"
        "규칙:\n"
        "- 필요한 파일만 수정해라.\n"
        "- 작업이 끝나면 가능하면 public verify 명령을 직접 실행해라.\n"
        "- 완료 후 종료해라.\n"
    )



def run_case(
    task: dict[str, Any],
    work_root: Path,
    hidden_root: Path,
    task_file_dir: Path,
    model: str,
    timeout_seconds: int,
    dry_run: bool,
    repeat_index: int,
    repeats: int,
) -> CodexCaseResult:
    case_id = str(task["id"])
    goal = common.task_goal(task)
    run_id = common.expand_run_id(case_id, repeat_index, repeats)
    workdir_name = case_id if repeats <= 1 else f"{case_id}__run{repeat_index + 1:02d}"
    workdir = work_root / workdir_name
    hidden_dir = hidden_root / workdir_name

    common.ensure_clean_dir(workdir)
    common.ensure_clean_dir(hidden_dir)
    common.materialize_task(task, workdir, task_file_dir)
    common.materialize_hidden_assets(task, hidden_dir, task_file_dir)
    before_state = task_utils.capture_tree_state(workdir)

    public_verify_cmd, hidden_verify_cmd = common.resolve_verify_commands(task, workdir, hidden_dir)
    stdout_log = workdir / "codex_stdout.jsonl"
    stderr_log = workdir / "codex_stderr.log"
    final_message_path = workdir / "codex_last_message.txt"

    if dry_run:
        return CodexCaseResult(
            case_id=case_id,
            run_id=run_id,
            repeat_index=repeat_index,
            repeats=repeats,
            goal=goal,
            workdir=str(workdir),
            hidden_dir=str(hidden_dir),
            exit_code=0,
            duration_seconds=0.0,
            public_verify_cmd=public_verify_cmd,
            public_verify_returncode=None,
            public_verify_passed=None,
            hidden_verify_cmd=hidden_verify_cmd,
            hidden_verify_returncode=None,
            hidden_verify_passed=None,
            verify_cmd=public_verify_cmd,
            verify_returncode=None,
            verify_passed=None,
            success=False,
            command_executions=0,
            file_change_events=0,
            changed_files=[],
            input_tokens=None,
            cached_input_tokens=None,
            output_tokens=None,
            edit_precision_score=None,
            quality_score=0.0,
            efficiency_score=0.0,
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
            final_message_path=str(final_message_path),
            final_message_excerpt=None,
        )

    prompt = build_prompt(task)
    cmd = [
        "codex", "exec",
        "--json",
        "--color", "never",
        "--full-auto",
        "--model", model,
        "--ephemeral",
        "--output-last-message", str(final_message_path),
        prompt,
    ]

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        exit_code = proc.returncode
        stdout_log.write_text(proc.stdout, encoding="utf-8")
        stderr_log.write_text(proc.stderr, encoding="utf-8")
    except subprocess.TimeoutExpired as e:
        exit_code = 124
        stdout_log.write_text(e.stdout or "", encoding="utf-8")
        stderr_log.write_text((e.stderr or "") + "\nTIMEOUT\n", encoding="utf-8")
    duration_seconds = time.time() - started

    events = read_json_lines_loose(stdout_log)
    summary = summarize_codex_events(events)
    public_rc, public_passed, public_stdout, public_stderr = common.run_verify(public_verify_cmd, workdir, hidden_dir)
    hidden_rc, hidden_passed, hidden_stdout, hidden_stderr = common.run_verify(hidden_verify_cmd, workdir, hidden_dir)

    changed_files = task_utils.diff_tree_states(before_state, task_utils.capture_tree_state(workdir))
    changed_files = task_utils.clean_path_list(changed_files)
    edit_precision_score = metrics.compute_edit_precision_score(
        changed_files,
        expected_changed_files=task.get("expected_changed_files"),
        allowed_changed_files=task.get("allowed_changed_files"),
    )

    final_message_excerpt = None
    if final_message_path.exists():
        final_message_excerpt = final_message_path.read_text(encoding="utf-8", errors="replace")[:500]

    success = bool(exit_code == 0)
    if public_passed is not None:
        success = success and public_passed
    if hidden_passed is not None:
        success = success and hidden_passed

    quality_score = metrics.compute_quality_score(
        final_decision="DONE" if exit_code == 0 else None,
        public_verify_passed=public_passed,
        hidden_verify_passed=hidden_passed,
        edit_precision_score=edit_precision_score,
    )
    efficiency_score = metrics.compute_efficiency_score(
        duration_seconds=duration_seconds,
        attempts=1,
        effort_count=int(summary["command_executions"]),
        quality_score=quality_score,
        target_duration_seconds=float(task.get("target_duration_seconds", 60.0)),
        target_effort_count=float(task.get("target_command_executions", 6.0)),
    )

    return CodexCaseResult(
        case_id=case_id,
        run_id=run_id,
        repeat_index=repeat_index,
        repeats=repeats,
        goal=goal,
        workdir=str(workdir),
        hidden_dir=str(hidden_dir),
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        public_verify_cmd=public_verify_cmd,
        public_verify_returncode=public_rc,
        public_verify_passed=public_passed,
        hidden_verify_cmd=hidden_verify_cmd,
        hidden_verify_returncode=hidden_rc,
        hidden_verify_passed=hidden_passed,
        verify_cmd=public_verify_cmd,
        verify_returncode=public_rc,
        verify_passed=public_passed,
        success=success,
        command_executions=int(summary["command_executions"]),
        file_change_events=int(summary["file_change_events"]),
        changed_files=changed_files,
        input_tokens=summary["input_tokens"],
        cached_input_tokens=summary["cached_input_tokens"],
        output_tokens=summary["output_tokens"],
        edit_precision_score=edit_precision_score,
        quality_score=quality_score,
        efficiency_score=efficiency_score,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
        final_message_path=str(final_message_path) if final_message_path.exists() else None,
        final_message_excerpt=final_message_excerpt,
        public_verify_stdout=public_stdout,
        public_verify_stderr=public_stderr,
        hidden_verify_stdout=hidden_stdout,
        hidden_verify_stderr=hidden_stderr,
    )



def result_to_dict(result: CodexCaseResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["duration_seconds"] = round(result.duration_seconds, 3)
    return payload



def summarize_case_aggregates(results: list[CodexCaseResult]) -> list[CaseAggregate]:
    grouped: dict[str, list[CodexCaseResult]] = {}
    for result in results:
        grouped.setdefault(result.case_id, []).append(result)

    aggregates: list[CaseAggregate] = []
    for case_id, runs in sorted(grouped.items()):
        runs = sorted(runs, key=lambda r: r.repeat_index)
        success_flags = [r.success for r in runs]
        quality_scores = [r.quality_score for r in runs]
        efficiency_scores = [r.efficiency_score for r in runs]
        durations = [r.duration_seconds for r in runs]
        command_counts = [r.command_executions for r in runs]
        public_known = [r.public_verify_passed for r in runs if r.public_verify_passed is not None]
        hidden_known = [r.hidden_verify_passed for r in runs if r.hidden_verify_passed is not None]
        best_run = max(runs, key=lambda r: (r.quality_score, r.efficiency_score, -r.duration_seconds), default=None)
        aggregates.append(
            CaseAggregate(
                case_id=case_id,
                repeats=len(runs),
                successes=sum(1 for flag in success_flags if flag),
                run_success_rate=sum(1 for flag in success_flags if flag) / len(runs),
                pass_at_k=metrics.compute_pass_at_k({case_id: success_flags}),
                avg_quality_score=statistics.mean(quality_scores),
                best_quality_score=max(quality_scores),
                avg_efficiency_score=statistics.mean(efficiency_scores),
                avg_duration_seconds=statistics.mean(durations),
                avg_command_executions=statistics.mean(command_counts),
                public_verify_pass_rate=(sum(1 for flag in public_known if flag) / len(public_known)) if public_known else None,
                hidden_verify_pass_rate=(sum(1 for flag in hidden_known if flag) / len(hidden_known)) if hidden_known else None,
                best_run_id=best_run.run_id if best_run else None,
            )
        )
    return aggregates



def aggregate(results: list[CodexCaseResult]) -> dict[str, Any]:
    if not results:
        return {
            "cases": 0,
            "runs": 0,
            "successes": 0,
            "success_rate": 0.0,
            "run_success_rate": 0.0,
            "case_pass_rate": 0.0,
            "pass_at_k": {},
            "avg_duration_seconds": 0.0,
            "avg_command_executions": 0.0,
            "avg_quality_score": 0.0,
            "avg_efficiency_score": 0.0,
        }

    case_successes = metrics.group_run_field(results, "success")
    public_known = [r.public_verify_passed for r in results if r.public_verify_passed is not None]
    hidden_known = [r.hidden_verify_passed for r in results if r.hidden_verify_passed is not None]
    return {
        "cases": len(case_successes),
        "runs": len(results),
        "successes": sum(1 for r in results if r.success),
        "success_rate": sum(1 for r in results if r.success) / len(results),
        "run_success_rate": sum(1 for r in results if r.success) / len(results),
        "case_pass_rate": sum(1 for flags in case_successes.values() if any(flags)) / len(case_successes),
        "pass_at_k": {str(k): v for k, v in metrics.compute_pass_at_k(case_successes).items()},
        "avg_duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "median_duration_seconds": statistics.median(r.duration_seconds for r in results),
        "avg_command_executions": statistics.mean(r.command_executions for r in results),
        "avg_input_tokens": statistics.mean((r.input_tokens or 0) for r in results),
        "avg_output_tokens": statistics.mean((r.output_tokens or 0) for r in results),
        "avg_quality_score": statistics.mean(r.quality_score for r in results),
        "avg_efficiency_score": statistics.mean(r.efficiency_score for r in results),
        "avg_public_verify_pass_rate": (sum(1 for flag in public_known if flag) / len(public_known)) if public_known else None,
        "avg_hidden_verify_pass_rate": (sum(1 for flag in hidden_known if flag) / len(hidden_known)) if hidden_known else None,
    }



def case_aggregate_to_dict(aggregate_item: CaseAggregate) -> dict[str, Any]:
    payload = asdict(aggregate_item)
    payload["pass_at_k"] = {str(k): v for k, v in aggregate_item.pass_at_k.items()}
    return payload



def print_summary(results: list[CodexCaseResult], summary: dict[str, Any]) -> None:
    print("\n=== Single Codex Quality Baseline Summary ===")
    print(f"cases: {summary['cases']}")
    print(f"runs: {summary['runs']}")
    print(f"run_success_rate: {summary['run_success_rate']:.3f}")
    print(f"case_pass_rate: {summary['case_pass_rate']:.3f}")
    print(f"avg_duration_seconds: {summary['avg_duration_seconds']:.2f}")
    print(f"median_duration_seconds: {summary['median_duration_seconds']:.2f}")
    print(f"avg_command_executions: {summary['avg_command_executions']:.2f}")
    print(f"avg_input_tokens: {summary['avg_input_tokens']:.0f}")
    print(f"avg_output_tokens: {summary['avg_output_tokens']:.0f}")
    print(f"avg_quality_score: {summary['avg_quality_score']:.2f}")
    print(f"avg_efficiency_score: {summary['avg_efficiency_score']:.2f}")
    if summary.get("pass_at_k"):
        print("pass_at_k: " + ", ".join(f"k={k}:{v:.3f}" for k, v in summary["pass_at_k"].items()))
    print("\nPer-run:")
    for r in results:
        public_state = "n/a" if r.public_verify_passed is None else ("pass" if r.public_verify_passed else "fail")
        hidden_state = "n/a" if r.hidden_verify_passed is None else ("pass" if r.hidden_verify_passed else "fail")
        print(
            f"- {r.run_id}: success={r.success} quality={r.quality_score:.1f} efficiency={r.efficiency_score:.1f} "
            f"public={public_state} hidden={hidden_state} cmds={r.command_executions} duration={r.duration_seconds:.2f}s"
        )



def main() -> int:
    args = parse_args()
    tasks_path = Path(args.tasks).resolve()
    task_file_dir = tasks_path.parent
    tasks = common.read_json_or_jsonl(tasks_path)
    work_root = Path(args.work_root).resolve()
    hidden_root = Path(args.hidden_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    hidden_root.mkdir(parents=True, exist_ok=True)

    results: list[CodexCaseResult] = []
    for task in tasks:
        repeats = common.task_repeats(task, args.repeats)
        for repeat_index in range(repeats):
            print(f"[run] {task['id']} ({repeat_index + 1}/{repeats})")
            results.append(run_case(task, work_root, hidden_root, task_file_dir, args.model, args.timeout_seconds, args.dry_run, repeat_index, repeats))

    summary = aggregate(results)
    case_aggregates = summarize_case_aggregates(results)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dry_run": args.dry_run,
        "tasks_path": str(tasks_path),
        "model": args.model,
        "summary": summary,
        "case_aggregates": [case_aggregate_to_dict(item) for item in case_aggregates],
        "results": [result_to_dict(r) for r in results],
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print_summary(results, summary)
    print(f"\nSaved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
