from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path
from typing import Iterable


NOISE_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
NOISE_PATTERNS = [
    "agentforge_debug_*.log",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
]



def is_noise_path(path: str | Path) -> bool:
    p = Path(path)
    if any(part in NOISE_PARTS for part in p.parts):
        return True
    return any(fnmatch.fnmatch(p.name, pattern) for pattern in NOISE_PATTERNS)



def resolve_command_template(command: str | None, *, workdir: str | Path, hidden_dir: str | Path | None = None) -> str | None:
    if command is None:
        return None
    return str(command).format(
        workdir=str(Path(workdir)),
        hidden_dir=str(Path(hidden_dir)) if hidden_dir is not None else "",
    )



def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()



def capture_tree_state(root: str | Path) -> dict[str, str]:
    base = Path(root)
    state: dict[str, str] = {}
    if not base.exists():
        return state
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = path.relative_to(base)
        if is_noise_path(rel):
            continue
        state[str(rel)] = file_digest(path)
    return state



def diff_tree_states(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: set[str] = set()
    all_paths = set(before) | set(after)
    for rel in all_paths:
        if before.get(rel) != after.get(rel):
            changed.add(rel)
    return sorted(changed)



def materialize_file_map(base_dir: str | Path, files_map: dict[str, str], text_loader) -> None:
    root = Path(base_dir)
    for rel_path, content in files_map.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text_loader(content), encoding="utf-8")



def clean_path_list(paths: Iterable[str]) -> list[str]:
    unique = []
    seen = set()
    for raw in paths:
        rel = str(Path(raw))
        if is_noise_path(rel):
            continue
        if rel not in seen:
            seen.add(rel)
            unique.append(rel)
    return sorted(unique)
