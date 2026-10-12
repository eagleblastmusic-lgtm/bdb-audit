"""Read-only screen projection and thin orchestration of the LOCAL workflow."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from ..core.canonical_json import parse
from ..core.errors import ValidationError
from .artifacts import WindowsActions, export_copy, package_probe, safe_path, verified_bytes
from .profile import MODE, STAGES, task_definition
from .recent import RecentCampaigns
from .report import export_report
from .workflow import LocalWorkflow

RESULT_LABELS = {"IMPORTED_UNTRUSTED": "IMPORTOWANY_NIEZAUFANY", "VALIDATED_STRUCTURE": "WYMAGA_DECYZJI",
                 "USER_ACCEPTED_LOCAL": "ZAAKCEPTOWANY_LOKALNIE", "REJECTED": "ODRZUCONY"}


class CampaignController:
    def __init__(self, root: str | Path, *, actions: WindowsActions | None = None,
                 recent: RecentCampaigns | None = None):
        self.root = LocalWorkflow(root).store.root
        self.actions = actions if actions is not None else WindowsActions()
        self.recent = recent

    def workflow(self, expected_head: str | None = None) -> LocalWorkflow:
        workflow = LocalWorkflow(self.root)
        if expected_head is not None and workflow.head != expected_head:
            raise ValidationError("LOCAL_SCREEN_CHANGED", "Stan zmienił się od podglądu. Odśwież i przeczytaj ponownie.")
        return workflow

    def view(self) -> dict[str, Any]:
        workflow = self.workflow()
        status = workflow.status()
        stage = workflow.stage if workflow.stage != "COMPLETE" else workflow.completed[-1]
        paths = {p["task_id"]: Path(p["path"]) for p in status["packages"]}
        rows = []
        for task, title, _ in STAGES[stage]:
            package = workflow.packages.get(task)
            row: dict[str, Any] = {"task_id": task, "title": title, "stage": stage,
                                   "available": task in status["available_tasks"], "result_ids": []}
            if package is not None:
                row.update(package_probe(self.root / "packages", paths[task], package["raw"]))
            else:
                row.update(state="DO PRZYGOTOWANIA" if row["available"] else "OCZEKUJE NA E5-A",
                           path=None, raw_verified=False)
            results = [(rid, result) for rid, result in workflow.results.items()
                       if result["response"].get("task_id") == task]
            row["result_ids"] = [rid for rid, _ in results]
            pending = [(rid, result) for rid, result in results
                       if result["state"] in {"IMPORTED_UNTRUSTED", "VALIDATED_STRUCTURE"}]
            accepted = workflow.accepted.get(task)
            selected = pending[-1] if pending else results[-1] if results else None
            row["result_state"] = RESULT_LABELS[selected[1]["state"]] if selected else "BRAK"
            row["accepted_result"] = accepted
            row["review_result"] = pending[-1][0] if pending else None
            row["complete"] = accepted is not None
            if accepted and not pending:
                row["result_state"] = "ZAAKCEPTOWANY_LOKALNIE"
            rows.append(row)
        progress = [{"stage": name, "state": "UKOŃCZONY" if name in workflow.completed
                     else "BIEŻĄCY" if name == workflow.stage else "OCZEKUJE"} for name in STAGES]
        reports = self.reports(workflow)
        return {"mode": MODE, "name": self.root.name, "root": str(self.root), "stage": stage,
                "workflow_stage": workflow.stage, "status": status, "packages": rows, "progress": progress,
                "reports": reports, "next": self._next(workflow, status, rows, reports),
                "accepted_count": len(workflow.accepted), "producer_counts": dict(Counter(
                    workflow.results[rid]["response"]["producer"]["kind"] for rid in workflow.accepted.values()))}

    @staticmethod
    def _next(workflow: LocalWorkflow, status: dict[str, Any], rows: list[dict[str, Any]],
              reports: list[dict[str, Any]]) -> dict[str, str]:
        def step(action: str, label: str, message: str) -> dict[str, str]:
            return {"action": action, "label": label, "message": message}
        if workflow.stage == "COMPLETE":
            current = [r for r in reports if r.get("verified") and r.get("history_head") == workflow.head]
            return step("report", "Otwórz raport" if current else "Utwórz raport", "E1–E6 ukończone lokalnie; to nie kwalifikacja HIGH ASSURANCE.")
        if workflow.pending_runs:
            return step("tools", "Odzyskaj receipt / rozstrzygnij przerwaną kontrolę", "Przejście etapu jest zablokowane przez rzeczywisty pending run.")
        broken = [r["task_id"] for r in rows if r["state"] == "NIESPÓJNA"]
        if broken:
            return step("packages", "Sprawdź niespójną paczkę", "Blokada otwierania: " + ", ".join(broken))
        if any(r["available"] and r["state"] in {"DO PRZYGOTOWANIA", "BRAK PLIKU"} for r in rows):
            return step("prepare", "Przygotuj / przywróć paczki", "Odtworzenie z vault zachowuje tożsamość i historię; sprzeczne bajty nie zostaną nadpisane.")
        review_row = next((r for r in rows if r["review_result"]), None)
        if review_row:
            return {**step("review", "Sprawdź i zatwierdź lokalnie", "Przeczytaj wyniki i dowody. Import ani powrót do menu nie oznaczają akceptacji."),
                    "result_id": review_row["review_result"]}
        if status["missing_results"]:
            rejected = any(r["result_state"] == "ODRZUCONY" and not r["complete"] for r in rows)
            return step("import", "Popraw / wybierz inny wynik" if rejected else "Dodaj wynik AI",
                        "Paczki są gotowe. Przekaż je audytorom. Brakujące wyniki: " + ", ".join(status["missing_results"]))
        following = list(STAGES)[list(STAGES).index(workflow.stage) + 1:] or ["COMPLETE"]
        label = "Zakończ E6 i utwórz raport" if following[0] == "COMPLETE" else "Przejdź do " + following[0]
        return step("advance", label, "Wszystkie obowiązkowe wyniki zostały ręcznie przyjęte lokalnie. Przejście wymaga osobnego potwierdzenia.")

    def _package(self, task: str) -> tuple[LocalWorkflow, Path, dict[str, Any]]:
        workflow = self.workflow()
        stage = workflow.stage if workflow.stage != "COMPLETE" else workflow.completed[-1]
        if task not in {t for t, _, _ in STAGES[stage]} or task not in workflow.packages:
            raise ValidationError("LOCAL_CURRENT_PACKAGE_REQUIRED", task)
        # The engine owns the publication path; the retained package owns its
        # exact byte identity. No path from a response, title or UI input is used.
        artifact = next(p for p in workflow.status()["packages"] if p["task_id"] == task)
        path = Path(artifact["path"])
        identity = workflow.packages[task]["raw"]
        verified_bytes(self.root / "packages", path, identity)
        return workflow, path, identity

    def select_package(self, task: str) -> Path:
        _, path, _ = self._package(task)
        self.actions.select(path)
        return path

    def open_package_folder(self, task: str | None = None) -> Path:
        view = self.view()
        tasks = [task] if task is not None else [r["task_id"] for r in view["packages"] if r["path"]]
        if not tasks:
            raise ValidationError("LOCAL_CURRENT_PACKAGE_REQUIRED")
        folders = {self._package(t)[1].parent for t in tasks}
        if len(folders) != 1:
            raise ValidationError("LOCAL_MULTIPLE_PACKAGE_FOLDERS", "Wybierz pojedynczą paczkę: " + ", ".join(map(str, folders)))
        path = folders.pop()
        self.actions.folder(path)
        return path

    def copy_package_path(self, task: str) -> dict[str, Any]:
        _, path, _ = self._package(task)
        return {"path": str(path), "copied": self.actions.clipboard(path)}

    def export_package(self, task: str, destination: str | Path) -> Path:
        _, path, identity = self._package(task)
        return export_copy(self.root, path, identity, Path(destination))

    def prepare(self) -> dict[str, Any]:
        workflow = self.workflow()
        safe_path(self.root, self.root / "packages", missing_ok=True)
        for artifact in workflow.status()["packages"]:
            safe_path(self.root / "packages", Path(artifact["path"]), missing_ok=True)
        return workflow.prepare()

    def import_result(self, file: str | Path) -> dict[str, Any]:
        workflow = self.workflow()
        inspected = workflow.inspect(file)
        if inspected["issues"]:
            raise ValidationError("LOCAL_IMPORT_VALIDATION_FAILED", "; ".join(inspected["issues"]))
        response = inspected["response"]
        if response["stage_id"] != workflow.stage or response["task_id"] not in workflow.status()["available_tasks"]:
            raise ValidationError("LOCAL_CURRENT_STAGE_REQUIRED", response["task_id"])
        imported = workflow.import_result(file, inspected["raw_sha256"])
        return workflow.validate(imported["result_id"])

    def preview(self, result_id: str) -> dict[str, Any]:
        workflow = self.workflow()
        return {**workflow.result_info(result_id), "history_head": workflow.head}

    def decide(self, result_id: str, decision: str, *, actor: str, expected_head: str,
               reason: str = "", replaces: str | None = None) -> dict[str, Any]:
        workflow = self.workflow(expected_head)
        if decision == "AKCEPTUJ LOCAL":
            return workflow.accept(result_id, actor, confirm=True, replaces=replaces)
        if decision == "ODRZUC":
            return workflow.reject(result_id, reason)
        raise ValidationError("LOCAL_MANUAL_CONFIRMATION_REQUIRED")

    def advance(self, expected_head: str) -> dict[str, Any]:
        workflow = self.workflow(expected_head)
        safe_path(self.root, self.root / "packages", missing_ok=True)
        for artifact in workflow.status()["packages"]:
            verified_bytes(self.root / "packages", Path(artifact["path"]), workflow.packages[artifact["task_id"]]["raw"])
        return workflow.advance()

    def export_report(self, output: str | Path | None = None) -> dict[str, Any]:
        workflow = self.workflow()
        if output is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            output = self.root / "reports" / (stamp + "-" + uuid.uuid4().hex[:8])
        path = Path(output).absolute()
        safe_path(path.parent, path, missing_ok=True)
        exported = export_report(workflow, path)
        if self.recent:
            try:
                self.recent.remember(workflow, path)
            except (OSError, ValueError):
                exported["shortcut_warning"] = "Eksport zapisany; skrót raportu nie został zapisany. Otwórz katalog eksportu z dysku."
        return exported

    def verify_report(self, root: str | Path, workflow: LocalWorkflow | None = None) -> dict[str, Any]:
        workflow = workflow if workflow is not None else self.workflow()
        path = Path(root).absolute()
        safe_path(path, path / "EVIDENCE_MANIFEST.json")
        manifest = parse((path / "EVIDENCE_MANIFEST.json").read_bytes())
        if (not isinstance(manifest, dict) or manifest.get("format") != "BDB_LOCAL_REPORT_EVIDENCE_1"
                or manifest.get("mode") != MODE or manifest.get("campaign_id") != workflow.campaign_id
                or not isinstance(manifest.get("history_head"), str)
                or manifest.get("history_head") not in {e["event_hash"] for e in workflow.events}):
            raise ValidationError("LOCAL_REPORT_CONTEXT_MISMATCH", str(path))
        entries = manifest.get("reports", [])
        if (not isinstance(entries, list) or len(entries) != 2
                or any(not isinstance(e, dict) or e.get("path") not in ("REPORT.md", "REPORT.json") for e in entries)
                or {e["path"] for e in entries} != {"REPORT.md", "REPORT.json"}):
            raise ValidationError("LOCAL_REPORT_MANIFEST_INVALID", str(path))
        for entry in entries:
            verified_bytes(path, path / entry["path"], {"raw_digest": entry.get("sha256"), "byte_length": entry.get("byte_length")})
        report = parse((path / "REPORT.json").read_bytes())
        if (not isinstance(report, dict) or not isinstance(report.get("status"), str)
                or not isinstance(report.get("accepted_responses"), list)
                or report.get("format") != "BDB_LOCAL_AUDIT_REPORT_1" or report.get("mode") != MODE
                or report.get("campaign_id") != workflow.campaign_id or report.get("input_history_head") != manifest["history_head"]):
            raise ValidationError("LOCAL_REPORT_CONTEXT_MISMATCH", str(path))
        return {"path": str(path), "verified": True, "history_head": manifest["history_head"],
                "status": report["status"], "accepted_count": len(report["accepted_responses"])}

    def reports(self, workflow: LocalWorkflow | None = None) -> list[dict[str, Any]]:
        roots: list[Path] = []
        base = self.root / "reports"
        if base.exists():
            try:
                safe_path(self.root, base)
                roots.extend(p.parent for p in base.glob("*/EVIDENCE_MANIFEST.json"))
            except (OSError, ValidationError):
                pass
        if self.recent:
            try:
                roots.extend(self.recent.report_shortcuts(self.root))
            except (OSError, ValueError):
                pass
        rows = []
        for root in sorted(set(roots), key=str, reverse=True):
            try:
                rows.append(self.verify_report(root, workflow))
            except (ValidationError, OSError, ValueError, KeyError, TypeError) as exc:
                rows.append({"path": str(root), "verified": False, "error": str(exc)})
        return rows

    def open_report(self, root: str | Path, action: str) -> str:
        self.verify_report(root)
        path = Path(root).absolute()
        if action == "markdown":
            self.actions.document(path / "REPORT.md")
            return str(path / "REPORT.md")
        if action == "folder":
            self.actions.folder(path)
            return str(path)
        if action == "json":
            return (path / "REPORT.json").read_text(encoding="utf-8")
        raise ValidationError("LOCAL_REPORT_ACTION_INVALID")
