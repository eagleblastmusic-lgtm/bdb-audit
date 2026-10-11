"""E1 successor operations; every write goes through Coordinator/Store.

Signatures stay outside canonical objects. A producer signs the exact prepared
command and installation scope. Preparing a request creates no authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from uuid import uuid4

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..coordinator import Coordinator
from ..history.installation_authority import sha
from ..history.raw_artifacts import AdmissionRawReader
from ..history.successor_wire import SuccessorCommand, copy, eq_ref


@dataclass(frozen=True)
class IntakeRequest:
    command: SuccessorCommand
    objects: tuple
    events: tuple
    raw: dict
    scope: dict

    def signing_bytes(self):
        return canonical_bytes({"domain": "BDB_NF02_AUTHENTICATED_COMMAND/1", "installation": self.command.runtime.identity,
                                "command_digest": self.command.digest, "scope": self.scope})


class NF02Intake:
    def __init__(self, store):
        if not store._nf02:
            raise ValidationError("NF02_INSTALLED_STORE_REQUIRED")
        self.store, self.runtime = store, store._nf02
        self.coordinator = Coordinator(store)

    def prepare_initialization(self, *, actor_ref, campaign_id, objects, events, raw_artifacts=None, command_id=None):
        """Prepare a new campaign packet for independent admission and signing.

        This only constructs values. The installation must already authorize
        the exact packet before Coordinator can accept it.
        """
        if self.store.head() is not None:
            raise ValidationError("NF02_NEW_EMPTY_HISTORY_REQUIRED")
        pins = self.runtime.bundle["initial_pins"]
        spec = next(obj for obj in self.runtime.installed_objects.values() if obj.kind == "spec_revision")
        command = SuccessorCommand(command_id=command_id or "command_" + str(uuid4()), command_kind="INITIALIZE_CAMPAIGN_FROM_LEGACY",
                                   actor_ref=actor_ref, expected_parent_head="EMPTY_HISTORY",
                                   command_payload={},
                                   governing_policy_ref=copy(pins["initial_governing_policy_ref"]), governing_spec_refs=(spec.ref.as_dict(),),
                                   idempotency_scope=campaign_id, proposed_campaign_id=campaign_id,
                                   bootstrap_profile_ref=copy(self.runtime.bundle["installation_bootstrap_profile_ref"]),
                                   history_namespace_ref=copy(pins["allowed_history_namespace_ref"]), runtime=self.runtime)
        return IntakeRequest(command, tuple(objects), tuple(copy(list(events))), dict(raw_artifacts or {}),
                             {"campaign_id": campaign_id, "purpose": "BOOTSTRAP"})

    def prepare_context(self, *, actor_ref, objects, events, raw_artifacts=None, command_id=None):
        command = self.command("PREPARE_NF02_E1_CONTEXT", actor_ref, {}, command_id=command_id)
        return IntakeRequest(command, tuple(objects), tuple(copy(list(events))), dict(raw_artifacts or {}),
                             {"campaign_id": command.campaign_ref, "purpose": "E1_CONTEXT"})

    @staticmethod
    def packet_bytes(request):
        """Exact external review input, not an approval or runtime capability."""
        return canonical_bytes({"command": request.command.body(), "objects": [o.record() for o in request.objects],
                                "events": list(request.events), "raw": sorted(request.raw)})

    def command(self, kind, actor_ref, payload=None, command_id=None):
        head = self.store.head()
        if head is None:
            raise ValidationError("NF02_NEW_CAMPAIGN_GENESIS_REQUIRED")
        prior = self.store.commits()[-1]
        return SuccessorCommand(command_id=command_id or "command_" + str(uuid4()), command_kind=kind,
                                actor_ref=actor_ref, expected_parent_head=head.as_dict(),
                                governing_policy_ref=prior["governing_policy_ref"], governing_spec_refs=tuple(prior["governing_spec_refs"]),
                                idempotency_scope=head.campaign_id, command_payload=payload, campaign_ref=head.campaign_id,
                                runtime=self.runtime)

    def _context(self, assignment_ref):
        con = self.store._connect()
        try:
            con.execute("BEGIN")
            head = self.store.head()
            records, events, commits = self.runtime.history(con, head)
            events = self.runtime.projected_events(events, records)
            assignment, attempt, claims, scope = self.runtime.context(records, events, assignment_ref, head.campaign_id)
            return records, events, self.runtime.cut(head, commits[-1]), assignment, attempt, claims, scope
        finally:
            con.close()

    def bind(self, *, actor_ref, assignment_ref, package_zip, command_id=None):
        raw = bytes(package_zip)
        records, events, cut, assignment, attempt, claims, scope = self._context(assignment_ref)
        obj = self.runtime.object("assignment_package_binding", {
            "binding_id": "assignment_package_binding_" + str(uuid4()), "assignment_ref": copy(assignment_ref),
            "binding_input_history_cut": cut, "package_raw_ref": self.raw_ref(raw, "NF02_INPUT_PACKAGE_TRANSPORT_V2")},
            logical_id=None)
        # Logical IDs are part of the full typed identity as well as the body.
        obj = self.runtime.object(obj.kind, obj.body, logical_id=obj.body["binding_id"])
        cmd = self.command("BIND_ASSIGNMENT_PACKAGE", actor_ref, {"artifact_ref": obj.ref.as_dict()}, command_id)
        return IntakeRequest(cmd, (obj,), tuple(self.runtime.expected_events(obj)), {sha(raw): raw}, scope)

    def start(self, *, actor_ref, binding_ref, command_id=None):
        head = self.store.head()
        cut = self.runtime.cut(head, self.store.commits()[-1])
        binding = self.store.resolve_accepted(binding_ref, cut)
        _, _, cut, assignment, attempt, _, scope = self._context(binding["body"]["assignment_ref"])
        cmd = self.command("START_ATTEMPT", actor_ref, {"package_binding_ref": copy(binding_ref), "input_history_cut": cut}, command_id)
        event = {"event_type": "AttemptStarted", "attempt_ref": assignment["attempt_ref"],
                 "assignment_ref": binding["body"]["assignment_ref"], "package_binding_ref": copy(binding_ref)}
        return IntakeRequest(cmd, (), (event,), {}, scope)

    def evidence(self, *, actor_ref, assignment_ref, binding_ref, slot_ref, result_zip, command_id=None):
        raw = bytes(result_zip)
        _, _, cut, _, attempt, _, scope = self._context(assignment_ref)
        body = {"admission_evidence_id": "lane_result_admission_evidence_" + str(uuid4()),
                "assignment_ref": copy(assignment_ref), "package_binding_ref": copy(binding_ref),
                "result_slot_contract_ref": copy(slot_ref), "admission_input_history_cut": cut,
                "result_raw_ref": self.raw_ref(raw, "NF02_RESULT_TRANSPORT_V2")}
        obj = self.runtime.object("lane_result_admission_evidence", body, "2", body["admission_evidence_id"])
        cmd = self.command("INGEST_EXTERNAL_LANE_RESULT", actor_ref, {"artifact_ref": obj.ref.as_dict()}, command_id)
        return IntakeRequest(cmd, (obj,), tuple(self.runtime.expected_events(obj, attempt, "STARTED", "RESULT_RECEIVED")), {sha(raw): raw}, scope)

    def result(self, *, actor_ref, evidence_ref, command_id=None):
        head = self.store.head()
        cut = self.runtime.cut(head, self.store.commits()[-1])
        evidence = self.store.resolve_accepted(evidence_ref, cut)
        e = evidence["body"]
        _, _, cut, assignment, attempt, claims, scope = self._context(e["assignment_ref"])
        binding = self.store.resolve_accepted(e["package_binding_ref"], cut)
        con = self.store._connect()
        try:
            reader = AdmissionRawReader(con, require_retained=True)
            package = self.runtime.raw(reader, binding["body"]["package_raw_ref"], "NF02_INPUT_PACKAGE_TRANSPORT_V2")
            semantic, _ = self.runtime.transport.package(package, {**claims, "result_slot_contract_refs": assignment["result_slot_contract_refs"]})
            raw = self.runtime.raw(reader, e["result_raw_ref"], "NF02_RESULT_TRANSPORT_V2")
            payload = parse(self.runtime.transport.result(raw, {**claims, "package_binding_ref": e["package_binding_ref"],
                            "result_slot_contract_ref": e["result_slot_contract_ref"], "input_package_digest": semantic}))
        finally:
            con.close()
        body = {"lane_result_id": "bdb_audit_lane_result_" + str(uuid4()), "admission_evidence_ref": copy(evidence_ref),
                "result_input_history_cut": cut, "result_payload": payload}
        obj = self.runtime.object("bdb_audit_lane_result", body, "2", body["lane_result_id"])
        cmd = self.command("ACCEPT_EXTERNAL_LANE_RESULT", actor_ref, {"artifact_ref": obj.ref.as_dict()}, command_id)
        return IntakeRequest(cmd, (obj,), tuple(self.runtime.expected_events(obj, attempt, "RESULT_RECEIVED", "RESULT_ACCEPTED")), {}, scope)

    def accept(self, request, signature):
        request = replace(request, command=SuccessorCommand(**request.command.body(), runtime=self.runtime),
                          objects=tuple(self.runtime.object(o.kind, o.body, o.version, o.logical_id, o.schema_revision_ref) for o in request.objects),
                          events=tuple(copy(list(request.events))), raw=dict(request.raw), scope=copy(request.scope))
        existing = self._existing(request, signature)
        if existing is not None:
            return existing
        try:
            return self.coordinator.accept(request.command, expected_head=request.command.expected_parent_head,
                                           immutable_objects=request.objects, ordered_events=request.events,
                                           raw_artifacts=request.raw, authentication=signature)
        except ValidationError as exc:
            if exc.code != "EXPECTED_HEAD_CONFLICT":
                raise
            existing = self._existing(request, signature)
            if existing is None:
                raise
            return existing

    def _existing(self, request, signature):
        """Operation retry resolves the original fact/receipt, never a new fact.

        This runs under the same independent lease and serialized writer lock.
        Direct Store submissions with a second body still reject as a conflict.
        """
        if not request.objects:
            return None  # STARTED retries use Store's exact command index.
        from ..history.store import AcceptanceResult
        from ..history.objects import AcceptedHead
        with self.runtime.lease(self.store.path) as leased:
            con = self.store._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                indexed = con.execute("SELECT command_digest FROM command_index WHERE command_id=?", (request.command.command_id,)).fetchone()
                if indexed:
                    if indexed[0] != request.command.digest:
                        raise ValidationError("ID_REUSE_CONFLICT")
                    return None  # Exact retry gets the independent Store checks.
                head = AcceptedHead(*con.execute("SELECT campaign_id,seq,commit_hash FROM accepted_head WHERE singleton=1").fetchone())
                records, events, commits = self.runtime.history(con, head)
                obj = request.objects[0]
                if len(request.objects) != 1 or request.command.command_payload != {"artifact_ref": obj.ref.as_dict()}:
                    raise ValidationError("NF02_SIGNED_ARTIFACT_BINDING_REQUIRED")
                from ..history.nf02_protocol import OPERATIONS
                if OPERATIONS.get(request.command.command_kind) != obj.kind or list(request.events) != self.runtime.expected_events(obj):
                    raise ValidationError("NF02_OPERATION_RETRY_CONFLICT")
                if any(type(raw) is not bytes or sha(raw) != digest for digest, raw in request.raw.items()):
                    raise ValidationError("NF02_BOUND_RAW_UNAVAILABLE_OR_CHANGED")
                expected_raw = {obj.body["package_raw_ref"]["raw_digest"]} if obj.kind == "assignment_package_binding" else (
                    {obj.body["result_raw_ref"]["raw_digest"]} if obj.kind == "lane_result_admission_evidence" else set())
                if set(request.raw) != expected_raw:
                    raise ValidationError("NF02_EXACT_RAW_PROPOSAL_REQUIRED")
                # A new request may resolve the original fact. It still cannot
                # supply an invented cut or contradict its signed parent.
                self.runtime.validate_input_cuts(request.objects, commits, request.command)
                cut_field = {"assignment_package_binding": "binding_input_history_cut", "lane_result_admission_evidence": "admission_input_history_cut",
                             "bdb_audit_lane_result": "result_input_history_cut"}[obj.kind]
                cut = obj.body[cut_field]
                if request.command.expected_parent_head != {"campaign_id": cut["campaign_id"], "commit_seq": cut["accepted_head_seq"], "commit_hash": cut["accepted_head_hash"]}:
                    raise ValidationError("NF02_CURRENT_CUT_OR_EVENT_BINDING_CONFLICT")
                if obj.kind == "bdb_audit_lane_result":
                    evidence = self.runtime.resolve(records, obj.body["admission_evidence_ref"])["object"]
                    assignment_ref = evidence.body["assignment_ref"]
                else:
                    assignment_ref = obj.body["assignment_ref"]
                if request.command.campaign_ref != head.campaign_id:
                    raise ValidationError("NF02_FOREIGN_CAMPAIGN")
                assignment, attempt, claims, scope = self.runtime.context(records, self.runtime.projected_events(events, records), assignment_ref, head.campaign_id)
                self.runtime.authority.authenticate(leased, request.command, signature, scope)
                matches = []
                for record in records.values():
                    old = record["object"]
                    if old.kind != obj.kind:
                        continue
                    if obj.kind == "bdb_audit_lane_result":
                        selected = eq_ref(old.body["admission_evidence_ref"], obj.body["admission_evidence_ref"])
                        identical = old.body["result_payload"] == obj.body["result_payload"]
                    else:
                        selected = eq_ref(old.body["assignment_ref"], assignment_ref)
                        if obj.kind == "assignment_package_binding":
                            identical = old.body["package_raw_ref"] == obj.body["package_raw_ref"]
                        else:
                            selected = selected and old.body["result_slot_contract_ref"] == obj.body["result_slot_contract_ref"]
                            identical = old.body["result_raw_ref"] == obj.body["result_raw_ref"] and eq_ref(old.body["package_binding_ref"], obj.body["package_binding_ref"])
                    if selected:
                        if not identical:
                            raise ValidationError("NF02_OPERATION_RETRY_CONFLICT")
                        self.runtime.retained(con, old)
                        matches.append(record)
                if not matches:
                    return None
                if len(matches) != 1:
                    raise ValidationError("NF02_RESULT_SLOT_CONFLICT")
                original = commits[matches[0]["seq"] - 1]
                receipt_row = con.execute("SELECT body FROM receipts WHERE command_digest=?", (original["command_digest"],)).fetchone()
                if receipt_row is None:
                    raise ValidationError("RECEIPT_MISSING_FOR_INDEX")
                receipt = self.runtime.receipt(json.loads(receipt_row[0]))
                return AcceptanceResult(self.runtime.commit(original), receipt, receipt.accepted_head, True)
            finally:
                con.close()

    def deliver(self, *, command, signature, sink):
        """Revalidate and release bound bytes with the SQLite writer lock held.

        sink must synchronously hand off bytes before returning; no mutable
        pathname or queued callback can become a later authorization source.
        Delivery diagnostics/ACK do not become canonical receipt authority.
        """
        command = SuccessorCommand(**command.body(), runtime=self.runtime)
        if command.command_kind != "DELIVER_BOUND_PACKAGE" or set(command.command_payload or {}) != {"package_binding_ref", "input_history_cut"}:
            raise ValidationError("NF02_DELIVERY_COMMAND_REQUIRED")
        with self.runtime.lease(self.store.path) as leased:
            con = self.store._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                from ..history.objects import AcceptedHead
                head = AcceptedHead(*con.execute("SELECT campaign_id,seq,commit_hash FROM accepted_head WHERE singleton=1").fetchone())
                records, events, commits = self.runtime.history(con, head)
                events = self.runtime.projected_events(events, records)
                cut = self.runtime.cut(head, commits[-1])
                if command.expected_parent_head != head.as_dict() or command.command_payload["input_history_cut"] != cut or command.campaign_ref != head.campaign_id:
                    raise ValidationError("NF02_STALE_DELIVERY_AUTHORIZATION")
                binding = self.runtime.resolve(records, command.command_payload["package_binding_ref"])
                assignment, attempt, claims, scope = self.runtime.context(records, events, binding["object"].body["assignment_ref"], head.campaign_id)
                self.runtime.authority.authenticate(leased, command, signature, scope)
                if self.runtime.state(events, "Attempt", attempt["attempt_id"], "CREATED") != "STARTED":
                    raise ValidationError("NF02_DELIVERY_REQUIRES_CURRENT_STARTED")
                starts = [c for c in commits if any(e.get("event_type") == "AttemptStarted" and eq_ref(e.get("attempt_ref"), assignment["attempt_ref"]) for e in c["ordered_event_bodies"])]
                if len(starts) != 1 or starts[0]["commit_seq"] <= binding["seq"]:
                    raise ValidationError("NF02_PRIOR_SEPARATE_STARTED_REQUIRED")
                raw = self.runtime.raw(AdmissionRawReader(con, require_retained=True), binding["object"].body["package_raw_ref"], "NF02_INPUT_PACKAGE_TRANSPORT_V2")
                self.runtime.transport.package(raw, {**claims, "result_slot_contract_refs": assignment["result_slot_contract_refs"]})
                self.runtime.authority.authenticate(leased, command, signature, scope)
                response = sink(raw, {"package_binding_ref": copy(binding["ref"]), "started_commit_ref": self.runtime.commit(starts[0]).as_object().ref.as_dict()})
                con.rollback()
                return response
            finally:
                con.close()

    def delivery_request(self, *, actor_ref, binding_ref, command_id=None):
        head = self.store.head()
        cut = self.runtime.cut(head, self.store.commits()[-1])
        return self.command("DELIVER_BOUND_PACKAGE", actor_ref, {"package_binding_ref": copy(binding_ref), "input_history_cut": cut}, command_id)

    def raw_ref(self, raw, profile):
        return {"raw_digest": sha(raw), "byte_length": len(raw), "media_type": "application/zip",
                "artifact_contract_ref": self.runtime.transport.pin(profile)}
