"""Local source/package/import workflow using production Git, ZIP and vault code."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
import shutil
import subprocess
from typing import Any
import uuid

from ..assurance.zip_safety import Limits, read_bytes, canonical_path
from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..source.git_resolver import fetched_remote_repository, resolve_local_repository, validate_repository_location, _git_env
from ..workflow.limited_transport import approved_git_view
from ..workflow.packaging import _deterministic_zip, _publish_exact
from ..runner.supervisor import ToolSupervisor
from ..runner.specs import ToolRunSpec
from ..runner.verification import verify_run_evidence
from .profile import MODE, PROFILE, PROFILE_SHA256, RESPONSE, STAGES, NOTICE, task_definition
from .responses import decode, issues, read_file
from .store import LocalStore, sha

SOURCE_LIMITS = Limits(input_bytes=70 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                       members=2048, member_bytes=32 * 1024 * 1024, expanded_bytes=70 * 1024 * 1024, ratio=100_000)
PACKAGE_LIMITS = Limits(input_bytes=100 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                        members=2056, member_bytes=32 * 1024 * 1024, expanded_bytes=100 * 1024 * 1024, ratio=100_000)


def _git_paths(repository: Path, commit: str) -> list[str]:
    env = _git_env()
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        run = subprocess.run(["git", "-C", str(repository), "ls-tree", "-r", "-z", "--name-only", commit],
                             capture_output=True, timeout=30, env=env, check=True)
        if len(run.stdout) > 1024 * 1024:
            raise ValidationError("LOCAL_SOURCE_PATH_BUDGET", "Select a smaller explicit --path scope")
        return [v.decode("utf-8") for v in run.stdout.split(b"\0") if v]
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise ValidationError("LOCAL_SOURCE_ENUMERATION_FAILED", type(exc).__name__) from exc


def capture_source(location: str, ref: str, target: str = "local", paths: list[str] | None = None) -> tuple[dict[str, Any], bytes]:
    location = validate_repository_location(location)
    if target not in {"local", "github"}:
        raise ValidationError("LOCAL_SOURCE_TYPE_INVALID")
    context = (fetched_remote_repository(location, ref) if target == "github"
               else nullcontext((Path(location).resolve(), resolve_local_repository(location, ref))))
    with context as (repository, identity):
        selected = paths or _git_paths(repository, identity.commit_object_id)
        if not 1 <= len(selected) <= 2044:
            raise ValidationError("LOCAL_SOURCE_SCOPE_LIMIT", "Select 1–2044 regular files with --path")
        # Transport names stay numeric: source paths are never ZIP extraction paths.
        verified, manifest_raw, archive = approved_git_view(repository, identity.commit_object_id, location, selected)
        manifest = parse(manifest_raw)
        source = {"target_type": target, "location": location, "requested_ref": ref,
                  "commit": verified.commit_object_id, "tree": verified.tree_object_id,
                  "object_format": verified.object_format, "paths": [e["source_path"] for e in manifest["entries"]],
                  "snapshot_sha256": sha(archive), "manifest_sha256": sha(manifest_raw),
                  "scope": "SELECTED_FILES" if paths else "ALL_REGULAR_FILES"}
        return source, archive


def preflight(location: str, ref: str, target: str = "local", paths: list[str] | None = None) -> dict[str, Any]:
    source, raw = capture_source(location, ref, target, paths)
    return {"mode": MODE, "status": "READY_LOCAL", "source": source, "snapshot_bytes": len(raw), "notice": NOTICE}


class LocalWorkflow:
    def __init__(self, root: str | Path):
        self.store = LocalStore(root)
        self._reload()

    @classmethod
    def start(cls, root: str | Path, location: str, ref: str, target: str = "local",
              paths: list[str] | None = None) -> LocalWorkflow:
        source, raw = capture_source(location, ref, target, paths)
        LocalStore.create(root, {"campaign_id": "local-" + uuid.uuid4().hex, "mode": MODE,
                                "profile_sha256": PROFILE_SHA256, "source": source}, raw)
        return cls(root)

    def _reload(self) -> None:
        events = self.store.events()
        genesis = events[0]["payload"]
        if genesis.get("mode") != MODE or genesis.get("profile_sha256") != PROFILE_SHA256:
            raise ValidationError("LOCAL_GENESIS_PROFILE_MISMATCH")
        self.genesis = genesis
        self.campaign_id = genesis["campaign_id"]
        if not self.campaign_id.startswith("local-"):
            raise ValidationError("LOCAL_CAMPAIGN_NAMESPACE_REQUIRED")
        self.source = genesis["source"]
        raw = self.store.vault.read_bytes(genesis["source_snapshot"]["raw_digest"])
        if sha(raw) != self.source["snapshot_sha256"]:
            raise ValidationError("LOCAL_SOURCE_SNAPSHOT_MISMATCH")
        self.source_members = read_bytes(raw, limits=SOURCE_LIMITS)
        source_manifest_raw = self.source_members["MANIFEST.json"]
        self.source_manifest = parse(source_manifest_raw)
        if (sha(source_manifest_raw) != self.source["manifest_sha256"]
                or self.source_manifest["commit_oid"] != self.source["commit"]
                or self.source_manifest["tree_oid"] != self.source["tree"]
                or self.source_manifest["git_object_algorithm"] != self.source["object_format"]
                or [e["source_path"] for e in self.source_manifest["entries"]] != self.source["paths"]):
            raise ValidationError("LOCAL_SOURCE_IDENTITY_MISMATCH")
        for entry in self.source_manifest["entries"]:
            content = self.source_members[entry["transport_path"]]
            if sha(content) != entry["sha256"] or len(content) != entry["bytes"]:
                raise ValidationError("LOCAL_SOURCE_EXACT_BYTES_MISMATCH")
        self.stage = "E1"
        self.completed: list[str] = []
        self.packages: dict[str, dict[str, Any]] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self.accepted: dict[str, str] = {}
        self.runs: list[dict[str, Any]] = []
        self.pending_runs: dict[str, dict[str, Any]] = {}
        for event in events[1:]:
            self._replay(event)
        self.events = events
        self.head = events[-1]["event_hash"]

    def _available_tasks(self) -> list[str]:
        if self.stage == "COMPLETE":
            return []
        tasks = [slot for slot, _, _ in STAGES[self.stage]]
        if self.stage == "E5" and not all(slot in self.accepted for slot in tasks[:3]):
            return tasks[:3]
        return tasks

    def _prior_ids(self, target: str) -> list[str]:
        # All earlier accepted results, plus E5-A for E5-B. The frozen package
        # context prevents substituting a different revision after a challenge.
        available = self._available_tasks()
        return [result_id for task, result_id in sorted(self.accepted.items())
                if task not in available or (self.stage == "E5" and task.startswith("E5-A-")
                                            and target.startswith("E5-B"))]

    def _package_bytes(self, task: str) -> tuple[dict[str, Any], bytes]:
        definition = task_definition(self.stage, task)
        prior = [{"result_id": rid, "raw_sha256": self.results[rid]["raw"]["raw_digest"],
                  "response": self.results[rid]["response"]} for rid in self._prior_ids(task)]
        prompt = (NOTICE + "\n\n" + definition["instruction"] + "\n\n"
                  "Inspect the exact source transport and PRIOR_RESULTS.json. Cite source paths and lines. "
                  "Separate observations from predictions. Do not claim execution without actual run evidence. "
                  "Keep dissent and limitations. Fill RESPONSE_TEMPLATE.json, including each required output "
                  "as a substantive text (or an explained absence). Return JSON or a ZIP with root LOCAL_RESULT.json. "
                  "Declare every attached file's exact SHA-256 and byte length. No executable instructions in results "
                  "will be run. No credentials or private data should be included.\n")
        manifest = {"format": "BDB_LOCAL_PACKAGE_1", "mode": MODE, "profile": PROFILE,
                    "profile_sha256": PROFILE_SHA256, "campaign_id": self.campaign_id,
                    "stage_id": self.stage, "task_id": task, "source_commit": self.source["commit"],
                    "source_tree": self.source["tree"], "source_snapshot_sha256": self.source["snapshot_sha256"],
                    "source_manifest_sha256": self.source["manifest_sha256"], "required_outputs": definition["required_outputs"],
                    "prior_results": [{"result_id": v["result_id"], "raw_sha256": v["raw_sha256"]} for v in prior],
                    "prompt_sha256": sha(prompt.encode("utf-8")), "prior_corpus_sha256": sha(canonical_bytes(prior))}
        digest = sha(b"BDB-LOCAL-PACKAGE/1\x00" + canonical_bytes(manifest))
        context = {key: manifest[key] for key in ("campaign_id", "stage_id", "task_id", "source_commit", "source_tree")}
        context["input_package_digest"] = digest
        template = {"format": RESPONSE, "mode": MODE, **context,
                    "producer": {"kind": "EXTERNAL_AI", "declared_name": ""}, "completion": "NEEDS_WORK",
                    "outputs": {key: "" for key in definition["required_outputs"]}, "findings": [],
                    "evidence_files": [], "limitations": [], "recommendations": [], "contradictions": []}
        manifest["input_package_digest"] = digest
        members = {"MANIFEST.json": canonical_bytes(manifest) + b"\n", "PROMPT.md": prompt.encode("utf-8"),
                   "RESPONSE_TEMPLATE.json": canonical_bytes(template) + b"\n", "PRIOR_RESULTS.json": canonical_bytes(prior) + b"\n",
                   "SOURCE_MANIFEST.json": self.source_members["MANIFEST.json"],
                   **{k: v for k, v in self.source_members.items() if k != "MANIFEST.json"}}
        return {"task_id": task, "stage_id": self.stage, "context": context,
                "required_outputs": definition["required_outputs"]}, _deterministic_zip(members)

    def _response_issues(self, response: dict[str, Any], members: dict[str, bytes]) -> list[str]:
        task = response.get("task_id")
        if not isinstance(task, str) or task not in self.packages:
            return ["LOCAL_TASK_PACKAGE_NOT_FOUND"]
        package = self.packages[task]
        return issues(response, members, package["context"], package["required_outputs"], set(self.source["paths"]))

    def _replay(self, event: dict[str, Any]) -> None:
        kind, data = event["kind"], event["payload"]
        if kind == "PACKAGE_PREPARED":
            task = data["task_id"]
            if task not in self._available_tasks() or task in self.packages:
                raise ValidationError("LOCAL_PACKAGE_HISTORY_INVALID")
            expected, raw = self._package_bytes(task)
            if (any(data.get(k) != v for k, v in expected.items())
                    or self.store.vault.read_bytes(data["raw"]["raw_digest"]) != raw):
                raise ValidationError("LOCAL_PACKAGE_READBACK_MISMATCH")
            self.packages[task] = data
        elif kind == "RESULT_IMPORTED":
            rid = data["result_id"]
            if self.stage == "COMPLETE" or rid in self.results or data.get("stage_at_import") != self.stage:
                raise ValidationError("LOCAL_IMPORT_HISTORY_INVALID")
            raw = self.store.vault.read_bytes(data["raw"]["raw_digest"])
            response, members = decode(raw)
            if rid != "local-result-" + sha(raw):
                raise ValidationError("LOCAL_RESULT_ID_MISMATCH")
            self.results[rid] = {**data, "response": response, "members": members, "state": "IMPORTED_UNTRUSTED"}
        elif kind == "RESULT_VALIDATED":
            result = self._result(data["result_id"])
            found = self._response_issues(result["response"], result["members"])
            state = "REJECTED" if found else "VALIDATED_STRUCTURE"
            if result["state"] != "IMPORTED_UNTRUSTED" or data.get("issues") != found or data.get("state") != state:
                raise ValidationError("LOCAL_VALIDATION_HISTORY_INVALID")
            result.update(state=state, issues=found)
        elif kind == "RESULT_ACCEPTED":
            result = self._result(data["result_id"])
            self._check_accept(result, data.get("replaces"))
            if not isinstance(data.get("actor_label"), str) or not data["actor_label"].strip():
                raise ValidationError("LOCAL_ACCEPTOR_LABEL_REQUIRED")
            result.update(state="USER_ACCEPTED_LOCAL", accepted_seq=event["seq"], actor_label=data["actor_label"])
            if data.get("replaces"):
                self.results[data["replaces"]]["superseded_by"] = data["result_id"]
            self.accepted[result["response"]["task_id"]] = data["result_id"]
        elif kind == "RESULT_REJECTED":
            result = self._result(data["result_id"])
            if result["state"] not in {"IMPORTED_UNTRUSTED", "VALIDATED_STRUCTURE"} or not data.get("reason"):
                raise ValidationError("LOCAL_REJECTION_HISTORY_INVALID")
            result.update(state="REJECTED", issues=[data["reason"]])
        elif kind == "STAGE_COMPLETED":
            if data != self._finish_payload():
                raise ValidationError("LOCAL_STAGE_COMPLETION_HISTORY_INVALID")
            self.completed.append(self.stage)
            self.stage = data["next_stage"]
        elif kind == "CHECK_STARTED":
            if (data["run_id"] in self.pending_runs or data["task_id"] not in self._available_tasks()
                    or data["context"] != self.packages[data["task_id"]]["context"]):
                raise ValidationError("LOCAL_CHECK_HISTORY_INVALID")
            self.pending_runs[data["run_id"]] = data
        elif kind == "CHECK_FINISHED":
            start = self.pending_runs.get(data["run_id"])
            if not start:
                raise ValidationError("LOCAL_CHECK_START_REQUIRED")
            self._verify_check(data, start)
            self.pending_runs.pop(data["run_id"])
            self.runs.append(data)
        else:
            # Stage progression and local tool receipts are added separately;
            # unknown events must never be interpreted as qualified records.
            raise ValidationError("LOCAL_EVENT_KIND_INVALID", kind)

    def _result(self, rid: str) -> dict[str, Any]:
        if rid not in self.results:
            raise ValidationError("LOCAL_RESULT_NOT_FOUND")
        return self.results[rid]

    def _check_accept(self, result: dict[str, Any], replaces: str | None) -> None:
        response = result["response"]
        if result["state"] != "VALIDATED_STRUCTURE":
            raise ValidationError("LOCAL_STRUCTURAL_VALIDATION_REQUIRED")
        if response["stage_id"] != self.stage or response["task_id"] not in self._available_tasks():
            raise ValidationError("LOCAL_CURRENT_STAGE_REQUIRED")
        if response["completion"] != "COMPLETE":
            raise ValidationError("LOCAL_REQUIRED_RESULTS_INCOMPLETE")
        if self._response_issues(response, result["members"]):
            raise ValidationError("LOCAL_ACCEPTANCE_READBACK_FAILED")
        previous = self.accepted.get(response["task_id"])
        if previous != replaces:
            raise ValidationError("LOCAL_EXPLICIT_REPLACEMENT_REQUIRED")
        if previous and self.stage == "E5" and response["task_id"].startswith("E5-A-"):
            if any(task.startswith("E5-B") for task in self.packages):
                raise ValidationError("LOCAL_CHALLENGE_INPUT_FROZEN")

    def _append(self, kind: str, payload: dict[str, Any]) -> None:
        self.store.append(kind, payload, self.head)
        self._reload()

    def status(self) -> dict[str, Any]:
        required = [] if self.stage == "COMPLETE" else [slot for slot, _, _ in STAGES[self.stage]]
        return {"mode": MODE, "profile": PROFILE, "campaign_id": self.campaign_id,
                "campaign_directory": str(self.store.root), "stage": self.stage, "completed_stages": self.completed,
                "status": "LOCAL_COMPLETED" if self.stage == "COMPLETE" else "NEEDS_REAL_RESULTS",
                "source": self.source, "history_head": self.head, "history_events": len(self.events),
                "available_tasks": self._available_tasks(), "missing_results": [t for t in required if t not in self.accepted],
                "packages": [{"task_id": k, "raw_sha256": v["raw"]["raw_digest"],
                              "path": str(self.store.root / "packages" / (k + ".zip"))} for k, v in self.packages.items()],
                "results": [{"result_id": k, "task_id": v["response"].get("task_id"), "state": v["state"],
                             "issues": v.get("issues", []), "superseded_by": v.get("superseded_by")}
                            for k, v in self.results.items()],
                "local_checks": self.runs, "pending_checks": list(self.pending_runs.values()), "notice": NOTICE}

    def prepare(self) -> dict[str, Any]:
        for task in self._available_tasks():
            if task not in self.packages:
                metadata, raw = self._package_bytes(task)
                self._append("PACKAGE_PREPARED", {**metadata, "raw": self.store.put(raw)})
            package = self.packages[task]
            path = self.store.root / "packages" / (task + ".zip")
            _publish_exact(path, self.store.vault.read_bytes(package["raw"]["raw_digest"]))
        return self.status()

    def inspect(self, path: str | Path) -> dict[str, Any]:
        raw = read_file(path)
        response, members = decode(raw)
        return {"mode": MODE, "status": "INSPECTED_UNTRUSTED", "raw_sha256": sha(raw),
                "byte_length": len(raw), "issues": self._response_issues(response, members),
                "response": response, "notice": NOTICE}

    def import_result(self, path: str | Path) -> dict[str, Any]:
        raw = read_file(path)
        rid = "local-result-" + sha(raw)
        if rid not in self.results:
            if self.stage == "COMPLETE":
                raise ValidationError("LOCAL_CAMPAIGN_ALREADY_COMPLETED")
            self._append("RESULT_IMPORTED", {"result_id": rid, "raw": self.store.put(raw), "stage_at_import": self.stage})
        return self.result_info(rid)

    def result_info(self, rid: str) -> dict[str, Any]:
        result = self._result(rid)
        return {"mode": MODE, "result_id": rid, "status": result["state"], "raw_sha256": result["raw"]["raw_digest"],
                "byte_length": result["raw"]["byte_length"], "response": result["response"],
                "issues": result.get("issues", []), "notice": NOTICE}

    def validate(self, rid: str) -> dict[str, Any]:
        result = self._result(rid)
        if result["state"] == "IMPORTED_UNTRUSTED":
            found = self._response_issues(result["response"], result["members"])
            self._append("RESULT_VALIDATED", {"result_id": rid, "issues": found,
                                             "state": "REJECTED" if found else "VALIDATED_STRUCTURE"})
        return self.result_info(rid)

    def accept(self, rid: str, actor_label: str, *, confirm: bool, replaces: str | None = None) -> dict[str, Any]:
        if not confirm:
            raise ValidationError("LOCAL_MANUAL_CONFIRMATION_REQUIRED", "Review the response and use --confirm-local")
        result = self._result(rid)
        if result["state"] == "USER_ACCEPTED_LOCAL" and not result.get("superseded_by"):
            return self.result_info(rid)
        self._check_accept(result, replaces)
        if not actor_label.strip():
            raise ValidationError("LOCAL_ACCEPTOR_LABEL_REQUIRED")
        self._append("RESULT_ACCEPTED", {"result_id": rid, "actor_label": actor_label, "replaces": replaces})
        return self.result_info(rid)

    def reject(self, rid: str, reason: str) -> dict[str, Any]:
        result = self._result(rid)
        if result["state"] not in {"IMPORTED_UNTRUSTED", "VALIDATED_STRUCTURE"} or not reason.strip():
            raise ValidationError("LOCAL_REJECTION_NOT_ALLOWED")
        self._append("RESULT_REJECTED", {"result_id": rid, "reason": reason})
        return self.result_info(rid)

    def _finish_payload(self) -> dict[str, Any]:
        if self.stage == "COMPLETE":
            raise ValidationError("LOCAL_CAMPAIGN_ALREADY_COMPLETED")
        tasks = [slot for slot, _, _ in STAGES[self.stage]]
        missing = [task for task in tasks if task not in self.accepted]
        if missing:
            raise ValidationError("LOCAL_STAGE_RESULTS_MISSING", ",".join(missing))
        if self.pending_runs:
            raise ValidationError("LOCAL_CHECKS_PENDING", "Recover or abandon explicitly before advancing")
        stages = list(STAGES)
        index = stages.index(self.stage)
        return {"stage_id": self.stage, "next_stage": stages[index + 1] if index + 1 < len(stages) else "COMPLETE",
                "results": [{"task_id": task, "result_id": self.accepted[task],
                             "raw_sha256": self.results[self.accepted[task]]["raw"]["raw_digest"]} for task in tasks],
                "completion_meaning": "Required responses structurally checked and manually accepted locally; claims unverified"}

    def advance(self) -> dict[str, Any]:
        if self.stage != "E1":
            raise ValidationError("LOCAL_LATER_STAGES_NOT_YET_ENABLED")
        self._append("STAGE_COMPLETED", self._finish_payload())
        return self.prepare()

    def _portable_source_paths(self) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        for name in self.source["paths"]:
            parts = name.split("/")
            if (canonical_path(name) != name or any(part in {"", ".", "..", ".git"} or part.rstrip(". ") != part
                    or part.split(".")[0].upper() in reserved or any(c in '<>"|?*' or ord(c) < 32 for c in part) for part in parts)
                    or name.casefold() in seen):
                raise ValidationError("LOCAL_SOURCE_PATH_NOT_PORTABLE", name)
            seen.add(name.casefold())
            names.append(name)
        return names

    def _verify_check(self, data: dict[str, Any], start: dict[str, Any]) -> None:
        files = data.get("files", {})
        if set(files) != {"RUN_MANIFEST.json", "RUN_RECEIPT.json", "stdout.bin", "stderr.bin"}:
            raise ValidationError("LOCAL_CHECK_EVIDENCE_INCOMPLETE")
        manifest = parse(self.store.vault.read_bytes(files["RUN_MANIFEST.json"]["raw_digest"]))
        receipt = parse(self.store.vault.read_bytes(files["RUN_RECEIPT.json"]["raw_digest"]))
        expected_hash = receipt.pop("receipt_digest")
        expected_spec = ToolRunSpec(start["run_id"], str(self.store.root / "work" / start["run_id"]),
                                    str(self.store.root / "checks" / start["run_id"]), tuple(start["argv"]),
                                    start["timeout_seconds"], start["max_output_bytes"])
        if (sha(canonical_bytes(receipt)) != expected_hash or receipt != data["result"]
                or receipt["run_id"] != start["run_id"] or manifest["argv"] != start["argv"]
                or receipt["spec_digest"] != expected_spec.digest
                or manifest["spec_digest"] != receipt["spec_digest"]
                or data["context"] != start["context"]):
            raise ValidationError("LOCAL_CHECK_RECEIPT_MISMATCH")
        for stream in ("stdout", "stderr"):
            ref = files[stream + ".bin"]
            if ref["raw_digest"] != receipt[stream + "_sha256"] or ref["byte_length"] != receipt[stream + "_bytes"]:
                raise ValidationError("LOCAL_CHECK_OUTPUT_MISMATCH")

    def recover_check(self, run_id: str) -> dict[str, Any]:
        start = self.pending_runs.get(run_id)
        if start is None:
            raise ValidationError("LOCAL_PENDING_CHECK_NOT_FOUND")
        evidence = self.store.root / "checks" / run_id
        verify_run_evidence(evidence)
        files = {name: self.store.put((evidence / name).read_bytes())
                 for name in ("RUN_MANIFEST.json", "RUN_RECEIPT.json", "stdout.bin", "stderr.bin")}
        result = parse((evidence / "RUN_RECEIPT.json").read_bytes())
        result.pop("receipt_digest")
        data = {"run_id": run_id, "task_id": start["task_id"], "context": start["context"], "files": files, "result": result}
        self._verify_check(data, start)
        self._append("CHECK_FINISHED", data)
        return {"mode": MODE, "status": "LOCAL_CHECK_RECORDED", **data, "notice": NOTICE}

    def run_check(self, task: str, argv: list[str], timeout: int = 60, max_output: int = 4 * 1024 * 1024) -> dict[str, Any]:
        if task not in self._available_tasks() or task not in self.packages:
            raise ValidationError("LOCAL_CURRENT_TASK_PACKAGE_REQUIRED")
        self._portable_source_paths()  # Reject before persisting intent or running anything.
        run_id = "local-run-" + uuid.uuid4().hex
        work = self.store.root / "work" / run_id
        evidence = self.store.root / "checks" / run_id
        spec = ToolRunSpec(run_id, str(work), str(evidence), tuple(argv), timeout, max_output)
        self._append("CHECK_STARTED", {"run_id": run_id, "task_id": task, "context": self.packages[task]["context"],
                                       "argv": argv, "timeout_seconds": timeout, "max_output_bytes": max_output})
        work.mkdir(parents=True)
        try:
            for entry in self.source_manifest["entries"]:
                path = work / entry["source_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.source_members[entry["transport_path"]])
            result = ToolSupervisor().run(spec)
        finally:
            # Only this freshly created UUID directory, resolved inside work.
            if work.resolve().parent != (self.store.root / "work").resolve():
                raise ValidationError("LOCAL_CHECK_CLEANUP_PATH_CHANGED")
            shutil.rmtree(work)
        if not (evidence / "RUN_RECEIPT.json").is_file():
            return {"mode": MODE, "status": "LOCAL_CHECK_INCOMPLETE", "run_id": run_id,
                    "result": result.as_dict(), "notice": NOTICE}
        return self.recover_check(run_id)
