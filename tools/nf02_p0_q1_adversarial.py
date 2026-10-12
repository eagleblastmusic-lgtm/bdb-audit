"""Retained Q1 material/context/history/entry-point cases in production code.

Only OS/CMS/HTTPS fixtures are simulated, explicitly. No production writer,
predicate, replay, schema, parser or identity function is replaced. This cannot
issue author/governance/runtime qualification or independently signed authority.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.limited_model import LimitedCorpus
from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake
from bdb_audit.workflow.limited_intake import LimitedRequest
from bdb_audit.workflow.inbox import E1ResultInbox
from bdb_audit.product_p0_cli import packet, run_p0
from bdb_audit.p0_service import execute
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_reference import history, sha, typed_refs
from tools.nf02_p0_q1_contexts import replaced
from tests.product import test_limited_p0 as f

ROOT = Path(__file__).resolve().parents[1]


def retained_authority(path):
    """Reconstruct explicit test-only OS/CMS inputs from retained actual bytes."""
    with sqlite3.connect(path) as con:
        raws = {digest: raw for digest, raw in con.execute("SELECT digest,body FROM immutable_raw_artifacts")}
        last = json.loads(con.execute("SELECT body FROM commits ORDER BY seq DESC LIMIT 1").fetchone()[0])
        trace = json.loads(raws[last["authorization_trace_raw_ref"]["raw_digest"]])
        root_raw, install_raw = (raws[trace[k + "_raw_ref"]["raw_digest"]] for k in ("root", "installation"))
        installation = json.loads(install_raw)
        files = {e["file"]: raws[e["sha256"]] for e in installation["installed_files"]}
        grants = [{"body": json.loads(raws[gd]), "raw": raws[gd], "signature": raws[sd], "digest": gd}
                  for gd, sd in con.execute("SELECT grant_digest,signature_digest FROM p0_grant_proofs")]
        leased = {"identity": sha(install_raw), "root": json.loads(root_raw), "root_raw": root_raw,
                  "installation": installation, "installation_raw": install_raw,
                  "installation_signature": raws[trace["installation_signature_raw_ref"]["raw_digest"]],
                  "corpus": LimitedCorpus(files), "files": files, "grants": grants}
    return f.SimulatedOsAuthority(leased), raws


def refs_paths(value, path=()):
    if isinstance(value, dict):
        if {"kind", "version", "logical_id", "revision_digest", "schema_revision_ref", "digest_profile"} <= value.keys():
            yield path, value
        else:
            for key, child in value.items():
                yield from refs_paths(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from refs_paths(child, (*path, index))


class Audit:
    def __init__(self, output):
        output = output.resolve()
        self.output = output
        output.mkdir(parents=True, exist_ok=False)
        (output / "states").mkdir()
        (output / "working").mkdir()
        (output / "inputs").mkdir()
        self.templates = []
        self.pools = []
        self.rows = []
        self.checkpoint = None
        self.monkeypatch = None
        self.original_accept = f.accept

    def record(self, case, expected, actual, inputs, **extra):
        row = {"id": "ADV-%05d" % (len(self.rows) + 1), "case": case, "expected": expected, "actual": actual,
               "input_exact_json_sha256": sha(reference_a(inputs)), "inputs": inputs, **extra}
        assert expected == actual, row
        self.rows.append(row)
        with (self.output / "ADVERSARIAL_CASES.jsonl").open("ab") as stream:
            stream.write(reference_a(row) + b"\n")
        if len(self.rows) % 100 == 0:
            print("ADVERSARIAL_CASES", len(self.rows), case, flush=True)

    def capture(self, intake, request, cert=f.COORDINATOR):
        label = self.label + "-%02d-" % (len([t for t in self.templates if t["label"] == self.label]) + 1) + request.command.command_kind
        state = self.output / "states" / (label + ".sqlite")
        shutil.copyfile(intake.store.path, state)
        body = packet(request)
        # Raw is retained separately by exact digest in the final accepted DB.
        template = {"id": label, "label": self.label, "request": request, "state": state, "packet": body,
                    "state_sha256": sha(state.read_bytes()), "authority": intake.runtime.authority, "runtime": intake.runtime, "cert": cert}
        self.templates.append(template)
        result = self.original_accept(intake, request, cert)
        template["post_head"] = result.head.as_dict()
        self.record(label + "/LEGAL", "ACCEPT_ONE_COMMIT", "ACCEPT_ONE_COMMIT", body,
                    input_database_sha256=template["state_sha256"], accepted_head=result.head.as_dict(), receipt_sha256=result.receipt.digest,
                    signing_bytes_sha256=sha(request.signing_bytes()), authority="SIMULATED_OS_CMS_HTTPS", normative="M04/M05/M08-M17")
        return result

    def deliver(self, intake, assignment, binding, gd):
        assert self.monkeypatch is not None
        job = intake.release_job(binding_ref=binding.ref.as_dict(), grant_digest=gd)
        expected_package = intake.package_bytes(assignment.ref.as_dict())

        def simulated_send(files, release, raw):
            assert raw == expected_package
            return {"http_status": 202, "response_sha256": sha(b"TEST_ONLY_RETRY"), "response_bytes": b"TEST_ONLY_RETRY"}

        self.monkeypatch.setattr("bdb_audit.workflow.limited_delivery.deliver_installed", simulated_send)
        intake.store.release_p0(job, authentication=f.test_signature(reference_a(intake.runtime.release_statement(job)), f.COORDINATOR))
        ack = {"domain": "BDB_P0_DELIVERY_ACK/1", "scope": job["scope"], "release_id": job["release_id"],
               "binding_ref": binding.ref.as_dict(), "start_event": job["start_event"], "package_raw_ref": binding.body["package_raw_ref"],
               "auditor_certificate_sha256": f.AUDITOR}
        raw = reference_a(ack) + b"\n"
        request = intake.delivery(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd, binding_ref=binding.ref.as_dict(),
                                  ack_bytes=raw, ack_signature=f.test_signature(raw, f.AUDITOR))
        self.capture(intake, request)
        return request.objects[0], job

    def build(self, reuse=None):
        assert self.monkeypatch is not None
        reuse = reuse.resolve() if reuse else None
        corpus = getattr(f.corpus, "__wrapped__")()
        if reuse:
            authority, raws = retained_authority(reuse / "CAMPAIGN_A/p0.sqlite")
            runtime = LimitedProtocol(authority, authority.leased)
            self.monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
            self.monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)
            for line in (reuse / "ADVERSARIAL_CASES.jsonl").read_bytes().splitlines():
                row = json.loads(line)
                assert row["case"].endswith("/LEGAL") and row["expected"] == row["actual"]
                label = row["case"].removesuffix("/LEGAL")
                state = reuse / "states" / (label + ".sqlite")
                assert sha(state.read_bytes()) == row["input_database_sha256"]
                body = row["inputs"]
                request = LimitedRequest(LimitedCommand(body["command"], runtime), tuple(runtime.object(o["kind"], o["body"], o["version"]) for o in body["objects"]),
                                         tuple(body["command"]["events"]), {d: raws[d] for d in body["raw_digests"]})
                assert sha(request.signing_bytes()) == row["signing_bytes_sha256"]
                self.templates.append({"id": label, "label": "CAMPAIGN_A_RETRY" if label.startswith("CAMPAIGN_A_RETRY") else "CAMPAIGN_A",
                    "request": request, "state": state, "packet": body, "state_sha256": row["input_database_sha256"], "authority": authority,
                    "runtime": runtime, "cert": f.OWNER if body["command"]["operation"] == "ABORT_ATTEMPT" else f.COORDINATOR, "post_head": row["accepted_head"]})
                self.rows.append(row)
            (self.output / "ADVERSARIAL_CASES.jsonl").write_bytes((reuse / "ADVERSARIAL_CASES.jsonl").read_bytes())
            self.collect_pool("CAMPAIGN_A", reuse / "CAMPAIGN_A/p0.sqlite")
            ops = ["INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ABORT_ATTEMPT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT"]
            (self.output / "REUSED_A_REFERENCE_HISTORY.json").write_bytes(reference_a(history(reuse / "CAMPAIGN_A/p0.sqlite", expected_operations=ops)) + b"\n")
        for label in (("CAMPAIGN_B",) if reuse else ("CAMPAIGN_A", "CAMPAIGN_B")):
            self.label = label
            folder = self.output / label
            folder.mkdir()
            setup = getattr(f.setup_p0, "__wrapped__")(corpus, folder, self.monkeypatch)
            self.monkeypatch.setattr(f, "accept", self.capture)
            flow = f.delivered(setup, self.monkeypatch)
            store, intake, authority, assignment, gd, grant, binding, delivery, job, calls = flow
            evidence, _ = f.evidence_request(flow)
            self.capture(intake, evidence)
            if label == "CAMPAIGN_A":
                # Accepted result belongs to the old attempt. Retry proceeds from
                # the saved pre-result DB, keeping an actual old result target pool.
                result = intake.result(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd, admission_ref=evidence.objects[0].ref.as_dict())
                self.capture(intake, result)
                shutil.copyfile(store.path, folder / "old-result-history.sqlite")
                shutil.copyfile(self.templates[-1]["state"], store.path)
                self.label = "CAMPAIGN_A_RETRY"
                source, genesis = setup[5:]
                scope = intake.runtime.auth_scope(genesis.body, source.body, assignment.ref.as_dict(), f.AUDITOR)
                recovery = grant(scope, "OWNER_RECOVERY")
                abort = intake.abort(actor_ref="TEST_ONLY_OWNER_RECOVERY", grant_digest=recovery,
                                     assignment_ref=assignment.ref.as_dict(), reason="OWNER_CANCELLED")
                self.capture(intake, abort, f.OWNER)
                attempt2, assignment2 = intake.draft_assignment(auditor_certificate_sha256=f.AUDITOR)
                scope = intake.runtime.auth_scope(genesis.body, source.body, assignment2.ref.as_dict(), f.AUDITOR)
                gd2 = grant(scope)
                grant(scope, "AUDITOR")
                request = intake.prepare("CREATE_ASSIGNMENT", [attempt2, assignment2], actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd2)
                self.capture(intake, request)
                package = intake.package_bytes(assignment2.ref.as_dict())
                bound = intake.bind(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd2, assignment_ref=assignment2.ref.as_dict(), package_zip=package)
                self.capture(intake, bound)
                binding2 = bound.objects[0]
                self.capture(intake, intake.start(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd2, binding_ref=binding2.ref.as_dict()))
                delivery2, job2 = self.deliver(intake, assignment2, binding2, gd2)
                flow2 = (store, intake, authority, assignment2, gd2, grant, binding2, delivery2, job2, calls)
                evidence2, _ = f.evidence_request(flow2)
                self.capture(intake, evidence2)
                self.capture(intake, intake.result(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd2, admission_ref=evidence2.objects[0].ref.as_dict()))
            self.collect_pool(label, store.path)
            ops = ["INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE"]
            if label == "CAMPAIGN_A":
                ops += ["ABORT_ATTEMPT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT"]
            independent = history(store.path, expected_operations=ops)
            (folder / "REFERENCE_HISTORY_CHECK.json").write_bytes(reference_a(independent) + b"\n")
        self.monkeypatch.setattr(f, "accept", self.original_accept)
        public = [{**{k: t[k] for k in ("id", "label", "packet", "state_sha256", "cert", "post_head")}, "state_file": t["state"].relative_to(ROOT).as_posix()} for t in self.templates]
        (self.output / "TEMPLATES.json").write_bytes(reference_a(public) + b"\n")
        (self.output / "ACCEPTED_TARGET_POOL.json").write_bytes(reference_a(self.pools) + b"\n")

    def collect_pool(self, label, path):
        with sqlite3.connect(path) as con:
            positions = {r["revision_digest"]: seq for seq, raw in con.execute("SELECT seq,body FROM commits") for r in json.loads(raw)["immutable_object_refs"]}
            for kind, version, schema, logical, raw, digest in con.execute("SELECT kind,version,schema_ref,logical_id,body,digest FROM immutable_objects"):
                self.pools.append({"label": label, "kind": kind, "seq": positions[digest], "body": json.loads(raw), "ref": {"kind": kind, "version": version,
                    "schema_revision_ref": json.loads(schema), "logical_id": logical, "revision_digest": digest, "digest_profile": "BDB-OBJECT-DIGEST-1"}})

    def replay_templates(self, template_file):
        """Execute retained legal input bytes on current production code first."""
        assert self.monkeypatch is not None
        directory = template_file.resolve().parent
        self.pools = json.loads((directory / "ACCEPTED_TARGET_POOL.json").read_bytes())
        authorities = {
            "CAMPAIGN_A": retained_authority(directory.parent / "adversarial-final/CAMPAIGN_A/p0.sqlite"),
            "CAMPAIGN_B": retained_authority(directory / "CAMPAIGN_B/p0.sqlite"),
        }
        self.monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
        self.monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)
        for t in json.loads(template_file.read_bytes()):
            group = "CAMPAIGN_B" if t["label"] == "CAMPAIGN_B" else "CAMPAIGN_A"
            authority, raws = authorities[group]
            self.monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority)
            state = ROOT / t["state_file"]
            assert sha(state.read_bytes()) == t["state_sha256"]
            working = self.output / "working/p0.sqlite"
            shutil.copyfile(state, working)
            intake = LimitedIntake(TransactionalHistoryStore.open_p0(working))
            b = t["packet"]
            request = LimitedRequest(LimitedCommand(b["command"], intake.runtime),
                tuple(intake.runtime.object(o["kind"], o["body"], o["version"]) for o in b["objects"]),
                tuple(b["command"]["events"]), {d: raws[d] for d in b["raw_digests"]})
            result = self.original_accept(intake, request, t["cert"])
            assert (result.head.commit_seq, result.head.campaign_id) == (t["post_head"]["commit_seq"], t["post_head"]["campaign_id"])
            self.templates.append({**t, "state": state, "request": request, "authority": authority, "runtime": intake.runtime})
            self.record(t["id"] + "/LEGAL", "ACCEPT_ONE_COMMIT", "ACCEPT_ONE_COMMIT", b,
                input_database_sha256=t["state_sha256"], accepted_head=result.head.as_dict(), receipt_sha256=result.receipt.digest,
                signing_bytes_sha256=sha(request.signing_bytes()), authority="SIMULATED_OS_CMS_HTTPS", normative="M04/M05/M08-M17")
        (self.output / "TEMPLATES.json").write_bytes(template_file.read_bytes())
        (self.output / "ACCEPTED_TARGET_POOL.json").write_bytes((directory / "ACCEPTED_TARGET_POOL.json").read_bytes())

    def rebind(self, template, probe):
        request = template["request"]
        return replace(request, command=LimitedCommand(request.command.body(), probe.runtime),
                       objects=tuple(probe.runtime.object(o.kind, o.body, o.version) for o in request.objects))

    def check_mutation(self, template, probe, index, path, value, variant, *, command=False, remove=False, add_target=None):
        before = f.snapshot(probe.store)
        request = self.rebind(template, probe)
        source = request.command.body() if command else request.objects[index].body
        altered = replaced(source, path, value, remove=remove)
        input_record = {"template": template["id"], "template_packet_sha256": sha(reference_a(template["packet"])),
                        "object_index": index, "command": command, "path": path, "value": value, "remove": remove,
                        "variant": variant, "altered_body_sha256": sha(reference_a(altered))}
        phase = "CLOSED_SCHEMA"
        try:
            if command:
                request = replace(request, command=LimitedCommand(altered, probe.runtime), events=tuple(altered["events"]))
            else:
                objects = tuple(probe.runtime.object(o.kind, altered if i == index else o.body, o.version) for i, o in enumerate(request.objects))
                if add_target is not None:
                    objects += (probe.runtime.object(add_target["kind"], add_target["body"]),)
                    input_record["additional_content_target"] = add_target
                phase = "PREPARE"
                request = probe.prepare(request.command.command_kind, objects, actor_ref=request.command.actor_ref,
                                        grant_digest=request.command.body()["grant_digest"], raw=request.raw,
                                        events=request.events if request.command.command_kind == "START_ATTEMPT" else None,
                                        command_id=request.command.command_id)
            input_record["signing_bytes_sha256"] = sha(request.signing_bytes())
            phase = "CENTRAL_STORE"
            self.original_accept(probe, request, template["cert"])
        except ValidationError as error:
            assert before == f.snapshot(probe.store), input_record
            self.record(template["id"] + "/" + variant, "DENY_WITHOUT_MUTATION", "DENY_WITHOUT_MUTATION", input_record,
                        input_database_sha256=template["state_sha256"], error_code=error.code, phase=phase, normative="M03/M04/M05/M14/M15/M16")
            return
        raise AssertionError((input_record, "Unexpected acceptance"))

    def mutations(self):
        assert self.monkeypatch is not None
        for template in [t for t in self.templates if t["label"] != "CAMPAIGN_B"]:
            self.monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: template["authority"])
            working = self.output / "working/p0.sqlite"
            shutil.copyfile(template["state"], working)
            probe = LimitedIntake(TransactionalHistoryStore.open_p0(working))
            request = template["request"]
            for index, obj in enumerate(request.objects):
                definition = probe.runtime.registry.contract(obj.kind, obj.version)
                for field in definition["material_refs"]:
                    name = field["field"]
                    self.check_mutation(template, probe, index, (name,), None, "REQUIRED_FIELD", remove=True)
                    if obj.body[name] is not None and field["ref_class"] == "PRIOR_OR_NULL_INITIAL":
                        self.check_mutation(template, probe, index, (name,), None, "RETRY_REQUIRES_BOTH_PREDECESSORS")
                    elif obj.body[name] is None and field["ref_class"] == "PRIOR_OR_NULL_INITIAL":
                        target = next(r for r in self.pools if r["kind"] + "/" + r["ref"]["version"] in field["allowed_keys"])
                        self.check_mutation(template, probe, index, (name,), target["ref"], "INITIAL_NON_NULL_PREDECESSOR")
                for path, ref in refs_paths(obj.body):
                    other_schema = next(probe.runtime.schema_ref(k) for k in probe.runtime.corpus.versions if k != ref["kind"])
                    for field, replacement in (("kind", "generic_import"), ("version", "999"), ("revision_digest", "0" * 64),
                        ("logical_id", ref["kind"] + "_00000000-0000-4000-8000-000000000000"), ("digest_profile", "RAW_SHA256"),
                        ("schema_revision_ref", {**ref["schema_revision_ref"], "raw_digest": "0" * 64}),
                        ("schema_revision_ref", other_schema), ("ref_class", "PRIOR")):
                        bad = {**ref, field: replacement}
                        self.check_mutation(template, probe, index, path, bad, "EXACT_REF_" + field.upper())
                    foreign = next((r for r in self.pools if r["label"] == "CAMPAIGN_B" and r["kind"] == ref["kind"]), None)
                    if foreign:
                        self.check_mutation(template, probe, index, path, foreign["ref"], "ACTUAL_ACCEPTED_FOREIGN_CAMPAIGN_TARGET")
                    future_target = next((r for r in self.pools if r["label"] == "CAMPAIGN_A" and r["kind"] == ref["kind"] and r["ref"] != ref and r["seq"] > template["post_head"]["commit_seq"]), None)
                    if future_target:
                        self.check_mutation(template, probe, index, path, future_target["ref"], "ACTUAL_ACCEPTED_LATER_FUTURE_TARGET")
                    stale = next((r for r in self.pools if r["label"] == "CAMPAIGN_A" and r["kind"] == ref["kind"] and r["ref"] != ref and r["seq"] < template["post_head"]["commit_seq"]), None)
                    if template["label"] == "CAMPAIGN_A_RETRY" and stale:
                        self.check_mutation(template, probe, index, path, stale["ref"], "ACTUAL_ACCEPTED_OTHER_ATTEMPT_TARGET")
                    # Exact target bytes proposed in this transaction cannot turn a
                    # prior-only ref into prior acceptance; the finite content set
                    # is itself a normative denial, before chronology laundering.
                    spec = next((s for s in definition["material_refs"] if path == (s["field"],)), None)
                    if spec and spec["ref_class"].startswith("PRIOR"):
                        future = next((r for r in self.pools if r["label"] == "CAMPAIGN_B" and r["kind"] == ref["kind"]), None)
                        if future:
                            self.check_mutation(template, probe, index, path, future["ref"], "SAME_COMMIT_PRIOR_CONTENT", add_target=future)
                for name, cut in obj.body.items():
                    if name.endswith("_cut"):
                        self.check_mutation(template, probe, index, (name, "head"), template["post_head"], "OWN_ACCEPTING_CUT_FORBIDDEN")
                        self.check_mutation(template, probe, index, (name, "head", "commit_seq"), cut["head"]["commit_seq"] + 100, "FUTURE_CUT_FORBIDDEN")
                        self.check_mutation(template, probe, index, (name, "head", "commit_seq"), 1, "STALE_CUT_FORBIDDEN") if cut["head"]["commit_seq"] != 1 else None
                for name in ("result_slot_id", "auditor_certificate_sha256", "namespace_authority_digest", "mode"):
                    if name in obj.body:
                        replacement = "0" * 64 if name.endswith("sha256") or name.endswith("digest") else "UNAUTHORIZED_OTHER_SCOPE"
                        self.check_mutation(template, probe, index, (name,), replacement, "CONTEXT_" + name.upper())
            body = request.command.body()
            for path, ref in refs_paths(body):
                for field, replacement in (("logical_id", ref["kind"] + "_00000000-0000-4000-8000-000000000000"),
                                           ("revision_digest", "0" * 64), ("schema_revision_ref", {**ref["schema_revision_ref"], "raw_digest": "0" * 64})):
                    self.check_mutation(template, probe, -1, path, {**ref, field: replacement}, "COMMAND_REF_" + field.upper(), command=True)
            for field in ("installation_digest", "namespace_authority_digest", "grant_digest", "actor_ref", "campaign_id", "mode"):
                value = "0" * 64 if field.endswith("digest") else ("PRODUCTION" if field == "mode" else "UNAUTHORIZED_OTHER_SCOPE")
                self.check_mutation(template, probe, -1, (field,), value, "COMMAND_CONTEXT_" + field.upper(), command=True)

    def entrypoints(self):
        assert self.monkeypatch is not None
        for template in [t for t in self.templates if t["label"] == "CAMPAIGN_A" or t["request"].command.command_kind == "ABORT_ATTEMPT"]:
            self.monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: template["authority"])
            working = self.output / "working/p0.sqlite"
            shutil.copyfile(template["state"], working)
            probe = LimitedIntake(TransactionalHistoryStore.open_p0(working))
            for entry in ("INTAKE_COORDINATOR", "STORE_DIRECT", "STORE_GENERATORS", "PRODUCT_CLI", "SERVICE_EXECUTE", "E1_INBOX"):
                op = template["request"].command.command_kind
                if entry == "E1_INBOX" and op not in {"INGEST_EVIDENCE", "ACCEPT_RESULT"}:
                    continue
                for authorized in (False, True):
                    shutil.copyfile(template["state"], working)
                    request = self.rebind(template, probe)
                    before = f.snapshot(probe.store)
                    signature = f.test_signature(request.signing_bytes(), template["cert"]) if authorized else b"NO_AUTHORITY"
                    receipt = None
                    try:
                        if entry in {"PRODUCT_CLI", "SERVICE_EXECUTE"}:
                            raw_dir = self.output / "inputs"
                            for digest, raw in request.raw.items():
                                (raw_dir / digest).write_bytes(raw)
                            packet_path, signature_path = raw_dir / "packet.json", raw_dir / "signature.p7s"
                            packet_path.write_bytes(reference_a(packet(request)) + b"\n")
                            signature_path.write_bytes(signature)
                            args = ["accept", "--store", str(working), "--input", str(packet_path), "--signature", str(signature_path), "--raw-dir", str(raw_dir)]
                            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                                if entry == "PRODUCT_CLI":
                                    code = run_p0(args)
                                    response = out.getvalue() + err.getvalue()
                                else:
                                    code, response = execute(args)
                            if code:
                                raise ValidationError(json.loads(response)["error"])
                            receipt = json.loads(response)["receipt"]
                        elif entry == "E1_INBOX":
                            inbox = E1ResultInbox.for_p0(probe.store)
                            fn = inbox.accept_p0_evidence if op == "INGEST_EVIDENCE" else inbox.accept_p0_result
                            receipt = fn(request, authentication=signature).receipt.body()
                        elif entry == "INTAKE_COORDINATOR":
                            receipt = probe.accept(request, signature).receipt.body()
                        else:
                            objects = (o for o in request.objects) if entry == "STORE_GENERATORS" else request.objects
                            events = (e for e in request.events) if entry == "STORE_GENERATORS" else request.events
                            receipt = probe.store.accept(request.command, immutable_objects=objects, ordered_events=events,
                                authentication=signature, raw_artifacts=request.raw).receipt.body()
                        assert authorized, (entry, op, "Unsigned accepted")
                        actual = "ACCEPT_ONE_COMMIT"
                        assert probe.store.head().commit_seq == template["post_head"]["commit_seq"]
                    except ValidationError:
                        assert not authorized, (entry, op, "Authorized denied")
                        assert before == f.snapshot(probe.store)
                        actual = "DENY_WITHOUT_MUTATION"
                    self.record(template["id"] + "/" + entry, "ACCEPT_ONE_COMMIT" if authorized else "DENY_WITHOUT_MUTATION", actual,
                        {"template": template["id"], "entry": entry, "signature_sha256": sha(signature), "packet_sha256": sha(reference_a(packet(request)))},
                        input_database_sha256=template["state_sha256"], receipt=receipt, normative="M05/M16 SAME CENTRAL PREDICATES", authority="SIMULATED_OS_CMS_HTTPS")
                    if authorized:
                        original_head = probe.store.head()
                        original_receipt = receipt
                        # Exact retry uses historical own input cuts and returns
                        # the original receipt, under current valid authority.
                        stable = f.snapshot(probe.store)
                        retry = probe.accept(request, signature)
                        assert retry.already_accepted and retry.receipt.body() == original_receipt and probe.store.head() == original_head
                        assert f.snapshot(probe.store) == stable
                        self.record(template["id"] + "/" + entry + "/EXACT_RETRY", "ORIGINAL_RECEIPT_NO_MUTATION", "ORIGINAL_RECEIPT_NO_MUTATION",
                                    {"command_signing_sha256": sha(request.signing_bytes()), "receipt_sha256": sha(reference_a(receipt))}, normative="M16")

    def run(self, reuse=None, templates=None):
        protocol_sha = sha((ROOT / "src/bdb_audit/history/limited_protocol.py").read_bytes())
        with pytest.MonkeyPatch.context() as monkeypatch:
            self.monkeypatch = monkeypatch
            if templates:
                self.replay_templates(templates)
            else:
                self.build(reuse)
            self.mutations()
            self.entrypoints()
        report = {"status": "PASS_RETAINED_LOCAL_CASES_NOT_REAL_AUTHORITY", "authority": "SIMULATED_OS_CMS_HTTPS",
                  "case_count": len(self.rows), "templates": len(self.templates), "accepted_targets": len(self.pools),
                  "expected_basis": "M03/M04/M05/M08-M17 literals and exact identities, not observed runtime decisions", "mismatches": [],
                  "reference_procedure_sha256": sha((ROOT / "tools/nf02_p0_reference.py").read_bytes()),
                  "harness_sha256": sha(Path(__file__).read_bytes()), "production_qualification": False}
        assert protocol_sha == sha((ROOT / "src/bdb_audit/history/limited_protocol.py").read_bytes())
        report["production_protocol_sha256"] = protocol_sha
        (self.output / "ADVERSARIAL_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
        print("ADVERSARIAL_PASS", report["case_count"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-build", type=Path)
    parser.add_argument("--replay-templates", type=Path)
    args = parser.parse_args()
    Audit(args.output).run(args.reuse_build, args.replay_templates)
