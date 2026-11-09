"""Local source/package/import workflow using production Git, ZIP and vault code."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any
import uuid

from ..assurance.zip_safety import Limits, read_bytes, canonical_path, snapshot, ArchiveInput
from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..source.git_resolver import fetched_remote_repository, resolve_local_repository, validate_repository_location, _git_env, _run_git
from ..workflow.limited_transport import approved_git_view
from ..workflow.packaging import _deterministic_zip, _publish_exact
from ..runner.supervisor import ToolSupervisor
from ..runner.specs import ToolRunSpec
from .artifacts import safe_path
from .profile import (MODE, PROFILE, PROFILE_SHA256, RESPONSE, STAGES, NOTICE, RESPONSE_GUIDE,
                      LEGACY_NOTICE, LEGACY_RESPONSE_GUIDE, task_definition)
from .contract import GENERATOR_VERSION, VALIDATION_VERSION, auditor_prompt, response_template, result_filename
from .responses import decode, issues, read_file, diagnostics, RESULT_LIMITS
from .store import LocalStore, sha

SOURCE_LIMITS = Limits(input_bytes=70 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                       members=2048, member_bytes=32 * 1024 * 1024, expanded_bytes=70 * 1024 * 1024, ratio=100_000)
LEGACY_PACKAGE_LIMITS = Limits(input_bytes=100 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                               members=2056, member_bytes=32 * 1024 * 1024, expanded_bytes=100 * 1024 * 1024, ratio=100_000)
# At most 70 MiB of source plus 19 responses of up to 2 MiB and transport metadata.
PACKAGE_LIMITS = Limits(input_bytes=128 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                        members=2056, member_bytes=48 * 1024 * 1024, expanded_bytes=127 * 1024 * 1024, ratio=100_000)


def _git_paths(repository: Path, commit: str) -> list[str]:
    env = _git_env()
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        run = subprocess.run(["git", "-C", str(repository), "ls-tree", "--full-tree", "-r", "-z", "--name-only", commit],
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
    explicit_sha = ref if re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", ref) else None
    context = (fetched_remote_repository(location, ref, explicit_sha) if target == "github"
               else nullcontext((Path(location).resolve(), resolve_local_repository(location, ref))))
    with context as (repository, identity):
        if target == "local" and _run_git(repository, ["rev-parse", "--show-prefix"]):
            raise ValidationError("LOCAL_SOURCE_REPOSITORY_ROOT_REQUIRED",
                                  "Select the repository root and use --path for a narrower scope")
        selected = paths or _git_paths(repository, identity.commit_object_id)
        if not 1 <= len(selected) <= 2044:
            raise ValidationError("LOCAL_SOURCE_SCOPE_LIMIT", "Select 1–2044 regular files with --path")
        # Transport names stay numeric: source paths are never ZIP extraction paths.
        verified, manifest_raw, archive = approved_git_view(repository, identity.commit_object_id, location, selected)
        read_bytes(archive, limits=SOURCE_LIMITS)
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
    def __init__(self, root: str | Path, *, history_head: str | None = None):
        self.store = LocalStore(root)
        try:
            self._reload(history_head)
        except (KeyError, TypeError, IndexError) as exc:
            raise ValidationError("LOCAL_HISTORY_FORMAT_INVALID", type(exc).__name__) from exc

    @classmethod
    def start(cls, root: str | Path, location: str, ref: str, target: str = "local",
              paths: list[str] | None = None) -> LocalWorkflow:
        source, raw = capture_source(location, ref, target, paths)
        LocalStore.create(root, {"campaign_id": "local-" + uuid.uuid4().hex, "mode": MODE,
                                "profile_sha256": PROFILE_SHA256, "source": source}, raw)
        return cls(root)

    def _reload(self, history_head: str | None = None) -> None:
        events = self.store.events()
        if history_head is not None:
            end = next((event["seq"] for event in events if event["event_hash"] == history_head), None)
            if end is None:
                raise ValidationError("LOCAL_REPORT_CONTEXT_MISMATCH")
            events = events[:end]
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
        self._source_line_counts: dict[str, int] | None = None
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
        self.captured_checks: dict[str, tuple[str, dict[str, Any]]] = {}
        self.abandoned_runs: list[dict[str, Any]] = []
        self.acceptance_policy: dict[str, Any] = {"enabled": False}
        self.batches: dict[str, dict[str, Any]] = {}
        for event in events[1:]:
            self._replay(event)
        self.events = events
        self.head = events[-1]["event_hash"]

    def _available_tasks(self, stage: str | None = None) -> list[str]:
        stage = stage or self.stage
        if stage == "COMPLETE":
            return []
        tasks = [slot for slot, _, _ in STAGES[stage]]
        if stage == "E5" and not all(slot in self.accepted for slot in tasks[:3]):
            return tasks[:3]
        return tasks

    def _prior_ids(self, target: str, stage: str) -> list[str]:
        # All earlier accepted results, plus E5-A for E5-B. The frozen package
        # context prevents substituting a different revision after a challenge.
        available = self._available_tasks(stage)
        return [result_id for task, result_id in sorted(self.accepted.items())
                if task not in available or (stage == "E5" and task.startswith("E5-A-")
                                            and target.startswith("E5-B"))]

    def _package_bytes(self, task: str, generator_version: int = 1, *,
                       stage: str | None = None) -> tuple[dict[str, Any], bytes]:
        if type(generator_version) is not int or generator_version not in (1, 2, GENERATOR_VERSION):
            raise ValidationError("LOCAL_PACKAGE_GENERATOR_UNKNOWN")
        stage = stage or self.stage
        definition = task_definition(stage, task)
        prior = [{"result_id": rid, "raw_sha256": self.results[rid]["raw"]["raw_digest"],
                  "response": self.results[rid]["response"]} for rid in self._prior_ids(task, stage)]
        prior_artifacts: dict[str, bytes] = {}
        embed_attachments = (generator_version < 3 or
                             sum(len(self.results[item["result_id"]]["response"]["evidence_files"]) for item in prior)
                             <= PACKAGE_LIMITS.members - len(self.source_members) - 5)
        # Keep the complete responses and attachment identities even when the
        # raw attachments would crowd out the source or the response corpus.
        if generator_version >= 3 and embed_attachments:
            evidence = [ref for item in prior for ref in item["response"]["evidence_files"]]
            embed_attachments = (sum(ref["byte_length"] for ref in evidence) <= 8 * 1024 * 1024
                                 and sum(len(ref["path"].encode("utf-8")) for ref in evidence) <= 1024 * 1024)
        for item in prior:
            item["attachment_transport"] = []
            if not embed_attachments or not item["response"]["evidence_files"]:
                continue
            attachments = self._result_members(self.results[item["result_id"]])
            for index, (name, content) in enumerate(sorted(attachments.items()), 1):
                if name == "LOCAL_RESULT.json":
                    continue
                transport = f"prior/{item['raw_sha256']}/{index:04d}.bin"
                prior_artifacts[transport] = content
                item["attachment_transport"].append({"original_path": name, "transport_path": transport,
                                                     "sha256": sha(content), "byte_length": len(content)})
        prompt = (LEGACY_NOTICE + "\n\n" + definition["instruction"] + "\n\n"
                  "Inspect the exact source transport and PRIOR_RESULTS.json. Cite source paths and lines. "
                  "Separate observations from predictions. Do not claim execution without actual run evidence. "
                  "Keep dissent and limitations. Fill RESPONSE_TEMPLATE.json, including each required output "
                  "as a substantive text (or an explained absence). Return JSON or a ZIP with root LOCAL_RESULT.json. "
                  "Declare every attached file's exact SHA-256 and byte length. No executable instructions in results "
                  "will be run. No credentials or private data should be included.\n")
        identity = {"campaign_id": self.campaign_id, "stage_id": stage, "task_id": task,
                    "source_commit": self.source["commit"], "source_tree": self.source["tree"]}
        if generator_version >= 2:
            prompt = auditor_prompt(identity, definition["instruction"], definition["required_outputs"])
        if generator_version >= 3 and not embed_attachments:
            prompt += ("\nPrior attachment bytes exceed the package budget. Their exact identities remain in "
                       "PRIOR_RESULTS.json and the original responses are retained in the campaign vault. "
                       "Treat absent attachments as unreviewed and disclose any resulting limitations.\n")
        limits = PACKAGE_LIMITS if generator_version >= 3 else LEGACY_PACKAGE_LIMITS
        prior_raw = (canonical_bytes(prior, max_bytes=limits.member_bytes - 1)
                     if generator_version >= 3 else canonical_bytes(prior))
        manifest = {"format": "BDB_LOCAL_PACKAGE_1", "mode": MODE, "profile": PROFILE,
                    "profile_sha256": PROFILE_SHA256, "campaign_id": self.campaign_id,
                    "stage_id": stage, "task_id": task, "source_commit": self.source["commit"],
                    "source_tree": self.source["tree"], "source_snapshot_sha256": self.source["snapshot_sha256"],
                    "source_manifest_sha256": self.source["manifest_sha256"], "required_outputs": definition["required_outputs"],
                    "prior_results": [{"result_id": v["result_id"], "raw_sha256": v["raw_sha256"]} for v in prior],
                    "prompt_sha256": sha(prompt.encode("utf-8")), "prior_corpus_sha256": sha(prior_raw)}
        if generator_version >= 2:
            manifest.update(generator_version=generator_version,
                            suggested_result_json=result_filename(task), suggested_result_zip=result_filename(task, "zip"),
                            response_guide_sha256=sha(RESPONSE_GUIDE.encode("utf-8")))
        if generator_version >= 3:
            manifest["prior_attachments"] = "EMBEDDED" if embed_attachments else "RETAINED_IN_VAULT"
        digest = sha(b"BDB-LOCAL-PACKAGE/1\x00" + canonical_bytes(manifest))
        context = {key: manifest[key] for key in ("campaign_id", "stage_id", "task_id", "source_commit", "source_tree")}
        context["input_package_digest"] = digest
        template = response_template(context, definition["required_outputs"])
        manifest["input_package_digest"] = digest
        members = {"MANIFEST.json": canonical_bytes(manifest) + b"\n", "PROMPT.md": prompt.encode("utf-8"),
                   "RESPONSE_TEMPLATE.json": canonical_bytes(template) + b"\n", "PRIOR_RESULTS.json": prior_raw + b"\n",
                   "SOURCE_MANIFEST.json": self.source_members["MANIFEST.json"],
                   **prior_artifacts,
                   **{k: v for k, v in self.source_members.items() if k != "MANIFEST.json"}}
        if generator_version >= 2:
            members["RESPONSE_FORMAT.md"] = RESPONSE_GUIDE.encode("utf-8")
        if len(members) > limits.members or sum(len(v) for v in members.values()) > limits.expanded_bytes:
            raise ValidationError("LOCAL_PACKAGE_RESOURCE_LIMIT", "Bound prior evidence size; retain large runs separately in vault")
        metadata = {"task_id": task, "stage_id": stage, "context": context,
                    "required_outputs": definition["required_outputs"]}
        if generator_version >= 2:
            metadata["generator_version"] = generator_version
        return metadata, _deterministic_zip(members)

    def _response_issues(self, response: dict[str, Any], members: dict[str, bytes], *,
                         current_contract: bool = False) -> list[str]:
        task = response.get("task_id")
        if not isinstance(task, str) or task not in self.packages:
            return ["LOCAL_TASK_PACKAGE_NOT_FOUND"]
        package = self.packages[task]
        line_counts = None
        if current_contract or package.get("generator_version", 1) >= 2:
            if self._source_line_counts is None:
                self._source_line_counts = {entry["source_path"]: len(self.source_members[entry["transport_path"]].splitlines())
                                            for entry in self.source_manifest["entries"]}
            line_counts = self._source_line_counts
        return issues(response, members, package["context"], package["required_outputs"], set(self.source["paths"]),
                      line_counts=line_counts)

    def _result_members(self, result: dict[str, Any]) -> dict[str, bytes]:
        raw = self.store.vault.read_bytes(result["raw"]["raw_digest"])
        return read_bytes(raw, limits=RESULT_LIMITS) if raw.startswith(b"PK") else {}

    def _result_issues(self, result: dict[str, Any]) -> list[str]:
        return self._response_issues(result["response"], self._result_members(result),
                                     current_contract=result.get("validation_version", 1) == VALIDATION_VERSION)

    def _replay(self, event: dict[str, Any]) -> None:
        kind, data = event["kind"], event["payload"]
        if kind == "PACKAGE_PREPARED":
            task = data["task_id"]
            if task not in self._available_tasks() or task in self.packages:
                raise ValidationError("LOCAL_PACKAGE_HISTORY_INVALID")
            expected, raw = self._package_bytes(task, data.get("generator_version", 1))
            if (any(data.get(k) != v for k, v in expected.items())
                    or self.store.vault.read_bytes(data["raw"]["raw_digest"]) != raw):
                raise ValidationError("LOCAL_PACKAGE_READBACK_MISMATCH")
            self.packages[task] = data
        elif kind == "RESULT_IMPORTED":
            rid = data["result_id"]
            if self.stage == "COMPLETE" or rid in self.results or data.get("stage_at_import") != self.stage:
                raise ValidationError("LOCAL_IMPORT_HISTORY_INVALID")
            raw = self.store.vault.read_bytes(data["raw"]["raw_digest"])
            response, _ = decode(raw)
            if rid != "local-result-" + sha(raw):
                raise ValidationError("LOCAL_RESULT_ID_MISMATCH")
            if (type(data.get("validation_version", 1)) is not int
                    or data.get("validation_version", 1) not in (1, VALIDATION_VERSION)):
                raise ValidationError("LOCAL_VALIDATION_VERSION_INVALID")
            self.results[rid] = {**data, "response": response, "state": "IMPORTED_UNTRUSTED"}
        elif kind == "RESULT_VALIDATED":
            result = self._result(data["result_id"])
            found = self._result_issues(result)
            state = "REJECTED" if found else "VALIDATED_STRUCTURE"
            if result["state"] != "IMPORTED_UNTRUSTED" or data.get("issues") != found or data.get("state") != state:
                raise ValidationError("LOCAL_VALIDATION_HISTORY_INVALID")
            result.update(state=state, issues=found)
        elif kind == "RESULT_ACCEPTED":
            result = self._result(data["result_id"])
            self._check_accept(result, data.get("replaces"))
            if not isinstance(data.get("actor_label"), str) or not data["actor_label"].strip():
                raise ValidationError("LOCAL_ACCEPTOR_LABEL_REQUIRED")
            mechanism = data.get("mechanism", "MANUAL")
            if mechanism not in {"MANUAL", "AUTO_POLICY"}:
                raise ValidationError("LOCAL_ACCEPTANCE_MECHANISM_INVALID")
            if mechanism == "AUTO_POLICY" and (not self.acceptance_policy["enabled"]
                    or data.get("policy_event_hash") != self.acceptance_policy["event_hash"]
                    or data["actor_label"] != self.acceptance_policy["actor_label"] or data.get("replaces") is not None):
                raise ValidationError("LOCAL_ACCEPTANCE_POLICY_REQUIRED")
            result.update(state="USER_ACCEPTED_LOCAL", accepted_seq=event["seq"], actor_label=data["actor_label"],
                          acceptance_mechanism=mechanism, policy_event_hash=data.get("policy_event_hash"))
            if data.get("replaces"):
                self.results[data["replaces"]]["superseded_by"] = data["result_id"]
            self.accepted[result["response"]["task_id"]] = data["result_id"]
        elif kind == "LOCAL_ACCEPTANCE_POLICY_SET":
            if (set(data) != {"enabled", "actor_label"} or type(data["enabled"]) is not bool
                    or not isinstance(data["actor_label"], str) or not data["actor_label"].strip()):
                raise ValidationError("LOCAL_ACCEPTANCE_POLICY_INVALID")
            self.acceptance_policy = {**data, "event_hash": event["event_hash"]}
        elif kind in {"BATCH_STARTED", "BATCH_ITEM_RECORDED", "BATCH_FINISHED"}:
            self._replay_batch(kind, data)
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
        elif kind == "CHECK_EVIDENCE_CAPTURED":
            run_id = data["run_id"]
            start = self.pending_runs.get(run_id)
            if not start or start.get("evidence_version") != 2 or run_id in self.captured_checks:
                raise ValidationError("LOCAL_CHECK_HISTORY_INVALID")
            self._verify_check(data, start)
            self.captured_checks[run_id] = (event["event_hash"], data)
        elif kind == "CHECK_FINISHED":
            run_id = data["run_id"]
            start = self.pending_runs.get(run_id)
            if not start:
                raise ValidationError("LOCAL_CHECK_START_REQUIRED")
            if start.get("evidence_version") == 2:
                captured = self.captured_checks.pop(run_id, None)
                if captured is None or data != {"run_id": run_id, "evidence_event_hash": captured[0]}:
                    raise ValidationError("LOCAL_CHECK_EVIDENCE_ANCHOR_MISMATCH")
                data = captured[1]
            else:
                self._verify_check(data, start)
            self.pending_runs.pop(run_id)
            self.runs.append(data)
        elif kind == "CHECK_ABANDONED":
            if data["run_id"] not in self.pending_runs or not data.get("reason"):
                raise ValidationError("LOCAL_CHECK_ABANDONMENT_INVALID")
            self.captured_checks.pop(data["run_id"], None)
            self.abandoned_runs.append({**self.pending_runs.pop(data["run_id"]), "reason": data["reason"]})
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
        if self._result_issues(result):
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
                "acceptance_policy": self.acceptance_policy, "batch_imports": self.batch_summaries(),
                "available_tasks": self._available_tasks(), "missing_results": [t for t in required if t not in self.accepted],
                "packages": [{"task_id": k, "raw_sha256": v["raw"]["raw_digest"],
                              "suggested_result_json": result_filename(k), "suggested_result_zip": result_filename(k, "zip"),
                              "path": str(self.store.root / "packages" / (k + ".zip"))} for k, v in self.packages.items()],
                "results": [{"result_id": k, "task_id": v["response"].get("task_id"), "state": v["state"],
                             "issues": v.get("issues", []), "superseded_by": v.get("superseded_by")}
                            for k, v in self.results.items()],
                "local_checks": self.runs, "pending_checks": list(self.pending_runs.values()),
                "abandoned_checks": self.abandoned_runs, "notice": NOTICE}

    def prepare(self) -> dict[str, Any]:
        for task in self._available_tasks():
            if task not in self.packages:
                metadata, raw = self._package_bytes(task, GENERATOR_VERSION)
                self._append("PACKAGE_PREPARED", {**metadata, "raw": self.store.put(raw)})
        # Publication is a recoverable projection. A crash after journal commit
        # can be repaired from exact retained bytes, including earlier phases.
        first = next(iter(self.packages.values()), {})
        guide = LEGACY_RESPONSE_GUIDE if first.get("generator_version", 1) == 1 else RESPONSE_GUIDE
        _publish_exact(self.store.root / "packages" / "RESPONSE_FORMAT.md", guide.encode("utf-8"))
        for task, package in self.packages.items():
            path = self.store.root / "packages" / (task + ".zip")
            _publish_exact(path, self.store.vault.read_bytes(package["raw"]["raw_digest"]))
        return self.status()

    def prompt(self, task: str) -> dict[str, Any]:
        """Read the frozen prompt, never regenerate it using current settings."""
        package = self.packages.get(task)
        if package is None:
            raise ValidationError("LOCAL_TASK_PACKAGE_NOT_FOUND")
        raw = self.store.vault.read_bytes(package["raw"]["raw_digest"])
        limits = PACKAGE_LIMITS if package.get("generator_version", 1) >= 3 else LEGACY_PACKAGE_LIMITS
        members = read_bytes(raw, limits=limits)
        manifest = parse(members["MANIFEST.json"])
        template = parse(members["RESPONSE_TEMPLATE.json"])
        prompt_raw = members["PROMPT.md"]
        digest_manifest = {k: v for k, v in manifest.items() if k != "input_package_digest"}
        if (sha(prompt_raw) != manifest["prompt_sha256"]
                or sha(b"BDB-LOCAL-PACKAGE/1\x00" + canonical_bytes(digest_manifest)) != package["context"]["input_package_digest"]
                or any(manifest.get(k) != v or template.get(k) != v for k, v in package["context"].items())):
            raise ValidationError("LOCAL_PROMPT_PACKAGE_MISMATCH")
        try:
            text = prompt_raw.decode("utf-8")
        except UnicodeError as exc:
            raise ValidationError("LOCAL_PROMPT_ENCODING_INVALID") from exc
        return {"task_id": task, "text": text, "prompt_sha256": sha(prompt_raw),
                "package_sha256": sha(raw), "context": package["context"],
                "suggested_result_json": result_filename(task), "suggested_result_zip": result_filename(task, "zip")}

    def set_acceptance_policy(self, enabled: bool, actor_label: str) -> dict[str, Any]:
        if type(enabled) is not bool or not isinstance(actor_label, str) or not actor_label.strip():
            raise ValidationError("LOCAL_ACCEPTANCE_POLICY_INVALID")
        if self.acceptance_policy["enabled"] != enabled:
            self._append("LOCAL_ACCEPTANCE_POLICY_SET", {"enabled": enabled, "actor_label": actor_label})
        return self.status()

    def _replay_batch(self, kind: str, data: dict[str, Any]) -> None:
        bid = data.get("batch_id")
        if not isinstance(bid, str) or not re.fullmatch(r"local-batch-[0-9a-f]{32}", bid):
            raise ValidationError("LOCAL_BATCH_HISTORY_INVALID")
        if kind == "BATCH_STARTED":
            files = data.get("files")
            if (bid in self.batches or data.get("stage_id") != self.stage or not isinstance(files, list)
                    or not 1 <= len(files) <= 128 or any(not isinstance(f, str) for f in files)):
                raise ValidationError("LOCAL_BATCH_HISTORY_INVALID")
            self.batches[bid] = {**data, "items": [], "finished": False}
            return
        batch = self.batches.get(bid)
        if batch is None or batch["finished"]:
            raise ValidationError("LOCAL_BATCH_HISTORY_INVALID")
        if kind == "BATCH_FINISHED":
            if len(batch["items"]) != len(batch["files"]):
                raise ValidationError("LOCAL_BATCH_HISTORY_INVALID")
            batch["finished"] = True
            return
        index = data.get("index")
        outcome = data.get("outcome")
        if (type(index) is not int or index != len(batch["items"]) or index >= len(batch["files"])
                or data.get("file") != batch["files"][index]
                or outcome not in {"ACCEPTED", "VALIDATED", "INCOMPLETE", "DUPLICATE", "REJECTED", "CONFLICT"}):
            raise ValidationError("LOCAL_BATCH_HISTORY_INVALID")
        if outcome in {"ACCEPTED", "VALIDATED", "INCOMPLETE", "DUPLICATE"}:
            result = self._result(data["result_id"])
            # already_present describes this vault write attempt, not raw
            # identity. A duplicate legitimately has True where the original
            # import had False; digest/length/media must still match exactly.
            raw_ref = data.get("raw")
            if (data.get("status") != result["state"] or data.get("task_id") != result["response"]["task_id"]
                    or not isinstance(raw_ref, dict)
                    or any(raw_ref.get(k) != result["raw"].get(k) for k in ("raw_digest", "byte_length", "media_type"))
                    or outcome == "ACCEPTED" and result["state"] != "USER_ACCEPTED_LOCAL"
                    or outcome in {"VALIDATED", "INCOMPLETE"} and result["state"] != "VALIDATED_STRUCTURE"
                    or outcome == "INCOMPLETE" and result["response"]["completion"] == "COMPLETE"):
                raise ValidationError("LOCAL_BATCH_HISTORY_INVALID")
        batch["items"].append(data)

    def batch_summary(self, bid: str) -> dict[str, Any]:
        batch = self.batches[bid]
        items = batch["items"]
        return {"batch_id": bid, "stage_id": batch["stage_id"],
                "status": "FINISHED" if batch["finished"] else "INTERRUPTED",
                "items": items, "selected": len(batch["files"]), "processed": len(items),
                "imported": sum(i["outcome"] in {"ACCEPTED", "VALIDATED", "INCOMPLETE"} for i in items),
                "accepted": sum(i["outcome"] == "ACCEPTED" for i in items),
                "rejected": sum(i["outcome"] in {"REJECTED", "CONFLICT"} for i in items),
                "duplicates": sum(i["outcome"] == "DUPLICATE" for i in items),
                "remaining_files": batch["files"][len(items):]}

    def batch_summaries(self) -> list[dict[str, Any]]:
        return [self.batch_summary(bid) for bid in self.batches]

    def batch_item_info(self, batch_id: str, index: int) -> dict[str, Any]:
        batch = self.batches.get(batch_id)
        if batch is None or type(index) is not int or not 0 <= index < len(batch["items"]):
            raise ValidationError("LOCAL_BATCH_ITEM_NOT_FOUND")
        item = batch["items"][index]
        if item.get("result_id") in self.results:
            return {"import_item": item, **self.result_info(item["result_id"])}
        preview: dict[str, Any] = {"import_item": item, "notice": NOTICE, "status": "REFUSED_UNTRUSTED"}
        if item.get("raw"):
            raw = self.store.vault.read_bytes(item["raw"]["raw_digest"])
            try:
                preview["response"] = decode(raw)[0]
            except ValidationError as exc:
                preview["parse_error"] = exc.code
        return preview

    def review_batch_conflict(self, batch_id: str, index: int) -> dict[str, Any]:
        """Explicitly stage retained conflict bytes for the existing manual review.

        This never invokes auto policy or replaces an accepted result. Acceptance
        still requires the manual decision and exact previous result ID.
        """
        info = self.batch_item_info(batch_id, index)
        item = info["import_item"]
        if item["outcome"] != "CONFLICT" or not item.get("raw"):
            raise ValidationError("LOCAL_BATCH_CONFLICT_REQUIRED")
        raw = self.store.vault.read_bytes(item["raw"]["raw_digest"])
        body, members = decode(raw)
        found = self._response_issues(body, members, current_contract=True)
        if found:
            raise ValidationError("LOCAL_IMPORT_VALIDATION_FAILED", "; ".join(found))
        if body["stage_id"] != self.stage or body["task_id"] not in self._available_tasks():
            raise ValidationError("LOCAL_CURRENT_STAGE_REQUIRED")
        imported = self.import_result(ArchiveInput(raw, item["file"]), item["raw"]["raw_digest"])
        return self.validate(imported["result_id"])

    def import_results(self, paths: list[str | Path]) -> dict[str, Any]:
        """Bounded sequential batch; each file is independently durable/atomic."""
        if not paths:
            return {"mode": MODE, "status": "CANCELLED", "items": [], "imported": 0,
                    "accepted": 0, "rejected": 0, "duplicates": 0}
        if len(paths) > 128:
            raise ValidationError("LOCAL_BATCH_FILE_LIMIT", "Wybierz najwyżej 128 plików naraz")
        files = [str(Path(p).absolute()) for p in paths]
        bid = "local-batch-" + uuid.uuid4().hex
        self._append("BATCH_STARTED", {"batch_id": bid, "stage_id": self.stage, "files": files})
        for index, file in enumerate(files):
            self._import_batch_item(bid, index, file)
        self._append("BATCH_FINISHED", {"batch_id": bid})
        return {"mode": MODE, **self.batch_summary(bid), "notice": NOTICE}

    def _import_batch_item(self, bid: str, index: int, file: str) -> None:
        row: dict[str, Any] = {"batch_id": bid, "index": index, "file": file}
        response: dict[str, Any] = {}
        entries: list[tuple[str, dict[str, Any]]] = []
        found: list[str] = []
        try:
            # Retain original bounded bytes even when their structure is refused.
            # Unsafe/oversized inputs never become response objects or execute.
            raw = snapshot(file, limits=RESULT_LIMITS).raw
            row["raw"] = self.store.put(raw)
            response, members = decode(raw)
            task = response.get("task_id")
            row["task_id"] = task if isinstance(task, str) else None
            found = self._response_issues(response, members)
            rid = "local-result-" + sha(raw)
            existing = self.results.get(rid)
            if not found and existing and existing["state"] in {"USER_ACCEPTED_LOCAL", "REJECTED"}:
                row.update(outcome="DUPLICATE", result_id=rid, status=existing["state"])
            else:
                # New ingestion uses today's explicit contract even when the
                # assigned package predates generator 2. Historical acceptance
                # and exact duplicates keep their recorded validation meaning.
                found = self._response_issues(response, members, current_contract=True)
                if not found and (self.stage == "COMPLETE" or response["stage_id"] != self.stage
                                  or task not in self._available_tasks()):
                    found = ["LOCAL_CURRENT_STAGE_REQUIRED"]
                conflict = not found and any(other_id != rid and r["response"].get("task_id") == task
                    and (other_id == self.accepted.get(task) or r["state"] == "VALIDATED_STRUCTURE"
                         and r["response"].get("completion") == "COMPLETE") for other_id, r in self.results.items())
                if conflict:
                    found = ["LOCAL_BATCH_RESULT_CONFLICT"]
                if found:
                    row.update(outcome="CONFLICT" if conflict else "REJECTED", status="REFUSED")
                else:
                    if existing is None:
                        entries.append(("RESULT_IMPORTED", {"result_id": rid, "raw": row["raw"], "stage_at_import": self.stage,
                                                            "validation_version": VALIDATION_VERSION}))
                    if existing is None or existing["state"] == "IMPORTED_UNTRUSTED":
                        entries.append(("RESULT_VALIDATED", {"result_id": rid, "issues": [], "state": "VALIDATED_STRUCTURE"}))
                    complete = response["completion"] == "COMPLETE"
                    automatic = complete and self.acceptance_policy["enabled"]
                    if automatic:
                        entries.append(("RESULT_ACCEPTED", {"result_id": rid, "actor_label": self.acceptance_policy["actor_label"],
                            "replaces": None, "mechanism": "AUTO_POLICY", "policy_event_hash": self.acceptance_policy["event_hash"]}))
                    outcome = "ACCEPTED" if automatic else "INCOMPLETE" if not complete else "VALIDATED"
                    if existing is not None and not automatic and existing["state"] == "VALIDATED_STRUCTURE":
                        outcome = "DUPLICATE"
                    row.update(outcome=outcome, result_id=rid, completion=response["completion"],
                               status="USER_ACCEPTED_LOCAL" if automatic else "VALIDATED_STRUCTURE")
        except ValidationError as exc:
            row.update(outcome="REJECTED", status="REFUSED")
            found = [exc.code]
        except OSError as exc:
            row.update(outcome="REJECTED", status="REFUSED", detail=type(exc).__name__)
            found = ["LOCAL_BATCH_FILE_READ_FAILED"]
        row.update(issues=found, diagnostics=diagnostics(response, found))
        entries.append(("BATCH_ITEM_RECORDED", row))
        # Do not catch journal/CAS/I/O failures here. Retrying the batch recognizes
        # committed files by their raw identity and never fabricates a new fact.
        previous = (len(self.events), self.head)
        self.store.append_many(entries, self.head, verified_seq=previous[0])
        for event in self.store.events(after=previous):
            self._replay(event)
            self.events.append(event)
            self.head = event["event_hash"]

    def inspect(self, path: str | Path, expected_sha256: str | None = None) -> dict[str, Any]:
        raw = read_file(path)
        if expected_sha256 is not None and sha(raw) != expected_sha256:
            raise ValidationError("LOCAL_RAW_SHA256_MISMATCH")
        response, members = decode(raw)
        found = self._response_issues(response, members, current_contract=True)
        return {"mode": MODE, "status": "INSPECTED_UNTRUSTED", "raw_sha256": sha(raw),
                "byte_length": len(raw), "issues": found,
                "response": response, "diagnostics": diagnostics(response, found),
                "notice": NOTICE}

    def import_result(self, path: str | Path | ArchiveInput, expected_sha256: str | None = None) -> dict[str, Any]:
        raw = read_file(path)
        if expected_sha256 is not None and sha(raw) != expected_sha256:
            raise ValidationError("LOCAL_RAW_SHA256_MISMATCH")
        rid = "local-result-" + sha(raw)
        if rid not in self.results:
            if self.stage == "COMPLETE":
                raise ValidationError("LOCAL_CAMPAIGN_ALREADY_COMPLETED")
            self._append("RESULT_IMPORTED", {"result_id": rid, "raw": self.store.put(raw), "stage_at_import": self.stage,
                                             "validation_version": VALIDATION_VERSION})
        return self.result_info(rid)

    def result_info(self, rid: str) -> dict[str, Any]:
        result = self._result(rid)
        return {"mode": MODE, "result_id": rid, "status": result["state"], "raw_sha256": result["raw"]["raw_digest"],
                "byte_length": result["raw"]["byte_length"], "response": result["response"],
                "issues": result.get("issues", []), "acceptance_mechanism": result.get("acceptance_mechanism"),
                "policy_event_hash": result.get("policy_event_hash"), "notice": NOTICE}

    def validate(self, rid: str) -> dict[str, Any]:
        result = self._result(rid)
        if result["state"] == "IMPORTED_UNTRUSTED":
            found = self._result_issues(result)
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
        self._append("RESULT_ACCEPTED", {"result_id": rid, "actor_label": actor_label, "replaces": replaces,
                                         "mechanism": "MANUAL"})
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
        automatic = any(self.results[self.accepted[t]].get("acceptance_mechanism") == "AUTO_POLICY" for t in tasks)
        meaning = ("Required responses structurally checked and accepted locally by manual decision or authorized policy; claims unverified"
                   if automatic else "Required responses structurally checked and manually accepted locally; claims unverified")
        return {"stage_id": self.stage, "next_stage": stages[index + 1] if index + 1 < len(stages) else "COMPLETE",
                "results": [{"task_id": task, "result_id": self.accepted[task],
                             "raw_sha256": self.results[self.accepted[task]]["raw"]["raw_digest"]} for task in tasks],
                "completion_meaning": meaning}

    def advance(self) -> dict[str, Any]:
        completion = self._finish_payload()
        next_stage = completion["next_stage"]
        entries = [("STAGE_COMPLETED", completion)]
        for task in self._available_tasks(next_stage):
            metadata, raw = self._package_bytes(task, GENERATOR_VERSION, stage=next_stage)
            entries.append(("PACKAGE_PREPARED", {**metadata, "raw": self.store.put(raw)}))
        # Move the stage only once every next-stage package is durable in the vault.
        self.store.append_many(entries, self.head)
        self._reload()
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
        if not isinstance(manifest, dict) or not isinstance(receipt, dict):
            raise ValidationError("LOCAL_CHECK_RECEIPT_MISMATCH")
        expected_hash = receipt.pop("receipt_digest", None)
        recorded_spec = start["spec"]
        if (recorded_spec["run_id"] != start["run_id"] or recorded_spec["argv"] != start["argv"]
                or recorded_spec["timeout_seconds"] != start["timeout_seconds"]
                or recorded_spec["max_output_bytes"] != start["max_output_bytes"]):
            raise ValidationError("LOCAL_CHECK_SPEC_MISMATCH")
        if (sha(canonical_bytes(receipt)) != expected_hash or receipt != data["result"]
                or receipt.get("run_id") != start["run_id"] or manifest.get("argv") != start["argv"]
                or receipt.get("spec_digest") != sha(canonical_bytes(recorded_spec))
                or manifest.get("spec_digest") != receipt["spec_digest"]
                or data["context"] != start["context"] or data["task_id"] != start["task_id"]):
            raise ValidationError("LOCAL_CHECK_RECEIPT_MISMATCH")
        if start.get("evidence_version") == 2:
            if (manifest.get("run_id") != start["run_id"]
                    or manifest.get("working_subdir") != recorded_spec["working_subdir"]
                    or not isinstance(manifest.get("capability_profile"), dict)
                    or sha(canonical_bytes(manifest["capability_profile"])) != receipt.get("capability_profile_digest")
                    or manifest.get("target_exit_code") != receipt.get("target_exit_code")
                    or (manifest.get("supervisor_status") != receipt.get("supervisor_status")
                        and not (receipt.get("supervisor_status") == "CLEANUP_FAILED"
                                 and receipt.get("cleanup_status") == "FAILED"))
                    or any(manifest.get(stream + "_sha256") != receipt.get(stream + "_sha256")
                           for stream in ("stdout", "stderr"))):
                raise ValidationError("LOCAL_CHECK_RECEIPT_MISMATCH")
        for stream in ("stdout", "stderr"):
            ref = files[stream + ".bin"]
            if ref["raw_digest"] != receipt[stream + "_sha256"] or ref["byte_length"] != receipt[stream + "_bytes"]:
                raise ValidationError("LOCAL_CHECK_OUTPUT_MISMATCH")

    def recover_check(self, run_id: str) -> dict[str, Any]:
        start = self.pending_runs.get(run_id)
        if start is None:
            raise ValidationError("LOCAL_PENDING_CHECK_NOT_FOUND")
        captured = self.captured_checks.get(run_id)
        if captured is None:
            raise ValidationError("TOOL_RUN_EVIDENCE_INCOMPLETE",
                                  "No supervisor result was captured in the journal; abandon and rerun the check")
        event_hash, data = captured
        self._append("CHECK_FINISHED", {"run_id": run_id, "evidence_event_hash": event_hash})
        return {"mode": MODE, "status": "LOCAL_CHECK_RECORDED", **data, "notice": NOTICE}

    def abandon_check(self, run_id: str, reason: str) -> dict[str, Any]:
        if run_id not in self.pending_runs or not reason.strip():
            raise ValidationError("LOCAL_PENDING_CHECK_NOT_FOUND_OR_REASON_MISSING")
        self._append("CHECK_ABANDONED", {"run_id": run_id, "reason": reason})
        return self.status()

    def run_check(self, task: str, argv: list[str], timeout: int = 60, max_output: int = 4 * 1024 * 1024) -> dict[str, Any]:
        if task not in self._available_tasks() or task not in self.packages:
            raise ValidationError("LOCAL_CURRENT_TASK_PACKAGE_REQUIRED")
        self._portable_source_paths()  # Reject before persisting intent or running anything.
        run_id = "local-run-" + uuid.uuid4().hex
        work = self.store.root / "work" / run_id
        evidence = self.store.root / "checks" / run_id
        spec = ToolRunSpec(run_id, str(work), str(evidence), tuple(argv), timeout, max_output)
        self._append("CHECK_STARTED", {"run_id": run_id, "task_id": task, "context": self.packages[task]["context"],
                                       "argv": argv, "timeout_seconds": timeout, "max_output_bytes": max_output,
                                       "spec": spec.as_dict(), "evidence_version": 2})
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
        start = self.pending_runs[run_id]
        files = {}
        for name in ("RUN_MANIFEST.json", "RUN_RECEIPT.json", "stdout.bin", "stderr.bin"):
            path = safe_path(self.store.root, evidence / name)
            limit = max_output if name.endswith(".bin") else 2 * 1024 * 1024
            with path.open("rb") as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValidationError("LOCAL_CHECK_EVIDENCE_SIZE_LIMIT", name)
            files[name] = self.store.put(raw)
        data = {"run_id": run_id, "task_id": task, "context": start["context"],
                "files": files, "result": result.as_dict()}
        # The trusted in-process result must match these exact bytes before any
        # later recovery can take authority from the journal instead of disk.
        self._verify_check(data, start)
        for attempt in range(3):
            self._reload()
            if self.pending_runs.get(run_id) != start:
                raise ValidationError("LOCAL_PENDING_CHECK_NOT_FOUND")
            try:
                self._append("CHECK_EVIDENCE_CAPTURED", data)
            except ValidationError as exc:
                if exc.code != "LOCAL_CAS_CONFLICT" or attempt == 2:
                    raise
            else:
                break
        return self.recover_check(run_id)
