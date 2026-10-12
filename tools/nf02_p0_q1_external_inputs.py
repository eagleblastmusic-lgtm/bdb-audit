"""Prepare an unsigned owner decision or verify supplied real public inputs.

No certificate/key/signature/qualification is issued. This tool never installs
machine authority or invokes Q2/RQ. Signing uses the owner's existing custody.
"""
import argparse
from pathlib import Path

from bdb_audit.history.limited_authority import verify_cms
from bdb_audit.history.limited_model import BASE, GRAPH_SHA
from bdb_audit.product_p0_cli import read_bounded
from tools.nf02_p0_q1_contexts import corpus
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_reference import valid, sha

LIMITS = [
    "Approve the separate BDB_NF02_P0_LIMITED_1 scope: 18 canonical contracts, 7 profiles, 43 schemas; all M01-M18 and Q1/Q2/RQ remain mandatory.",
    "Approve approved-Git-only empty-history bootstrap, fixed owner-approved source view/task and one EXTERNAL_AUDIT_RESULT slot; no legacy assurance transfer or migration.",
    "Accept nonblind external-host audit with possible prior knowledge; no blind/reset/zero-knowledge assurance.",
    "Accept auditor submission semantics without finding truth, Completion, STOP, release or full NF02 closure.",
    "Accept at-least-once delivery of identical bytes under the same release ID; no exactly-once network guarantee.",
    "Accept the explicit absence of a full-host rollback/independent monotonic-anchor guarantee; do not activate uses requiring that guarantee.",
    "This model decision does not grant runtime authority, assert Q1/Q2/RQ PASS or activate production import; actual qualification and separately signed installation/grants remain required.",
    "Preserve full R5.4.2, its 131-contract scope, approval, readers, history and evidence unchanged.",
]


def prepare(actor, output):
    c = corpus()
    body = {**c.bindings(), "scope_graph_sha256": GRAPH_SHA, "owner_actor_ref": actor,
            "decision": "APPROVE_LIMITED_P0_MODEL", "accepted_limits": LIMITS}
    raw = reference_a(body) + b"\n"
    assert raw == reference_b(body) + b"\n"
    assert valid(c.schemas.documents["external/OWNER_MODEL_DECISION__1"], body,
                 {d["$id"]: d for d in c.schemas.documents.values()})
    c.external("OWNER_MODEL_DECISION", raw)
    with output.open("xb") as stream:
        stream.write(raw)
    print(reference_a({"status": "PREPARED_UNSIGNED_NOT_AUTHORITY", "file": str(output),
                       "sha256": sha(raw), "bytes": len(raw), "sign_exact_file_bytes": True}).decode())


def verify(decision, signature, certificate, owner_pin, expected_sha256):
    c = corpus()
    raw = read_bounded(decision, 2 * 1024 * 1024)
    sig = read_bounded(signature, 2 * 1024 * 1024)
    der = read_bounded(certificate, 2 * 1024 * 1024)
    if sha(raw) != expected_sha256 or sha(der) != owner_pin:
        raise ValueError("Out-of-band exact decision/certificate identity mismatch")
    body = c.external("OWNER_MODEL_DECISION", raw)
    if body["scope_graph_sha256"] != GRAPH_SHA:
        raise ValueError("Owner graph mismatch")
    verify_cms(raw, sig, owner_pin)
    print(reference_a({"status": "REAL_OWNER_DECISION_SIGNATURE_READBACK_PASS_NOT_Q1_Q2_RQ", "owner_actor_ref": body["owner_actor_ref"],
        "decision_sha256": sha(raw), "signature_sha256": sha(sig), "owner_der_sha256": sha(der),
        "schema_sha256": sha(c.files[BASE + "schemas/external/OWNER_MODEL_DECISION__1.schema.json"]),
        "production_import": "BLOCKED", "authority_installed": False}).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="action", required=True)
    p = subs.add_parser("prepare-owner-decision")
    p.add_argument("--owner-actor-ref", required=True)
    p.add_argument("--output", type=Path, required=True)
    p = subs.add_parser("verify-owner-decision")
    p.add_argument("--decision", type=Path, required=True)
    p.add_argument("--signature", type=Path, required=True)
    p.add_argument("--certificate-der", type=Path, required=True)
    p.add_argument("--owner-pin", required=True)
    p.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    if args.action == "prepare-owner-decision":
        prepare(args.owner_actor_ref, args.output)
    else:
        verify(args.decision, args.signature, args.certificate_der, args.owner_pin, args.expected_sha256)
