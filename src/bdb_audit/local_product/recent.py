"""Optional campaign shortcuts; verified LOCAL stores remain authoritative."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import sqlite3
from typing import Any

from ..core.errors import ValidationError
from .artifacts import safe_path
from .workflow import LocalWorkflow


class RecentCampaigns:
    def __init__(self, path: str | Path | None = None):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "BDBAudit"
        self.path = Path(path) if path is not None else base / "local-campaigns.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        safe_path(self.path.parent, self.path)
        with self.path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValidationError("LOCAL_RECENT_INDEX_TOO_LARGE")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("format") != "BDB_LOCAL_SHORTCUTS_1":
            raise ValidationError("LOCAL_RECENT_INDEX_INVALID")
        entries = data.get("campaigns")
        if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("path"), str)
                                               or not isinstance(e.get("last_opened"), (int, float)) for e in entries):
            raise ValidationError("LOCAL_RECENT_INDEX_INVALID")
        return entries

    def remember(self, workflow: LocalWorkflow, report: str | Path | None = None) -> None:
        entries = self._load()
        location = str(workflow.store.root)
        entry = next((e for e in entries if e["path"] == location), {"path": location, "reports": []})
        entry = {**entry, "last_opened": time.time()}
        if report is not None:
            entry["reports"] = list(dict.fromkeys([*entry.get("reports", []), str(Path(report).resolve())]))
        entries = [entry, *(e for e in entries if e["path"] != location)][:200]
        safe_path(self.path.parent, self.path, missing_ok=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".local-shortcuts-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"format": "BDB_LOCAL_SHORTCUTS_1", "campaigns": entries}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def entries(self) -> list[dict[str, Any]]:
        rows = []
        for entry in sorted(self._load(), key=lambda e: e["last_opened"], reverse=True):
            row = {**entry, "name": Path(entry["path"]).name}
            try:
                workflow = LocalWorkflow(entry["path"])
                row.update(state=workflow.status()["status"], source=workflow.source, stage=workflow.stage,
                           last_activity=workflow.store.path.stat().st_mtime, history_events=len(workflow.events))
            except (ValidationError, OSError, ValueError, sqlite3.Error) as exc:
                row.update(state="BRAK / NIESPÓJNY STORE", error=str(exc))
            rows.append(row)
        return rows

    def report_shortcuts(self, root: Path) -> list[Path]:
        for entry in self._load():
            if entry["path"] == str(root):
                return [Path(value) for value in entry.get("reports", []) if isinstance(value, str)]
        return []
