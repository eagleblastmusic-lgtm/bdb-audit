"""Qualification-chain unit probes with explicitly simulated CMS/OS.

These in-memory/temporary records are not issued qualifications or authority.
No certificate, key, protected installation or real PASS is created.
"""

from contextlib import contextmanager
from pathlib import Path

import pytest

from bdb_audit.core.canonical_json import canonical_bytes
from bdb_audit.core.errors import ValidationError
from bdb_audit.history import limited_authority as module
from bdb_audit.history.limited_model import BASE, GRAPH_SHA, domain_hash, sha
from bdb_audit.history.limited_wire import identifier
from tools.nf02_p0_installation_packet import root_objects
from tools.nf02_p0_q1 import Vectors
from tests.product.test_limited_p0 import (
    corpus as p0_corpus,
    OWNER,
    QUALIFIER,
    AUDITOR,
    simulated_verify,
    test_signature,
)

corpus = p0_corpus


def transport(body):
    return canonical_bytes(body) + b"\n"


def chain(corpus, *, mode="PRODUCTION", broken=None):
    vectors = Vectors(corpus.schemas.documents)
    files = dict(corpus.files)

    def record(name, body, signer):
        raw = transport(body)
        files[name] = raw
        files[name + ".p7s"] = test_signature(raw, signer)
        return sha(raw)

    def shape(name, **fields):
        return {
            **vectors.sample(corpus.schemas.documents["external/" + name + "__1"]),
            **corpus.bindings(),
            **fields,
        }

    code = [{"file": "TEST_ONLY.py", "sha256": "7" * 64, "bytes": 1}]
    files["TEST_ONLY_FINAL_AUDIT"] = b"TEST_ONLY_NO_ISSUED_Q1"
    files["TEST_ONLY_INDEPENDENT_REVIEW"] = b"TEST_ONLY_NO_ISSUED_Q2"
    files["TEST_ONLY_REAL_RUN"] = b"TEST_ONLY_NO_EXTERNAL_EXECUTION"
    files["TEST_ONLY_BOUNDARY"] = b"TEST_ONLY_NO_OS_QUALIFICATION"
    files["TEST_ONLY_CASES"] = b"TEST_ONLY_NO_RQ"
    files["ENVIRONMENT.json"] = transport({"TEST_ONLY": True})
    decision = shape("OWNER_MODEL_DECISION", scope_graph_sha256=GRAPH_SHA)
    if broken == "graph":
        decision["scope_graph_sha256"] = "0" * 64
    decision_sha = record("TEST_ONLY_DECISION.json", decision, OWNER)
    readback = {
        e["file"]: e
        for g in ("normative", "machine")
        for e in corpus.manifest[g + "_files"]
    }
    author = shape(
        "AUTHOR_QUALIFICATION",
        owner_decision_sha256=decision_sha,
        readback_files=[readback[n] for n in sorted(readback)],
        final_audit_sha256=sha(files["TEST_ONLY_FINAL_AUDIT"]),
    )
    if broken == "readback":
        author["readback_files"] = author["readback_files"][:-1]
    author_sha = record("TEST_ONLY_AUTHOR.json", author, OWNER)
    freeze = shape(
        "INDEPENDENT_FREEZE",
        owner_decision_sha256=decision_sha,
        author_qualification_sha256=author_sha,
        independent_review_sha256=sha(files["TEST_ONLY_INDEPENDENT_REVIEW"]),
    )
    freeze_sha = record("TEST_ONLY_FREEZE.json", freeze, QUALIFIER)
    if mode == "PRODUCTION":
        qualified = shape(
            "RUNTIME_QUALIFICATION",
            independent_freeze_sha256=freeze_sha,
            implementation_files=code,
            qualification_namespace="TEST_ONLY_QUAL",
            qualified_auditor_certificate_sha256=AUDITOR,
            environment_evidence_sha256=sha(files["ENVIRONMENT.json"]),
            real_external_run_evidence_sha256=sha(files["TEST_ONLY_REAL_RUN"]),
            executor_boundary_evidence_sha256=sha(files["TEST_ONLY_BOUNDARY"]),
            test_evidence=[
                {
                    "file": "TEST_ONLY_CASES",
                    "sha256": sha(files["TEST_ONLY_CASES"]),
                    "bytes": len(files["TEST_ONLY_CASES"]),
                }
            ],
        )
        if broken == "namespace":
            qualified["qualification_namespace"] = "TEST_ONLY_PROD"
        if broken == "freeze":
            qualified["independent_freeze_sha256"] = "0" * 64
        if broken == "environment":
            qualified["environment_evidence_sha256"] = sha(files["TEST_ONLY_BOUNDARY"])
        if broken == "test_bytes":
            qualified["test_evidence"][0]["bytes"] += 1
        qualified_sha = record("TEST_ONLY_RQ.json", qualified, QUALIFIER)
    else:
        qualified = shape(
            "QUALIFICATION_MANDATE",
            freeze_sha256=freeze_sha,
            implementation_files=code,
            qualification_namespace="TEST_ONLY_QUAL",
            not_before="2000-01-01T00:00:00Z",
            not_after="2099-01-01T00:00:00Z",
        )
        if broken == "expired_mandate":
            qualified["not_after"] = "2001-01-01T00:00:00Z"
        qualified_sha = record("TEST_ONLY_MANDATE.json", qualified, OWNER)
        files["TEST_ONLY_MANDATE.json.qualifier.p7s"] = test_signature(
            files["TEST_ONLY_MANDATE.json"], QUALIFIER
        )
        if broken == "qualifier_mandate_signature":
            files["TEST_ONLY_MANDATE.json.qualifier.p7s"] = b"TEST_ONLY_INVALID"
    if broken == "implementation":
        code = [{**code[0], "sha256": "8" * 64}]
    for label, filename in (
        ("final_audit", "TEST_ONLY_FINAL_AUDIT"),
        ("independent_review", "TEST_ONLY_INDEPENDENT_REVIEW"),
        ("real_run", "TEST_ONLY_REAL_RUN"),
    ):
        if broken == label:
            files.pop(filename)
    installation = {
        "mode": mode,
        "freeze_sha256": freeze_sha,
        "runtime_qualification_sha256": qualified_sha if mode == "PRODUCTION" else None,
        "qualification_mandate_sha256": qualified_sha if mode != "PRODUCTION" else None,
        "implementation_files": code,
    }
    root = {
        "owner_certificate_sha256": OWNER,
        "qualifier_certificate_sha256": QUALIFIER,
        "namespace_id": "TEST_ONLY_PROD" if mode == "PRODUCTION" else "TEST_ONLY_QUAL",
    }
    return {
        "corpus": corpus,
        "files": files,
        "installation": installation,
        "root": root,
    }


@pytest.mark.parametrize("mode", ["PRODUCTION", "QUALIFICATION_ONLY"])
def test_chain_predicates_do_not_conflate_production_and_qualification(
    corpus, monkeypatch, mode
):
    monkeypatch.setattr(module, "verify_cms", simulated_verify)
    leased = chain(corpus, mode=mode)
    qualified = module.LimitedMachineAuthority().verify_qualification(leased)
    assert (
        qualified["implementation_files"]
        == leased["installation"]["implementation_files"]
    )


@pytest.mark.parametrize(
    "broken,mode,code",
    [
        ("graph", "PRODUCTION", "P0_OWNER_GRAPH_MISMATCH"),
        ("readback", "PRODUCTION", "P0_Q1_EXACT_READBACK_REQUIRED"),
        ("final_audit", "PRODUCTION", "P0_QUALIFICATION_EVIDENCE_MISSING"),
        ("independent_review", "PRODUCTION", "P0_QUALIFICATION_EVIDENCE_MISSING"),
        ("real_run", "PRODUCTION", "P0_QUALIFICATION_EVIDENCE_MISSING"),
        ("namespace", "PRODUCTION", "P0_RQ_BINDING_MISMATCH"),
        ("freeze", "PRODUCTION", "P0_RQ_BINDING_MISMATCH"),
        ("environment", "PRODUCTION", "P0_RQ_ENVIRONMENT_BINDING_MISMATCH"),
        ("test_bytes", "PRODUCTION", "P0_RQ_TEST_EVIDENCE_MISMATCH"),
        ("implementation", "PRODUCTION", "P0_QUALIFIED_IMPLEMENTATION_DRIFT"),
        ("expired_mandate", "QUALIFICATION_ONLY", "P0_CURRENT_AUTHORITY_REQUIRED"),
        (
            "qualifier_mandate_signature",
            "QUALIFICATION_ONLY",
            "TEST_ONLY_SIGNATURE_REJECTED",
        ),
    ],
)
def test_incomplete_or_conflicting_qualification_fails_closed(
    corpus, monkeypatch, broken, mode, code
):
    monkeypatch.setattr(module, "verify_cms", simulated_verify)
    with pytest.raises(ValidationError, match=code):
        module.LimitedMachineAuthority().verify_qualification(
            chain(corpus, mode=mode, broken=broken)
        )


def test_production_loader_rejects_owner_grant_for_auditor_outside_rq(
    corpus, tmp_path, monkeypatch
):
    """Exercise the actual loader, replacing only OS/CMS and the separately tested Q chain."""
    root = {
        "model_id": "BDB_NF02_P0_LIMITED_1",
        "root_id": identifier("installation_root"),
        "namespace_id": "TEST_ONLY_PROD",
        "owner_certificate_sha256": OWNER,
        "qualifier_certificate_sha256": QUALIFIER,
    }
    root["namespace_authority_digest"] = domain_hash("BDB-NF02-P0-NAMESPACE/1", root)
    roots = root_objects(corpus, root["namespace_authority_digest"])
    files = {**corpus.files, "ENVIRONMENT.json": transport({"TEST_ONLY": True})}
    code_root = Path(module.__file__).resolve().parents[1]
    code = [
        {
            "file": p.relative_to(code_root).as_posix(),
            "sha256": sha(p.read_bytes()),
            "bytes": p.stat().st_size,
        }
        for p in sorted(code_root.rglob("*"))
        if p.is_file() and p.suffix in {".py", ".json"}
    ]
    installation = {
        **corpus.bindings(),
        "mode": "PRODUCTION",
        "freeze_sha256": "5" * 64,
        "runtime_qualification_sha256": "6" * 64,
        "qualification_mandate_sha256": None,
        "installed_files": [
            {"file": n, "sha256": sha(raw), "bytes": len(raw)}
            for n, raw in sorted(files.items())
        ],
        "implementation_files": code,
        "namespace_authority_digest": root["namespace_authority_digest"],
        "external_schema_root_sha256": sha(
            files[BASE + "schemas/canonical/schema_registry__3.schema.json"]
        ),
        "coordinator_os_identity": {
            "sid": "S-1-5-21-1-2-3-1001",
            "privilege_class": "NON_ADMIN_SERVICE_ACCOUNT",
        },
        "initial_root_refs": [o.ref.as_dict() for _, o in sorted(roots.items())],
    }
    raw = transport(installation)
    root["installation_sha256"] = sha(raw)
    files.update(
        {
            "root.json": transport(root),
            "installation.json": raw,
            "installation.p7s": test_signature(raw, OWNER),
        }
    )
    grant = Vectors(corpus.schemas.documents).sample(
        corpus.schemas.documents["external/PRINCIPAL_GRANT__1"]
    )
    grant.update(
        installation_digest=sha(raw),
        certificate_sha256="9" * 64,
        role="AUDITOR",
        operations=["ACK_DELIVERY"],
    )
    grant_raw = transport(grant)
    files["grants/" + sha(grant_raw) + ".json"] = grant_raw
    files["grants/" + sha(grant_raw) + ".json.p7s"] = test_signature(grant_raw, OWNER)
    target = tmp_path / "TEST_ONLY_UNPROTECTED_ROOT"
    for name, data in files.items():
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    @contextmanager
    def locked(path, *, directory=False, check_acl=True):
        yield b"" if directory else path.read_bytes()

    monkeypatch.setattr(module, "machine_root", lambda: target)
    monkeypatch.setattr(module, "_locked_file", locked)
    monkeypatch.setattr(module, "_protected", lambda paths: None)
    monkeypatch.setattr(module, "verify_service", lambda *args: None)
    monkeypatch.setattr(module, "verify_environment", lambda *args: None)
    monkeypatch.setattr(module, "verify_cms", simulated_verify)
    monkeypatch.setattr(
        module.LimitedMachineAuthority,
        "verify_qualification",
        lambda *args: {"qualified_auditor_certificate_sha256": AUDITOR},
    )
    with pytest.raises(ValidationError, match="P0_RQ_AUDITOR_IDENTITY_MISMATCH"):
        with module.LimitedMachineAuthority().lease():
            pytest.fail(
                "Unqualified auditor must not become trusted through an owner grant"
            )
