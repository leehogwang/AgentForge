from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_QUALITY_WEIGHTS = {
    "decision": 0.10,
    "public_verify": 0.45,
    "hidden_verify": 0.35,
    "edit_precision": 0.10,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def compute_pass_at_k(grouped_results: Mapping[str, Sequence[bool]], ks: Sequence[int] | None = None) -> dict[int, float]:
    if not grouped_results:
        return {}
    max_runs = max((len(v) for v in grouped_results.values()), default=0)
    if max_runs <= 0:
        return {}
    if ks is None:
        ks = list(range(1, max_runs + 1))

    pass_at: dict[int, float] = {}
    case_values = list(grouped_results.values())
    for raw_k in ks:
        k = int(raw_k)
        if k <= 0:
            continue
        successes = 0
        for runs in case_values:
            window = list(runs[:k])
            if any(window):
                successes += 1
        pass_at[k] = successes / len(case_values)
    return pass_at


def compute_edit_precision_score(
    changed_files: Sequence[str] | None,
    expected_changed_files: Sequence[str] | None = None,
    allowed_changed_files: Sequence[str] | None = None,
) -> float | None:
    changed = {str(p) for p in (changed_files or []) if str(p)}
    expected = {str(p) for p in (expected_changed_files or []) if str(p)}
    allowed = {str(p) for p in (allowed_changed_files or []) if str(p)}

    if not expected and not allowed:
        return None
    if not allowed:
        allowed = set(expected)

    missing_ratio = len(expected - changed) / max(len(expected), 1) if expected else 0.0
    unexpected_ratio = len(changed - allowed) / max(len(changed), 1) if changed else 0.0
    score = 1.0 - (0.6 * missing_ratio) - (0.4 * unexpected_ratio)
    return round(_clamp(score), 4)



def compute_quality_score(
    *,
    final_decision: str | None,
    public_verify_passed: bool | None,
    hidden_verify_passed: bool | None,
    edit_precision_score: float | None = None,
    weights: Mapping[str, float] | None = None,
) -> float:
    weights = dict(DEFAULT_QUALITY_WEIGHTS if weights is None else weights)
    components: list[tuple[float, float]] = []

    if final_decision is not None:
        components.append((1.0 if str(final_decision).upper() == "DONE" else 0.0, weights.get("decision", 0.0)))
    if public_verify_passed is not None:
        components.append((1.0 if public_verify_passed else 0.0, weights.get("public_verify", 0.0)))
    if hidden_verify_passed is not None:
        components.append((1.0 if hidden_verify_passed else 0.0, weights.get("hidden_verify", 0.0)))
    if edit_precision_score is not None:
        components.append((_clamp(edit_precision_score), weights.get("edit_precision", 0.0)))

    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        return 0.0
    score = sum(value * weight for value, weight in components) / total_weight
    return round(score * 100.0, 2)



def compute_efficiency_score(
    *,
    duration_seconds: float,
    attempts: int,
    effort_count: int,
    quality_score: float,
    target_duration_seconds: float = 60.0,
    target_effort_count: float = 10.0,
) -> float:
    quality_ratio = _clamp((quality_score or 0.0) / 100.0)
    if quality_ratio <= 0.0:
        return 0.0

    attempts = max(int(attempts or 1), 1)
    effort_count = max(int(effort_count or 0), 0)
    duration_seconds = max(float(duration_seconds or 0.0), 0.0)
    target_duration_seconds = max(float(target_duration_seconds or 60.0), 1.0)
    target_effort_count = max(float(target_effort_count or 10.0), 1.0)

    duration_component = target_duration_seconds / (target_duration_seconds + duration_seconds)
    attempts_component = 1.0 / attempts
    effort_component = target_effort_count / (target_effort_count + effort_count)

    raw_efficiency = (0.5 * duration_component) + (0.25 * attempts_component) + (0.25 * effort_component)
    return round(quality_ratio * raw_efficiency * 100.0, 2)



def group_run_field(results: Sequence[Any], field: str) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for item in results:
        case_id = getattr(item, "case_id", None)
        if case_id is None and isinstance(item, Mapping):
            case_id = item.get("case_id")
        if case_id is None:
            continue
        value = getattr(item, field, None)
        if isinstance(item, Mapping):
            value = item.get(field)
        grouped.setdefault(str(case_id), []).append(value)
    return grouped
