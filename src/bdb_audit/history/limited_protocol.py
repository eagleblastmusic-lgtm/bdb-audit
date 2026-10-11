"""Approved finite P0 predicates, executed by the existing Store writer."""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from ..workflow.limited_transport import LimitedTransport, approved_git_view
from .installation_authority import verify_cms
from .limited_authority import LimitedMachineAuthority, instant
from .limited_model import BASE, domain_hash, sha, strict_json
from .limited_wire import (LimitedObject, LimitedCommand, LimitedRef, LimitedCommit, LimitedReceipt,
                           value_body, refs_in, sorted_refs, copy)
from .objects import AcceptedHead
from .raw_artifacts import AdmissionRawReader

ROOT_KINDS = {"artifact_contract_registry", "schema_registry", "policy_revision", "spec_revision",
              "trust_profile", "installation_bootstrap_profile"}
FACT_STATES = {"campaign_genesis": "GENESIS", "assignment_manifest": "ASSIGNED",
               "assignment_package_binding": "BOUND", "nf02_p0_delivery": "DELIVERED",
               "lane_result_admission_evidence": "EVIDENCE_ACCEPTED", "bdb_audit_lane_result": "RESULT_ACCEPTED",
               "nf02_p0_abort": "ABORTED"}


def raw_refs(value):
    if isinstance(value, dict):
        if {"raw_digest", "byte_length", "artifact_contract_ref", "media_type"} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from raw_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from raw_refs(child)


class LimitedProtocol:
    limited = True
    command_type = LimitedCommand
    object_type = LimitedObject

    def __init__(self, authority, leased):
        self.authority, self.identity = authority, leased["identity"]
        self.corpus = leased["corpus"]
        self.registry, self.schemas = self.corpus.registry, self.corpus.schemas
        self.transport = LimitedTransport(self.corpus)
        self.installation, self.root = copy(leased["installation"]), copy(leased["root"])
        self.pins = {}
        roots = {}
        for ref in self.installation["initial_root_refs"]:
            matches = []
            for raw in leased["files"].values():
                if len(raw) > 2 * 1024 * 1024:
                    continue
                try:
                    body = strict_json(raw)
                    if isinstance(body, dict) and body.get("object_id") == ref["logical_id"]:
                        obj = self.object(ref["kind"], body)
                        if obj.ref.as_dict() == ref:
                            matches.append(obj)
                except ValidationError:
                    continue
            if len(matches) != 1 or ref["kind"] in roots:
                raise ValidationError("P0_INITIAL_ROOT_IDENTITY_MISMATCH")
            roots[ref["kind"]] = matches[0]
            self.pins[ref["kind"]] = ref
        if set(roots) != ROOT_KINDS:
            raise ValidationError("P0_SIX_ROOTS_REQUIRED")
        self.roots = roots
        self.validate_roots()

    @classmethod
    def installed(cls):
        authority = LimitedMachineAuthority()
        with authority.lease() as leased:
            return cls(authority, leased)

    @contextmanager
    def lease(self, path=None):
        with self.authority.lease() as leased:
            if leased["identity"] != self.identity:
                raise ValidationError("P0_INSTALLATION_CHANGED")
            if path is None:
                yield leased
            else:
                with self.authority.storage_lease(path, leased):
                    yield leased

    def schema_ref(self, kind, version=None):
        return self.corpus.schema_ref(kind, version)

    def object(self, kind, body, version=None, logical_id=None, schema_ref=None):
        version = version or self.corpus.versions[kind]
        return LimitedObject(kind, body, schema_ref or self.schema_ref(kind, version),
                             logical_id or body.get("object_id"), version, self)

    def object_from_row(self, row):
        return self.object(row[0], strict_json(row[4]), row[1], row[3], strict_json(row[2]))

    def ref(self, value, *, ref_class="CONTENT_OR_PRIOR"):
        self.schemas.validate_ref(value)
        if value["schema_revision_ref"] != self.schema_ref(value["kind"], value["version"]):
            raise ValidationError("P0_SCHEMA_IDENTITY_MISMATCH")
        return LimitedRef(value["kind"], value["revision_digest"], value["digest_profile"], value["schema_revision_ref"],
                          value["logical_id"], ref_class, value["version"])

    def commit(self, body):
        return LimitedCommit(body, self)

    def receipt(self, body):
        return LimitedReceipt(body, self)

    def cut(self, current, prior):
        return {"head": current.as_dict(), **{k: copy(prior[k]) for k in ("policy_ref", "spec_ref", "schema_registry_ref")},
                "source_ref": copy(self._source_ref)}

    def cut_for(self, current, records):
        return {"head": current.as_dict(), "policy_ref": self.pins["policy_revision"], "spec_ref": self.pins["spec_revision"],
                "schema_registry_ref": self.pins["schema_registry"],
                "source_ref": next(r["ref"] for r in records.values() if r["object"].kind == "nf02_p0_source_snapshot")}

    def resolve(self, records, ref):
        self.ref(ref)
        record = records.get(ref["revision_digest"])
        if record is None or record["ref"] != ref:
            raise ValidationError("P0_REFERENCE_NOT_PRIOR_ACCEPTED")
        return record

    def order(self, objects):
        remaining = {o.digest: o for o in objects}
        if len(remaining) != len(objects):
            raise ValidationError("P0_DUPLICATE_OBJECT")
        content = set(remaining)
        done: set[str] = set()
        out = []
        while remaining:
            ready = [o for o in remaining.values() if {r["revision_digest"] for r in refs_in(o.body)} & content <= done]
            if not ready:
                raise ValidationError("P0_CONTENT_CYCLE")
            obj = min(ready, key=lambda o: (o.kind, o.logical_id, o.digest))
            out.append(obj)
            done.add(obj.digest)
            del remaining[obj.digest]
        return out

    def basis(self, objects, events):
        content = {o.digest for o in objects}
        pinned = {r["revision_digest"] for r in self.pins.values()}
        return sorted_refs(r for v in [*[o.body for o in objects], events] for r in refs_in(v)
                           if r["revision_digest"] not in content | pinned)

    def validate_roots(self):
        reg = self.roots["artifact_contract_registry"].body
        if reg["contracts"] != sorted(self.corpus.descriptor["canonical_contracts"]):
            raise ValidationError("P0_REGISTRY_EXACT_MEMBERSHIP")
        if reg["model_descriptor_raw_ref"] != self.corpus.raw_ref(self.corpus.files[BASE + "MODEL.json"], "BDB_CJSON_1", "application/json"):
            raise ValidationError("P0_MODEL_DESCRIPTOR_IDENTITY")
        bindings = [{"schema_id": self.schema_ref(kind)["schema_id"], "schema_raw_ref": self.corpus.raw_ref(
            self.corpus.files[BASE + "schemas/canonical/" + kind + "__" + version + ".schema.json"], "BDB_CJSON_1", "application/schema+json")}
                    for kind, version in self.corpus.versions.items()]
        bindings.sort(key=lambda r: r["schema_id"])
        if self.roots["schema_registry"].body["bindings"] != bindings:
            raise ValidationError("P0_SCHEMA_REGISTRY_EXACT_BINDINGS")
        for obj in self.roots.values():
            self.check_profiles(obj.body)
            for ref in refs_in(obj.body):
                if self.pins.get(ref["kind"]) != ref:
                    raise ValidationError("P0_INITIAL_PIN_MISMATCH")
        boot = self.roots["installation_bootstrap_profile"].body
        if boot["namespace_authority_digest"] != self.root["namespace_authority_digest"]:
            raise ValidationError("P0_EIGHT_BOOTSTRAP_PINS_MISMATCH")

    def check_profiles(self, value):
        if isinstance(value, dict):
            if set(value) == {"profile_id", "revision_digest"}:
                if value != self.corpus.pin(value["profile_id"]):
                    raise ValidationError("P0_PROFILE_PIN_MISMATCH")
            else:
                for child in value.values():
                    self.check_profiles(child)
        elif isinstance(value, list):
            for child in value:
                self.check_profiles(child)

    def raw(self, reader, ref):
        self.check_profiles(ref)
        raw = reader.read_bytes(ref["raw_digest"])
        if len(raw) != ref["byte_length"]:
            raise ValidationError("P0_RAW_IDENTITY_MISMATCH")
        return raw

    def context(self, records, assignment_ref, reader):
        assignment = self.resolve(records, assignment_ref)["object"].body
        attempt = self.resolve(records, assignment["attempt_ref"])["object"].body
        genesis = self.resolve(records, assignment["campaign_ref"])["object"].body
        source = self.resolve(records, assignment["source_ref"])["object"].body
        if (attempt["campaign_ref"] != assignment["campaign_ref"] or attempt["source_ref"] != assignment["source_ref"]
                or attempt["auditor_certificate_sha256"] != assignment["auditor_certificate_sha256"]
                or genesis["source_ref"] != assignment["source_ref"] or genesis["task_raw_ref"] != assignment["task_raw_ref"]):
            raise ValidationError("P0_ASSIGNMENT_CONTEXT_JOIN")
        manifest, members = self.transport.source(self.raw(reader, source["source_manifest_raw_ref"]),
                                                   self.raw(reader, source["source_archive_raw_ref"]), source)
        task = self.raw(reader, genesis["task_raw_ref"])
        expected = self.transport.input_members(self.raw(reader, source["source_manifest_raw_ref"]), members, task)
        if assignment["input_members"] != self.transport.member_records(expected):
            raise ValidationError("P0_APPROVED_VIEW_MEMBERS_MISMATCH")
        scope = {"campaign_id": genesis["campaign_id"], "attempt_ref": assignment["attempt_ref"],
                 "assignment_ref": assignment_ref, "source_ref": assignment["source_ref"], "slot_id": "EXTERNAL_AUDIT_RESULT"}
        return assignment, source, manifest, expected, scope

    def auth_scope(self, genesis, source, assignment_ref=None, auditor=None):
        source_scope = domain_hash("BDB-NF02-P0-SOURCE-SCOPE/1", {
            "repository_id": source["repository_id"], "git_object_algorithm": source["git_object_algorithm"],
            "git_commit_object_id": source["git_commit_object_id"], "git_tree_object_id": source["git_tree_object_id"],
            "source_manifest_raw_ref": source["source_manifest_raw_ref"]})
        return {"campaign_id": genesis["campaign_id"], "source_scope_digest": source_scope,
                "view_task_digest": domain_hash("BDB-NF02-P0-VIEW-TASK/1", {"source_scope_digest": source_scope,
                    "approved_view_digest": source["approved_view_digest"], "task_raw_ref": genesis["task_raw_ref"]}),
                "assignment_scope_digest": None if assignment_ref is None else domain_hash("BDB-NF02-P0-ASSIGNMENT-SCOPE/1", {
                    "assignment_ref": assignment_ref, "slot_id": "EXTERNAL_AUDIT_RESULT",
                    "auditor_certificate_sha256": auditor})}

    @staticmethod
    def state_of(events):
        state = "EMPTY"
        for e in events:
            if e["event_type"] == "P0AttemptStarted":
                state = "STARTED"
            else:
                state = FACT_STATES.get(e["artifact_ref"]["kind"], state)
        return state

    def validate_step(self, records, events, current, command, objects, reader, *, leased=None, at=None, con=None):
        b, op = command.body(), command.command_kind
        domain = [o for o in objects if o.kind != "command_envelope"]
        expected_kinds = sorted(self.corpus.operations[op]["objects"])
        if sorted(o.kind + "/" + o.version for o in domain) != expected_kinds:
            raise ValidationError("P0_OPERATION_OBJECT_SET")
        if b["proposed_object_refs"] != sorted_refs(o.ref.as_dict() for o in domain):
            raise ValidationError("P0_COMMAND_PROPOSED_REFS")
        expected_events = [{"event_type": "P0FactAccepted", "artifact_ref": o.ref.as_dict()} for o in self.order(domain)]
        if op != "START_ATTEMPT" and b["events"] != expected_events:
            raise ValidationError("P0_COMMAND_EVENT_SET")
        if b["basis_refs"] != self.basis(domain, b["events"]):
            raise ValidationError("P0_COMMAND_PRIOR_BASIS")
        parent = current.as_dict() if current else "EMPTY_HISTORY"
        if b["expected_parent"] != parent:
            raise ValidationError("EXPECTED_HEAD_CONFLICT")
        if any(b[k] != self.pins[kind] for k, kind in (("policy_ref", "policy_revision"), ("spec_ref", "spec_revision"), ("schema_registry_ref", "schema_registry"))):
            raise ValidationError("P0_CONTEXT_PIN_MISMATCH")
        state = self.state_of(events)
        for obj in domain:
            self.check_profiles(obj.body)
            for cut_name, cut in obj.body.items():
                if cut_name.endswith("_cut") and (current is None or cut != self.cut_for(current, records)):
                    raise ValidationError("P0_INPUT_CUT_MISMATCH")
            for ref in refs_in(obj.body):
                if ref["revision_digest"] in {o.digest for o in domain}:
                    spec = next((s for s in self.registry.contract(obj.kind, obj.version)["material_refs"] if obj.body.get(s["field"]) == ref), None)
                    allowed = {"CONTENT_AT_INITIALIZATION_ONLY", "SAME_CREATE_ASSIGNMENT_CONTENT", "PINNED_INSTALLATION"}
                    if not spec or spec["ref_class"] not in allowed:
                        raise ValidationError("P0_PRIOR_TARGET_IN_SAME_COMMIT")
                elif self.pins.get(ref["kind"]) != ref:
                    self.resolve(records, ref)
            for ref in raw_refs(obj.body):
                self.raw(reader, ref)
            if any(r["object"].logical_id == obj.logical_id for r in records.values()):
                raise ValidationError("P0_LOGICAL_ID_REUSE")
        for ref in b["basis_refs"]:
            self.resolve(records, ref)
        if op == "INITIALIZE_P0_FROM_APPROVED_GIT":
            if current is not None:
                raise ValidationError("P0_NEW_EMPTY_CAMPAIGN_REQUIRED")
            roots = {o.kind: o.ref.as_dict() for o in domain if o.kind in ROOT_KINDS}
            if roots != self.pins:
                raise ValidationError("P0_BOOTSTRAP_ROOTS_MISMATCH")
            genesis = next(o for o in domain if o.kind == "campaign_genesis").body
            source = next(o for o in domain if o.kind == "nf02_p0_source_snapshot").body
            if (genesis["campaign_id"] != genesis["object_id"] or genesis["campaign_id"] != b["campaign_id"]
                    or genesis["source_ref"] != next(o.ref.as_dict() for o in domain if o.kind == "nf02_p0_source_snapshot")
                    or genesis["namespace_authority_digest"] != self.root["namespace_authority_digest"] or genesis["mode"] != b["mode"]):
                raise ValidationError("P0_GENESIS_CONTEXT_MISMATCH")
            expected_repo = domain_hash("BDB-NF02-P0-REPOSITORY/1", {"namespace_authority_digest": self.root["namespace_authority_digest"], "repository_id": source["repository_id"]})
            if source["repository_authority_digest"] != expected_repo:
                raise ValidationError("P0_REPOSITORY_AUTHORITY_MISMATCH")
            self.transport.source(self.raw(reader, source["source_manifest_raw_ref"]), self.raw(reader, source["source_archive_raw_ref"]), source)
            repositories = strict_json(self.corpus.files["SOURCE_REPOSITORIES.json"])
            matches = [r for r in repositories.get("repositories", []) if r.get("repository_id") == source["repository_id"]]
            if set(repositories) != {"repositories"} or len(matches) != 1 or set(matches[0]) != {"repository_id", "path"}:
                raise ValidationError("P0_APPROVED_REPOSITORY_REQUIRED")
            view = strict_json(self.raw(reader, source["source_manifest_raw_ref"]))
            identity, actual_manifest, actual_archive = approved_git_view(matches[0]["path"],
                source["git_commit_object_id"], source["repository_id"], [e["source_path"] for e in view["entries"]])
            if (identity.commit_object_id != source["git_commit_object_id"] or identity.tree_object_id != source["git_tree_object_id"]
                    or actual_manifest != self.raw(reader, source["source_manifest_raw_ref"])
                    or actual_archive != self.raw(reader, source["source_archive_raw_ref"])):
                raise ValidationError("P0_ACTUAL_GIT_SOURCE_MISMATCH")
            self.transport.input_members(self.raw(reader, source["source_manifest_raw_ref"]), {}, self.raw(reader, genesis["task_raw_ref"]))
            return self.auth_scope(genesis, source)
        if not current or b["campaign_id"] != current.campaign_id:
            raise ValidationError("P0_CAMPAIGN_MISMATCH")
        assignment_ref = None
        if op == "CREATE_ASSIGNMENT":
            if state not in {"GENESIS", "ABORTED"}:
                raise ValidationError("P0_CREATE_STATE_CONFLICT")
            attempt = next(o for o in domain if o.kind == "attempt")
            assignment = next(o for o in domain if o.kind == "assignment_manifest")
            extended = {**records, attempt.digest: {"object": attempt, "ref": attempt.ref.as_dict(), "seq": current.commit_seq + 1}}
            extended[assignment.digest] = {"object": assignment, "ref": assignment.ref.as_dict(), "seq": current.commit_seq + 1}
            assignment_ref = assignment.ref.as_dict()
            a, source, _, _, _ = self.context(extended, assignment_ref, reader)
            old_attempts = [r for r in records.values() if r["object"].kind == "attempt"]
            previous = max(old_attempts, key=lambda r: r["seq"]) if old_attempts else None
            aborts = [r for r in records.values() if r["object"].kind == "nf02_p0_abort"]
            if state == "GENESIS":
                if attempt.body["retry_of_attempt_ref"] is not None or attempt.body["abort_basis_ref"] is not None:
                    raise ValidationError("P0_INITIAL_ATTEMPT_RETRY_REFS")
            else:
                abort = max(aborts, key=lambda r: r["seq"])
                if previous is None:
                    raise ValidationError("P0_RETRY_PREDECESSOR_MISMATCH")
                if attempt.body["retry_of_attempt_ref"] != previous["ref"] or attempt.body["abort_basis_ref"] != abort["ref"] or abort["object"].body["attempt_ref"] != previous["ref"]:
                    raise ValidationError("P0_RETRY_PREDECESSOR_MISMATCH")
        else:
            if op == "START_ATTEMPT":
                if len(b["events"]) != 1 or b["events"][0]["event_type"] != "P0AttemptStarted":
                    raise ValidationError("P0_EXACT_START_EVENT_REQUIRED")
                assignment_ref = b["events"][0]["assignment_ref"]
            elif op == "ACCEPT_RESULT":
                evidence = self.resolve(records, domain[0].body["admission_ref"])["object"]
                assignment_ref = evidence.body["assignment_ref"]
            else:
                assignment_ref = domain[0].body["assignment_ref"]
            a, source, manifest, members, scope = self.context(records, assignment_ref, reader)
            latest = max((r for r in records.values() if r["object"].kind == "assignment_manifest"), key=lambda r: r["seq"])
            if assignment_ref != latest["ref"]:
                raise ValidationError("P0_ASSIGNMENT_NOT_ACTIVE")
            required = {"BIND_PACKAGE": "ASSIGNED", "START_ATTEMPT": "BOUND", "CONFIRM_DELIVERY": "STARTED", "INGEST_EVIDENCE": "DELIVERED", "ACCEPT_RESULT": "EVIDENCE_ACCEPTED"}
            if op in required and state != required[op]:
                raise ValidationError("P0_OPERATION_STATE_CONFLICT")
            if op == "BIND_PACKAGE":
                self.transport.package(self.raw(reader, domain[0].body["package_raw_ref"]), a, scope, members)
            elif op == "ABORT_ATTEMPT":
                if state not in {"ASSIGNED", "BOUND", "STARTED", "DELIVERED", "EVIDENCE_ACCEPTED"} or domain[0].body["from_state"] != state or domain[0].body["attempt_ref"] != a["attempt_ref"]:
                    raise ValidationError("P0_ABORT_CONTEXT_MISMATCH")
            else:
                binding_record = next(r for r in records.values() if r["object"].kind == "assignment_package_binding" and r["object"].body["assignment_ref"] == assignment_ref)
                binding = binding_record["object"]
                self.transport.package(self.raw(reader, binding.body["package_raw_ref"]), a, scope, members)
                if op == "START_ATTEMPT":
                    if b["events"] != [{"event_type": "P0AttemptStarted", "assignment_ref": assignment_ref, "attempt_ref": a["attempt_ref"], "binding_ref": binding.ref.as_dict()}]:
                        raise ValidationError("P0_START_CONTEXT_MISMATCH")
                else:
                    start = next(e["_position"] for e in events if e["event_type"] == "P0AttemptStarted" and e["assignment_ref"] == assignment_ref)
                    target = domain[0] if op != "ACCEPT_RESULT" else evidence
                    if target.body["binding_ref"] != binding.ref.as_dict() or target.body["auditor_certificate_sha256"] != a["auditor_certificate_sha256"]:
                        raise ValidationError("P0_FULL_RESULT_JOIN_MISMATCH")
                    if op == "CONFIRM_DELIVERY":
                        if target.body["start_event"] != start:
                            raise ValidationError("P0_DELIVERY_START_MISMATCH")
                        ack = strict_json(self.raw(reader, target.body["ack_raw_ref"]))
                        self.schemas.validate("wire/DELIVERY_ACK__1", ack)
                        if self.raw(reader, target.body["ack_raw_ref"]) != canonical_bytes(ack) + b"\n":
                            raise ValidationError("P0_CJSON_TRANSPORT_REQUIRED")
                        release_id = self.release_id(scope, binding, start, a)
                        expected = {"domain": "BDB_P0_DELIVERY_ACK/1", "scope": scope, "release_id": release_id,
                                    "binding_ref": binding.ref.as_dict(), "start_event": start,
                                    "package_raw_ref": binding.body["package_raw_ref"], "auditor_certificate_sha256": a["auditor_certificate_sha256"]}
                        if ack != expected or target.body["release_id"] != release_id:
                            raise ValidationError("P0_ACK_CONTEXT_MISMATCH")
                        if at is None:
                            row = con.execute("SELECT body FROM p0_release_jobs WHERE release_id=?", (release_id,)).fetchone()
                            if row is None or strict_json(row[0])["status"] != "SENT":
                                raise ValidationError("P0_REAL_DELIVERY_REQUIRED")
                        auditor_op, signed_raw, signature = "ACK_DELIVERY", self.raw(reader, target.body["ack_raw_ref"]), self.raw(reader, target.body["ack_signature_raw_ref"])
                    else:
                        delivery = self.resolve(records, target.body["delivery_ref"])["object"]
                        if (delivery.body["assignment_ref"] != assignment_ref or delivery.body["binding_ref"] != binding.ref.as_dict()
                                or delivery.body["start_event"] != start or delivery.body["auditor_certificate_sha256"] != a["auditor_certificate_sha256"]):
                            raise ValidationError("P0_DELIVERY_JOIN_MISMATCH")
                        returned = strict_json(self.raw(reader, target.body["return_raw_ref"]))
                        self.schemas.validate("wire/AUDIT_RETURN__1", returned)
                        if self.raw(reader, target.body["return_raw_ref"]) != canonical_bytes(returned) + b"\n":
                            raise ValidationError("P0_CJSON_TRANSPORT_REQUIRED")
                        expected = {"domain": "BDB_P0_AUDIT_RETURN/1", "scope": scope, "binding_ref": binding.ref.as_dict(),
                                    "delivery_ref": delivery.ref.as_dict(), "result_raw_ref": target.body["result_raw_ref"],
                                    "auditor_certificate_sha256": a["auditor_certificate_sha256"], "execution_declaration": "EXECUTED_ASSIGNED_AUDIT"}
                        if returned != expected:
                            raise ValidationError("P0_SIGNED_RETURN_JOIN_MISMATCH")
                        payload = self.transport.result(self.raw(reader, target.body["result_raw_ref"]), {"scope": scope,
                            "binding_ref": binding.ref.as_dict(), "delivery_ref": delivery.ref.as_dict(), "package_raw_ref": binding.body["package_raw_ref"]}, manifest)
                        if op == "ACCEPT_RESULT" and canonical_bytes(domain[0].body["result_payload"]) != canonical_bytes(payload):
                            raise ValidationError("P0_RESULT_REDERIVATION_MISMATCH")
                        auditor_op, signed_raw, signature = "RETURN_AUDIT", self.raw(reader, target.body["return_raw_ref"]), self.raw(reader, target.body["return_signature_raw_ref"])
                    genesis = self.resolve(records, a["campaign_ref"])["object"].body
                    auth_scope = self.auth_scope(genesis, source, assignment_ref, a["auditor_certificate_sha256"])
                    self.authority.select_grant(leased, operation=auditor_op, certificate=a["auditor_certificate_sha256"], scope=auth_scope, at=at)
                    verify_cms(signed_raw, signature, a["auditor_certificate_sha256"], at_time=at)
        genesis = self.resolve(records, a["campaign_ref"])["object"].body
        if genesis["campaign_id"] != b["campaign_id"]:
            raise ValidationError("P0_CAMPAIGN_CONTEXT_JOIN")
        scope = self.auth_scope(genesis, source, assignment_ref, a["auditor_certificate_sha256"])
        if op in {"CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT"}:
            scope.update(_auditor_operation=auditor_op, _auditor_certificate_sha256=a["auditor_certificate_sha256"],
                         _auditor_signed_raw=signed_raw, _auditor_signature=signature)
        return scope

    @staticmethod
    def release_id(scope, binding, start, assignment):
        return domain_hash("BDB-NF02-P0-RELEASE/1", {"campaign_id": scope["campaign_id"], "assignment_ref": scope["assignment_ref"],
            "binding_ref": binding.ref.as_dict(), "start_event": start, "package_raw_ref": binding.body["package_raw_ref"],
            "auditor_certificate_sha256": assignment["auditor_certificate_sha256"]})

    def validate(self, *, con, current, command, objects, events, raw_artifacts, leased, authentication, retry=False):
        records, prior_events, commits = self.history(con, current) if current else ({}, [], [])
        if events != command.body()["events"]:
            raise ValidationError("P0_SIGNED_EVENTS_MISMATCH")
        if retry:
            row = next(c for c in commits if c["command_digest"] == command.digest)
            original = {r["revision_digest"] for r in row["immutable_object_refs"]}
            if {o.digest for o in objects} != original:
                raise ValidationError("P0_RETRY_CONTENT_MISMATCH")
            prior_seq = row["commit_seq"] - 1
            records = {d: r for d, r in records.items() if r["seq"] <= prior_seq}
            prior_events = [e for e in prior_events if e["_seq"] <= prior_seq]
            current = AcceptedHead(**row["previous_head"]) if prior_seq else None
        reader = AdmissionRawReader(con, proposed=raw_artifacts, allow_staged=False, require_retained=retry)
        # Bootstrap pinned raw material is independent of supplied raw inputs.
        reader.proposed.update({sha(raw): raw for raw in leased["files"].values()})
        at = strict_json(AdmissionRawReader(con, require_retained=True).read_bytes(row["authorization_trace_raw_ref"]["raw_digest"]))["verified_at_utc"] if retry else None
        scope = self.validate_step(records, prior_events, current, command, objects, reader, leased=leased, con=con, at=at)
        grant = self.recheck_authority(leased, command, authentication, scope)
        if retry:
            return {}, scope
        trace, raw = self.trace(command, authentication, leased, grant)
        reader.verified.update(raw)
        # The trace identity is returned as operation context, never signed into
        # a command that would then contain its own signature/hash.
        scope = {**scope, "_trace_ref": trace}
        return reader.verified, scope

    def recheck_authority(self, leased, command, signature, scope):
        grant = self.authority.authenticate(leased, command, signature, scope)
        if "_auditor_operation" in scope:
            self.authority.select_grant(leased, operation=scope["_auditor_operation"],
                certificate=scope["_auditor_certificate_sha256"], scope=scope)
            verify_cms(scope["_auditor_signed_raw"], scope["_auditor_signature"], scope["_auditor_certificate_sha256"])
        return grant

    def trace(self, command, signature, leased, grant):
        values = {"command_signature": (signature, "application/pkcs7-signature"), "root": (leased["root_raw"], "application/json"),
                  "installation": (leased["installation_raw"], "application/json"), "installation_signature": (leased["installation_signature"], "application/pkcs7-signature"),
                  "grant": (grant["raw"], "application/json"), "grant_signature": (grant["signature"], "application/pkcs7-signature")}
        body = {"domain": "BDB_P0_AUTHORIZATION_TRACE/1", "command_ref": command.as_object().ref.as_dict(),
                "verified_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "signer_certificate_sha256": grant["body"]["certificate_sha256"]}
        raw = {sha(data): data for data in leased["files"].values()}
        for item in leased["grants"]:
            raw.update({sha(item[k]): item[k] for k in ("raw", "signature")})
        for name, (data, media) in values.items():
            body[name + "_raw_ref"] = self.corpus.raw_ref(data, "P0_AUTHORIZATION_V1", media)
            raw[sha(data)] = data
        self.schemas.validate("wire/AUTHORIZATION_TRACE__1", body)
        data = canonical_bytes(body)
        raw[sha(data)] = data
        return self.corpus.raw_ref(data, "P0_AUTHORIZATION_V1", "application/json"), raw

    def build_acceptance(self, command, objects, current, context):
        seq = current.commit_seq + 1 if current else 1
        ordered = self.order(objects)
        b = command.body()
        commit = self.commit(value_body("commit_body", {"command_ref": command.as_object().ref.as_dict(), "command_digest": command.digest,
            "actor_ref": command.actor_ref, "campaign_id": b["campaign_id"], "commit_seq": seq, "previous_head": b["expected_parent"],
            **{k: b[k] for k in ("policy_ref", "spec_ref", "schema_registry_ref")}, "authorization_trace_raw_ref": context["_trace_ref"],
            "immutable_object_refs": [o.ref.as_dict() for o in ordered], "events": b["events"]}))
        head = AcceptedHead(b["campaign_id"], seq, commit.digest)
        receipt = self.receipt(value_body("command_receipt", {"command_ref": command.as_object().ref.as_dict(),
            "commit_ref": commit.obj.ref.as_dict(), "accepted_head": head.as_dict(),
            "result_object_refs": sorted_refs(o.ref.as_dict() for o in objects if o.kind != "command_envelope")}))
        return commit, receipt, head

    def persist_grant_proofs(self, con, leased):
        # A derived locator only. Replay verifies actual owner CMS again.
        for item in leased["grants"]:
            values = (item["digest"], sha(item["signature"]), item["body"]["certificate_sha256"])
            old = con.execute("SELECT grant_digest,signature_digest,certificate_sha256 FROM p0_grant_proofs WHERE grant_digest=?", (values[0],)).fetchone()
            if old is not None and old != values:
                raise ValidationError("P0_RETAINED_GRANT_PROOF_CONFLICT")
            con.execute("INSERT OR IGNORE INTO p0_grant_proofs VALUES(?,?,?)", values)

    def persist_domain_effects(self, con, command, objects):
        if command.command_kind == "CONFIRM_DELIVERY":
            delivery = next(o for o in objects if o.kind == "nf02_p0_delivery")
            row = con.execute("SELECT body FROM p0_release_jobs WHERE release_id=?", (delivery.body["release_id"],)).fetchone()
            job = strict_json(row[0])
            job["status"] = "ACKNOWLEDGED"
            con.execute("UPDATE p0_release_jobs SET body=? WHERE release_id=?", (canonical_bytes(job), job["release_id"]))

    def release_job(self, con, current, records, events, binding_ref, grant_digest):
        if self.state_of(events) not in {"STARTED", "DELIVERED"}:
            raise ValidationError("P0_RELEASE_STATE_CONFLICT")
        reader = AdmissionRawReader(con, require_retained=True)
        binding = self.resolve(records, binding_ref)["object"]
        a, _, _, members, scope = self.context(records, binding.body["assignment_ref"], reader)
        latest = max((r for r in records.values() if r["object"].kind == "assignment_manifest"), key=lambda r: r["seq"])
        if scope["assignment_ref"] != latest["ref"]:
            raise ValidationError("P0_RELEASE_ASSIGNMENT_NOT_ACTIVE")
        start = next(e["_position"] for e in events if e["event_type"] == "P0AttemptStarted" and e["binding_ref"] == binding_ref)
        package = self.raw(reader, binding.body["package_raw_ref"])
        self.transport.package(package, a, scope, members)
        job = {"domain": "BDB_P0_RELEASE/1", "scope": scope, "release_id": self.release_id(scope, binding, start, a),
            "binding_ref": binding_ref, "start_event": start, "authorized_cut": self.cut_for(current, records),
            "installation_digest": self.identity, "grant_digest": grant_digest, "package_raw_ref": binding.body["package_raw_ref"],
            "auditor_certificate_sha256": a["auditor_certificate_sha256"], "status": "PREPARED"}
        self.schemas.validate("wire/RELEASE_JOB__1", job)
        genesis = self.resolve(records, a["campaign_ref"])["object"].body
        source = self.resolve(records, a["source_ref"])["object"].body
        return job, package, self.auth_scope(genesis, source, scope["assignment_ref"], a["auditor_certificate_sha256"])

    def release_statement(self, job):
        return {"domain": "BDB_P0_RELEASE_REQUEST/1", "model_id": self.corpus.descriptor["model_id"],
            "mode": self.installation["mode"], "namespace_authority_digest": self.root["namespace_authority_digest"],
            "installation_digest": self.identity, "grant_digest": job["grant_digest"], "job": copy(job)}

    def authenticate_release(self, leased, job, signature, scope):
        grant = self.authority.select_grant(leased, operation="RELEASE_PACKAGE", digest=job["grant_digest"], scope=scope)
        self.authority.select_grant(leased, operation="ACK_DELIVERY", certificate=job["auditor_certificate_sha256"], scope=scope)
        verify_cms(canonical_bytes(self.release_statement(job)), signature, grant["body"]["certificate_sha256"])
        return grant

    def trace_release(self, job, signature, leased, grant):
        # Protected operational evidence; it is neither a new canonical kind
        # nor an authorization input. Only actual CMS/current grants grant I/O.
        raw = {sha(data): data for data in leased["files"].values()}
        values = {"root": (leased["root_raw"], "application/json"), "installation": (leased["installation_raw"], "application/json"),
            "installation_signature": (leased["installation_signature"], "application/pkcs7-signature"), "grant": (grant["raw"], "application/json"),
            "grant_signature": (grant["signature"], "application/pkcs7-signature"), "request_signature": (signature, "application/pkcs7-signature")}
        body = {"request": self.release_statement(job), "verified_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for name, (data, media) in values.items():
            body[name + "_raw_ref"] = self.corpus.raw_ref(data, "P0_AUTHORIZATION_V1", media)
            raw[sha(data)] = data
        for item in leased["grants"]:
            raw.update({sha(item[k]): item[k] for k in ("raw", "signature")})
        data = canonical_bytes(body)
        raw[sha(data)] = data
        return self.corpus.raw_ref(data, "P0_AUTHORIZATION_V1", "application/json"), raw

    def history(self, con, current):
        records: dict[str, Any] = {}
        events: list[Any] = []
        commits: list[Any] = []
        previous: Any = "EMPTY_HISTORY"
        reader = AdmissionRawReader(con, require_retained=True)
        for seq, digest, raw in con.execute("SELECT seq,commit_hash,body FROM commits ORDER BY seq"):
            body = strict_json(raw)
            commit = self.commit(body)
            if seq != len(commits) + 1 or body["commit_seq"] != seq or body["previous_head"] != previous or commit.digest != digest or body["campaign_id"] != current.campaign_id:
                raise ValidationError("P0_HISTORY_INTEGRITY_FAILURE")
            objects = []
            for ref in body["immutable_object_refs"]:
                row = con.execute("SELECT kind,version,schema_ref,logical_id,body FROM immutable_objects WHERE digest=?", (ref["revision_digest"],)).fetchone()
                if row is None:
                    raise ValidationError("P0_HISTORY_OBJECT_MISSING")
                obj = self.object_from_row(row)
                if obj.ref.as_dict() != ref or obj.digest in records:
                    raise ValidationError("P0_HISTORY_REFERENCE_INTEGRITY")
                objects.append(obj)
            if [o.ref.as_dict() for o in self.order(objects)] != body["immutable_object_refs"]:
                raise ValidationError("P0_HISTORY_CONTENT_ORDER")
            command_obj = next(o for o in objects if o.kind == "command_envelope")
            command = LimitedCommand(command_obj.body, self)
            if (body["command_ref"] != command_obj.ref.as_dict() or body["command_digest"] != command.digest
                    or body["actor_ref"] != command.actor_ref or body["events"] != command.body()["events"]
                    or any(body[k] != command.body()[k] for k in ("policy_ref", "spec_ref", "schema_registry_ref"))):
                raise ValidationError("P0_HISTORY_COMMAND_BINDING")
            trace = strict_json(self.raw(reader, body["authorization_trace_raw_ref"]))
            self.schemas.validate("wire/AUTHORIZATION_TRACE__1", trace)
            at = trace["verified_at_utc"]
            root = self.corpus.external("ROOT", self.raw(reader, trace["root_raw_ref"]))
            install_raw = self.raw(reader, trace["installation_raw_ref"])
            install = self.corpus.external("INSTALLATION_RECORD", install_raw)
            grant_raw = self.raw(reader, trace["grant_raw_ref"])
            grant = self.corpus.external("PRINCIPAL_GRANT", grant_raw)
            if (root != self.root or sha(install_raw) != self.identity or install != self.installation
                    or command.body()["grant_digest"] != sha(grant_raw) or grant["installation_digest"] != self.identity
                    or trace["command_ref"] != command_obj.ref.as_dict() or trace["signer_certificate_sha256"] != grant["certificate_sha256"]):
                raise ValidationError("P0_HISTORY_AUTHORITY_TRACE")
            grants = []
            for gd, sd, cert in con.execute("SELECT grant_digest,signature_digest,certificate_sha256 FROM p0_grant_proofs"):
                candidate, sig = reader.read_bytes(gd), reader.read_bytes(sd)
                g = self.corpus.external("PRINCIPAL_GRANT", candidate)
                if g["installation_digest"] != self.identity or g["certificate_sha256"] != cert:
                    raise ValidationError("P0_HISTORY_GRANT_PROOF_INTEGRITY")
                if not instant(g["not_before"]) <= instant(at) < instant(g["not_after"]):
                    continue
                verify_cms(candidate, sig, root["owner_certificate_sha256"], at_time=at)
                grants.append({"body": g, "raw": candidate, "signature": sig, "digest": gd})
            historical = {"identity": self.identity, "installation": install, "root": root, "grants": grants}
            input_head = AcceptedHead(**previous) if previous != "EMPTY_HISTORY" else None
            scope = self.validate_step(records, events, input_head, command, objects, reader, leased=historical, at=at)
            self.authority.select_grant(historical, operation=command.command_kind, actor=command.actor_ref,
                                        digest=sha(grant_raw), scope=scope, at=at)
            for content, signature in ((install_raw, self.raw(reader, trace["installation_signature_raw_ref"])),
                                       (grant_raw, self.raw(reader, trace["grant_signature_raw_ref"]))):
                verify_cms(content, signature, root["owner_certificate_sha256"], at_time=at)
            verify_cms(command.signing_bytes(), self.raw(reader, trace["command_signature_raw_ref"]), grant["certificate_sha256"], at_time=at)
            receipt_row = con.execute("SELECT receipt_digest,body FROM receipts WHERE command_id=?", (command.command_id,)).fetchone()
            receipt = self.receipt(strict_json(receipt_row[1])) if receipt_row else None
            head = AcceptedHead(body["campaign_id"], seq, digest)
            expected_refs = sorted_refs(o.ref.as_dict() for o in objects if o.kind != "command_envelope")
            index = con.execute("SELECT command_digest,receipt_digest FROM command_index WHERE command_id=?", (command.command_id,)).fetchone()
            if (receipt is None or receipt.digest != receipt_row[0] or receipt.command_ref.as_dict() != command_obj.ref.as_dict()
                    or receipt.obj.body["commit_ref"] != commit.obj.ref.as_dict() or receipt.accepted_head != head
                    or receipt.obj.body["result_object_refs"] != expected_refs or index != (command.digest, receipt.digest)):
                raise ValidationError("P0_HISTORY_RECEIPT_INTEGRITY")
            records.update({o.digest: {"object": o, "ref": o.ref.as_dict(), "seq": seq} for o in objects})
            for ordinal, event in enumerate(body["events"]):
                events.append({**event, "_seq": seq, "_position": {"commit_hash": digest, "ordinal": ordinal}})
            commits.append(body)
            previous = head.as_dict()
        if current and previous != current.as_dict():
            raise ValidationError("P0_HISTORY_HEAD_INTEGRITY")
        self._source_ref = next((r["ref"] for r in records.values() if r["object"].kind == "nf02_p0_source_snapshot"), None)
        return records, events, commits

    def retained(self, con, obj):
        reader = AdmissionRawReader(con, require_retained=True)
        records, _, _ = self.history(con, AcceptedHead(*con.execute("SELECT campaign_id,seq,commit_hash FROM accepted_head").fetchone()))
        pending, seen = [obj.body], set()
        while pending:
            value = pending.pop()
            for ref in raw_refs(value):
                self.raw(reader, ref)
            for ref in refs_in(value):
                if ref["revision_digest"] not in seen:
                    seen.add(ref["revision_digest"])
                    pending.append(self.resolve(records, ref)["object"].body)
        return reader.verified

    def projected_events(self, events, records):
        return events

    def state(self, events, aggregate, identifier, default):
        return self.state_of(events)
