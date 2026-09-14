from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Iterable

from .models import FeatureRevision


def _feature_id(path: Path, anchor: str) -> str:
    return "feature_" + hashlib.sha256(f"{path.as_posix()}::{anchor}".encode()).hexdigest()[:20]


def discover_python_features(root: str | Path, source_identity: str) -> tuple[FeatureRevision, ...]:
    base = Path(root).resolve()
    found: list[FeatureRevision] = []
    for path in sorted(base.rglob("*.py")):
        if any(part.startswith(".") for part in path.relative_to(base).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (OSError, UnicodeError, SyntaxError):
            continue
        rel = path.relative_to(base)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                anchor = f"{rel.as_posix()}:{node.name}:{node.lineno}"
                confidence = "PROVISIONAL" if isinstance(node, ast.ClassDef) else "CONFIRMED"
                found.append(FeatureRevision(
                    _feature_id(rel, anchor), "1", source_identity,
                    user_task=f"Exercise entrypoint {node.name}",
                    entrypoints=(anchor,), requirement_refs=(),
                    discovery_confidence=confidence,
                ))
    return tuple(found)
