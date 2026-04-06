#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rich.layout import Layout

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import benchmark_metrics as metrics
import benchmark_task_utils as task_utils


class DummyLive:
    def __init__(self) -> None:
        self._started = False

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False


@dataclass
class CaseResult:
    case_id: str
    run_id: str
    repeat_index: int
    repeats: int
    goal: str
    workdir: str
    hidden_dir: str
    run_status: str
    duration_seconds: float
    attempts: int
    final_decision: str | None
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
    tool_calls: int
    shell_calls: int
    read_file_calls: int
    write_file_calls: int
    list_files_calls: int
    changed_files: list[str]
    confidence: float | None
    edit_precision_score: float | None
    quality_score: float
    efficiency_score: float
    session_events_path: str | None
    memory_events_path: str | None
    attempts_path: str | None
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
    avg_attempts: float
    avg_tool_calls: float
    public_verify_pass_rate: float | None
    hidden_verify_pass_rate: float | None
    best_run_id: str | None



def repo_root_from_script() -> Path:
    return SCRIPT_DIR.parent



def load_agentforge(repo_root: Path):
    script_path = repo_root / "agentforge"
    loader = importlib.machinery.SourceFileLoader("agentforge_module", str(script_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"Failed to build import spec for {script_path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module



def build_single_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="worker", ratio=4),
        Layout(name="evaluator", ratio=2),
        Layout(name="cmd_bar", size=3),
    )
    return layout



def read_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped[0] == "[":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of task objects")
        return data
    tasks = []
    for line in text.splitlines():
        if line.strip():
            tasks.append(json.loads(line))
    return tasks



def load_text_maybe_from_file(value: str, task_file_dir: Path) -> str:
    if value.startswith("@file:"):
        return (task_file_dir / value.removeprefix("@file:")).read_text(encoding="utf-8")
    return value



def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)



def copy_template(template_dir: Path, dest_dir: Path) -> None:
    if not template_dir.exists():
        raise FileNotFoundError(f"template_dir not found: {template_dir}")
    for item in template_dir.iterdir():
        dest = dest_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)



def task_goal(task: dict[str, Any]) -> str:
    goal = task.get("goal") or task.get("issue_statement")
    if not goal:
        raise ValueError(f"Task must define 'goal' or 'issue_statement': {task}")
    return str(goal)



def task_repeats(task: dict[str, Any], default_repeats: int) -> int:
    return max(int(task.get("repeats", default_repeats)), 1)



def _load_text_factory(task_file_dir: Path):
    return lambda value: load_text_maybe_from_file(value, task_file_dir)



def materialize_task(task: dict[str, Any], workdir: Path, task_file_dir: Path) -> None:
    loader = _load_text_factory(task_file_dir)

    template_dir = task.get("template_dir")
    if template_dir:
        copy_template((task_file_dir / template_dir).resolve(), workdir)

    task_utils.materialize_file_map(workdir, task.get("files") or {}, loader)

    for rel_path in task.get("mkdirs") or []:
        (workdir / rel_path).mkdir(parents=True, exist_ok=True)

    init_git = bool(task.get("init_git", False))
    if init_git:
        subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
        subprocess.run(["git", "config", "user.email", "bench@example.com"], cwd=workdir, check=True)
        subprocess.run(["git", "config", "user.name", "AgentForge Bench"], cwd=workdir, check=True)
        subprocess.run(["git", "add", "."], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=workdir, check=True)

    setup_commands = task.get("setup_commands") or task.get("setup") or task.get("repo_setup") or []
    if isinstance(setup_commands, str):
        setup_commands = [setup_commands]
    for command in setup_commands:
        subprocess.run(str(command), cwd=workdir, shell=True, check=True)



def materialize_hidden_assets(task: dict[str, Any], hidden_dir: Path, task_file_dir: Path) -> None:
    loader = _load_text_factory(task_file_dir)

    hidden_template_dir = task.get("hidden_template_dir")
    if hidden_template_dir:
        copy_template((task_file_dir / hidden_template_dir).resolve(), hidden_dir)

    task_utils.materialize_file_map(hidden_dir, task.get("hidden_files") or {}, loader)



def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows



def summarize_events(events: list[dict[str, Any]]) -> dict[str, int]:
    tool_events = [e for e in events if e.get("event_type") == "tool_call"]
    by_name: dict[str, int] = {}
    for e in tool_events:
        name = e.get("tool_name", "unknown")
        by_name[name] = by_name.get(name, 0) + 1
    return {
        "tool_calls": len(tool_events),
        "shell_calls": by_name.get("shell", 0) + by_name.get("shell_background", 0),
        "read_file_calls": by_name.get("read_file", 0),
        "write_file_calls": by_name.get("write_file", 0),
        "list_files_calls": by_name.get("list_files", 0),
    }



def build_verify_env(workdir: Path, hidden_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["TARGET_WORKDIR"] = str(workdir)
    env["BENCH_WORKDIR"] = str(workdir)
    env["BENCH_HIDDEN_DIR"] = str(hidden_dir)
    return env



def resolve_verify_commands(task: dict[str, Any], workdir: Path, hidden_dir: Path) -> tuple[str | None, str | None]:
    public_cmd = task.get("public_verify") or task.get("verify") or task.get("verify_cmd")
    hidden_cmd = task.get("hidden_verify") or task.get("hidden_verify_cmd")
    return (
        task_utils.resolve_command_template(public_cmd, workdir=workdir, hidden_dir=hidden_dir),
        task_utils.resolve_command_template(hidden_cmd, workdir=workdir, hidden_dir=hidden_dir),
    )



def run_verify(command: str | None, workdir: Path, hidden_dir: Path) -> tuple[int | None, bool | None, str | None, str | None]:
    if not command:
        return None, None, None, None
    proc = subprocess.run(
        command,
        cwd=workdir,
        shell=True,
        text=True,
        capture_output=True,
        env=build_verify_env(workdir, hidden_dir),
    )
    return proc.returncode, proc.returncode == 0, proc.stdout, proc.stderr



def expand_run_id(case_id: str, repeat_index: int, repeats: int) -> str:
    if repeats <= 1:
        return case_id
    return f"{case_id}#run{repeat_index + 1}"



def run_case(
    agentforge,
    task: dict[str, Any],
    work_root: Path,
    hidden_root: Path,
    task_file_dir: Path,
    default_worker_model: str | None,
    default_eval_model: str | None,
    default_max_iterations: int,
    default_eval_every: int,
    dry_run: bool,
    reset_knowledge: bool,
    repeat_index: int,
    repeats: int,
) -> CaseResult:
    case_id = str(task["id"])
    run_id = expand_run_id(case_id, repeat_index, repeats)
    goal = task_goal(task)
    mode = str(task.get("mode", "code"))

    workdir_name = case_id if repeats <= 1 else f"{case_id}__run{repeat_index + 1:02d}"
    workdir = work_root / workdir_name
    hidden_dir = hidden_root / workdir_name
    ensure_clean_dir(workdir)
    ensure_clean_dir(hidden_dir)
    materialize_task(task, workdir, task_file_dir)
    materialize_hidden_assets(task, hidden_dir, task_file_dir)
    before_state = task_utils.capture_tree_state(workdir)

    public_verify_cmd, hidden_verify_cmd = resolve_verify_commands(task, workdir, hidden_dir)
    max_iterations = int(task.get("max_iterations", default_max_iterations))
    eval_every = int(task.get("eval_every", default_eval_every))
    worker_model = task.get("worker_model", default_worker_model)
    eval_model = task.get("eval_model", default_eval_model)

    knowledge_dir = Path(agentforge._knowledge_path(goal))
    if reset_knowledge and knowledge_dir.exists():
        shutil.rmtree(knowledge_dir, ignore_errors=True)

    agentforge._set_session_context(str(workdir))
    events_path = Path(agentforge._current_event_log_file())
    memory_events_path = Path(agentforge._memory_events_path(goal))
    for path in (events_path, memory_events_path):
        if path.exists():
            path.unlink()

    if dry_run:
        return CaseResult(
            case_id=case_id,
            run_id=run_id,
            repeat_index=repeat_index,
            repeats=repeats,
            goal=goal,
            workdir=str(workdir),
            hidden_dir=str(hidden_dir),
            run_status="dry_run",
            duration_seconds=0.0,
            attempts=0,
            final_decision=None,
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
            tool_calls=0,
            shell_calls=0,
            read_file_calls=0,
            write_file_calls=0,
            list_files_calls=0,
            changed_files=[],
            confidence=None,
            edit_precision_score=None,
            quality_score=0.0,
            efficiency_score=0.0,
            session_events_path=str(events_path),
            memory_events_path=str(memory_events_path),
            attempts_path=str(knowledge_dir / "attempts.jsonl"),
        )

    layout = build_single_layout()
    live = DummyLive()
    started = time.time()
    run_status = agentforge.run_agent_loop(
        goal=goal,
        workdir=str(workdir),
        worker_model=worker_model,
        eval_model=eval_model,
        max_iter=max_iterations,
        layout=layout,
        live=live,
        mode=mode,
        eval_every=eval_every,
    )
    duration_seconds = time.time() - started

    attempts_path = knowledge_dir / "attempts.jsonl"
    attempts = read_jsonl(attempts_path)
    memory_events = read_jsonl(memory_events_path)
    counters = summarize_events(memory_events)
    last_attempt = attempts[-1] if attempts else {}
    final_decision = last_attempt.get("decision")
    confidence = last_attempt.get("confidence")

    changed_files = task_utils.diff_tree_states(before_state, task_utils.capture_tree_state(workdir))
    changed_files = task_utils.clean_path_list(changed_files)
    edit_precision_score = metrics.compute_edit_precision_score(
        changed_files,
        expected_changed_files=task.get("expected_changed_files"),
        allowed_changed_files=task.get("allowed_changed_files"),
    )

    public_rc, public_passed, public_stdout, public_stderr = run_verify(public_verify_cmd, workdir, hidden_dir)
    hidden_rc, hidden_passed, hidden_stdout, hidden_stderr = run_verify(hidden_verify_cmd, workdir, hidden_dir)

    success = final_decision == "DONE"
    if public_passed is not None:
        success = success and public_passed
    if hidden_passed is not None:
        success = success and hidden_passed

    quality_score = metrics.compute_quality_score(
        final_decision=final_decision,
        public_verify_passed=public_passed,
        hidden_verify_passed=hidden_passed,
        edit_precision_score=edit_precision_score,
    )
    effort_count = counters["tool_calls"]
    efficiency_score = metrics.compute_efficiency_score(
        duration_seconds=duration_seconds,
        attempts=max(len(attempts), 1),
        effort_count=effort_count,
        quality_score=quality_score,
        target_duration_seconds=float(task.get("target_duration_seconds", 60.0)),
        target_effort_count=float(task.get("target_tool_calls", 10.0)),
    )

    return CaseResult(
        case_id=case_id,
        run_id=run_id,
        repeat_index=repeat_index,
        repeats=repeats,
        goal=goal,
        workdir=str(workdir),
        hidden_dir=str(hidden_dir),
        run_status=run_status,
        duration_seconds=duration_seconds,
        attempts=len(attempts),
        final_decision=final_decision,
        public_verify_cmd=public_verify_cmd,
        public_verify_returncode=public_rc,
        public_verify_passed=public_passed,
        hidden_verify_cmd=hidden_verify_cmd,
        hidden_verify_returncode=hidden_rc,
        hidden_verify_passed=hidden_passed,
        verify_cmd=public_verify_cmd,
        verify_returncode=public_rc,
        verify_passed=public_passed,
        success=bool(success),
        tool_calls=counters["tool_calls"],
        shell_calls=counters["shell_calls"],
        read_file_calls=counters["read_file_calls"],
        write_file_calls=counters["write_file_calls"],
        list_files_calls=counters["list_files_calls"],
        changed_files=changed_files,
        confidence=confidence,
        edit_precision_score=edit_precision_score,
        quality_score=quality_score,
        efficiency_score=efficiency_score,
        session_events_path=str(events_path) if events_path else None,
        memory_events_path=str(memory_events_path) if memory_events_path else None,
        attempts_path=str(attempts_path),
        public_verify_stdout=public_stdout,
        public_verify_stderr=public_stderr,
        hidden_verify_stdout=hidden_stdout,
        hidden_verify_stderr=hidden_stderr,
    )



def summarize_case_aggregates(results: list[CaseResult]) -> list[CaseAggregate]:
    grouped: dict[str, list[CaseResult]] = {}
    for result in results:
        grouped.setdefault(result.case_id, []).append(result)

    aggregates: list[CaseAggregate] = []
    for case_id, runs in sorted(grouped.items()):
        runs = sorted(runs, key=lambda r: r.repeat_index)
        success_flags = [r.success for r in runs]
        quality_scores = [r.quality_score for r in runs]
        efficiency_scores = [r.efficiency_score for r in runs]
        durations = [r.duration_seconds for r in runs]
        attempts = [r.attempts for r in runs]
        tool_calls = [r.tool_calls for r in runs]
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
                avg_attempts=statistics.mean(attempts),
                avg_tool_calls=statistics.mean(tool_calls),
                public_verify_pass_rate=(sum(1 for flag in public_known if flag) / len(public_known)) if public_known else None,
                hidden_verify_pass_rate=(sum(1 for flag in hidden_known if flag) / len(hidden_known)) if hidden_known else None,
                best_run_id=best_run.run_id if best_run else None,
            )
        )
    return aggregates



def aggregate(results: list[CaseResult]) -> dict[str, Any]:
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
            "avg_attempts": 0.0,
            "avg_tool_calls": 0.0,
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
        "avg_attempts": statistics.mean(r.attempts for r in results),
        "avg_tool_calls": statistics.mean(r.tool_calls for r in results),
        "avg_quality_score": statistics.mean(r.quality_score for r in results),
        "avg_efficiency_score": statistics.mean(r.efficiency_score for r in results),
        "avg_public_verify_pass_rate": (sum(1 for flag in public_known if flag) / len(public_known)) if public_known else None,
        "avg_hidden_verify_pass_rate": (sum(1 for flag in hidden_known if flag) / len(hidden_known)) if hidden_known else None,
        "decisions": {
            key: sum(1 for r in results if r.final_decision == key)
            for key in sorted({r.final_decision for r in results if r.final_decision})
        },
    }



def result_to_dict(result: CaseResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["duration_seconds"] = round(result.duration_seconds, 3)
    return payload



def case_aggregate_to_dict(aggregate_item: CaseAggregate) -> dict[str, Any]:
    payload = asdict(aggregate_item)
    payload["pass_at_k"] = {str(k): v for k, v in aggregate_item.pass_at_k.items()}
    return payload



def print_summary(results: list[CaseResult], summary: dict[str, Any]) -> None:
    print("\n=== AgentForge Quality Benchmark Summary ===")
    print(f"cases: {summary['cases']}")
    print(f"runs: {summary['runs']}")
    print(f"run_success_rate: {summary['run_success_rate']:.3f}")
    print(f"case_pass_rate: {summary['case_pass_rate']:.3f}")
    print(f"avg_duration_seconds: {summary['avg_duration_seconds']:.2f}")
    print(f"median_duration_seconds: {summary['median_duration_seconds']:.2f}")
    print(f"avg_attempts: {summary['avg_attempts']:.2f}")
    print(f"avg_tool_calls: {summary['avg_tool_calls']:.2f}")
    print(f"avg_quality_score: {summary['avg_quality_score']:.2f}")
    print(f"avg_efficiency_score: {summary['avg_efficiency_score']:.2f}")
    if summary.get("pass_at_k"):
        print("pass_at_k: " + ", ".join(f"k={k}:{v:.3f}" for k, v in summary["pass_at_k"].items()))
    print("\nPer-run:")
    for r in results:
        public_state = "n/a" if r.public_verify_passed is None else ("pass" if r.public_verify_passed else "fail")
        hidden_state = "n/a" if r.hidden_verify_passed is None else ("pass" if r.hidden_verify_passed else "fail")
        print(
            f"- {r.run_id}: success={r.success} decision={r.final_decision} "
            f"quality={r.quality_score:.1f} efficiency={r.efficiency_score:.1f} "
            f"public={public_state} hidden={hidden_state} attempts={r.attempts} tools={r.tool_calls} duration={r.duration_seconds:.2f}s"
        )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark AgentForge on a task suite")
    parser.add_argument("--tasks", required=True, help="Path to JSON or JSONL task suite")
    parser.add_argument("--work-root", default="./.bench_runs", help="Directory to create isolated case workdirs")
    parser.add_argument("--hidden-root", default="./.bench_hidden", help="Directory to create hidden verifier assets")
    parser.add_argument("--output", default="./benchmark_results.json", help="Where to save results JSON")
    parser.add_argument("--worker-model", default=None, help="Default worker model")
    parser.add_argument("--eval-model", default=None, help="Default evaluator model")
    parser.add_argument("--max-iterations", type=int, default=8, help="Default max iterations per task")
    parser.add_argument("--eval-every", type=int, default=1, help="Default evaluator frequency")
    parser.add_argument("--repeats", type=int, default=1, help="Default repeat count per task")
    parser.add_argument("--dry-run", action="store_true", help="Prepare task directories without calling the model")
    parser.add_argument(
        "--keep-knowledge",
        action="store_true",
        help="Do not delete ~/.agentforge/knowledge/<goal> before each run",
    )
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    repo_root = repo_root_from_script()
    agentforge = load_agentforge(repo_root)

    tasks_path = Path(args.tasks).resolve()
    task_file_dir = tasks_path.parent
    tasks = read_json_or_jsonl(tasks_path)
    work_root = Path(args.work_root).resolve()
    hidden_root = Path(args.hidden_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    hidden_root.mkdir(parents=True, exist_ok=True)

    results: list[CaseResult] = []
    for task in tasks:
        if "id" not in task:
            raise ValueError(f"Each task must have 'id': {task}")
        repeats = task_repeats(task, args.repeats)
        for repeat_index in range(repeats):
            print(f"[run] {task['id']} ({repeat_index + 1}/{repeats})")
            result = run_case(
                agentforge=agentforge,
                task=task,
                work_root=work_root,
                hidden_root=hidden_root,
                task_file_dir=task_file_dir,
                default_worker_model=args.worker_model,
                default_eval_model=args.eval_model,
                default_max_iterations=args.max_iterations,
                default_eval_every=args.eval_every,
                dry_run=args.dry_run,
                reset_knowledge=not args.keep_knowledge,
                repeat_index=repeat_index,
                repeats=repeats,
            )
            results.append(result)

    summary = aggregate(results)
    case_aggregates = summarize_case_aggregates(results)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dry_run": args.dry_run,
        "repo_root": str(repo_root),
        "tasks_path": str(tasks_path),
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
