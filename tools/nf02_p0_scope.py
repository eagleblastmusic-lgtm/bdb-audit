"""Reproduce the P0 dependency inventory without changing or qualifying R5.4.2.

This is a decision-packet tool, not an installation or qualification authority.
It traverses declared contract domains, including conditional references, and
checks retained build bytes. It does not perform 131 semantic contract reviews.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = Path("docs/R5_4_2/autonomous_2026_10_07")
OUTPUT = Path("docs/PRODUCT_V1/NF02_P0_SUCCESSOR_DEPENDENCIES.json")
# Operations explicitly required by the owner's P0 request, plus their installed
# bootstrap and durable command/commit/receipt context. No numeric target count.
ROOT_KINDS = {
    "assignment_package_binding": "exact assigned package authorization",
    "lane_result_admission_evidence": "authorized retained-result admission",
    "bdb_audit_lane_result": "later result derived from prior admission",
    "campaign_genesis": "new legal campaign; no backfill",
    "installation_bootstrap_profile": "eight independently installed initial pins",
    "artifact_contract_registry": "exact finite semantic registration",
    "schema_registry": "raw-backed executable schema authority",
    "policy_revision": "governing authorization and acceptance predicates",
    "spec_revision": "binding, STARTED and result chronology",
    "trust_profile": "independent producer, vault and recovery boundary",
    "source_identity": "independently resolved exact source identity",
    "command_envelope": "authenticated authority-changing request",
    "commit_body": "atomic single-writer accepted closure",
    "command_receipt": "durable command/commit binding and retry",
}


def read(relative: Path | str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def identity(relative: Path | str) -> dict[str, Any]:
    path = ROOT / relative
    raw = path.read_bytes()
    return {"file": Path(relative).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def walk(roots: list[str], adjacency: dict[str, list[dict[str, Any]]]) -> tuple[set[str], dict[str, Any]]:
    seen = set(roots)
    queue = deque(sorted(seen))
    witnesses: dict[str, Any] = {}
    while queue:
        source = queue.popleft()
        for edge in sorted(adjacency.get(source, []), key=lambda e: (e["to"], e["field"])):
            if edge["to"] not in seen:
                seen.add(edge["to"])
                witnesses[edge["to"]] = edge
                queue.append(edge["to"])
    return seen, witnesses


def check_report(report_path: Path, report: dict[str, Any]) -> dict[str, Any]:
    sources = report.get("source_inputs", report.get("sources", []))
    if isinstance(sources, dict):
        sources = [{"file": k, "raw_digest": v} for k, v in sources.items()]
    drift = []
    for source in sources:
        path = Path(source["file"])
        actual = identity(path)
        if actual["sha256"] != source["raw_digest"]:
            drift.append({"file": path.as_posix(), "expected": source["raw_digest"],
                          "observed": actual["sha256"]})
    return {"report": identity(report_path), "source_files_checked": len(sources),
            "source_drift": drift, "qualification": False}


def generate() -> dict[str, Any]:
    reg_report_path = EXECUTION / "REGISTRY_BUILD_CANDIDATE_READBACK.json"
    reg_report = read(reg_report_path)
    reg_path = EXECUTION / reg_report["file"]
    registry = read(reg_path)
    assert identity(reg_path)["sha256"] == reg_report["raw_digest"]
    rows = {r["kind"] + "/" + r["version"]: r for r in registry["contracts"]}
    assert len(rows) == len(registry["contracts"]), "duplicate contract key"
    roots = sorted(key for key, row in rows.items() if row["kind"] in ROOT_KINDS)
    assert {rows[key]["kind"] for key in roots} == set(ROOT_KINDS)
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for key, row in rows.items():
        adjacency[key] = []
        for ref in row["material_refs"]:
            for target in ref.get("allowed_keys", []):
                assert target in rows, (key, ref["field"], target)
                adjacency[key].append({"from": key, "field": ref["field"], "to": target,
                                       "ref_class": ref["ref_class"],
                                       "cardinality": ref["cardinality"]})
    closure, witnesses = walk(roots, adjacency)
    profiles = read(EXECUTION / "design/EXTERNAL_PROFILE_CONTRACTS.json")
    wire = {key: value.get("wire_profile_id", key) for key, value in profiles.items()}
    assert len(set(wire.values())) == len(wire), "profile wire identity collision"
    used_profiles = {p for key in closure for ref in rows[key]["material_refs"]
                     for p in ref.get("profile_contracts", [])}
    assert used_profiles <= set(wire.values())
    profile_rules = read(EXECUTION / "design/PROFILE_REFERENCE_CONTRACTS.json")
    profile_adjacency: dict[str, list[dict[str, Any]]] = {}
    profile_refs = []
    for ref in profile_rules["material_refs"]:
        owner = wire.get(ref["owner"], ref["owner"])
        targets = [wire.get(target, target) for target in ref["targets"]]
        profile_refs.append({**ref, "owner": owner, "targets": targets})
        for target in targets:
            if target in wire.values():
                profile_adjacency.setdefault(owner, []).append(
                    {"from": owner, "field": ref["field"], "to": target})
    for name, contract in profiles.items():
        for target in contract["dependencies"]:
            target = wire.get(target, target)
            if target in wire.values():
                profile_adjacency.setdefault(wire[name], []).append(
                    {"from": wire[name], "field": "declared_profile_dependencies", "to": target})
    profile_closure, profile_witnesses = walk(sorted(used_profiles), profile_adjacency)
    build_path = EXECUTION / "BUILD_TIME_CANDIDATE_READBACK.json"
    build = read(build_path)
    schemas = {}
    schema_bytes_checked = 0
    for entry in build["entries"]:
        schema_path = Path(build["directory"]) / entry["file"]
        actual = identity(schema_path)
        assert actual["sha256"] == entry["raw_digest"], schema_path
        assert actual["bytes"] == entry["byte_length"], schema_path
        body = read(schema_path)
        assert body["$id"] == entry["$id"] and body["$schema"] == entry["dialect"]
        assert entry["$id"] not in schemas
        schemas[entry["$id"]] = entry
        schema_bytes_checked += actual["bytes"]
    schema_roots = ["BDB_SCHEMA_REGISTRY::" + key for key in closure]
    schema_roots += ["BDB_EXTERNAL_PROFILE_SCHEMA::" + key for key in profile_closure]
    schema_adjacency: dict[str, list[dict[str, Any]]] = {}
    for schema_id, entry in schemas.items():
        for dependency in entry["dependency_closure"]:
            target = dependency["$id"]
            assert target in schemas, (schema_id, target)
            assert schemas[target]["raw_digest"] == dependency["raw_digest"]
            assert schemas[target]["file"] == dependency["file"]
            schema_adjacency.setdefault(schema_id, []).append(
                {"from": schema_id, "field": "dependency_closure", "to": target})
    # Raw validation consumes the payload grammar pinned by each raw profile.
    # A profile's JSON schema does not itself $ref that separately retained schema.
    for name, contract in profiles.items():
        if wire[name] in profile_closure and "payload_grammar" in contract:
            schema_id = "BDB_EXTERNAL_PROFILE_SCHEMA::" + wire[name]
            target = "BDB_RAW_PAYLOAD_SCHEMA::" + wire[name]
            assert target in schemas, (name, target)
            schema_adjacency.setdefault(schema_id, []).append(
                {"from": schema_id, "field": "payload_schema_ref / payload_grammar", "to": target})
    schema_closure, schema_witnesses = walk(schema_roots, schema_adjacency)
    assert set(schema_roots) <= set(schemas)
    mapping_path = EXECUTION / "design/VERSION_IMPACT_PLAN.json"
    mapping_report = read(mapping_path)
    mapping = mapping_report["mapping"]
    assert set(mapping.values()) == set(rows)
    old_path = Path("docs/R5_4_1/candidate/BDB_AUDIT_V2_ARTIFACT_CONTRACT_REGISTRY_R5_4.json")
    old = read(old_path)
    old_keys = {r["kind"] + "/" + r["version"] for r in old["contracts"]}
    old_kinds = {r["kind"] for r in old["contracts"]}
    classification = {}
    for key in closure:
        classification[key] = ("SAME_PREDECESSOR_CONTRACT_KEY" if key in old_keys else
                               "SUCCESSOR_VERSION" if rows[key]["kind"] in old_kinds else "NEW_KIND")
    own_path = EXECUTION / "OWN_REFERENCE_RESOLUTIONS.json"
    own_nodes = {n["key"]: n for n in read(own_path)["nodes"]}
    inverse = {target: source for source, target in mapping.items()}
    contracts = []
    for key in sorted(closure):
        row = rows[key]
        source_key = inverse[key]
        node = own_nodes[source_key]
        section = node["source_section"]
        source = ({k: v for k, v in section.items() if k != "complete_section_text"}
                  if section is not None else
                  {"file": node["body"].get("file"), "section": node["body"].get("section"),
                   "raw_digest": node["body"].get("source_raw_digest"),
                   "status": "UNQUALIFIED_PROPOSED_BODY; no complete inherited normative section"})
        contracts.append({"key": key, "source_design_key": source_key,
                          "predecessor_kind_versions": sorted(k for k in old_keys if k.split('/')[0] == row['kind']),
                          "change_class": classification[key], "version_decision": mapping_report["decisions"].get(source_key),
                          "normative_source": source, "canonical_role": row["canonical_role"],
                          "producer_authority": row["producer_authority"],
                          "required_validation_layers": row["required_validation_layers"],
                          "schema_id": row["schema_ref"], "material_refs": row["material_refs"],
                          "reachability": {"root_reason": ROOT_KINDS[row["kind"]]} if key in roots else witnesses[key]})
    approved_graph_path = Path("docs/R5_4_2/R5_4_2_SEMANTIC_CLOSURE_GRAPH.json")
    approved = read(approved_graph_path)
    approved_rows = {n["key"]: n for n in approved["nodes"]}
    approved_roots = [key for key, node in approved_rows.items() if node['kind'] in ROOT_KINDS]
    approved_adj: dict[str, list[dict[str, Any]]] = {}
    for edge in approved["edges"]:
        assert edge['from'] in approved_rows and edge['to'] in approved_rows
        approved_adj.setdefault(edge["from"], []).append(edge)
    approved_closure, _ = walk(approved_roots, approved_adj)
    reports = [reg_report_path, build_path, EXECUTION / "SCHEMA_REGISTRY_BUILD_READBACK.json",
               EXECUTION / "INITIAL_PROTOCOL_BUILD_READBACK.json",
               EXECUTION / "NORMATIVE_BUILD_CANDIDATE_READBACK.json",
               EXECUTION / "GOLDEN_BUILD_CANDIDATE_READBACK.json"]
    source_checks = [check_report(path, read(path)) for path in reports]
    inputs = [Path("tools/nf02_p0_scope.py"), approved_graph_path,
              Path("docs/R5_4_2/OWNER_R5_4_2_SEMANTIC_CLOSURE_APPROVAL.json"),
              Path("docs/R5_4_2/OWNER_DELEGATED_DECISION_REGISTER.md"), reg_path,
              old_path, mapping_path, own_path, EXECUTION / "design/EXTERNAL_PROFILE_CONTRACTS.json",
              EXECUTION / "design/PROFILE_REFERENCE_CONTRACTS.json",
              EXECUTION / "design/PAYLOAD_REFERENCE_CONTRACTS.json", *reports]
    broad_domains = []
    for key in sorted(closure):
        for ref in rows[key]["material_refs"]:
            if len(ref.get("allowed_keys", [])) == len(rows):
                broad_domains.append({"owner": key, "field": ref["field"],
                                      "target_count": len(ref["allowed_keys"]),
                                      "ref_class": ref["ref_class"]})
    payload_refs = read(EXECUTION / "design/PAYLOAD_REFERENCE_CONTRACTS.json")["material_refs"]
    wire_payload_refs = [{**r, "targets": [mapping.get(t, wire.get(t, t)) for t in r["targets"]]}
                         for r in payload_refs]
    schema_entries = [{"$id": sid, **identity(Path(build["directory"]) / schemas[sid]["file"]),
                       "dialect": schemas[sid]["dialect"],
                       "dependency_ids": [d["$id"] for d in schemas[sid]["dependency_closure"]],
                       "reachability": "CONTRACT_OR_PROFILE_ROOT" if sid in schema_roots else schema_witnesses[sid]}
                      for sid in sorted(schema_closure)]
    return {
        "record_type": "BDB_NF02_P0_SUCCESSOR_SCOPE_ANALYSIS/1",
        "status": "DECISION_REQUIRED_CLOSURE_REACHES_FULL_R5_4_2_DOMAIN",
        "authority": "PREPARATION_ONLY; not normative approval, Q1/Q2, installation or runtime authority",
        "method": "Transitive whole-contract allowed-key/profile/schema dependency domains; conditional references retained. No semantic review or runtime instance witness is inferred.",
        "inputs": [identity(path) for path in dict.fromkeys(inputs)],
        "approved_R5_4_2": {"roots": sorted(approved_roots),
                               "reachable": sorted(approved_closure),
                               "registered_total": len(approved_rows),
                               "excluded": sorted(set(approved_rows) - approved_closure)},
        "current_unqualified_draft": {"roots": roots, "registered_total": len(rows),
                                       "excluded": sorted(set(rows) - closure),
                                       "schema_build_directory": build["directory"],
                                       "semantic_parity_pending_nodes": build["semantic_pending_nodes"],
                                       "inherited_schema_parity_pending": build["inherited_schema_parity_pending"]},
        "counts": {"canonical_contracts": len(closure), "canonical_edges": sum(len(adjacency[k]) for k in closure),
                   "profile_contracts": len(profile_closure),
                   "schema_files": len(schema_closure),
                   "schema_groups": dict(sorted(Counter(s.split("::")[0] for s in schema_closure).items())),
                   "schema_files_verified": len(schemas), "schema_bytes_verified": schema_bytes_checked,
                   "version_classes": dict(sorted(Counter(classification.values()).items()))},
        "whole_domain_reference_fields": broad_domains,
        "contracts": contracts,
        "profile_contracts": [{"design_id": key, "wire_id": wire[key],
                                "declared_dependencies": profiles[key]["dependencies"],
                                "root": wire[key] in used_profiles,
                                "witness": profile_witnesses.get(wire[key]),
                                "rule_source": "design/EXTERNAL_PROFILE_CONTRACTS.json"}
                               for key in sorted(wire) if wire[key] in profile_closure],
        "profile_material_refs": [r for r in profile_refs if r["owner"] in profile_closure],
        "payload_material_refs": wire_payload_refs,
        "schemas": schema_entries,
        "global_invariants": registry["global_invariants"],
        "source_readback_checks": source_checks,
        "qualification": {"Q1": "NOT_PERFORMED", "Q2": "NOT_PERFORMED", "semantic_fixed_point": False,
                          "independent_authority_established": False, "production_import": "BLOCKED",
                          "full_131_semantic_review_started": False},
        "decision_boundary": "Reducing this existing model requires an explicitly approved restricted normative successor and a fresh closure; current strategic approval does not approve that change.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare the retained decision inventory")
    args = parser.parse_args()
    result = generate()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        assert (ROOT / OUTPUT).read_bytes() == raw, "decision inventory drift"
    else:
        (ROOT / OUTPUT).write_bytes(raw)
    print(json.dumps({"output": OUTPUT.as_posix(), "bytes": len(raw), "counts": result["counts"],
                      "approved_closure": len(result["approved_R5_4_2"]["reachable"]),
                      "source_drift_count": sum(len(c["source_drift"]) for c in result["source_readback_checks"]),
                      "qualification": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
