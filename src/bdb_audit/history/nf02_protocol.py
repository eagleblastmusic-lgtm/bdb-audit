"""Inactive-until-installed §192 protocol over the existing transactional Store.

Prepared schemas, a local successful test, and a serialized actor name never
activate this adapter. The production entry point reads MachineAuthority only.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..core.registry import ContractRegistry, canonical_reference_set
from ..schemas.binding import SchemaBindings
from ..workflow.nf02_transport import NF02Transport, ASSIGNMENT_CLAIMS
from .installation_authority import MachineAuthority, sha
from .objects import AcceptedHead
from .raw_artifacts import AdmissionRawReader
from .successor_wire import (SuccessorObject, SuccessorRef, SuccessorCommand,
                             SuccessorCommit, SuccessorReceipt, copy, eq_ref)

FACTS = {"assignment_package_binding": "1", "lane_result_admission_evidence": "2", "bdb_audit_lane_result": "2"}
OPERATIONS = {"BIND_ASSIGNMENT_PACKAGE": "assignment_package_binding",
              "START_ATTEMPT": None, "INGEST_EXTERNAL_LANE_RESULT": "lane_result_admission_evidence",
              "ACCEPT_EXTERNAL_LANE_RESULT": "bdb_audit_lane_result"}
PROFILE_NAMES = ("NF02_INPUT_PACKAGE_TRANSPORT_V2", "NF02_RESULT_TRANSPORT_V2", "NF02_PACKAGE_SEMANTIC_PROFILE_V1",
                 "NF02_RESULT_NORMALIZER_V2", "NF02_EXTERNAL_LANE_SLOT_V2", "NF02_PROTOCOL_PROFILE_V2")


class InstalledContractRegistry(ContractRegistry):
    def __init__(self, raw, expected_digest):
        if sha(raw) != expected_digest:
            raise ValidationError("REGISTRY_PIN_MISMATCH")
        self._raw, self._doc = raw, parse(raw)
        self._contracts = {(r["kind"], r["version"]): r for r in self._doc["contracts"]}
        self._extension_contracts = {}
        if len(self._contracts) != len(self._doc["contracts"]):
            raise ValidationError("DUPLICATE_CONTRACT_KIND")
        self.validate_definition(self._doc)
        for kind, version in FACTS.items():
            row = self.contract(kind, version)
            if row["producer_authority"] != "TRUSTED_COORDINATOR_ACCEPTANCE" or row["reference_contract_mode"] != "EXPLICIT_COMPLETE":
                raise ValidationError("NF02_SUCCESSOR_CONTRACT_REQUIRED")

    def register_extension_contract(self, contract_entry):
        raise ValidationError("NF02_RUNTIME_EXTENSION_FORBIDDEN")

    def target(self, kind):
        if kind not in self._doc["reference_target_classes"] and not any(k == kind for k, _ in self._contracts):
            raise ValidationError("UNRESOLVED_REFERENCE_TARGET", str(kind))
        return kind


def values_at(body, path):
    values = [body]
    for segment in path.split("."):
        array = segment.endswith("[]")
        key = segment[:-2] if array else segment
        next_values: list[Any] = []
        for value in values:
            if not isinstance(value, dict) or key not in value:
                continue
            child = value[key]
            next_values.extend(child if array or isinstance(child, list) else [child])
        values = next_values
    return values


class NF02Protocol:
    def __init__(self, authority, leased):
        self.authority = authority
        self.identity = leased["identity"]
        installation, files = leased["installation"], leased["files"]
        self.installation = copy(installation)
        self.files = dict(files)
        self.bundle = parse(files[installation["pin_bundle"]])
        base = str(Path(installation["pin_bundle"]).parent).replace("\\", "/")
        self.base = base
        manifest = parse(files[installation["candidate_manifest"]])
        for category in ("normative", "machine"):
            entries = manifest[category + "_candidate_files"]
            if len({e["file"] for e in entries}) != len(entries):
                raise ValidationError("NF02_CANDIDATE_DUPLICATE")
            for entry in entries:
                raw = files[base + "/" + entry["file"]]
                if {"file": entry["file"], "bytes": len(raw), "sha256": sha(raw)} != {k: entry[k] for k in ("file", "bytes", "sha256")}:
                    raise ValidationError("NF02_CANDIDATE_READBACK_MISMATCH", entry["file"])
            preimage = sorted([{k: e[k] for k in ("file", "bytes", "sha256")} for e in entries], key=lambda e: e["file"])
            if sha(canonical_bytes(preimage)) != manifest[category + "_candidate_set_sha256"]:
                raise ValidationError("NF02_CANDIDATE_SET_MISMATCH")
        registry_raw = files[base + "/BDB_AUDIT_V2_ARTIFACT_CONTRACT_REGISTRY_R5_4.json"]
        self.registry = InstalledContractRegistry(registry_raw, sha(registry_raw))
        schema_record = parse(files[base + "/objects/schema_registry__2.json"])
        self.schema_registry = schema_record
        external = self.bundle["external_schema_root"]
        external_raw = files[base + "/" + external["file"]]
        if len(external_raw) != external["byte_length"] or sha(external_raw) != external["raw_digest"]:
            raise ValidationError("NF02_EXTERNAL_SCHEMA_ROOT_MISMATCH")
        root_bindings = SchemaBindings([("schema_registry", "2", external_raw, external["raw_digest"])], self.registry)
        root_bindings.validate_schema("schema_registry", canonical_bytes(schema_record["body"]), "2")
        bindings = []
        raw_by_digest = {sha(raw): raw for raw in files.values()}
        for binding in schema_record["body"]["bindings"]:
            key, ref = binding["schema_key"], binding["schema_raw_ref"]
            if binding["status"] != "ACTIVE" or key != parse(raw_by_digest[ref["raw_digest"]])["$id"]:
                raise ValidationError("NF02_SCHEMA_BINDING_MISMATCH")
            kind, version = key.removeprefix("BDB_SCHEMA_REGISTRY::").split("/")
            raw = raw_by_digest[ref["raw_digest"]]
            if len(raw) != ref["byte_length"] or ref["media_type"] != "application/schema+json":
                raise ValidationError("NF02_SCHEMA_BINDING_MISMATCH")
            bindings.append((kind, version, raw, ref["raw_digest"]))
        keys = [b["schema_key"] for b in schema_record["body"]["bindings"]]
        if keys != sorted(set(keys), key=lambda k: k.encode("utf-8")):
            raise ValidationError("NF02_SCHEMA_BINDING_ORDER")
        self.schemas = SchemaBindings(bindings, self.registry)
        for key in self.bundle["bootstrap_executable_schema_keys"]:
            self.schemas.require_bound(key)
        self.schema_documents = {key: parse(raw) for key, (raw, _) in self.schemas._bindings.items()}
        self.installed_objects = {}
        for name in ("artifact_contract_registry__1", "policy_revision__1", "spec_revision__1", "trust_profile__1", "installation_bootstrap_profile__1", "schema_registry__2"):
            value = parse(files[base + "/objects/" + name + ".json"])
            obj = self.object(value["kind"], value["body"], value["version"], value["ref"].get("logical_id"))
            if obj.ref.as_dict() != value["ref"]:
                raise ValidationError("NF02_INITIAL_OBJECT_PIN_MISMATCH")
            self.installed_objects[obj.digest] = obj
        installation_body = self.installed_objects[self.bundle["installation_bootstrap_profile_ref"]["revision_digest"]].body
        if any(installation_body[pin] != ref for pin, ref in self.bundle["initial_pins"].items()):
            raise ValidationError("NF02_INITIAL_PROFILE_PIN_MISMATCH")
        registry_obj = self.object("schema_registry", schema_record["body"], version="2", logical_id=schema_record["ref"].get("logical_id"))
        if registry_obj.ref.as_dict() != schema_record["ref"] or registry_obj.ref.as_dict() != self.bundle["initial_pins"]["initial_schema_registry_ref"]:
            raise ValidationError("NF02_SCHEMA_REGISTRY_PIN_MISMATCH")
        self.transport = NF02Transport({name: files[base + "/profiles/" + name + ".json"] for name in PROFILE_NAMES},
                                       {name: files[base + "/schemas/" + name + ".schema.json"] for name in PROFILE_NAMES[:2]})
        protocol = self.transport.profile("NF02_PROTOCOL_PROFILE_V2")
        for field, name in (("input_transport_ref", PROFILE_NAMES[0]), ("result_transport_ref", PROFILE_NAMES[1]),
                            ("package_semantic_profile_ref", PROFILE_NAMES[2]), ("normalizer_ref", PROFILE_NAMES[3]), ("result_slot_ref", PROFILE_NAMES[4])):
            if protocol[field] != self.transport.pin(name):
                raise ValidationError("NF02_PROFILE_DEPENDENCY_MISMATCH")

    @classmethod
    def installed(cls):
        authority = MachineAuthority()
        with authority.lease() as leased:
            return cls(authority, leased)

    @contextmanager
    def lease(self, path=None):
        with self.authority.lease() as leased:
            if leased["identity"] != self.identity:
                raise ValidationError("NF02_INSTALLATION_CHANGED_REOPEN_REQUIRED")
            if path is None:
                yield leased
            else:
                with self.authority.storage_lease(path):
                    yield leased

    def schema_ref(self, kind, version="1"):
        key = self.registry.contract(kind, version)["schema_ref"]
        return {"kind": "schema", "revision_digest": self.schemas.require_bound(key)[1]}

    def object(self, kind, body, version="1", logical_id=None, schema_ref=None):
        return SuccessorObject(kind, body, schema_ref or "", logical_id, version, self)

    def object_from_row(self, row):
        schema = parse(row[2]) if isinstance(row[2], bytes) else row[2]
        return self.object(row[0], json.loads(row[4]), row[1], row[3], schema)

    def ref(self, value, *, ref_class="CONTENT_OR_PRIOR"):
        return SuccessorRef.from_dict(value, ref_class=ref_class)

    def object_refs(self, obj, classes):
        key = self.registry.contract(obj.kind, obj.version)["schema_ref"]
        for spec in self.schema_documents[key]["x-bdb-material-refs"]:
            if spec["ref_class"] not in classes:
                continue
            for value in values_at(obj.body, spec["field"]):
                if isinstance(value, dict) and "schema_revision_ref" in value:
                    yield self.ref(value, ref_class=spec["ref_class"])

    def commit(self, body):
        return SuccessorCommit(body["campaign_id"], body["commit_seq"], body["prev_history_ref"], self.ref(body["command_ref"], ref_class="CONTENT_OBJECT"),
                               body["command_digest"], body["actor_ref"], body["expected_parent_head"], body["governing_policy_ref"],
                               tuple(body["governing_spec_refs"]), tuple(body["ordered_event_bodies"]),
                               tuple(self.ref(ref, ref_class="CONTENT_OBJECT") for ref in body["immutable_object_refs"]), self)

    def receipt(self, body):
        return SuccessorReceipt(body["command_id"], self.ref(body["command_ref"], ref_class="CONTENT_OBJECT"),
                                tuple(self.ref(ref, ref_class="CONTENT_OBJECT") for ref in body["result_object_refs"]), body["accepted_commit_ref"],
                                AcceptedHead.from_dict(body["accepted_head"]), runtime=self)

    def cut(self, current, prior):
        return {"campaign_id": current.campaign_id, "accepted_head_seq": current.commit_seq,
                "accepted_head_hash": current.commit_hash, "governing_policy_ref": copy(prior["governing_policy_ref"]),
                "governing_spec_refs": copy(prior["governing_spec_refs"])}

    def history(self, con, current):
        records: dict[str, Any] = {}
        events: list[Any] = []
        commits: list[Any] = []
        parent: Any = "EMPTY_HISTORY"
        for seq, digest, raw in con.execute("SELECT seq,commit_hash,body FROM commits ORDER BY seq"):
            body = json.loads(raw)
            commit = self.commit(body)
            if seq != len(commits) + 1 or commit.digest != digest or commit.prev_history_ref != parent or body["campaign_id"] != current.campaign_id:
                raise ValidationError("ACCEPTED_HISTORY_INTEGRITY_FAILURE")
            for ref in body["immutable_object_refs"]:
                row = con.execute("SELECT kind,version,schema_ref,logical_id,body FROM immutable_objects WHERE digest=?", (ref["revision_digest"],)).fetchone()
                if row is None:
                    raise ValidationError("ACCEPTED_HISTORY_INTEGRITY_FAILURE")
                obj = self.object_from_row(row)
                if not eq_ref(obj.ref.as_dict(), ref):
                    raise ValidationError("ACCEPTED_HISTORY_INTEGRITY_FAILURE")
                records.setdefault(obj.digest, {"object": obj, "seq": seq, "ref": ref})
            if body["command_digest"] not in records or records[body["command_digest"]]["object"].body["expected_parent_head"] != parent:
                raise ValidationError("COMMAND_BINDING_CONFLICT")
            command_body = records[body["command_digest"]]["object"].body
            if (body["command_ref"] != records[body["command_digest"]]["ref"]
                    or any(command_body[field] != body[field] for field in ("actor_ref", "governing_policy_ref", "governing_spec_refs"))):
                raise ValidationError("COMMAND_BINDING_CONFLICT")
            self.projected_events(events + body["ordered_event_bodies"], records)
            parent = {"campaign_id": current.campaign_id, "commit_seq": seq, "commit_hash": digest}
            events.extend(body["ordered_event_bodies"])
            commits.append(body)
        if current and (not commits or parent != current.as_dict()):
            raise ValidationError("ACCEPTED_HISTORY_INTEGRITY_FAILURE")
        return records, events, commits

    def resolve(self, records, ref):
        typed = self.ref(ref)
        record = records.get(typed.revision_digest)
        if record is None or not eq_ref(ref, record["ref"]):
            raise ValidationError("OBJECT_NOT_ACCEPTED_AT_CUT")
        return record

    @staticmethod
    def state(events, aggregate, identifier, default):
        state = default
        for event in events:
            if str(event.get("aggregate", "")).lower() == aggregate.lower() and event.get("aggregate_id", event.get("id")) == identifier:
                if event.get("from_state") != state:
                    raise ValidationError("NF02_HISTORY_TRANSITION_CONFLICT")
                state = event.get("to_state")
        return state

    def context(self, records, events, assignment_ref, campaign_id):
        record = self.resolve(records, assignment_ref)
        assignment = record["object"].body
        attempt = self.resolve(records, assignment["attempt_ref"])["object"].body
        lane = self.resolve(records, attempt["lane_run_ref"])["object"].body
        stage = self.resolve(records, lane["stage_run_ref"])["object"].body
        if stage["campaign_ref"] != campaign_id:
            raise ValidationError("NF02_FOREIGN_CAMPAIGN")
        for left, right in ((assignment["source_generation_ref"], lane["source_generation_ref"]),
                            (assignment["source_generation_ref"], stage["source_generation_ref"]),
                            (assignment["executor_profile_ref"], attempt["executor_profile_ref"]),
                            (assignment["delivery_profile_ref"], attempt["delivery_profile_ref"]),
                            (assignment["lane_spec_ref"], lane["lane_spec_ref"]),
                            (assignment["stage_spec_ref"], stage["stage_spec_ref"])):
            if not eq_ref(left, right):
                raise ValidationError("NF02_ASSIGNMENT_CONTEXT_CONFLICT")
        for field in ("source_generation_ref", "executor_profile_ref", "delivery_profile_ref", "lane_spec_ref", "stage_spec_ref"):
            self.resolve(records, assignment[field])
        slots = assignment["result_slot_contract_refs"]
        if not slots or any(slot not in attempt["result_slot_contracts"] or slot not in lane["required_result_slots"] for slot in slots):
            raise ValidationError("NF02_UNDECLARED_RESULT_SLOT")
        knowledge = self.resolve(records, assignment["knowledge_state_ref"])["object"].body
        if not eq_ref(knowledge["attempt_ref"], assignment["attempt_ref"]):
            raise ValidationError("NF02_KNOWLEDGE_ATTEMPT_CONFLICT")
        isolation = self.resolve(records, knowledge["isolation_qualification_ref"])["object"].body
        lane_spec = self.resolve(records, assignment["lane_spec_ref"])["object"].body
        required_isolation = lane_spec["required_isolation_assurance"]
        if (required_isolation not in {"ENFORCED", "DECLARED"} or isolation.get("result") != required_isolation
                or not eq_ref(isolation["attempt_ref"], assignment["attempt_ref"])
                or not eq_ref(isolation["executor_profile_ref"], assignment["executor_profile_ref"])
                or not eq_ref(isolation["delivery_profile_ref"], assignment["delivery_profile_ref"])
                or isolation["required_isolation_assurance"] != lane_spec["required_isolation_assurance"]):
            raise ValidationError("NF02_ISOLATION_PREREQUISITE_UNMET")
        if required_isolation == "ENFORCED" and any(not isolation[field] for field in (
                "enforcement_receipt_refs", "filesystem_boundary_evidence_refs", "network_boundary_evidence_refs",
                "tool_boundary_evidence_refs", "session_boundary_evidence_refs")):
            raise ValidationError("NF02_ENFORCEMENT_EVIDENCE_REQUIRED")
        if not assignment["grant_refs"] or not assignment["view_manifest_refs"]:
            raise ValidationError("NF02_GRANT_VIEW_PREREQUISITE_UNMET")
        granted_views = []
        grants = {}
        for ref in assignment["grant_refs"]:
            grant = self.resolve(records, ref)["object"].body
            if not eq_ref(grant["attempt_ref"], assignment["attempt_ref"]) or not eq_ref(grant["delivery_profile_ref"], assignment["delivery_profile_ref"]):
                raise ValidationError("NF02_GRANT_CONTEXT_CONFLICT")
            granted_views.append(grant["view_manifest_ref"])
            grants[ref["revision_digest"]] = grant
        for ref in assignment["view_manifest_refs"]:
            self.resolve(records, ref)
            if ref not in granted_views or ref not in knowledge["allowed_view_refs"]:
                raise ValidationError("NF02_VIEW_NOT_GRANTED")
        exposures = []
        for ref in knowledge["potential_exposure_refs"]:
            exposure = self.resolve(records, ref)["object"].body
            grant = grants.get(exposure["grant_ref"]["revision_digest"])
            if (grant is None or not eq_ref(exposure["attempt_ref"], assignment["attempt_ref"])
                    or not eq_ref(exposure["view_manifest_ref"], grant["view_manifest_ref"])
                    or exposure["channel_class"] != grant["channel_class"]):
                raise ValidationError("NF02_EXPOSURE_GRANT_CONTEXT_CONFLICT")
            exposures.append(exposure["grant_ref"])
        if any(ref not in exposures for ref in assignment["grant_refs"]):
            raise ValidationError("NF02_POTENTIAL_EXPOSURE_MISSING")
        for ref in knowledge["contamination_assessment_refs"] + isolation["contamination_assessment_refs"]:
            assessment = self.resolve(records, ref)["object"].body
            if not eq_ref(assessment["attempt_ref"], assignment["attempt_ref"]) or assessment["result"] != "CLEAN":
                raise ValidationError("NF02_CONTAMINATION_PREREQUISITE_UNMET")
        for field in ("enforcement_receipt_refs", "filesystem_boundary_evidence_refs", "network_boundary_evidence_refs", "tool_boundary_evidence_refs", "session_boundary_evidence_refs"):
            for ref in isolation[field]:
                self.resolve(records, ref)
        source = self.resolve(records, assignment["source_generation_ref"])["object"].body
        identity = self.resolve(records, source["source_identity_ref"])["object"].body
        if (identity["profile_ref"] != source["source_identity_profile_ref"]
                or identity["materialized_source_manifest_ref"] != source["materialized_source_manifest_ref"]
                or identity["completeness_state"] != "COMPLETE_SOURCE"
                or identity["authorized_repository_or_snapshot_ref"] != source.get("repository_authority_ref", source.get("snapshot_authority_ref"))):
            raise ValidationError("NF02_SOURCE_IDENTITY_CONTEXT_CONFLICT")
        if identity["authority_mode"] == "AUTHORIZED_GIT" and (
                not identity.get("git_commit_object_id") or not identity.get("git_tree_object_id")
                or identity["git_commit_object_id"] == identity["git_tree_object_id"]):
            raise ValidationError("NF02_SOURCE_COMMIT_TREE_CONFLICT")
        for aggregate, identifier in (("Lane", lane["lane_run_id"]), ("Stage", stage["stage_run_id"])):
            if self.state(events, aggregate, identifier, "PLANNED") not in {"RUNNING", "WAITING_RESULT", "WAITING_FOR_REQUIRED_INPUT"}:
                raise ValidationError("NF02_PARENT_RUN_NOT_ACTIVE")
        if self.state(events, "Campaign", campaign_id, "CREATED") != "AUDIT_RUNNING":
            raise ValidationError("NF02_CAMPAIGN_NOT_ACTIVE")
        claims = {key: copy(assignment[key]) for key in ASSIGNMENT_CLAIMS - {"assignment_ref"}}
        claims["assignment_ref"] = copy(assignment_ref)
        scope = {"assignment_ref": copy(assignment_ref), "result_slot_contract_refs": copy(slots)}
        return assignment, attempt, claims, scope

    def binding(self, records, assignment_ref):
        found = [r for r in records.values() if r["object"].kind == "assignment_package_binding" and eq_ref(r["object"].body["assignment_ref"], assignment_ref)]
        if len(found) != 1:
            raise ValidationError("NF02_UNIQUE_PRIOR_BINDING_REQUIRED")
        return found[0]

    def raw(self, reader, ref, name):
        if (set(ref) != {"raw_digest", "byte_length", "media_type", "artifact_contract_ref"}
                or ref["artifact_contract_ref"] != self.transport.pin(name) or ref["media_type"] != "application/zip"
                or type(ref["byte_length"]) is not int or ref["byte_length"] <= 0):
            raise ValidationError("NF02_EXACT_RAW_REF_REQUIRED")
        raw = reader.read_bytes(ref["raw_digest"])
        if len(raw) != ref["byte_length"]:
            raise ValidationError("NF02_BOUND_RAW_UNAVAILABLE_OR_CHANGED")
        return raw

    def expected_events(self, obj, attempt=None, start=None, end=None):
        return [{"event_type": "ArtifactAccepted", "artifact_ref": obj.ref.as_dict()}]

    def projected_events(self, events, records):
        """Derive FSM effects from exact accepted events. Never runtime authority."""
        out = []
        names = {"CAMPAIGN": ("Campaign", "campaign_id"), "STAGE_RUN": ("Stage", "stage_run_id"),
                 "LANE_RUN": ("Lane", "lane_run_id"), "ATTEMPT": ("Attempt", "attempt_id")}
        for event in events:
            kind = event.get("event_type")
            fields = {"CampaignGenesisAccepted": {"event_type", "artifact_ref"},
                      "ArtifactAccepted": {"event_type", "artifact_ref"},
                      "StateTransitionAccepted": {"event_type", "aggregate_kind", "aggregate_ref", "from_state", "to_state", "basis_refs"},
                      "AttemptStarted": {"event_type", "attempt_ref", "assignment_ref", "package_binding_ref"}}
            if kind not in fields or set(event) != fields[kind]:
                raise ValidationError("NF02_CLOSED_EVENT_REQUIRED")
            if kind == "CampaignGenesisAccepted":
                obj = self.resolve(records, event["artifact_ref"])["object"]
                if obj.kind != "campaign_genesis":
                    raise ValidationError("NF02_EVENT_TARGET_CONFLICT")
                out.append({"aggregate": "Campaign", "aggregate_id": obj.body["campaign_id"], "from_state": "CREATED", "to_state": "GENESIS_ACCEPTED"})
            elif kind == "StateTransitionAccepted":
                if event["aggregate_kind"] not in names or event["aggregate_kind"] == "ATTEMPT" or not event["basis_refs"]:
                    raise ValidationError("NF02_SEPARATE_STARTED_COMMAND_REQUIRED")
                for ref in event["basis_refs"]:
                    self.resolve(records, ref)
                name, id_field = names[event["aggregate_kind"]]
                obj = self.resolve(records, event["aggregate_ref"])["object"]
                if obj.kind != {"CAMPAIGN": "campaign_genesis", "STAGE_RUN": "stage_run", "LANE_RUN": "lane_run"}[event["aggregate_kind"]]:
                    raise ValidationError("NF02_EVENT_TARGET_CONFLICT")
                out.append({"aggregate": name, "aggregate_id": obj.body[id_field], "from_state": event["from_state"], "to_state": event["to_state"]})
            elif kind == "AttemptStarted":
                attempt = self.resolve(records, event["attempt_ref"])["object"].body
                assignment = self.resolve(records, event["assignment_ref"])["object"].body
                binding = self.resolve(records, event["package_binding_ref"])["object"].body
                if assignment["attempt_ref"] != event["attempt_ref"] or binding["assignment_ref"] != event["assignment_ref"]:
                    raise ValidationError("NF02_EVENT_TARGET_CONFLICT")
                out.append({"aggregate": "Attempt", "aggregate_id": attempt["attempt_id"], "from_state": "CREATED", "to_state": "STARTED"})
            elif kind == "ArtifactAccepted":
                obj = self.resolve(records, event["artifact_ref"])["object"]
                if obj.kind == "lane_result_admission_evidence":
                    assignment = self.resolve(records, obj.body["assignment_ref"])["object"].body
                    attempt = self.resolve(records, assignment["attempt_ref"])["object"].body
                    out.append({"aggregate": "Attempt", "aggregate_id": attempt["attempt_id"], "from_state": "STARTED", "to_state": "RESULT_RECEIVED"})
                elif obj.kind == "bdb_audit_lane_result":
                    evidence = self.resolve(records, obj.body["admission_evidence_ref"])["object"].body
                    assignment = self.resolve(records, evidence["assignment_ref"])["object"].body
                    attempt = self.resolve(records, assignment["attempt_ref"])["object"].body
                    out.append({"aggregate": "Attempt", "aggregate_id": attempt["attempt_id"], "from_state": "RESULT_RECEIVED", "to_state": "RESULT_ACCEPTED"})
        from ..orchestration.fsm import project_states
        project_states(out)
        return out

    def validate(self, *, con, current, command, objects, events, raw_artifacts, leased, authentication, retry=False):
        records, prior_events, commits = self.history(con, current) if current else ({}, [], [])
        prior_wire_events = prior_events
        prior_events = self.projected_events(prior_events, records)
        domain = [obj for obj in objects if obj.kind != "command_envelope"]
        if sum(obj.kind == "command_envelope" for obj in objects) != 1:
            raise ValidationError("NF02_EXACT_COMMAND_CLOSURE_REQUIRED")
        if any(type(raw) is not bytes or sha(raw) != digest for digest, raw in raw_artifacts.items()):
            raise ValidationError("NF02_BOUND_RAW_UNAVAILABLE_OR_CHANGED")
        expected_parent = current.as_dict() if current else "EMPTY_HISTORY"
        if retry:
            original = next((c for c in commits if c["command_digest"] == command.digest), None)
            if original is None or [o.ref.as_dict() for o in objects] != [records[r["revision_digest"]]["ref"] for r in original["immutable_object_refs"]]:
                # Closure canonical order need not equal caller input order.
                if original is None or {o.digest for o in objects} != {r["revision_digest"] for r in original["immutable_object_refs"]}:
                    raise ValidationError("ID_REUSE_CONFLICT")
            if events != original["ordered_event_bodies"]:
                raise ValidationError("ID_REUSE_CONFLICT")
        elif command.expected_parent_head != expected_parent:
            raise ValidationError("EXPECTED_HEAD_CONFLICT")
        campaign_id = command.campaign_ref or command.proposed_campaign_id
        if current and campaign_id != current.campaign_id:
            raise ValidationError("NF02_FOREIGN_CAMPAIGN")
        reader = AdmissionRawReader(con, proposed=raw_artifacts, allow_staged=False)
        if command.command_kind in {"INITIALIZE_CAMPAIGN_FROM_LEGACY", "PREPARE_NF02_E1_CONTEXT"}:
            purpose = "BOOTSTRAP" if current is None else "E1_CONTEXT"
            self.authority.authenticate(leased, command, authentication, {"campaign_id": campaign_id, "purpose": purpose})
            packet = {"command": command.body(), "objects": [o.record() for o in domain], "events": events,
                      "raw": sorted(raw_artifacts)}
            table = "bootstrap_packets" if purpose == "BOOTSTRAP" else "context_packets"
            if sha(canonical_bytes(packet)) not in leased["installation"][table].get(campaign_id, []):
                raise ValidationError("NF02_INDEPENDENT_CONTEXT_ADMISSION_REQUIRED")
            if purpose == "BOOTSTRAP":
                if command.command_kind != "INITIALIZE_CAMPAIGN_FROM_LEGACY" or current:
                    raise ValidationError("INITIALIZATION_ALREADY_COMPLETED")
                genesis = [o for o in domain if o.kind == "campaign_genesis"]
                if len(genesis) != 1 or genesis[0].body["schema_set_ref"] != self.bundle["initial_pins"]["initial_schema_registry_ref"]:
                    raise ValidationError("NF02_GENESIS_SCHEMA_CONTEXT_CONFLICT")
                if command.bootstrap_profile_ref != self.bundle["installation_bootstrap_profile_ref"] or command.history_namespace_ref != self.bundle["initial_pins"]["allowed_history_namespace_ref"]:
                    raise ValidationError("NF02_GENESIS_INSTALLATION_CONTEXT_CONFLICT")
                installed_spec = next(obj for obj in self.installed_objects.values() if obj.kind == "spec_revision")
                if (command.governing_policy_ref != self.bundle["initial_pins"]["initial_governing_policy_ref"]
                        or list(command.governing_spec_refs) != [installed_spec.ref.as_dict()]):
                    raise ValidationError("NF02_GENESIS_INSTALLATION_CONTEXT_CONFLICT")
            else:
                if (any(o.kind in FACTS for o in domain) or any(e.get("event_type") in {"AttemptStarted", "CampaignGenesisAccepted"} for e in events)
                        or any(e.get("to_state") in {"STARTED", "RESULT_RECEIVED", "RESULT_ACCEPTED", "COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED", "CLOSED", "CAMPAIGN_CONCLUDED"} for e in events)):
                    raise ValidationError("NF02_CONTEXT_CANNOT_ADMIT_EXECUTION")
            for digest in raw_artifacts:
                reader.read_bytes(digest)
            self.validate_references(objects, records, current, command)
            self.validate_input_cuts(objects, commits, command)
            tentative = dict(records)
            tentative.update({obj.digest: {"object": obj, "seq": current.commit_seq + 1 if current else 1,
                                          "ref": obj.ref.as_dict()} for obj in objects})
            self.projected_events(prior_wire_events + events, tentative)
            return reader.verified, {"campaign_id": campaign_id, "purpose": purpose}
        if not current or command.command_kind not in OPERATIONS:
            raise ValidationError("NF02_OPERATION_NOT_AUTHORIZED")
        genesis = [r["object"] for r in records.values() if r["object"].kind == "campaign_genesis"]
        if len(genesis) != 1 or genesis[0].body["schema_set_ref"] != self.bundle["initial_pins"]["initial_schema_registry_ref"]:
            raise ValidationError("NF02_NEW_CAMPAIGN_REQUIRED")
        if command.governing_policy_ref != commits[-1]["governing_policy_ref"] or list(command.governing_spec_refs) != commits[-1]["governing_spec_refs"]:
            raise ValidationError("SEMANTIC_CONTEXT_NOT_EFFECTIVE_AT_INPUT_HISTORY")
        if command.command_kind == "START_ATTEMPT":
            if domain or set(command.command_payload or {}) != {"package_binding_ref", "input_history_cut"}:
                raise ValidationError("NF02_SEPARATE_STARTED_COMMAND_REQUIRED")
            b = self.resolve(records, command.command_payload["package_binding_ref"])
            assignment_ref = b["object"].body["assignment_ref"]
        else:
            expected_kind = OPERATIONS[command.command_kind]
            assert expected_kind is not None
            if len(domain) != 1 or domain[0].kind != expected_kind or domain[0].version != FACTS[expected_kind]:
                raise ValidationError("NF02_SEPARATE_FACT_COMMAND_REQUIRED")
            obj = domain[0]
            if command.command_payload != {"artifact_ref": obj.ref.as_dict()}:
                raise ValidationError("NF02_SIGNED_ARTIFACT_BINDING_REQUIRED")
            if obj.kind == "bdb_audit_lane_result":
                evidence = self.resolve(records, obj.body["admission_evidence_ref"])
                assignment_ref = evidence["object"].body["assignment_ref"]
            else:
                assignment_ref = obj.body["assignment_ref"]
        assignment, attempt, claims, scope = self.context(records, prior_events, assignment_ref, campaign_id)
        self.authority.authenticate(leased, command, authentication, scope)
        if retry:
            # Retry rechecks live authorization and retained byte integrity, but
            # does not reinterpret a historic command as a new state transition.
            for obj in domain:
                self.retained(con, obj)
            if command.command_kind == "START_ATTEMPT":
                self.retained(con, b["object"])
            return {}, scope
        cut = self.cut(current, commits[-1])
        state = self.state(prior_events, "Attempt", attempt["attempt_id"], "CREATED")
        if command.command_kind == "BIND_ASSIGNMENT_PACKAGE":
            if state != "CREATED" or any(r["object"].kind == "assignment_package_binding" and eq_ref(r["object"].body["assignment_ref"], assignment_ref) for r in records.values()):
                raise ValidationError("NF02_BINDING_CONFLICT_OR_ALREADY_STARTED")
            raw = self.raw(reader, obj.body["package_raw_ref"], "NF02_INPUT_PACKAGE_TRANSPORT_V2")
            _, members = self.transport.package(raw, {**claims, "result_slot_contract_refs": assignment["result_slot_contract_refs"]})
            self.validate_disclosure(records, assignment, members)
            expected_events = self.expected_events(obj)
            cut_value = obj.body["binding_input_history_cut"]
        else:
            b = self.binding(records, assignment_ref)
            package = self.raw(AdmissionRawReader(con, require_retained=True), b["object"].body["package_raw_ref"], "NF02_INPUT_PACKAGE_TRANSPORT_V2")
            semantic, members = self.transport.package(package, {**claims, "result_slot_contract_refs": assignment["result_slot_contract_refs"]})
            self.validate_disclosure(records, assignment, members)
            if command.command_kind == "START_ATTEMPT":
                if state != "CREATED" or not eq_ref(command.command_payload["package_binding_ref"], b["ref"]):
                    raise ValidationError("NF02_START_REQUIRES_PRIOR_BINDING")
                expected_events = [{"event_type": "AttemptStarted", "attempt_ref": assignment["attempt_ref"],
                                    "assignment_ref": assignment_ref, "package_binding_ref": b["ref"]}]
                cut_value = command.command_payload["input_history_cut"]
            else:
                starts = [(c["commit_seq"], e) for c in commits for e in c["ordered_event_bodies"]
                          if e.get("event_type") == "AttemptStarted" and eq_ref(e.get("attempt_ref"), assignment["attempt_ref"])]
                if len(starts) != 1 or starts[0][0] <= b["seq"]:
                    raise ValidationError("NF02_PRIOR_SEPARATE_STARTED_REQUIRED")
                if obj.kind == "lane_result_admission_evidence":
                    e = obj.body
                    if state != "STARTED" or not eq_ref(e["package_binding_ref"], b["ref"]):
                        raise ValidationError("NF02_RESULT_NOT_LAWFULLY_STARTED")
                    slot = e["result_slot_contract_ref"]
                    self.validate_slot(assignment, slot)
                    if any(r["object"].kind == obj.kind and eq_ref(r["object"].body["assignment_ref"], assignment_ref)
                           and r["object"].body["result_slot_contract_ref"] == slot for r in records.values()):
                        raise ValidationError("NF02_RESULT_SLOT_CONFLICT")
                    result_raw = self.raw(reader, e["result_raw_ref"], "NF02_RESULT_TRANSPORT_V2")
                    self.transport.result(result_raw, {**claims, "package_binding_ref": b["ref"], "result_slot_contract_ref": slot, "input_package_digest": semantic})
                    expected_events = self.expected_events(obj, attempt, "STARTED", "RESULT_RECEIVED")
                    cut_value = e["admission_input_history_cut"]
                else:
                    e = evidence["object"].body
                    self.validate_slot(assignment, e["result_slot_contract_ref"])
                    if state != "RESULT_RECEIVED" or evidence["seq"] <= starts[0][0]:
                        raise ValidationError("NF02_PRIOR_EVIDENCE_REQUIRED")
                    if any(r["object"].kind == obj.kind and eq_ref(r["object"].body["admission_evidence_ref"], evidence["ref"]) for r in records.values()):
                        raise ValidationError("NF02_RESULT_SLOT_CONFLICT")
                    result_raw = self.raw(AdmissionRawReader(con, require_retained=True), e["result_raw_ref"], "NF02_RESULT_TRANSPORT_V2")
                    normalized = self.transport.result(result_raw, {**claims, "package_binding_ref": b["ref"], "result_slot_contract_ref": e["result_slot_contract_ref"], "input_package_digest": semantic})
                    if canonical_bytes(obj.body["result_payload"]) != normalized:
                        raise ValidationError("NF02_NORMALIZED_RESULT_MISMATCH")
                    expected_events = self.expected_events(obj, attempt, "RESULT_RECEIVED", "RESULT_ACCEPTED")
                    cut_value = obj.body["result_input_history_cut"]
        if cut_value != cut or events != expected_events:
            raise ValidationError("NF02_CURRENT_CUT_OR_EVENT_BINDING_CONFLICT")
        self.validate_references(objects, records, current, command)
        self.validate_input_cuts(objects, commits, command)
        return reader.verified, scope

    def validate_input_cuts(self, objects, commits, command):
        for obj in objects:
            if obj.kind == "command_envelope":
                continue  # Exact parent-head binding is checked separately.
            key = self.registry.contract(obj.kind, obj.version)["schema_ref"]
            for spec in self.schema_documents[key]["x-bdb-material-refs"]:
                if spec["ref_class"] != "HISTORY_INPUT":
                    continue
                for cut in values_at(obj.body, spec["field"]):
                    if cut.get("kind") == "EMPTY_HISTORY_CUT" and not commits:
                        if (cut["history_namespace_ref"] != command.history_namespace_ref
                                or cut["governing_policy_ref"] != command.governing_policy_ref
                                or cut["governing_spec_refs"] != list(command.governing_spec_refs)):
                            raise ValidationError("NF02_INPUT_HISTORY_CONTEXT_CONFLICT")
                    else:
                        seq = cut.get("accepted_head_seq", 0)
                        if type(seq) is not int or not 1 <= seq <= len(commits):
                            raise ValidationError("NF02_INPUT_HISTORY_CONTEXT_CONFLICT")
                        prior = commits[seq - 1]
                        if cut != self.cut(AcceptedHead(prior["campaign_id"], seq, self.commit(prior).digest), prior):
                            raise ValidationError("NF02_INPUT_HISTORY_CONTEXT_CONFLICT")

    def validate_slot(self, assignment, slot):
        if slot not in assignment["result_slot_contract_refs"] or slot != self.transport.pin("NF02_EXTERNAL_LANE_SLOT_V2"):
            raise ValidationError("NF02_UNDECLARED_RESULT_SLOT")

    def validate_disclosure(self, records, assignment, members):
        """Only exact members present in accepted, granted view manifests."""
        allowed: dict[str, Any] = {}
        for ref in assignment["view_manifest_refs"]:
            view = self.resolve(records, ref)["object"].body
            for member in view["allowed_member_refs"]:
                if set(member) != {"raw_digest", "byte_length", "media_type", "artifact_contract_ref"}:
                    raise ValidationError("NF02_EXACT_VIEW_MEMBER_PROFILE_REQUIRED")
                if member["raw_digest"] in allowed and allowed[member["raw_digest"]] != member:
                    raise ValidationError("NF02_VIEW_MEMBER_CONFLICT")
                allowed[member["raw_digest"]] = member
        for name, raw in members.items():
            if name == "MANIFEST.json":
                continue
            entry = allowed.get(sha(raw))
            if entry is None or entry["raw_digest"] != sha(raw) or entry["byte_length"] != len(raw):
                raise ValidationError("NF02_UNGRANTED_PACKAGE_MEMBER", name)
        if {sha(raw) for name, raw in members.items() if name != "MANIFEST.json"} != set(allowed):
            raise ValidationError("NF02_ASSIGNED_VIEW_MEMBER_MISSING")

    def validate_references(self, objects, records, current, command):
        content = {o.digest: o for o in objects}
        for obj in objects:
            for ref in obj.content_refs + obj.prior_content_refs:
                if ref.ref_class == "PRIOR_ACCEPTED_ONLY" or ref.revision_digest not in content:
                    if ref.ref_class != "PRIOR_ACCEPTED_ONLY" and ref.as_dict() in self.bundle["initial_pins"].values():
                        # Independently installed initial objects are pinned
                        # content, never fabricated prior campaign acceptance.
                        continue
                    self.resolve(records, ref.as_dict())
                elif not eq_ref(content[ref.revision_digest].ref.as_dict(), ref.as_dict()):
                    raise ValidationError("NF02_TYPED_REFERENCE_CONFLICT")

    def retained(self, con, obj):
        reader = AdmissionRawReader(con, require_retained=True)
        if obj.kind not in FACTS:
            return {}
        head = AcceptedHead(*con.execute("SELECT campaign_id,seq,commit_hash FROM accepted_head WHERE singleton=1").fetchone())
        records, events, commits = self.history(con, head)
        accepted = self.resolve(records, obj.ref.as_dict())
        original = obj
        evidence = None
        if obj.kind == "bdb_audit_lane_result":
            evidence = self.resolve(records, obj.body["admission_evidence_ref"])
            obj = evidence["object"]
            if evidence["seq"] >= accepted["seq"]:
                raise ValidationError("NF02_PRIOR_EVIDENCE_REQUIRED")
        elif obj.kind == "lane_result_admission_evidence":
            evidence = accepted
        binding = accepted if obj.kind == "assignment_package_binding" else self.resolve(records, obj.body["package_binding_ref"])
        binding_body = binding["object"].body
        prior_seq = binding_body["binding_input_history_cut"]["accepted_head_seq"]
        if prior_seq != binding["seq"] - 1:
            raise ValidationError("NF02_INPUT_HISTORY_CONTEXT_CONFLICT")
        prefix = {digest: r for digest, r in records.items() if r["seq"] <= prior_seq}
        prefix_events = [event for commit in commits[:prior_seq] for event in commit["ordered_event_bodies"]]
        assignment, attempt, claims, scope = self.context(prefix, self.projected_events(prefix_events, prefix), binding_body["assignment_ref"], head.campaign_id)
        package = self.raw(reader, binding_body["package_raw_ref"], "NF02_INPUT_PACKAGE_TRANSPORT_V2")
        semantic, members = self.transport.package(package, {**claims, "result_slot_contract_refs": assignment["result_slot_contract_refs"]})
        self.validate_disclosure(prefix, assignment, members)
        if evidence is not None:
            body = evidence["object"].body
            starts = [commit for commit in commits if any(event.get("event_type") == "AttemptStarted" and event["attempt_ref"] == assignment["attempt_ref"] for event in commit["ordered_event_bodies"])]
            if len(starts) != 1 or not binding["seq"] < starts[0]["commit_seq"] < evidence["seq"]:
                raise ValidationError("NF02_PRIOR_SEPARATE_STARTED_REQUIRED")
            self.validate_slot(assignment, body["result_slot_contract_ref"])
            result_raw = self.raw(reader, body["result_raw_ref"], "NF02_RESULT_TRANSPORT_V2")
            normalized = self.transport.result(result_raw, {**claims, "package_binding_ref": binding["ref"],
                         "result_slot_contract_ref": body["result_slot_contract_ref"], "input_package_digest": semantic})
            if original.kind == "bdb_audit_lane_result" and canonical_bytes(original.body["result_payload"]) != normalized:
                raise ValidationError("NF02_NORMALIZED_RESULT_MISMATCH")
        return reader.verified
