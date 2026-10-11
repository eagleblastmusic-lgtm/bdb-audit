"""Signed P0 command preparation through the existing Coordinator/Store."""
from dataclasses import dataclass

from ..coordinator import Coordinator
from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from ..history.limited_model import MODEL_ID, sha
from ..history.limited_wire import LimitedCommand, copy, identifier, value_body, sorted_refs
from ..history.raw_artifacts import AdmissionRawReader
from .limited_transport import fixed_zip


@dataclass(frozen=True)
class LimitedRequest:
    command: LimitedCommand
    objects: tuple
    events: tuple
    raw: dict

    def signing_bytes(self):
        return self.command.signing_bytes()


class LimitedIntake:
    def __init__(self, store):
        if not getattr(store._nf02, "limited", False):
            raise ValidationError("P0_INSTALLED_STORE_REQUIRED")
        self.store, self.runtime = store, store._nf02

    def snapshot(self):
        with self.runtime.lease(self.store.path):
            con = self.store._connect()
            try:
                con.execute("BEGIN")
                from ..history.objects import AcceptedHead
                row = con.execute("SELECT campaign_id,seq,commit_hash FROM accepted_head WHERE singleton=1").fetchone()
                head = AcceptedHead(*row) if row else None
                records, events, _ = self.runtime.history(con, head) if head else ({}, [], [])
                return head, records, events
            finally:
                con.close()

    def make(self, kind, fields, object_id=None):
        return self.runtime.object(kind, value_body(kind, fields, object_id))

    def prepare(self, operation, objects, *, actor_ref, grant_digest, raw=None, events=None, command_id=None):
        head, records, _ = self.snapshot()
        objects = tuple(objects)
        if events is None:
            events = [{"event_type": "P0FactAccepted", "artifact_ref": o.ref.as_dict()} for o in self.runtime.order(objects)]
        campaign_id = head.campaign_id if head else next(o.body["campaign_id"] for o in objects if o.kind == "campaign_genesis")
        command_id = command_id or identifier("command_envelope")
        b = value_body("command_envelope", {"command_id": command_id, "operation": operation, "actor_ref": actor_ref,
            "installation_digest": self.runtime.identity, "grant_digest": grant_digest,
            "namespace_authority_digest": self.runtime.root["namespace_authority_digest"], "mode": self.runtime.installation["mode"],
            "campaign_id": campaign_id, "expected_parent": head.as_dict() if head else "EMPTY_HISTORY",
            "policy_ref": self.runtime.pins["policy_revision"], "spec_ref": self.runtime.pins["spec_revision"],
            "schema_registry_ref": self.runtime.pins["schema_registry"], "proposed_object_refs": sorted_refs(o.ref.as_dict() for o in objects),
            "events": list(events), "basis_refs": self.runtime.basis(objects, list(events))}, command_id)
        return LimitedRequest(LimitedCommand(b, self.runtime), objects, tuple(copy(list(events))), dict(raw or {}))

    def initialize(self, *, source, genesis, actor_ref, grant_digest, raw, command_id=None):
        return self.prepare("INITIALIZE_P0_FROM_APPROVED_GIT", (*self.runtime.roots.values(), source, genesis),
                            actor_ref=actor_ref, grant_digest=grant_digest, raw=raw, command_id=command_id)

    def draft_assignment(self, *, auditor_certificate_sha256, attempt_id=None, assignment_id=None):
        head, records, events = self.snapshot()
        if not head or self.runtime.state_of(events) not in {"GENESIS", "ABORTED"}:
            raise ValidationError("P0_CREATE_STATE_CONFLICT")
        genesis = next(r["object"] for r in records.values() if r["object"].kind == "campaign_genesis")
        source = self.runtime.resolve(records, genesis.body["source_ref"])["object"]
        cut = self.runtime.cut_for(head, records)
        attempts = [r for r in records.values() if r["object"].kind == "attempt"]
        aborts = [r for r in records.values() if r["object"].kind == "nf02_p0_abort"]
        prior = max(attempts, key=lambda r: r["seq"])["ref"] if attempts else None
        abort = max(aborts, key=lambda r: r["seq"])["ref"] if aborts else None
        attempt = self.make("attempt", {"campaign_ref": genesis.ref.as_dict(), "source_ref": source.ref.as_dict(), "creation_cut": cut,
            "retry_of_attempt_ref": prior, "abort_basis_ref": abort, "auditor_certificate_sha256": auditor_certificate_sha256}, attempt_id)
        con = self.store._connect()
        try:
            reader = AdmissionRawReader(con, require_retained=True)
            manifest_raw = self.runtime.raw(reader, source.body["source_manifest_raw_ref"])
            _, members = self.runtime.transport.source(manifest_raw, self.runtime.raw(reader, source.body["source_archive_raw_ref"]), source.body)
            task = self.runtime.raw(reader, genesis.body["task_raw_ref"])
            inputs = self.runtime.transport.input_members(manifest_raw, members, task)
        finally:
            con.close()
        assignment = self.make("assignment_manifest", {"campaign_ref": genesis.ref.as_dict(), "source_ref": source.ref.as_dict(),
            "attempt_ref": attempt.ref.as_dict(), "assignment_cut": cut, "auditor_certificate_sha256": auditor_certificate_sha256,
            "task_raw_ref": genesis.body["task_raw_ref"], "input_members": self.runtime.transport.member_records(inputs),
            "result_slot_id": "EXTERNAL_AUDIT_RESULT", "package_profile_ref": self.runtime.corpus.pin("P0_PACKAGE_TRANSPORT_V1"),
            "result_profile_ref": self.runtime.corpus.pin("P0_RESULT_TRANSPORT_V1"), "isolation_profile_ref": self.runtime.corpus.pin("P0_EXECUTION_ISOLATION_V1")}, assignment_id)
        return attempt, assignment

    def package_bytes(self, assignment_ref):
        _, records, _ = self.snapshot()
        con = self.store._connect()
        try:
            a, _, _, members, scope = self.runtime.context(records, assignment_ref, AdmissionRawReader(con, require_retained=True))
            manifest = {"scope": scope, "assignment_cut": a["assignment_cut"], "members": self.runtime.transport.member_records(members)}
            return fixed_zip({"MANIFEST.json": canonical_bytes(manifest) + b"\n", **members})
        finally:
            con.close()

    def bind(self, *, actor_ref, grant_digest, assignment_ref, package_zip, object_id=None, command_id=None):
        head, records, _ = self.snapshot()
        obj = self.make("assignment_package_binding", {"assignment_ref": assignment_ref,
            "binding_cut": self.runtime.cut_for(head, records), "package_raw_ref": self.runtime.corpus.raw_ref(package_zip, "P0_PACKAGE_TRANSPORT_V1", "application/zip")}, object_id)
        return self.prepare("BIND_PACKAGE", [obj], actor_ref=actor_ref, grant_digest=grant_digest,
                            raw={sha(package_zip): package_zip}, command_id=command_id)

    def start(self, *, actor_ref, grant_digest, binding_ref, command_id=None):
        _, records, _ = self.snapshot()
        binding = self.runtime.resolve(records, binding_ref)["object"].body
        a = self.runtime.resolve(records, binding["assignment_ref"])["object"].body
        event = {"event_type": "P0AttemptStarted", "attempt_ref": a["attempt_ref"], "assignment_ref": binding["assignment_ref"], "binding_ref": binding_ref}
        return self.prepare("START_ATTEMPT", [], actor_ref=actor_ref, grant_digest=grant_digest, events=[event], command_id=command_id)

    def delivery(self, *, actor_ref, grant_digest, binding_ref, ack_bytes, ack_signature, object_id=None, command_id=None):
        head, records, _ = self.snapshot()
        binding = self.runtime.resolve(records, binding_ref)["object"].body
        from ..history.limited_model import strict_json
        ack = strict_json(ack_bytes)
        a = self.runtime.resolve(records, binding["assignment_ref"])["object"].body
        obj = self.make("nf02_p0_delivery", {"assignment_ref": binding["assignment_ref"], "binding_ref": binding_ref,
            "start_event": ack["start_event"], "delivery_cut": self.runtime.cut_for(head, records), "release_id": ack["release_id"],
            "ack_raw_ref": self.runtime.corpus.raw_ref(ack_bytes, "P0_AUTHORIZATION_V1", "application/json"),
            "ack_signature_raw_ref": self.runtime.corpus.raw_ref(ack_signature, "P0_AUTHORIZATION_V1", "application/pkcs7-signature"),
            "auditor_certificate_sha256": a["auditor_certificate_sha256"]}, object_id)
        return self.prepare("CONFIRM_DELIVERY", [obj], actor_ref=actor_ref, grant_digest=grant_digest,
                            raw={sha(ack_bytes): ack_bytes, sha(ack_signature): ack_signature}, command_id=command_id)

    def evidence(self, *, actor_ref, grant_digest, assignment_ref, binding_ref, delivery_ref, result_zip,
                 return_bytes, return_signature, object_id=None, command_id=None):
        head, records, _ = self.snapshot()
        a = self.runtime.resolve(records, assignment_ref)["object"].body
        obj = self.make("lane_result_admission_evidence", {"assignment_ref": assignment_ref, "binding_ref": binding_ref,
            "delivery_ref": delivery_ref, "admission_cut": self.runtime.cut_for(head, records), "result_slot_id": "EXTERNAL_AUDIT_RESULT",
            "result_raw_ref": self.runtime.corpus.raw_ref(result_zip, "P0_RESULT_TRANSPORT_V1", "application/zip"),
            "return_raw_ref": self.runtime.corpus.raw_ref(return_bytes, "P0_AUTHORIZATION_V1", "application/json"),
            "return_signature_raw_ref": self.runtime.corpus.raw_ref(return_signature, "P0_AUTHORIZATION_V1", "application/pkcs7-signature"),
            "auditor_certificate_sha256": a["auditor_certificate_sha256"]}, object_id)
        return self.prepare("INGEST_EVIDENCE", [obj], actor_ref=actor_ref, grant_digest=grant_digest,
                            raw={sha(v): v for v in (result_zip, return_bytes, return_signature)}, command_id=command_id)

    def result(self, *, actor_ref, grant_digest, admission_ref, object_id=None, command_id=None):
        head, records, _ = self.snapshot()
        e = self.runtime.resolve(records, admission_ref)["object"].body
        con = self.store._connect()
        try:
            reader = AdmissionRawReader(con, require_retained=True)
            _, _, manifest, _, scope = self.runtime.context(records, e["assignment_ref"], reader)
            binding = self.runtime.resolve(records, e["binding_ref"])["object"].body
            payload = self.runtime.transport.result(self.runtime.raw(reader, e["result_raw_ref"]), {"scope": scope,
                "binding_ref": e["binding_ref"], "delivery_ref": e["delivery_ref"], "package_raw_ref": binding["package_raw_ref"]}, manifest)
        finally:
            con.close()
        obj = self.make("bdb_audit_lane_result", {"admission_ref": admission_ref, "result_cut": self.runtime.cut_for(head, records), "result_payload": payload}, object_id)
        return self.prepare("ACCEPT_RESULT", [obj], actor_ref=actor_ref, grant_digest=grant_digest, command_id=command_id)

    def abort(self, *, actor_ref, grant_digest, assignment_ref, reason, object_id=None, command_id=None):
        head, records, events = self.snapshot()
        a = self.runtime.resolve(records, assignment_ref)["object"].body
        obj = self.make("nf02_p0_abort", {"attempt_ref": a["attempt_ref"], "assignment_ref": assignment_ref,
            "abort_cut": self.runtime.cut_for(head, records), "from_state": self.runtime.state_of(events), "reason": reason}, object_id)
        return self.prepare("ABORT_ATTEMPT", [obj], actor_ref=actor_ref, grant_digest=grant_digest, command_id=command_id)

    def release_job(self, *, binding_ref, grant_digest):
        head, records, events = self.snapshot()
        con = self.store._connect()
        try:
            return self.runtime.release_job(con, head, records, events, binding_ref, grant_digest)[0]
        finally:
            con.close()

    def accept(self, request, authentication):
        return Coordinator(self.store).accept(request.command, immutable_objects=request.objects, ordered_events=request.events,
                                               raw_artifacts=request.raw, authentication=authentication)
