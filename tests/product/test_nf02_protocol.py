"""Unqualified protocol integration. No fixture principal is an installed root.

Use unchanged exact predecessor candidate schemas/bodies as test input only.
The test-only authority is patched at the OS boundary, never selected by API.
"""
from contextlib import contextmanager
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import io
import json
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest

from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.installation_authority import sha
from bdb_audit.history.nf02_protocol import NF02Protocol
from bdb_audit.history.store import TransactionalHistoryStore, InjectedCrash
from bdb_audit.history.successor_wire import SuccessorCommand, copy
from bdb_audit.workflow.nf02_intake import NF02Intake, IntakeRequest
from bdb_audit.workflow.nf02_transport import ASSIGNMENT_CLAIMS

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "docs/R5_4_1/candidate"
SIMULATED_SIGNATURE = b"TEST_ONLY_NOT_A_PRODUCTION_SIGNATURE"


class SimulatedMachineAuthority:
    def __init__(self, files, installation):
        self.leased = {"identity": "f" * 64, "files": files, "installation": installation}
        self.revoked = False

    @contextmanager
    def lease(self):
        if self.revoked:
            raise ValidationError("NF02_PRODUCER_NOT_AUTHORIZED")
        yield self.leased

    def authenticate(self, leased, command, signature, scope):
        if self.revoked or signature != SIMULATED_SIGNATURE or command.actor_ref != "TEST_ONLY_INDEPENDENT_PRINCIPAL":
            raise ValidationError("NF02_PRODUCER_NOT_AUTHORIZED")
        campaign = command.campaign_ref or command.proposed_campaign_id
        if campaign != "campaign_genesis_00000000-0000-4000-8000-000000000001":
            raise ValidationError("NF02_PRODUCER_NOT_AUTHORIZED")

    @contextmanager
    def storage_lease(self, path):
        # This fixture also simulates the protected service storage boundary.
        # It cannot be configured through production Store.open_nf02.
        yield


def repack(manifest, other):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted({"MANIFEST.json": canonical_bytes(manifest), **other}.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return out.getvalue()


@pytest.fixture
def protocol(tmp_path, monkeypatch):
    files = {"candidate/" + str(p.relative_to(CANDIDATE)).replace("\\", "/"): p.read_bytes()
             for p in CANDIDATE.rglob("*") if p.is_file()}
    files["manifest.json"] = (ROOT / "docs/R5_4_1/R5_4_1_CANDIDATE_MANIFEST.json").read_bytes()
    installation = {"pin_bundle": "candidate/INSTALLATION_PIN_BUNDLE_R5_4.json", "candidate_manifest": "manifest.json",
                    "bootstrap_packets": {}, "context_packets": {}}
    authority = SimulatedMachineAuthority(files, installation)
    monkeypatch.setattr("bdb_audit.history.nf02_protocol.MachineAuthority", lambda: authority)
    store = TransactionalHistoryStore.open_nf02(tmp_path / "new.sqlite")
    runtime = store._nf02
    fixture = parse(files["candidate/fixtures/NF02_OBJECT_FIXTURE_R5_4.json"])
    refs = {}
    model_objects = {o["ref"]["revision_digest"]: o for o in fixture["objects"]}

    def remap(value):
        if isinstance(value, dict):
            if "revision_digest" in value and value.get("kind") != "schema" and value["revision_digest"] in refs:
                return copy(refs[value["revision_digest"]])
            if "accepted_head_seq" in value:
                head = store.head()
                if head:
                    return runtime.cut(head, store.commits()[-1])
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return value

    def object_from_template(template):
        body = remap(template["body"])
        if template["kind"] == "view_manifest":
            with zipfile.ZipFile(io.BytesIO(files["candidate/fixtures/input_package.zip"])) as archive:
                prompt = archive.read("PROMPT.md")
            raw_ref = {"raw_digest": sha(prompt), "byte_length": len(prompt), "media_type": "text/markdown",
                       "artifact_contract_ref": copy(body["allowed_member_refs"][0]["artifact_contract_ref"])}
            body["allowed_member_refs"].append(raw_ref)
        obj = runtime.object(template["kind"], body, template["version"], template["ref"].get("logical_id"))
        refs[template["ref"]["revision_digest"]] = obj.ref.as_dict()
        return obj

    for index in range(3):
        original = fixture["commits"][index]["body"]
        objects = []
        for ref in original["immutable_object_refs"]:
            template = model_objects[ref["revision_digest"]]
            if template["kind"] != "command_envelope":
                objects.append(object_from_template(template))
        cmd_body = copy(model_objects[original["command_digest"]]["body"])
        cmd_body = remap(cmd_body)
        cmd_body["command_id"] = "command_" + str(uuid4())
        cmd_body["actor_ref"] = "TEST_ONLY_INDEPENDENT_PRINCIPAL"
        if index:
            cmd_body["command_kind"] = "PREPARE_NF02_E1_CONTEXT"
            cmd_body["expected_parent_head"] = store.head().as_dict()
        command = SuccessorCommand(**cmd_body, runtime=runtime)
        if index == 0:
            genesis_ref = next(o.ref.as_dict() for o in objects if o.kind == "campaign_genesis")
            events = [{"event_type": "CampaignGenesisAccepted", "artifact_ref": genesis_ref}]
        elif index == 1:
            events = [{"event_type": "StateTransitionAccepted", "aggregate_kind": "CAMPAIGN", "aggregate_ref": genesis_ref,
                       "from_state": "GENESIS_ACCEPTED", "to_state": "E0_READY", "basis_refs": [genesis_ref]},
                      {"event_type": "StateTransitionAccepted", "aggregate_kind": "CAMPAIGN", "aggregate_ref": genesis_ref,
                       "from_state": "E0_READY", "to_state": "AUDIT_RUNNING", "basis_refs": [genesis_ref]}]
        else:
            lane = next(o for o in objects if o.kind == "lane_run")
            stage = next(o for o in objects if o.kind == "stage_run")
            events = []
            for kind, obj in (("STAGE_RUN", stage), ("LANE_RUN", lane)):
                for start, end in (("PLANNED", "READY"), ("READY", "RUNNING")):
                    events.append({"event_type": "StateTransitionAccepted", "aggregate_kind": kind, "aggregate_ref": obj.ref.as_dict(),
                                   "from_state": start, "to_state": end, "basis_refs": [genesis_ref]})
        service = NF02Intake(store)
        if index == 0:
            prepared = service.prepare_initialization(actor_ref=command.actor_ref, campaign_id=command.proposed_campaign_id,
                                                        objects=objects, events=events, command_id=command.command_id)
        else:
            prepared = service.prepare_context(actor_ref=command.actor_ref, objects=objects, events=events, command_id=command.command_id)
        command = prepared.command
        packet = parse(service.packet_bytes(prepared))
        table = "bootstrap_packets" if index == 0 else "context_packets"
        installation[table].setdefault(command.campaign_ref or command.proposed_campaign_id, []).append(sha(canonical_bytes(packet)))
        store.accept(command, immutable_objects=objects, ordered_events=events, authentication=SIMULATED_SIGNATURE)
    assignment_ref = refs[fixture["assignment"]["ref"]["revision_digest"]]
    assignment = store.resolve_accepted(assignment_ref, runtime.cut(store.head(), store.commits()[-1]))["body"]
    package_manifest = remap(fixture["package_manifest"])
    package_manifest.update({k: copy(assignment[k]) for k in ASSIGNMENT_CLAIMS - {"assignment_ref"}})
    package_manifest["assignment_ref"] = assignment_ref
    with zipfile.ZipFile(io.BytesIO(files["candidate/fixtures/input_package.zip"])) as archive:
        members = {n: archive.read(n) for n in archive.namelist() if n != "MANIFEST.json"}
    semantic_pin = runtime.transport.pin("NF02_PACKAGE_SEMANTIC_PROFILE_V1")
    descriptor = {"profile_ref": semantic_pin,
                  "manifest": {k: v for k, v in package_manifest.items() if k != "package_semantic_digest"},
                  "members": package_manifest["members"]}
    package_manifest["package_semantic_digest"] = {"profile_ref": semantic_pin, "digest": sha(canonical_bytes(descriptor))}
    package = repack(package_manifest, members)
    return store, NF02Intake(store), authority, assignment_ref, assignment, package, fixture


def result_zip(protocol, binding_ref):
    store, intake, _, assignment_ref, assignment, package, fixture = protocol
    claims = {k: copy(assignment[k]) for k in ASSIGNMENT_CLAIMS - {"assignment_ref"}}
    semantic, _ = intake.runtime.transport.package(package, {**claims, "assignment_ref": assignment_ref, "result_slot_contract_refs": assignment["result_slot_contract_refs"]})
    manifest = copy(fixture["result_manifest"])
    manifest.update(claims, assignment_ref=assignment_ref, package_binding_ref=binding_ref, input_package_digest=semantic)
    manifest["result_slot_contract_ref"] = assignment["result_slot_contract_refs"][0]
    raw = (CANDIDATE / "fixtures/audit_result.zip").read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = {n: archive.read(n) for n in archive.namelist() if n != "MANIFEST.json"}
    return repack(manifest, members)


def test_binding_started_evidence_result_in_real_store_and_restart(protocol):
    store, intake, _, assignment_ref, assignment, package, _ = protocol
    binding = intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=assignment_ref, package_zip=package)
    b = intake.accept(binding, SIMULATED_SIGNATURE)
    assert b.head.commit_seq == 4
    assert store.read_accepted_raw(binding.objects[0].ref, intake.runtime.cut(store.head(), store.commits()[-1]))[sha(package)] == package
    start = intake.start(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", binding_ref=binding.objects[0].ref.as_dict())
    assert intake.accept(start, SIMULATED_SIGNATURE).head.commit_seq == 5
    delivery = intake.delivery_request(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", binding_ref=binding.objects[0].ref.as_dict())
    received = []
    intake.deliver(command=delivery, signature=SIMULATED_SIGNATURE, sink=lambda raw, envelope: received.append(raw))
    assert received == [package]
    raw = result_zip(protocol, binding.objects[0].ref.as_dict())
    evidence = intake.evidence(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=assignment_ref,
                               binding_ref=binding.objects[0].ref.as_dict(), slot_ref=assignment["result_slot_contract_refs"][0], result_zip=raw)
    assert intake.accept(evidence, SIMULATED_SIGNATURE).head.commit_seq == 6
    restarted = TransactionalHistoryStore.open_nf02(store.path)
    resumed = NF02Intake(restarted)
    result = resumed.result(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", evidence_ref=evidence.objects[0].ref.as_dict())
    accepted = resumed.accept(result, SIMULATED_SIGNATURE)
    assert accepted.head.commit_seq == 7
    assert restarted.rebuild_projection()["state"] == "AUDIT_RUNNING"
    assert result.objects[0].body["result_payload"] == parse(fixture_payload(raw))
    assert restarted.read_accepted_raw(result.objects[0].ref, resumed.runtime.cut(restarted.head(), restarted.commits()[-1]))[sha(raw)] == raw
    assert resumed.accept(result, SIMULATED_SIGNATURE).receipt == accepted.receipt
    old_start = replace(start, command=replace(start.command, runtime=restarted._nf02))
    assert resumed.accept(old_start, SIMULATED_SIGNATURE).head.commit_seq == 5
    assert restarted.head().commit_seq == 7
    baseline = snapshot(restarted)
    with pytest.raises(ValidationError, match="NF02_INSTALLED_READER_REQUIRED"):
        TransactionalHistoryStore(restarted.path)
    assert snapshot(restarted) == baseline


def fixture_payload(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return canonical_bytes(parse(archive.read("MANIFEST.json"))["result_payload"])


def test_no_machine_authority_creates_no_database(tmp_path):
    path = tmp_path / "blocked.sqlite"
    with pytest.raises(ValidationError, match="NF02_INSTALLATION_AUTHORITY_NOT_ESTABLISHED"):
        TransactionalHistoryStore.open_nf02(path)
    assert not path.exists()


def snapshot(store):
    return {str(p.relative_to(Path(store.path).parent)): p.read_bytes() for p in Path(store.path).parent.rglob("*") if p.is_file()}


def submit(store, request, signature=SIMULATED_SIGNATURE):
    return store.accept(request.command, immutable_objects=request.objects, ordered_events=request.events,
                        raw_artifacts=request.raw, authentication=signature)


def alter(intake, request, update):
    obj = request.objects[0]
    body = copy(obj.body)
    update(body)
    new = intake.runtime.object(obj.kind, body, obj.version, obj.logical_id)
    return replace(request, objects=(new,), command=replace(request.command, command_payload={"artifact_ref": new.ref.as_dict()}),
                   events=tuple(intake.runtime.expected_events(new)))


def accept_binding(protocol):
    store, intake, _, ref, _, package, _ = protocol
    request = intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, package_zip=package)
    accepted = intake.accept(request, SIMULATED_SIGNATURE)
    return request, accepted


def start_binding(protocol, binding):
    return protocol[1].accept(protocol[1].start(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", binding_ref=binding.objects[0].ref.as_dict()), SIMULATED_SIGNATURE)


def make_evidence(protocol, binding):
    _, intake, _, ref, assignment, _, _ = protocol
    return intake.evidence(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, binding_ref=binding.objects[0].ref.as_dict(),
                           slot_ref=assignment["result_slot_contract_refs"][0], result_zip=result_zip(protocol, binding.objects[0].ref.as_dict()))


def test_rejections_before_and_after_started_preserve_all_bytes(protocol):
    store, intake, authority, assignment_ref, _, package, _ = protocol
    binding = intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=assignment_ref, package_zip=package)
    baseline = snapshot(store)
    attempts = [
        lambda: submit(store, binding, b"caller HMAC"),
        lambda: submit(store, replace(binding, command=replace(binding.command, actor_ref="SELF_GRANTED"))),
        lambda: submit(store, replace(binding, command=replace(binding.command, campaign_ref="foreign-campaign"))),
        lambda: submit(store, replace(binding, raw={sha(package): package + b"changed"})),
        lambda: submit(store, replace(binding, raw={})),
        lambda: submit(store, replace(binding, events=binding.events + ({"event_type": "AttemptStarted", "attempt_ref": assignment_ref},))),
        lambda: submit(store, alter(intake, binding, lambda b: b["binding_input_history_cut"].update(accepted_head_hash="a" * 64))),
        lambda: submit(store, alter(intake, binding, lambda b: b["assignment_ref"].update(schema_revision_ref={"kind": "schema", "revision_digest": "a" * 64}))),
        lambda: submit(store, replace(binding, command=replace(binding.command, command_payload={"artifact_ref": assignment_ref}))),
        lambda: submit(store, replace(binding, objects=(*binding.objects, replace(binding.command, command_id="command_" + str(uuid4())).as_object()))),
        lambda: submit(store, replace(binding, events=tuple({**event, "actor_ref": "SELF_GRANTED"} for event in binding.events))),
    ]
    for attempt in attempts:
        with pytest.raises(ValidationError):
            attempt()
        assert snapshot(store) == baseline
    intake.accept(binding, SIMULATED_SIGNATURE)
    evidence = make_evidence(protocol, binding)
    before_start = snapshot(store)
    with pytest.raises(ValidationError, match="NF02_PRIOR_SEPARATE_STARTED_REQUIRED"):
        submit(store, evidence)
    assert snapshot(store) == before_start
    start_binding(protocol, binding)
    evidence = make_evidence(protocol, binding)
    baseline = snapshot(store)
    for invalid in (
        alter(intake, evidence, lambda e: e["package_binding_ref"].update(revision_digest="a" * 64)),
        alter(intake, evidence, lambda e: e["result_slot_contract_ref"].update(revision_digest="a" * 64)),
        alter(intake, evidence, lambda e: e["admission_input_history_cut"].update(accepted_head_seq=1)),
    ):
        with pytest.raises(ValidationError):
            submit(store, invalid)
        assert snapshot(store) == baseline
    with zipfile.ZipFile(io.BytesIO(next(iter(evidence.raw.values())))) as archive:
        manifest = parse(archive.read("MANIFEST.json"))
        members = {name: archive.read(name) for name in archive.namelist() if name != "MANIFEST.json"}
    for field in ("attempt_ref", "source_generation_ref", "stage_spec_ref", "executor_profile_ref", "delivery_profile_ref"):
        changed = copy(manifest)
        changed[field]["revision_digest"] = "a" * 64
        bad_zip = repack(changed, members)
        bad_request = intake.evidence(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=assignment_ref,
                                      binding_ref=binding.objects[0].ref.as_dict(), slot_ref=manifest["result_slot_contract_ref"], result_zip=bad_zip)
        with pytest.raises(ValidationError, match="NF02_ACCEPTED_CONTEXT_CLAIM_MISMATCH"):
            submit(store, bad_request)
        assert snapshot(store) == baseline
    # No same-commit evidence/result or generic transition substitute.
    result_body = {"lane_result_id": "bdb_audit_lane_result_" + str(uuid4()), "admission_evidence_ref": evidence.objects[0].ref.as_dict(),
                   "result_input_history_cut": intake.runtime.cut(store.head(), store.commits()[-1]), "result_payload": parse(fixture_payload(next(iter(evidence.raw.values()))))}
    result = intake.runtime.object("bdb_audit_lane_result", result_body, "2", result_body["lane_result_id"])
    for invalid in (replace(evidence, objects=(*evidence.objects, result)),
                    replace(evidence, command=replace(evidence.command, command_kind="TRANSITION"))):
        with pytest.raises(ValidationError):
            submit(store, invalid)
        assert snapshot(store) == baseline
    intake.accept(evidence, SIMULATED_SIGNATURE)
    proposal = intake.result(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", evidence_ref=evidence.objects[0].ref.as_dict())
    with pytest.raises(ValidationError, match="NF02_NORMALIZED_RESULT_MISMATCH"):
        submit(store, alter(intake, proposal, lambda r: r["result_payload"].update(notes="invented")))
    authority.revoked = True
    baseline = snapshot(store)
    with pytest.raises(ValidationError, match="NF02_PRODUCER_NOT_AUTHORIZED"):
        intake.accept(proposal, SIMULATED_SIGNATURE)
    assert snapshot(store) == baseline


def test_operation_retry_returns_original_receipt_and_conflicts(protocol):
    store, intake, _, ref, _, package, _ = protocol
    binding, original = accept_binding(protocol)
    baseline = snapshot(store)
    retry = intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, package_zip=package)
    assert retry.objects[0].digest != binding.objects[0].digest
    resolved = intake.accept(retry, SIMULATED_SIGNATURE)
    assert resolved.already_accepted and resolved.receipt == original.receipt
    assert snapshot(store) == baseline
    with pytest.raises(ValidationError):
        submit(store, retry)  # A second binding body cannot enter history.
    start_binding(protocol, binding)
    evidence = make_evidence(protocol, binding)
    first = intake.accept(evidence, SIMULATED_SIGNATURE)
    repeated = make_evidence(protocol, binding)
    assert intake.accept(repeated, SIMULATED_SIGNATURE).receipt == first.receipt
    invalid = alter(intake, repeated, lambda e: e["result_raw_ref"].update(raw_digest="a" * 64))
    invalid = replace(invalid, raw={"a" * 64: b"changed"})
    baseline = snapshot(store)
    with pytest.raises(ValidationError):
        intake.accept(invalid, SIMULATED_SIGNATURE)
    assert snapshot(store) == baseline


def test_crash_recovery_at_every_store_boundary(protocol, tmp_path):
    store, intake, _, ref, _, package, _ = protocol
    for index, boundary in enumerate(store.HOOKS):
        path = tmp_path / f"crash_{index}.sqlite"
        import sqlite3
        with store._connect() as source, sqlite3.connect(path) as destination:
            source.backup(destination)
        crashed = TransactionalHistoryStore.open_nf02(path, crash_hook=lambda at, selected=boundary: at == selected)
        service = NF02Intake(crashed)
        request = service.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, package_zip=package)
        before = snapshot(crashed)
        with pytest.raises(InjectedCrash):
            service.accept(request, SIMULATED_SIGNATURE)
        durable = boundary == "after_commit_durability_before_ack"
        restored = TransactionalHistoryStore.open_nf02(path)
        assert restored.head().commit_seq == (4 if durable else 3)
        if not durable:
            assert snapshot(crashed) == before
        accepted = NF02Intake(restored).accept(replace(request, command=replace(request.command, runtime=restored._nf02),
                                                        objects=tuple(restored._nf02.object(o.kind, o.body, o.version, o.logical_id) for o in request.objects)), SIMULATED_SIGNATURE)
        assert accepted.head.commit_seq == 4 and accepted.already_accepted == durable
        con = restored._connect()
        try:
            assert con.execute("SELECT body FROM immutable_raw_artifacts WHERE digest=?", (sha(package),)).fetchone()[0] == package
            assert con.execute("SELECT count(*) FROM receipts").fetchone()[0] == 4
        finally:
            con.close()


def test_concurrent_identical_bind_has_one_fact_and_one_receipt(protocol):
    store, intake, _, ref, _, package, _ = protocol
    requests = [intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, package_zip=package) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda r: intake.accept(r, SIMULATED_SIGNATURE), requests))
    assert results[0].receipt == results[1].receipt
    assert sum(r.already_accepted for r in results) == 1
    assert store.head().commit_seq == 4
    assert len([r for r in store.commits() if any(e.get("artifact_ref", {}).get("kind") == "assignment_package_binding" for e in r["ordered_event_bodies"])]) == 1


def test_concurrent_different_result_bytes_conflict_atomically(protocol):
    store, intake, _, ref, assignment, _, _ = protocol
    binding, _ = accept_binding(protocol)
    start_binding(protocol, binding)
    first = make_evidence(protocol, binding)
    original_raw = next(iter(first.raw.values()))
    with zipfile.ZipFile(io.BytesIO(original_raw)) as archive:
        manifest = parse(archive.read("MANIFEST.json"))
        members = {name: archive.read(name) for name in archive.namelist() if name != "MANIFEST.json"}
    manifest["result_payload"]["notes"] = "a different auditor proposal"
    other_raw = repack(manifest, members)
    second = intake.evidence(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, binding_ref=binding.objects[0].ref.as_dict(),
                             slot_ref=assignment["result_slot_contract_refs"][0], result_zip=other_raw)

    def accepting(request):
        try:
            return intake.accept(request, SIMULATED_SIGNATURE)
        except ValidationError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(accepting, (first, second)))
    assert sum(isinstance(r, ValidationError) for r in results) == 1
    assert next(r for r in results if isinstance(r, ValidationError)).code == "NF02_OPERATION_RETRY_CONFLICT"
    assert store.head().commit_seq == 6
    con = store._connect()
    try:
        assert con.execute("SELECT count(*) FROM immutable_raw_artifacts WHERE digest IN (?,?)", (sha(original_raw), sha(other_raw))).fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM receipts").fetchone()[0] == 6
    finally:
        con.close()


def test_caller_mutation_after_validation_cannot_change_durable_command(protocol):
    store, intake, _, ref, _, package, _ = protocol
    request = intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, package_zip=package)
    command_digest, fact_digest = request.command.digest, request.objects[0].digest

    def mutate(at):
        if at == "before_object_durability":
            request.command.command_payload["artifact_ref"]["revision_digest"] = "a" * 64
            request.objects[0].body["package_raw_ref"]["raw_digest"] = "b" * 64
            request.raw.clear()

    store.crash_hook = mutate
    accepted = submit(store, request)
    assert accepted.commit.command_digest == command_digest
    assert fact_digest in [r.revision_digest for r in accepted.commit.immutable_object_refs]
    assert store.object_record(fact_digest)["body"]["package_raw_ref"]["raw_digest"] == sha(package)
    assert store.head().commit_seq == 4


def test_revocation_before_commit_rolls_back_raw_facts_receipt_and_head(protocol):
    store, intake, authority, ref, _, package, _ = protocol
    request = intake.bind(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref, package_zip=package)
    baseline = snapshot(store)

    def revoke(at):
        if at == "after_head_durability":
            authority.revoked = True

    store.crash_hook = revoke
    with pytest.raises(ValidationError, match="NF02_PRODUCER_NOT_AUTHORIZED"):
        submit(store, request)
    assert snapshot(store) == baseline and store.head().commit_seq == 3


def test_delivery_serializes_against_result_writer_and_rejects_late_release(protocol):
    store, intake, _, _, _, package, _ = protocol
    binding, _ = accept_binding(protocol)
    start_binding(protocol, binding)
    delivery = intake.delivery_request(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", binding_ref=binding.objects[0].ref.as_dict())
    evidence = make_evidence(protocol, binding)
    released, finish = Event(), Event()
    received = []

    def sink(raw, envelope):
        assert raw == package
        received.append(raw)
        released.set()
        assert finish.wait(10)

    with ThreadPoolExecutor(max_workers=2) as executor:
        sending = executor.submit(intake.deliver, command=delivery, signature=SIMULATED_SIGNATURE, sink=sink)
        assert released.wait(10)
        accepting = executor.submit(intake.accept, evidence, SIMULATED_SIGNATURE)
        assert not accepting.done()
        finish.set()
        sending.result(timeout=10)
        assert accepting.result(timeout=15).head.commit_seq == 6
    baseline = snapshot(store)
    with pytest.raises(ValidationError, match="NF02_STALE_DELIVERY_AUTHORIZATION"):
        intake.deliver(command=delivery, signature=SIMULATED_SIGNATURE, sink=lambda *args: received.append(args))
    assert received == [package] and snapshot(store) == baseline


def test_missing_retained_raw_blocks_restart_readback_and_retry(protocol):
    store, intake, authority, _, _, _, _ = protocol
    binding, _ = accept_binding(protocol)
    start_binding(protocol, binding)
    evidence = make_evidence(protocol, binding)
    intake.accept(evidence, SIMULATED_SIGNATURE)
    con = store._connect()
    try:
        con.execute("DELETE FROM immutable_raw_artifacts WHERE digest=?", (evidence.objects[0].body["result_raw_ref"]["raw_digest"],))
        con.commit()
    finally:
        con.close()
    restarted = TransactionalHistoryStore.open_nf02(store.path)
    baseline = snapshot(store)
    with pytest.raises(ValidationError, match="VAULT_INTEGRITY_BLOCKED"):
        NF02Intake(restarted).result(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", evidence_ref=evidence.objects[0].ref.as_dict())
    assert snapshot(store) == baseline
    # Replaying a receipt never needs old credentials, but a new write/retry
    # still requires current authority. Neither event can restore raw from ZIP.
    authority.revoked = True
    with pytest.raises(ValidationError, match="NF02_PRODUCER_NOT_AUTHORIZED"):
        NF02Intake(restarted).accept(evidence, SIMULATED_SIGNATURE)
    assert snapshot(store) == baseline


def test_e1_inbox_accepts_evidence_then_separate_result(protocol, tmp_path):
    from bdb_audit.workflow.inbox import E1ResultInbox
    store, intake, _, ref, assignment, _, _ = protocol
    binding, _ = accept_binding(protocol)
    start_binding(protocol, binding)
    raw = result_zip(protocol, binding.objects[0].ref.as_dict())
    path = tmp_path / "delivered.zip"
    path.write_bytes(raw)
    inbox = E1ResultInbox.for_nf02(store)
    evidence = inbox.prepare_nf02_ingest(path, actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", assignment_ref=ref,
                                          binding_ref=binding.objects[0].ref.as_dict(), slot_ref=assignment["result_slot_contract_refs"][0])
    _, status, digest = inbox.ingest_zip(path, request=evidence, authentication=SIMULATED_SIGNATURE)
    assert status == "EVIDENCE_ACCEPTED" and store.head().commit_seq == 6
    assert digest == store.head().commit_hash
    result = intake.result(actor_ref="TEST_ONLY_INDEPENDENT_PRINCIPAL", evidence_ref=evidence.objects[0].ref.as_dict())
    assert inbox.accept_nf02_result(result, authentication=SIMULATED_SIGNATURE).head.commit_seq == 7
