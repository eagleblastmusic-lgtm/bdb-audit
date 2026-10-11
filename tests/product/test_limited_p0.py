"""Local integration only. Patched OS/CMS are NOT independent qualification."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path

import pytest

from bdb_audit.core.canonical_json import canonical_bytes
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_authority import LimitedMachineAuthority, ROLE_OPERATIONS
from bdb_audit.history.limited_model import (
    BASE,
    MODEL_ID,
    LimitedCorpus,
    domain_hash,
    sha,
)
from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.limited_wire import LimitedCommand, identifier, value_body, copy
from bdb_audit.history.store import TransactionalHistoryStore, InjectedCrash
from bdb_audit.workflow.limited_intake import LimitedIntake
from bdb_audit.workflow.limited_transport import approved_git_view, fixed_zip
from bdb_audit.workflow.inbox import E1ResultInbox

ROOT = Path(__file__).resolve().parents[2]
OWNER, QUALIFIER, COORDINATOR, AUDITOR = (n * 64 for n in "1234")


def transport(value):
    return canonical_bytes(value) + b"\n"


def test_signature(raw, cert):
    return ("TEST_ONLY_SIMULATED_CMS/" + cert + "/" + sha(raw)).encode("ascii")


test_signature.__test__ = False


def simulated_verify(raw, signature, cert, *, at_time=None):
    if signature != test_signature(raw, cert):
        raise ValidationError("TEST_ONLY_SIGNATURE_REJECTED")


@pytest.fixture
def corpus():
    manifest = json.loads((ROOT / BASE / "CANDIDATE_MANIFEST.json").read_bytes())
    names = {
        e["file"] for g in ("normative", "machine") for e in manifest[g + "_files"]
    }
    names.add(BASE + "CANDIDATE_MANIFEST.json")
    return LimitedCorpus({n: (ROOT / n).read_bytes() for n in names})


class SimulatedOsAuthority(LimitedMachineAuthority):
    def __init__(self, leased):
        self.leased = leased
        self.revoked = False

    @contextmanager
    def lease(self):
        if self.revoked:
            raise ValidationError("P0_CURRENT_SCOPED_GRANT_REQUIRED")
        yield self.leased

    @contextmanager
    def storage_lease(self, path, leased):
        yield


def make_roots(runtime):
    c = runtime.corpus
    def obj(k, fields):
        return runtime.object(k, value_body(k, fields))
    registry = obj(
        "artifact_contract_registry",
        {
            "contracts": sorted(c.descriptor["canonical_contracts"]),
            "model_descriptor_raw_ref": c.raw_ref(
                c.files[BASE + "MODEL.json"], "BDB_CJSON_1", "application/json"
            ),
        },
    )
    bindings = [
        {
            "schema_id": c.schema_ref(k)["schema_id"],
            "schema_raw_ref": c.raw_ref(
                c.files[BASE + "schemas/canonical/" + k + "__" + v + ".schema.json"],
                "BDB_CJSON_1",
                "application/schema+json",
            ),
        }
        for k, v in c.versions.items()
    ]
    schemas = obj(
        "schema_registry",
        {
            "registry_ref": registry.ref.as_dict(),
            "bindings": sorted(bindings, key=lambda r: r["schema_id"]),
        },
    )
    policy = obj(
        "policy_revision",
        {
            "authorization_profile_ref": c.pin("P0_AUTHORIZATION_V1"),
            "recovery_profile_ref": c.pin("P0_HISTORY_RECOVERY_V1"),
            "allowed_model": MODEL_ID,
        },
    )
    spec = obj(
        "spec_revision",
        {
            "source_profile_ref": c.pin("P0_BOOTSTRAP_SOURCE_V1"),
            "package_profile_ref": c.pin("P0_PACKAGE_TRANSPORT_V1"),
            "result_profile_ref": c.pin("P0_RESULT_TRANSPORT_V1"),
            "history_profile_ref": c.pin("P0_HISTORY_RECOVERY_V1"),
        },
    )
    props = c.schemas.documents["canonical/trust_profile__3"]["properties"]
    trust = obj(
        "trust_profile",
        {
            "authorization_profile_ref": c.pin("P0_AUTHORIZATION_V1"),
            "isolation_profile_ref": c.pin("P0_EXECUTION_ISOLATION_V1"),
            **{
                k: props[k]["const"]
                for k in (
                    "executor_write_boundary",
                    "assurance",
                    "explicit_non_guarantees",
                )
            },
        },
    )
    bootstrap = obj(
        "installation_bootstrap_profile",
        {
            "registry_ref": registry.ref.as_dict(),
            "schema_registry_ref": schemas.ref.as_dict(),
            "policy_ref": policy.ref.as_dict(),
            "spec_ref": spec.ref.as_dict(),
            "trust_ref": trust.ref.as_dict(),
            "serialization_profile_ref": c.pin("BDB_CJSON_1"),
            "source_profile_ref": c.pin("P0_BOOTSTRAP_SOURCE_V1"),
            "namespace_authority_digest": runtime.root["namespace_authority_digest"],
            "initial_command": "INITIALIZE_P0_FROM_APPROVED_GIT",
        },
    )
    return {o.kind: o for o in (registry, schemas, policy, spec, trust, bootstrap)}


@pytest.fixture
def setup_p0(corpus, tmp_path, monkeypatch):
    seed = LimitedProtocol.__new__(LimitedProtocol)
    seed.corpus, seed.registry, seed.schemas = corpus, corpus.registry, corpus.schemas
    root = {
        "model_id": MODEL_ID,
        "owner_certificate_sha256": OWNER,
        "qualifier_certificate_sha256": QUALIFIER,
        "root_id": identifier("installation_root"),
        "namespace_id": "TEST_ONLY_QUALIFICATION_NAMESPACE",
    }
    root["namespace_authority_digest"] = domain_hash("BDB-NF02-P0-NAMESPACE/1", root)
    seed.root = root
    roots = make_roots(seed)
    files = {
        **corpus.files,
        **{"objects/" + k + ".json": transport(o.body) for k, o in roots.items()},
        "SOURCE_REPOSITORIES.json": transport(
            {
                "repositories": [
                    {"repository_id": "TEST_ONLY_REPOSITORY", "path": str(ROOT)}
                ]
            }
        ),
    }
    corpus = LimitedCorpus(files)
    install = {
        **corpus.bindings(),
        "mode": "QUALIFICATION_ONLY",
        "freeze_sha256": "5" * 64,
        "runtime_qualification_sha256": None,
        "qualification_mandate_sha256": "6" * 64,
        "installed_files": [
            {"file": n, "sha256": sha(raw), "bytes": len(raw)}
            for n, raw in sorted(files.items())
        ],
        "implementation_files": [
            {"file": "TEST_ONLY_NO_OS_QUALIFICATION", "sha256": "7" * 64, "bytes": 1}
        ],
        "namespace_authority_digest": root["namespace_authority_digest"],
        "external_schema_root_sha256": sha(
            files[BASE + "schemas/canonical/schema_registry__3.schema.json"]
        ),
        "coordinator_os_identity": {
            "sid": "TEST_ONLY_NO_SERVICE_SID",
            "privilege_class": "NON_ADMIN_SERVICE_ACCOUNT",
        },
        "initial_root_refs": [o.ref.as_dict() for _, o in sorted(roots.items())],
    }
    install_raw = transport(install)
    root["installation_sha256"] = sha(install_raw)
    leased = {
        "identity": sha(install_raw),
        "root": root,
        "root_raw": transport(root),
        "installation": install,
        "installation_raw": install_raw,
        "installation_signature": test_signature(install_raw, OWNER),
        "corpus": corpus,
        "files": files,
        "grants": [],
    }
    authority = SimulatedOsAuthority(leased)
    monkeypatch.setattr(
        "bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority
    )
    monkeypatch.setattr(
        "bdb_audit.history.limited_protocol.verify_cms", simulated_verify
    )
    monkeypatch.setattr(
        "bdb_audit.history.limited_authority.verify_cms", simulated_verify
    )
    store = TransactionalHistoryStore.open_p0(tmp_path / "p0.sqlite")
    intake, runtime = LimitedIntake(store), store._nf02
    _, manifest_raw, source_zip = approved_git_view(
        ROOT, "HEAD", "TEST_ONLY_REPOSITORY", ["pyproject.toml"]
    )
    manifest = json.loads(manifest_raw)
    source = intake.make(
        "nf02_p0_source_snapshot",
        {
            "repository_authority_digest": domain_hash(
                "BDB-NF02-P0-REPOSITORY/1",
                {
                    "namespace_authority_digest": root["namespace_authority_digest"],
                    "repository_id": manifest["repository_id"],
                },
            ),
            "repository_id": manifest["repository_id"],
            "git_object_algorithm": manifest["git_object_algorithm"],
            "git_commit_object_id": manifest["commit_oid"],
            "git_tree_object_id": manifest["tree_oid"],
            "source_manifest_raw_ref": corpus.raw_ref(
                manifest_raw, "P0_BOOTSTRAP_SOURCE_V1", "application/json"
            ),
            "source_archive_raw_ref": corpus.raw_ref(
                source_zip, "P0_BOOTSTRAP_SOURCE_V1", "application/zip"
            ),
            "approved_view_digest": sha(manifest_raw),
        },
    )
    task = b"# TEST ONLY\nAudit the assigned source.\n"
    campaign = identifier("campaign_genesis")
    genesis = intake.make(
        "campaign_genesis",
        {
            "campaign_id": campaign,
            "mode": "QUALIFICATION_ONLY",
            "task_raw_ref": corpus.raw_ref(
                task, "P0_PACKAGE_TRANSPORT_V1", "text/markdown"
            ),
            "installation_ref": runtime.pins["installation_bootstrap_profile"],
            "source_ref": source.ref.as_dict(),
            "namespace_authority_digest": root["namespace_authority_digest"],
        },
        campaign,
    )

    def grant(scope, role="COORDINATOR"):
        body = {
            "installation_digest": runtime.identity,
            "actor_ref": "TEST_ONLY_" + role,
            "certificate_sha256": {
                "COORDINATOR": COORDINATOR,
                "AUDITOR": AUDITOR,
                "OWNER_RECOVERY": OWNER,
            }[role],
            "role": role,
            **scope,
            "operations": sorted(ROLE_OPERATIONS[role]),
            "not_before": "2020-01-01T00:00:00Z",
            "not_after": "2099-01-01T00:00:00Z",
        }
        raw = transport(body)
        item = {
            "body": body,
            "raw": raw,
            "signature": test_signature(raw, OWNER),
            "digest": sha(raw),
        }
        leased["grants"].append(item)
        return item["digest"]

    initial_grant = grant(runtime.auth_scope(genesis.body, source.body))
    request = intake.initialize(
        source=source,
        genesis=genesis,
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=initial_grant,
        raw={sha(v): v for v in (task, manifest_raw, source_zip)},
    )
    return store, intake, authority, request, grant, source, genesis


def accept(intake, request, cert=COORDINATOR):
    return intake.accept(request, test_signature(request.signing_bytes(), cert))


def assigned(setup_p0):
    store, intake, authority, init, grant, source, genesis = setup_p0
    assert accept(intake, init).head.commit_seq == 1
    attempt, assignment = intake.draft_assignment(auditor_certificate_sha256=AUDITOR)
    scope = intake.runtime.auth_scope(
        genesis.body, source.body, assignment.ref.as_dict(), AUDITOR
    )
    gd = grant(scope)
    grant(scope, "AUDITOR")
    request = intake.prepare(
        "CREATE_ASSIGNMENT",
        [attempt, assignment],
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
    )
    assert accept(intake, request).head.commit_seq == 2
    return store, intake, authority, assignment, gd, grant


def test_approved_corpus_exact_and_immutable(corpus):
    assert (
        len(corpus.versions),
        len(corpus.descriptor["profiles"]),
        len(corpus.schemas.documents),
    ) == (18, 7, 43)
    files = dict(corpus.files)
    files[BASE + "MODEL.json"] += b" "
    with pytest.raises(ValidationError, match="P0_CANDIDATE_CONTENT_DRIFT"):
        LimitedCorpus(files)


def test_legal_bootstrap_binding_then_later_started(setup_p0):
    store, intake, _, assignment, gd, _ = assigned(setup_p0)
    package = intake.package_bytes(assignment.ref.as_dict())
    binding = intake.bind(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        assignment_ref=assignment.ref.as_dict(),
        package_zip=package,
    )
    assert accept(intake, binding).head.commit_seq == 3
    start = intake.start(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        binding_ref=binding.objects[0].ref.as_dict(),
    )
    assert not start.objects
    assert accept(intake, start).head.commit_seq == 4
    before = store.head()
    assert accept(intake, start).already_accepted
    assert store.head() == before
    restarted = TransactionalHistoryStore.open_p0(store.path)
    assert restarted.rebuild_projection()["state"] == "STARTED"


def test_real_authority_absent_does_not_create_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bdb_audit.history.limited_authority.machine_root", lambda: tmp_path / "missing"
    )
    with pytest.raises(
        ValidationError, match="P0_INSTALLATION_AUTHORITY_NOT_ESTABLISHED"
    ):
        TransactionalHistoryStore.open_p0(tmp_path / "blocked.sqlite")
    assert not (tmp_path / "blocked.sqlite").exists()


def snapshot(store):
    return {
        p.name: p.read_bytes() for p in Path(store.path).parent.iterdir() if p.is_file()
    }


@pytest.mark.parametrize(
    "mutation",
    ["actor", "grant", "signature", "campaign", "mode", "namespace", "events", "raw"],
)
def test_binding_denial_has_no_file_mutation(setup_p0, mutation):
    store, intake, _, assignment, gd, _ = assigned(setup_p0)
    raw = intake.package_bytes(assignment.ref.as_dict())
    request = intake.bind(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        assignment_ref=assignment.ref.as_dict(),
        package_zip=raw,
    )
    body = request.command.body()
    signature = None
    if mutation == "actor":
        body["actor_ref"] = "ATTACKER"
    elif mutation == "grant":
        body["grant_digest"] = "f" * 64
    elif mutation == "signature":
        signature = b"ATTACKER OWN HMAC"
    elif mutation == "campaign":
        body["campaign_id"] = identifier("campaign_genesis")
    elif mutation == "mode":
        body["mode"] = "PRODUCTION"
    elif mutation == "namespace":
        body["namespace_authority_digest"] = "f" * 64
    elif mutation == "events":
        request = replace(request, events=())
    elif mutation == "raw":
        request = replace(request, raw={sha(raw): raw + b" "})
    request = replace(request, command=LimitedCommand(body, intake.runtime))
    before = snapshot(store)
    with pytest.raises(ValidationError):
        intake.accept(
            request, signature or test_signature(request.signing_bytes(), COORDINATOR)
        )
    assert snapshot(store) == before


def test_cas_equal_command_retry_and_competing_binding(setup_p0):
    store, intake, _, assignment, gd, _ = assigned(setup_p0)
    raw = intake.package_bytes(assignment.ref.as_dict())
    a = intake.bind(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        assignment_ref=assignment.ref.as_dict(),
        package_zip=raw,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(intake, a), range(2)))
    assert sum(r.already_accepted for r in results) == 1
    assert store.head().commit_seq == 3
    before = snapshot(store)
    body = a.command.body()
    body["command_id"] = body["object_id"] = identifier("command_envelope")
    with pytest.raises(ValidationError):
        accept(intake, replace(a, command=LimitedCommand(body, intake.runtime)))
    assert snapshot(store) == before


@pytest.mark.parametrize("boundary", TransactionalHistoryStore.HOOKS[:-1])
def test_acceptance_crash_rolls_back_all_raw_facts_receipts_and_head(
    setup_p0, boundary
):
    store, intake, _, request, _, _, _ = setup_p0
    before = snapshot(store)

    def fail(name):
        if name == boundary:
            raise InjectedCrash(name)

    store.crash_hook = fail
    with pytest.raises(InjectedCrash):
        accept(intake, request)
    store.crash_hook = None
    assert snapshot(store) == before
    assert accept(intake, request).head.commit_seq == 1


def started(setup_p0):
    store, intake, authority, assignment, gd, grant = assigned(setup_p0)
    package = intake.package_bytes(assignment.ref.as_dict())
    binding = intake.bind(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        assignment_ref=assignment.ref.as_dict(),
        package_zip=package,
    )
    accept(intake, binding)
    binding = binding.objects[0]
    accept(
        intake,
        intake.start(
            actor_ref="TEST_ONLY_COORDINATOR",
            grant_digest=gd,
            binding_ref=binding.ref.as_dict(),
        ),
    )
    return store, intake, authority, assignment, gd, grant, binding, package


def delivered(setup_p0, monkeypatch):
    store, intake, authority, assignment, gd, grant, binding, package = started(
        setup_p0
    )
    calls = []

    def send(files, job, raw):
        assert raw == package
        calls.append((job["release_id"], raw))
        return {
            "http_status": 202,
            "response_sha256": sha(b"TEST_ONLY"),
            "response_bytes": b"TEST_ONLY",
        }

    monkeypatch.setattr("bdb_audit.workflow.limited_delivery.deliver_installed", send)
    job = intake.release_job(binding_ref=binding.ref.as_dict(), grant_digest=gd)
    statement = canonical_bytes(intake.runtime.release_statement(job))
    assert (
        store.release_p0(job, authentication=test_signature(statement, COORDINATOR))[
            "status"
        ]
        == "SENT"
    )
    ack = {
        "domain": "BDB_P0_DELIVERY_ACK/1",
        "scope": job["scope"],
        "release_id": job["release_id"],
        "binding_ref": job["binding_ref"],
        "start_event": job["start_event"],
        "package_raw_ref": job["package_raw_ref"],
        "auditor_certificate_sha256": AUDITOR,
    }
    ack_raw = transport(ack)
    request = intake.delivery(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        binding_ref=binding.ref.as_dict(),
        ack_bytes=ack_raw,
        ack_signature=test_signature(ack_raw, AUDITOR),
    )
    assert accept(intake, request).head.commit_seq == 5
    return (
        store,
        intake,
        authority,
        assignment,
        gd,
        grant,
        binding,
        request.objects[0],
        job,
        calls,
    )


def evidence_request(delivered_p0):
    store, intake, _, assignment, gd, _, binding, delivery, job, _ = delivered_p0
    report = b"# TEST ONLY external report\nNo claim of independent execution.\n"
    payload = {
        "findings": [],
        "report_paths": ["REPORT.md"],
        "evidence_paths": [],
        "log_paths": [],
        "notes": ["LOCAL SIMULATION ONLY"],
    }
    manifest = {
        "scope": job["scope"],
        "binding_ref": binding.ref.as_dict(),
        "delivery_ref": delivery.ref.as_dict(),
        "package_raw_ref": binding.body["package_raw_ref"],
        "members": intake.runtime.transport.member_records({"REPORT.md": report}),
        "payload": payload,
    }
    raw = fixed_zip({"MANIFEST.json": transport(manifest), "REPORT.md": report})
    returned = {
        "domain": "BDB_P0_AUDIT_RETURN/1",
        "scope": job["scope"],
        "binding_ref": binding.ref.as_dict(),
        "delivery_ref": delivery.ref.as_dict(),
        "result_raw_ref": intake.runtime.corpus.raw_ref(
            raw, "P0_RESULT_TRANSPORT_V1", "application/zip"
        ),
        "auditor_certificate_sha256": AUDITOR,
        "execution_declaration": "EXECUTED_ASSIGNED_AUDIT",
    }
    returned_raw = transport(returned)
    return intake.evidence(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        assignment_ref=assignment.ref.as_dict(),
        binding_ref=binding.ref.as_dict(),
        delivery_ref=delivery.ref.as_dict(),
        result_zip=raw,
        return_bytes=returned_raw,
        return_signature=test_signature(returned_raw, AUDITOR),
    ), raw


def test_signed_ack_evidence_later_result_real_store_e1_inbox_restart(
    setup_p0, monkeypatch
):
    flow = delivered(setup_p0, monkeypatch)
    store, intake, _, _, gd, _, _, _, _, calls = flow
    request, raw = evidence_request(flow)
    inbox = E1ResultInbox.for_p0(store)
    assert (
        inbox.accept_p0_evidence(
            request, authentication=test_signature(request.signing_bytes(), COORDINATOR)
        ).head.commit_seq
        == 6
    )
    restarted = TransactionalHistoryStore.open_p0(store.path)
    resumed = LimitedIntake(restarted)
    result = resumed.result(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=gd,
        admission_ref=request.objects[0].ref.as_dict(),
    )
    final = E1ResultInbox.for_p0(restarted).accept_p0_result(
        result, authentication=test_signature(result.signing_bytes(), COORDINATOR)
    )
    assert final.head.commit_seq == 7
    assert restarted.rebuild_projection()["state"] == "RESULT_ACCEPTED"
    cut = resumed.runtime.cut(restarted.head(), restarted.commits()[-1])
    assert restarted.read_accepted_raw(result.objects[0].ref, cut)[sha(raw)] == raw
    before = snapshot(restarted)
    assert accept(resumed, result).already_accepted
    assert snapshot(restarted) == before
    assert len(calls) == 1


def test_release_crash_retry_has_same_id_and_bytes(
    setup_p0, monkeypatch
):
    store, intake, _, assignment, gd, _, binding, package = started(setup_p0)
    calls = []

    def send(files, job, raw):
        calls.append((job["release_id"], raw))
        return {"http_status": 202, "response_bytes": b"TEST ONLY"}

    monkeypatch.setattr("bdb_audit.workflow.limited_delivery.deliver_installed", send)
    job = intake.release_job(binding_ref=binding.ref.as_dict(), grant_digest=gd)
    signature = test_signature(
        canonical_bytes(intake.runtime.release_statement(job)), COORDINATOR
    )

    def crash(name):
        if name == "after_p0_release_before_sent":
            raise InjectedCrash(name)

    store.crash_hook = crash
    with pytest.raises(InjectedCrash):
        store.release_p0(job, authentication=signature)
    store.crash_hook = None
    restarted = TransactionalHistoryStore.open_p0(store.path)
    assert restarted.release_p0(job, authentication=signature)["status"] == "SENT"
    assert calls == [(job["release_id"], package)] * 2
    assert restarted.head().commit_seq == 4


@pytest.mark.parametrize(
    "mutation", ["signature", "raw", "binding", "payload", "auditor_revoked"]
)
def test_evidence_or_result_substitution_denied_without_mutation(
    setup_p0, monkeypatch, mutation
):
    flow = delivered(setup_p0, monkeypatch)
    store, intake, authority, _, gd, _, binding, _, _, _ = flow
    request, raw = evidence_request(flow)
    if mutation == "payload":
        accept(intake, request)
        result = intake.result(
            actor_ref="TEST_ONLY_COORDINATOR",
            grant_digest=gd,
            admission_ref=request.objects[0].ref.as_dict(),
        )
        body = result.objects[0].body.copy()
        body["result_payload"] = {**body["result_payload"], "notes": ["FORGED"]}
        forged = intake.runtime.object("bdb_audit_lane_result", body)
        request = intake.prepare(
            "ACCEPT_RESULT",
            [forged],
            actor_ref="TEST_ONLY_COORDINATOR",
            grant_digest=gd,
        )
    elif mutation == "raw":
        request = replace(request, raw={**request.raw, sha(raw): raw + b"extra"})
    elif mutation == "signature":
        old = request.objects[0]
        body = copy(old.body)
        data = b"CALLER SELF HMAC"
        body["return_signature_raw_ref"] = intake.runtime.corpus.raw_ref(
            data, "P0_AUTHORIZATION_V1", "application/pkcs7-signature"
        )
        forged = intake.runtime.object(old.kind, body)
        request = intake.prepare(
            "INGEST_EVIDENCE",
            [forged],
            actor_ref="TEST_ONLY_COORDINATOR",
            grant_digest=gd,
            raw={**request.raw, sha(data): data},
        )
    elif mutation == "binding":
        old = request.objects[0]
        body = copy(old.body)
        body["binding_ref"]["revision_digest"] = "e" * 64
        forged = intake.runtime.object(old.kind, body)
        request = intake.prepare(
            "INGEST_EVIDENCE",
            [forged],
            actor_ref="TEST_ONLY_COORDINATOR",
            grant_digest=gd,
            raw=request.raw,
        )
    else:
        authority.leased["grants"] = [
            g for g in authority.leased["grants"] if g["body"]["role"] != "AUDITOR"
        ]
    before = snapshot(store)
    with pytest.raises(ValidationError):
        accept(intake, request)
    assert snapshot(store) == before


def test_auditor_revocation_at_final_commit_rolls_back_evidence(setup_p0, monkeypatch):
    flow = delivered(setup_p0, monkeypatch)
    store, intake, authority, *_ = flow
    request, _ = evidence_request(flow)
    before = snapshot(store)

    def revoke(name):
        if name == "after_head_durability":
            authority.leased["grants"] = [g for g in authority.leased["grants"] if g["body"]["role"] != "AUDITOR"]

    store.crash_hook = revoke
    with pytest.raises(ValidationError, match="GRANT_REQUIRED"):
        accept(intake, request)
    assert snapshot(store) == before
