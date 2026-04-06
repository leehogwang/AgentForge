from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS = load_module(REPO_ROOT / "benchmarks" / "benchmark_metrics.py", "benchmark_metrics")
TASK_UTILS = load_module(REPO_ROOT / "benchmarks" / "benchmark_task_utils.py", "benchmark_task_utils")


def test_compute_pass_at_k_uses_repeats_per_case():
    grouped = {
        "case-a": [True, False, False],
        "case-b": [False, True, False],
        "case-c": [False, False, False],
    }
    pass_at = METRICS.compute_pass_at_k(grouped, ks=[1, 2, 3])
    assert pass_at == {1: 1 / 3, 2: 2 / 3, 3: 2 / 3}



def test_quality_score_rewards_hidden_pass_more_than_done_flag():
    weak = METRICS.compute_quality_score(
        final_decision="DONE",
        public_verify_passed=True,
        hidden_verify_passed=False,
        edit_precision_score=0.5,
    )
    strong = METRICS.compute_quality_score(
        final_decision="DONE",
        public_verify_passed=True,
        hidden_verify_passed=True,
        edit_precision_score=1.0,
    )
    assert 0 <= weak < strong <= 100
    assert strong >= 90



def test_efficiency_score_depends_on_quality_and_cost():
    fast_good = METRICS.compute_efficiency_score(
        duration_seconds=12.0,
        attempts=1,
        effort_count=4,
        quality_score=100.0,
        target_duration_seconds=30.0,
        target_effort_count=8.0,
    )
    slow_good = METRICS.compute_efficiency_score(
        duration_seconds=120.0,
        attempts=3,
        effort_count=20,
        quality_score=100.0,
        target_duration_seconds=30.0,
        target_effort_count=8.0,
    )
    failed = METRICS.compute_efficiency_score(
        duration_seconds=5.0,
        attempts=1,
        effort_count=1,
        quality_score=0.0,
        target_duration_seconds=30.0,
        target_effort_count=8.0,
    )
    assert fast_good > slow_good > failed
    assert failed == 0.0



def test_resolve_command_template_expands_workdir_and_hidden_dir():
    rendered = TASK_UTILS.resolve_command_template(
        "python {hidden_dir}/hidden_test.py --target {workdir}",
        workdir="/tmp/work",
        hidden_dir="/tmp/hidden",
    )
    assert rendered == "python /tmp/hidden/hidden_test.py --target /tmp/work"



def test_snapshot_diff_ignores_noise_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pkg.py").write_text("print('a')\n", encoding="utf-8")
        before = TASK_UTILS.capture_tree_state(root)

        (root / "pkg.py").write_text("print('b')\n", encoding="utf-8")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "pkg.cpython-313.pyc").write_bytes(b"x")
        (root / "agentforge_debug_20260406.log").write_text("debug\n", encoding="utf-8")
        after = TASK_UTILS.capture_tree_state(root)
        changed = TASK_UTILS.diff_tree_states(before, after)

        assert changed == ["pkg.py"]
