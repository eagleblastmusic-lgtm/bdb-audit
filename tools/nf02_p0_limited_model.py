"""Build/check one proposed bounded NF02 P0 model; never qualify or install it."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL"
MODEL_ID = "BDB_NF02_P0_LIMITED_1"
DIALECT = "https://json-schema.org/draft/2020-12/schema"
COMMON = "urn:bdb:p0:wire:COMMON/1"
ADR = "F1_QUALIFICATION/inputs/ADR-006_CANONICAL_SERIALIZATION_AND_IDENTITY_PROFILE.md"
PREFIX = "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/"
KINDS = {
    "artifact_contract_registry": "2", "schema_registry": "3", "policy_revision": "3",
    "spec_revision": "3", "trust_profile": "3", "installation_bootstrap_profile": "2",
    "nf02_p0_source_snapshot": "1", "campaign_genesis": "3", "attempt": "3",
    "assignment_manifest": "3", "assignment_package_binding": "3", "nf02_p0_delivery": "1",
    "lane_result_admission_evidence": "4", "bdb_audit_lane_result": "4", "nf02_p0_abort": "1",
    "command_envelope": "3", "commit_body": "3", "command_receipt": "3",
}
PROFILES: dict[str, dict[str, Any]] = {
    "BDB_CJSON_1": {"purpose": "Unchanged ADR-006 serialization and domain-separated identity",
        "rules": ["UTF8_NO_BOM", "NO_FLOATS_OR_DUPLICATE_KEYS", "EXACT_RAW_SHA256",
                  "UNCHANGED_BDB_OBJECT_DIGEST_1", "COMMIT_HASH_EQUALS_COMMIT_BODY_OBJECT_DIGEST"]},
    "P0_AUTHORIZATION_V1": {"purpose": "Independent protected root and exact principal/operation/context rights",
        "rules": ["READ_ONLY_MACHINE_ROOT", "OWNER_AND_QUALIFIER_DISTINCT_FROM_AUDITOR",
                  "CMS_SHA256_EXACT_CERTIFICATE_PIN", "CURRENT_SCOPE_AND_REVOCATION_LEASE",
                  "SIGN_COMMAND_MODEL_INSTALLATION_NAMESPACE_SCOPE", "NO_CALLER_ROOT_OR_ISSUER"]},
    "P0_BOOTSTRAP_SOURCE_V1": {"purpose": "New empty history from independently approved Git source",
        "rules": ["GIT_COMMIT_AND_TREE_VERIFIED_SEPARATELY", "ACTUAL_SOURCE_MANIFEST_SHA256",
                  "OWNER_APPROVED_REPOSITORY_SOURCE_AND_VIEW", "NO_LEGACY_ASSURANCE_TRANSFER",
                  "EXTERNAL_SCHEMA_ROOT_FIRST", "EXACT_EIGHT_INITIAL_PINS", "ONE_CONTENT_KAHN_SORT"]},
    "P0_PACKAGE_TRANSPORT_V1": {"purpose": "Bound exact package; sole fixed approved input view",
        "quotas": {"archive_bytes": 67108864, "members": 2048, "member_bytes": 33554432, "expanded_bytes": 67108864, "json_bytes": 2097152, "json_depth": 32},
        "rules": ["ZIP_STORED_FIXED_METADATA", "ASCII_SORTED_SAFE_MEMBER_PATHS",
                  "EXACT_MANIFEST_MEMBER_SHA256_AND_LENGTH", "EXACT_APPROVED_VIEW_PLUS_TASK",
                  "NO_SEMANTIC_CHECKSUM_ALIAS", "NO_REPACK_SUBSTITUTION"]},
    "P0_RESULT_TRANSPORT_V1": {"purpose": "Retained original ZIP and finite deterministic result normalization",
        "quotas": {"archive_bytes": 33554432, "members": 2048, "member_bytes": 16777216, "expanded_bytes": 33554432, "json_bytes": 2097152, "json_depth": 32},
        "rules": ["BOUNDED_STRICT_JSON_AND_ZIP", "EXACT_ASSIGNMENT_SOURCE_BINDING_DELIVERY_SLOT",
                  "AUDITOR_SIGNED_RETURN_NOT_SELF_AUTHORITY", "ORIGINAL_BYTES_RETAINED",
                  "RESULT_EQUALS_CJSON_NORMALIZATION", "FINDINGS_ARE_UNQUALIFIED_SUBMISSIONS"]},
    "P0_EXECUTION_ISOLATION_V1": {"purpose": "Separate external host; approved fixed view; non-blind audit",
        "rules": ["NO_EXECUTOR_ACCESS_TO_COORDINATOR_CODE_ROOT_OR_VAULT",
                  "NON_ADMIN_COORDINATOR_CANNOT_WRITE_INSTALLATION_ROOT_OR_CODE",
                  "QUALIFIED_CONFIGURED_TRANSPORT_AND_PRINCIPAL", "SOURCE_ONLY_APPROVED_VIEW",
                  "NO_BLINDNESS_OR_NO_PRIOR_KNOWLEDGE_CLAIM", "NO_RESULT_CODE_EXECUTION"]},
    "P0_HISTORY_RECOVERY_V1": {"purpose": "Single-writer chronological accepted history and durable retry",
        "rules": ["ATOMIC_HEAD_OBJECT_RAW_RECEIPT_CAS", "EXACT_PRIOR_REFS_AND_CUT",
                  "BIND_THEN_LATER_START_THEN_DELIVERY_THEN_EVIDENCE_THEN_RESULT",
                  "NO_MISSING_RAW_REPAIR_OR_BACKFILL", "CURRENT_AUTHORITY_FOR_NEW_WRITES",
                  "AT_LEAST_ONCE_SAME_BYTES_DELIVERY", "NO_FULL_HOST_ROLLBACK_GUARANTEE"]},
}
for _transport_profile in ["P0_PACKAGE_TRANSPORT_V1", "P0_RESULT_TRANSPORT_V1"]:
    PROFILES[_transport_profile]["mime_mapping"] = {
        ".json": "application/json", ".md": "text/markdown", ".txt": "text/plain",
        ".log": "text/plain", ".png": "image/png", "default": "application/octet-stream"}
S = {"type": "string", "minLength": 1, "maxLength": 4096}
SHA = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
OID = {"type": "string", "pattern": "^([0-9a-f]{40}|[0-9a-f]{64})$"}
UTC = {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"}
N = {"type": "integer", "minimum": 0, "maximum": 9007199254740991}
PATH = {"type": "string", "maxLength": 512,
        "pattern": "^[A-Za-z0-9_-]+(?:[.][A-Za-z0-9_-]+)*(?:/[A-Za-z0-9_-]+(?:[.][A-Za-z0-9_-]+)*)*$"}
SCHEMA_NODES: dict[str, dict[str, Any]] = {}
CONTRACTS: dict[str, dict[str, Any]] = {}
QUALIFICATION_CASES = {
    "Q1": {
        "Q1-01": "Exact normative/machine manifests, complete membership and readback; zero unexplained mismatches",
        "Q1-02": "All 18 body/Registry field-target/predicate/schema definitions agree; no hidden target or alias",
        "Q1-03": "All 7 profiles and 43 offline schemas plus every inline representation and external prerequisite have closed dependencies",
        "Q1-04": "Every allowed command/event/state/retry branch is accounted for; excluded operations are explicit denials",
        "Q1-05": "Positive and wrong-kind/version/extra-field/bounds/schema-revision cases for every schema and nested union",
        "Q1-06": "CJSON/RawDigest/ObjectDigest/commit-hash fixtures verified by two independent reference procedures",
        "Q1-07": "DAG dependency order, Kahn tie-break, duplicates, cycles, self/future refs and prior-only rules",
        "Q1-08": "Eight external initial pins, source/view/task authority, root-schema precedence and empty-history bootstrap",
        "Q1-09": "Separate Q1/Q2/runtime roles and exact signed inputs; qualification mode cannot become production by caller choice",
        "Q1-10": "Compatibility and non-guarantees reviewed; unchanged R5.4.2 and historical bytes/readers proven",
        "Q1-11": "Final retained audit covers all predicates and cases; author record is external and not independent assurance",
    },
    "Q2": {
        "Q2-01": "Genuinely independent authorized reviewer verifies exact approved candidate and both manifests",
        "Q2-02": "Independent semantic review of all 18 contracts/7 profiles/43 schemas and all normative clauses",
        "Q2-03": "Independent adversarial assessment of authority, finite dispatch, bootstrap and isolation boundaries",
        "Q2-04": "Every Q1 finding closed or explicit owner-approved limit; no hidden safety exception",
        "Q2-05": "Independent review binds retained evidence and author record; owner risk/compatibility decision binds same bytes",
        "Q2-06": "Authorized external FREEZE; code/install/runtime remain unqualified and blocked until runtime gate",
    },
    "RQ": {
        "RQ-01": "Real owner/qualifier/auditor identification, independent certificate provisioning and separated private keys",
        "RQ-02": "Non-admin service cannot modify installation root/code; executor cannot modify root/code/DB/vault/outbox",
        "RQ-03": "CMS wrong signer/body/domain/installation/namespace/context/algorithm/expiry and revoked/missing rights deny",
        "RQ-04": "Root/grant/code/storage replacement, reparse, rename and revocation races fail closed under leases",
        "RQ-05": "Frozen model/code/schema bytes verified on install and restart; incomplete/drifting qualification denied",
        "RQ-06": "Qualification mandate is independently signed, isolated, time-scoped; production denied before RQ and cross-mode transfer denied",
        "RQ-07": "Real authorized Git repository commit/tree/blob types, algorithm and complete approved source view match",
        "RQ-08": "Unsupported path/mode/submodule/LFS and omitted/substituted/extra source/task members deny without history change",
        "RQ-09": "Real empty-history bootstrap checks all eight pins and dependency order; replayed bootstrap/post-genesis roots deny",
        "RQ-10": "Assignment and retry after authorized abort use exact source/task/auditor/slot; one active attempt and no retry after result",
        "RQ-11": "Package exact SHA256/length/members/metadata; substituted or repacked ZIP denies without history mutation",
        "RQ-12": "Binding accepted before distinct START; missing/same-commit/reordered/wrong-context/duplicate START denied",
        "RQ-13": "Real configured external-host transport releases retained bound bytes under current rights/state",
        "RQ-14": "No public callback chooses trusted destination or marks SENT; fake ACK and wrong auditor/source/slot/package denied",
        "RQ-15": "Delivery crash/retry/ACK loss preserves same release ID and bytes; actual at-least-once limits verified",
        "RQ-16": "Genuine independently observed external audit execution and signed exact ZIP return with actual report",
        "RQ-17": "Raw ZIP, signature, return and authorization trace durable before acceptance; corruption/missing raw deny on replay",
        "RQ-18": "ZIP traversal/aliases/duplicates/encryption/metadata/bomb/quotas and strict JSON duplicate/float/surrogate/bounds rejected",
        "RQ-19": "Evidence after prior acknowledged delivery; result after prior evidence; same-commit chain/cut laundering denied",
        "RQ-20": "Full campaign/attempt/assignment/source/slot/binding/start/delivery/raw/profile/cut join rejects every substitution",
        "RQ-21": "Original retained result ZIP is reread and deterministically normalized; modified payload/path/report/claims denied",
        "RQ-22": "One evidence/result per slot; result cannot grant finding truth, completion, STOP, release or full NF02 closure",
        "RQ-23": "Owner-authorized abort preserves all facts/raw; revoked auditor cannot abort or reuse old attempt for new result",
        "RQ-24": "Current role/scope rights immediately before COMMIT and delivery; changed authority denies without accepted mutation",
        "RQ-25": "Byte-for-byte no-history-mutation checks for all denied commands/events/raw and each public/direct entry point",
        "RQ-26": "Atomic single Store CAS: concurrent equal retry, competing bind/result and mismatched command ID have one correct outcome",
        "RQ-27": "Real process termination/power-loss-equivalent durability boundaries: raw/object/commit/receipt/head all or none",
        "RQ-28": "New-process restart and complete replay reverify stored raw/command CMS/installation/grant context and receipts",
        "RQ-29": "Exact command retry returns original receipt without append; conflicting bytes/current missing rights denied",
        "RQ-30": "Generic Store, E1 inbox, typed events/generators, installed standalone and alternate CLI cannot bypass same predicates",
        "RQ-31": "Historical readers/materials preserved; model/profile/schema/namespace mismatch never falls back to older path",
        "RQ-32": "Actual production-equivalent OS/runtime/code/dependencies/external transport and auditor boundary included in signed RQ evidence",
    },
}


def arr(item: Any, *, minimum: int = 0, maximum: int = 4096) -> dict[str, Any]:
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum, "uniqueItems": True}


def obj(fields: dict[str, Any], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": fields,
            "required": sorted(set(fields) - set(optional)), "additionalProperties": False}


def typ(name: str) -> dict[str, Any]:
    return {"$ref": COMMON + "#/$defs/" + name}


def ref(*kinds: str) -> dict[str, Any]:
    assert set(kinds) <= set(KINDS)
    return {"allOf": [typ("TypedRef"), {"properties": {"kind": {"enum": list(kinds)}}}]}


def pin(profile: str) -> dict[str, Any]:
    assert profile in PROFILES
    return {"allOf": [typ("ProfileRef"), {"properties": {"profile_id": {"const": profile}}}]}


def raw(profile: str, media: str) -> dict[str, Any]:
    return {"allOf": [typ("RawRef"), {"properties": {"media_type": {"const": media},
                              "artifact_contract_ref": pin(profile)}}]}


def register(key: str, category: str, schema: dict[str, Any], *, deps: list[str] | None = None) -> None:
    SCHEMA_NODES[key] = {"category": category, "schema": {"$schema": DIALECT, "$id": key, **schema},
                         "semantic_dependencies": deps or []}


def canonical(kind: str, fields: dict[str, Any], *, refs: dict[str, tuple[list[str], str]],
              profiles: list[str], predicates: list[str], optional: tuple[str, ...] = (), role: str = "FACT") -> None:
    key = kind + "/" + KINDS[kind]
    sid = "urn:bdb:p0:canonical:" + key
    body = obj({"object_id": {"allOf": [typ("LogicalId"), {"pattern": "^" + kind + "_"}]},
                "model_id": {"const": MODEL_ID}, **fields}, optional)
    dependencies = [COMMON, *["urn:bdb:p0:profile:" + p for p in profiles]]
    for targets, _ in refs.values():
        dependencies.extend("urn:bdb:p0:canonical:" + t + "/" + KINDS[t] for t in targets)
    register(sid, "canonical", body, deps=sorted(set(dependencies)))
    CONTRACTS[key] = {"kind": kind, "version": KINDS[kind], "schema_id": sid, "canonical_role": role,
                      "reference_contract_mode": "EXPLICIT_COMPLETE",
                      "material_refs": [{"field": f, "allowed_keys": [k + "/" + KINDS[k] for k in ts],
                                         "ref_class": rc} for f, (ts, rc) in refs.items()],
                      "profiles": profiles, "predicates": predicates,
                      "producer_authority": "INDEPENDENTLY_AUTHORIZED_COORDINATOR",
                      "body": body}


def construct() -> dict[str, Any]:
    SCHEMA_NODES.clear()
    CONTRACTS.clear()
    schema_ids = ["urn:bdb:p0:canonical:" + k + "/" + v for k, v in KINDS.items()]
    typed_ref = obj({"kind": {"enum": sorted(KINDS)}, "version": {"type": "string"},
                     "revision_digest": SHA, "schema_revision_ref": obj({"schema_id": {"enum": schema_ids}, "raw_digest": SHA}),
                     "digest_profile": {"const": "BDB-OBJECT-DIGEST-1"}, "logical_id": typ("LogicalId")})
    typed_ref["oneOf"] = [{"properties": {"kind": {"const": k}, "version": {"const": v},
                                         "logical_id": {"pattern": "^" + k + "_"},
                                         "schema_revision_ref": {"properties": {"schema_id": {"const": "urn:bdb:p0:canonical:" + k + "/" + v}}}}}
                          for k, v in KINDS.items()]
    defs = {
        "LogicalId": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,63}_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
        "TypedRef": typed_ref,
        "ProfileRef": obj({"profile_id": {"enum": sorted(PROFILES)}, "revision_digest": SHA}),
        "RawRef": obj({"raw_digest": SHA, "byte_length": N, "media_type": S, "artifact_contract_ref": typ("ProfileRef")}),
        "Head": obj({"campaign_id": typ("LogicalId"), "commit_seq": {**N, "minimum": 1}, "commit_hash": SHA}),
        "HistoryCut": obj({"head": typ("Head"), "policy_ref": ref("policy_revision"), "spec_ref": ref("spec_revision"),
                            "schema_registry_ref": ref("schema_registry"), "source_ref": ref("nf02_p0_source_snapshot")}),
        "EventId": obj({"commit_hash": SHA, "ordinal": N}),
        "FileEntry": obj({"file": PATH, "sha256": SHA, "bytes": N}),
        "Member": obj({"path": PATH, "sha256": SHA, "bytes": N, "media_type": S}),
        "State": {"enum": ["ASSIGNED", "BOUND", "STARTED", "DELIVERED", "EVIDENCE_ACCEPTED", "RESULT_ACCEPTED", "ABORTED"]},
    }
    # The shared wire declares all subordinate representations openly. Field-
    # specific refs in each body narrow its finite TypedRef union.
    register(COMMON, "wire", {"$defs": defs, "not": {}})
    for p, value in PROFILES.items():
        register("urn:bdb:p0:profile:" + p, "profile", {"const": {"profile_id": p, **value}})

    roots = ["artifact_contract_registry", "schema_registry", "policy_revision", "spec_revision", "trust_profile", "installation_bootstrap_profile"]
    core = ["BDB_CJSON_1", "P0_AUTHORIZATION_V1", "P0_HISTORY_RECOVERY_V1"]
    canonical("artifact_contract_registry", {"contracts": arr({"enum": sorted(k + "/" + v for k, v in KINDS.items())}, minimum=18, maximum=18),
              "model_descriptor_raw_ref": raw("BDB_CJSON_1", "application/json")},
              refs={}, profiles=["BDB_CJSON_1"], predicates=["REGISTRY_EXACT_18_KEYS_AND_FIELD_TARGETS", "NO_EXTENSIONS_OR_GENERIC_ARTIFACT_DISPATCH"], role="TRUST_ROOT")
    canonical("schema_registry", {"registry_ref": ref("artifact_contract_registry"),
              "bindings": arr(obj({"schema_id": {"enum": ["urn:bdb:p0:canonical:" + k + "/" + v for k, v in KINDS.items()]},
                                   "schema_raw_ref": raw("BDB_CJSON_1", "application/schema+json")}), minimum=18, maximum=18)},
              refs={"registry_ref": (["artifact_contract_registry"], "PINNED_INSTALLATION")}, profiles=["BDB_CJSON_1"],
              predicates=["EXTERNAL_ROOT_SCHEMA_BEFORE_REGISTRY", "EXACT_UNIQUE_SORTED_BINDINGS_FOR_ALL_18", "RAW_BYTES_ID_LENGTH_DIALECT_AND_OFFLINE_DEPENDENCIES"])
    canonical("policy_revision", {"authorization_profile_ref": pin("P0_AUTHORIZATION_V1"),
              "recovery_profile_ref": pin("P0_HISTORY_RECOVERY_V1"), "allowed_model": {"const": MODEL_ID}},
              refs={}, profiles=core, predicates=["EXACT_FIXED_OPERATION_DOMAIN", "DENY_LEGACY_GENERIC_TRANSITION_COMPLETION_STOP_RELEASE"])
    canonical("spec_revision", {"source_profile_ref": pin("P0_BOOTSTRAP_SOURCE_V1"), "package_profile_ref": pin("P0_PACKAGE_TRANSPORT_V1"),
              "result_profile_ref": pin("P0_RESULT_TRANSPORT_V1"), "history_profile_ref": pin("P0_HISTORY_RECOVERY_V1")},
              refs={}, profiles=list(PROFILES), predicates=["EXACT_OPERATION_FACT_EVENT_AND_FSM_TABLE", "NO_VERSION_FALLBACK"])
    canonical("trust_profile", {"authorization_profile_ref": pin("P0_AUTHORIZATION_V1"), "isolation_profile_ref": pin("P0_EXECUTION_ISOLATION_V1"),
              "executor_write_boundary": {"const": "SEPARATE_EXTERNAL_HOST_NO_COORDINATOR_ROOT_CODE_VAULT_WRITE"},
              "assurance": {"const": "CONTROLLED_VIEW_NON_BLIND_PROVENANCE_ONLY"},
              "explicit_non_guarantees": {"const": ["NO_FINDING_TRUTH_QUALIFICATION", "NO_BLINDNESS_OR_ZERO_KNOWLEDGE", "FULL_HOST_ROLLBACK_NOT_DETECTED"]}},
              refs={}, profiles=core + ["P0_EXECUTION_ISOLATION_V1"], predicates=["ACTUAL_QUALIFIED_BOUNDARY_AND_CURRENT_GRANT", "DECLARATIONS_ARE_NOT_AUTHORITY"])
    canonical("installation_bootstrap_profile", {"registry_ref": ref("artifact_contract_registry"), "schema_registry_ref": ref("schema_registry"),
              "policy_ref": ref("policy_revision"), "spec_ref": ref("spec_revision"), "trust_ref": ref("trust_profile"),
              "serialization_profile_ref": pin("BDB_CJSON_1"), "source_profile_ref": pin("P0_BOOTSTRAP_SOURCE_V1"),
              "namespace_authority_digest": SHA, "initial_command": {"const": "INITIALIZE_P0_FROM_APPROVED_GIT"}},
              refs={f: ([k], "PINNED_INSTALLATION") for f, k in [("registry_ref", "artifact_contract_registry"), ("schema_registry_ref", "schema_registry"),
                    ("policy_ref", "policy_revision"), ("spec_ref", "spec_revision"), ("trust_ref", "trust_profile")]},
              profiles=core + ["P0_BOOTSTRAP_SOURCE_V1"], predicates=["EXACT_EIGHT_INITIAL_PINS", "INDEPENDENT_INSTALLATION_NOT_CALLER_NAMESPACE"])
    canonical("nf02_p0_source_snapshot", {"repository_authority_digest": SHA, "repository_id": S,
              "git_object_algorithm": {"enum": ["sha1", "sha256"]}, "git_commit_object_id": OID,
              "git_tree_object_id": OID, "source_manifest_raw_ref": raw("P0_BOOTSTRAP_SOURCE_V1", "application/json"),
              "source_archive_raw_ref": raw("P0_BOOTSTRAP_SOURCE_V1", "application/zip"), "approved_view_digest": SHA},
              refs={}, profiles=["BDB_CJSON_1", "P0_BOOTSTRAP_SOURCE_V1", "P0_EXECUTION_ISOLATION_V1"],
              predicates=["OWNER_APPROVED_SOURCE_SCOPE_BEFORE_GENESIS", "REAL_RESOLVER_COMMIT_TREE_TYPES_AND_BYTES", "COMPLETE_SAFE_SOURCE_MANIFEST_AND_VIEW"])
    canonical("campaign_genesis", {"campaign_id": typ("LogicalId"), "mode": {"enum": ["QUALIFICATION_ONLY", "PRODUCTION"]},
              "task_raw_ref": raw("P0_PACKAGE_TRANSPORT_V1", "text/markdown"),
              "installation_ref": ref("installation_bootstrap_profile"), "source_ref": ref("nf02_p0_source_snapshot"), "namespace_authority_digest": SHA},
              refs={"installation_ref": (["installation_bootstrap_profile"], "PINNED_INSTALLATION"), "source_ref": (["nf02_p0_source_snapshot"], "CONTENT_AT_INITIALIZATION_ONLY")},
              profiles=core + ["P0_BOOTSTRAP_SOURCE_V1", "P0_PACKAGE_TRANSPORT_V1"], predicates=["SEQ_ONE_EMPTY_HISTORY_ONLY", "ONE_FIXED_SOURCE_TASK_AND_RESULT_SLOT", "Q1_FREEZE_AND_MODE_APPROPRIATE_EXTERNAL_AUTHORITY"])
    canonical("attempt", {"campaign_ref": ref("campaign_genesis"), "source_ref": ref("nf02_p0_source_snapshot"),
              "creation_cut": typ("HistoryCut"), "retry_of_attempt_ref": {"anyOf": [{"type": "null"}, ref("attempt")]},
              "abort_basis_ref": {"anyOf": [{"type": "null"}, ref("nf02_p0_abort")]}, "auditor_certificate_sha256": SHA},
              refs={"campaign_ref": (["campaign_genesis"], "PRIOR"), "source_ref": (["nf02_p0_source_snapshot"], "PRIOR"),
                    "retry_of_attempt_ref": (["attempt"], "PRIOR_OR_NULL_INITIAL"), "abort_basis_ref": (["nf02_p0_abort"], "PRIOR_OR_NULL_INITIAL")},
              profiles=core + ["P0_EXECUTION_ISOLATION_V1"], predicates=["ONE_ACTIVE_ATTEMPT", "INITIAL_NULL_OR_EXACT_ABORTED_PREDECESSOR", "NO_RETRY_AFTER_ACCEPTED_RESULT"])
    canonical("assignment_manifest", {"campaign_ref": ref("campaign_genesis"), "source_ref": ref("nf02_p0_source_snapshot"),
              "attempt_ref": ref("attempt"), "assignment_cut": typ("HistoryCut"), "auditor_certificate_sha256": SHA,
              "task_raw_ref": raw("P0_PACKAGE_TRANSPORT_V1", "text/markdown"), "input_members": arr(typ("Member"), minimum=1),
              "result_slot_id": {"const": "EXTERNAL_AUDIT_RESULT"}, "package_profile_ref": pin("P0_PACKAGE_TRANSPORT_V1"),
              "result_profile_ref": pin("P0_RESULT_TRANSPORT_V1"), "isolation_profile_ref": pin("P0_EXECUTION_ISOLATION_V1")},
              refs={"campaign_ref": (["campaign_genesis"], "PRIOR"), "source_ref": (["nf02_p0_source_snapshot"], "PRIOR"), "attempt_ref": (["attempt"], "SAME_CREATE_ASSIGNMENT_CONTENT")},
              profiles=list(PROFILES), predicates=["EXACT_FIXED_OWNER_APPROVED_SOURCE_VIEW_TASK_AND_SINGLE_SLOT", "ONE_ASSIGNMENT_PER_ATTEMPT", "NO_CALLER_GRANT_OR_VIEW_SUBSET"])
    canonical("assignment_package_binding", {"assignment_ref": ref("assignment_manifest"), "binding_cut": typ("HistoryCut"),
              "package_raw_ref": raw("P0_PACKAGE_TRANSPORT_V1", "application/zip")},
              refs={"assignment_ref": (["assignment_manifest"], "PRIOR")}, profiles=core + ["P0_PACKAGE_TRANSPORT_V1"],
              predicates=["EXACT_ASSIGNED_PACKAGE_MEMBERS_CLAIMS_AND_RAW", "UNIQUE_BINDING_PER_ASSIGNMENT", "RAW_DURABLE_BEFORE_ACCEPTANCE"])
    canonical("nf02_p0_delivery", {"assignment_ref": ref("assignment_manifest"), "binding_ref": ref("assignment_package_binding"),
              "start_event": typ("EventId"), "delivery_cut": typ("HistoryCut"), "release_id": SHA,
              "ack_raw_ref": raw("P0_AUTHORIZATION_V1", "application/json"),
              "ack_signature_raw_ref": raw("P0_AUTHORIZATION_V1", "application/pkcs7-signature"), "auditor_certificate_sha256": SHA},
              refs={"assignment_ref": (["assignment_manifest"], "PRIOR"), "binding_ref": (["assignment_package_binding"], "PRIOR")},
              profiles=core + ["P0_EXECUTION_ISOLATION_V1", "P0_PACKAGE_TRANSPORT_V1"],
              predicates=["LATER_THAN_PRIOR_START", "PROTECTED_RELEASE_JOB_SENT_BY_QUALIFIED_TRANSPORT", "EXACT_AUDITOR_ACK_AND_PACKAGE_BYTES", "ONE_ACKNOWLEDGED_DELIVERY"])
    canonical("lane_result_admission_evidence", {"assignment_ref": ref("assignment_manifest"), "binding_ref": ref("assignment_package_binding"),
              "delivery_ref": ref("nf02_p0_delivery"), "admission_cut": typ("HistoryCut"), "result_slot_id": {"const": "EXTERNAL_AUDIT_RESULT"},
              "result_raw_ref": raw("P0_RESULT_TRANSPORT_V1", "application/zip"),
              "return_raw_ref": raw("P0_AUTHORIZATION_V1", "application/json"),
              "return_signature_raw_ref": raw("P0_AUTHORIZATION_V1", "application/pkcs7-signature"), "auditor_certificate_sha256": SHA},
              refs={"assignment_ref": (["assignment_manifest"], "PRIOR"), "binding_ref": (["assignment_package_binding"], "PRIOR"), "delivery_ref": (["nf02_p0_delivery"], "PRIOR")},
              profiles=list(PROFILES), predicates=["PRIOR_BINDING_START_AND_DELIVERY", "AUTHENTICATED_CURRENT_EXACT_AUDITOR_RETURN", "FULL_SLOT_ATTEMPT_SOURCE_CAMPAIGN_AND_CUT_JOIN",
                                                    "EXACT_RESULT_RAW_RETAINED_AND_VALIDATED", "ONE_ADMISSION_PER_SLOT"])
    canonical("bdb_audit_lane_result", {"admission_ref": ref("lane_result_admission_evidence"), "result_cut": typ("HistoryCut"),
              "result_payload": {"$ref": "urn:bdb:p0:wire:NORMALIZED_RESULT/1"}},
              refs={"admission_ref": (["lane_result_admission_evidence"], "PRIOR")}, profiles=core + ["P0_RESULT_TRANSPORT_V1"],
              predicates=["LATER_THAN_PRIOR_EVIDENCE", "REREAD_ORIGINAL_RAW_AND_REDERIVE_PAYLOAD", "ONE_RESULT_PER_SLOT", "NO_TRUTH_COMPLETION_OR_PASS_PROMOTION"])
    canonical("nf02_p0_abort", {"attempt_ref": ref("attempt"), "assignment_ref": ref("assignment_manifest"), "abort_cut": typ("HistoryCut"),
              "from_state": {"enum": ["ASSIGNED", "BOUND", "STARTED", "DELIVERED", "EVIDENCE_ACCEPTED"]},
              "reason": {"enum": ["OWNER_CANCELLED", "DELIVERY_FAILED", "EXECUTION_FAILED", "AUTHORITY_WITHDRAWN", "INVALID_RESULT"]}},
              refs={"attempt_ref": (["attempt"], "PRIOR"), "assignment_ref": (["assignment_manifest"], "PRIOR")}, profiles=core,
              predicates=["CURRENT_OWNER_AUTHORIZED_ABORT", "ONLY_NONTERMINAL_ATTEMPT", "RETAIN_ALL_RAW_AND_FACTS", "EXACT_RETRY_BASIS_NOT_GENERAL_CHECKPOINT"])

    fact_kinds = [k for k in KINDS if k not in {"command_envelope", "commit_body", "command_receipt"}]
    commands = ["INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT",
                "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT", "ABORT_ATTEMPT"]
    events = [{"name": "P0FactAccepted", "fields": obj({"event_type": {"const": "P0FactAccepted"}, "artifact_ref": ref(*fact_kinds)})},
              {"name": "P0AttemptStarted", "fields": obj({"event_type": {"const": "P0AttemptStarted"}, "attempt_ref": ref("attempt"),
                                                           "assignment_ref": ref("assignment_manifest"), "binding_ref": ref("assignment_package_binding")})}]
    SCHEMA_NODES[COMMON]["schema"]["$defs"]["Event"] = {"oneOf": [e["fields"] for e in events]}
    canonical("command_envelope", {"command_id": {"allOf": [typ("LogicalId"), {"pattern": "^command_envelope_"}]},
              "operation": {"enum": commands}, "actor_ref": S, "installation_digest": SHA, "grant_digest": SHA,
              "namespace_authority_digest": SHA, "mode": {"enum": ["QUALIFICATION_ONLY", "PRODUCTION"]},
              "campaign_id": typ("LogicalId"), "expected_parent": {"oneOf": [{"const": "EMPTY_HISTORY"}, typ("Head")]},
              "policy_ref": ref("policy_revision"), "spec_ref": ref("spec_revision"), "schema_registry_ref": ref("schema_registry"),
              "proposed_object_refs": arr(ref(*fact_kinds), maximum=15), "events": arr(typ("Event"), maximum=15),
              "basis_refs": arr(ref(*fact_kinds), maximum=15)},
              refs={"policy_ref": (["policy_revision"], "PINNED_OR_PRIOR_CONTEXT"), "spec_ref": (["spec_revision"], "PINNED_OR_PRIOR_CONTEXT"),
                    "schema_registry_ref": (["schema_registry"], "PINNED_OR_PRIOR_CONTEXT"), "proposed_object_refs": (fact_kinds, "EXACT_OPERATION_CONTENT"),
                    "basis_refs": (fact_kinds, "EXACT_OPERATION_PRIOR")}, profiles=list(PROFILES),
              predicates=["EXACT_OPERATION_CLOSURE_TABLE_NOT_GENERIC_PERMISSION", "NO_FREEFORM_PAYLOAD_OR_EVENTS", "CURRENT_SIGNATURE_ROLE_SCOPE_AND_PARENT"], role="DECISION")
    operation_kinds = [roots + ["nf02_p0_source_snapshot", "campaign_genesis"], ["attempt", "assignment_manifest"],
                       ["assignment_package_binding"], [], ["nf02_p0_delivery"], ["lane_result_admission_evidence"],
                       ["bdb_audit_lane_result"], ["nf02_p0_abort"]]
    branches = []
    for index, (operation, kinds) in enumerate(zip(commands, operation_kinds, strict=True)):
        fields = {"operation": {"const": operation},
                  "expected_parent": {"const": "EMPTY_HISTORY"} if index == 0 else typ("Head"),
                  "proposed_object_refs": arr(ref(*kinds) if kinds else {}, minimum=len(kinds), maximum=len(kinds)),
                  "events": arr(events[1]["fields"] if index == 3 else
                                obj({"event_type": {"const": "P0FactAccepted"}, "artifact_ref": ref(*kinds)}),
                                minimum=1 if index == 3 else len(kinds), maximum=1 if index == 3 else len(kinds))}
        branches.append({"properties": fields})
    SCHEMA_NODES["urn:bdb:p0:canonical:command_envelope/3"]["schema"]["oneOf"] = branches
    CONTRACTS["command_envelope/3"]["body"]["oneOf"] = branches
    canonical("commit_body", {"command_ref": ref("command_envelope"), "command_digest": SHA, "actor_ref": S,
              "campaign_id": typ("LogicalId"), "commit_seq": {**N, "minimum": 1},
              "previous_head": {"oneOf": [{"const": "EMPTY_HISTORY"}, typ("Head")]},
              "policy_ref": ref("policy_revision"), "spec_ref": ref("spec_revision"), "schema_registry_ref": ref("schema_registry"),
              "authorization_trace_raw_ref": raw("P0_AUTHORIZATION_V1", "application/json"),
              "immutable_object_refs": arr(ref("command_envelope", *fact_kinds), minimum=1, maximum=16), "events": arr(typ("Event"), maximum=15)},
              refs={"command_ref": (["command_envelope"], "SAME_COMMIT_CONTENT"), "immutable_object_refs": (["command_envelope", *fact_kinds], "CONTENT_TOPOLOGICAL"),
                    "policy_ref": (["policy_revision"], "PINNED_OR_PRIOR_CONTEXT"), "spec_ref": (["spec_revision"], "PINNED_OR_PRIOR_CONTEXT"),
                    "schema_registry_ref": (["schema_registry"], "PINNED_OR_PRIOR_CONTEXT")}, profiles=core,
              predicates=["ONE_KAHN_CONTENT_DAG_NO_OLD_COMMAND_FIRST_RULE", "COMMAND_PARENT_CONTEXT_AND_EVENTS_EQUAL", "ATOMIC_CAS_OBJECT_RAW_HEAD_RECEIPT"], role="FACT")
    canonical("command_receipt", {"command_ref": ref("command_envelope"), "commit_ref": ref("commit_body"), "accepted_head": typ("Head"),
              "result_object_refs": arr(ref(*fact_kinds), maximum=15)},
              refs={"command_ref": (["command_envelope"], "POST_ACCEPTANCE_SIDECAR"), "commit_ref": (["commit_body"], "POST_ACCEPTANCE_SIDECAR"),
                    "result_object_refs": (fact_kinds, "EXACT_OPERATION_POST_ACCEPTANCE")}, profiles=core,
              predicates=["COMMAND_ID_DIGEST_AND_COMMIT_EQUALITY", "EXACT_RETRY_ORIGINAL_RECEIPT", "NO_RECEIPT_IN_OWN_ACCEPTING_PREIMAGE"], role="DERIVED_PROJECTION")

    scope = obj({"campaign_id": typ("LogicalId"), "attempt_ref": ref("attempt"), "assignment_ref": ref("assignment_manifest"),
                 "source_ref": ref("nf02_p0_source_snapshot"), "slot_id": {"const": "EXTERNAL_AUDIT_RESULT"}})
    source_manifest = obj({"repository_id": S, "git_object_algorithm": {"enum": ["sha1", "sha256"]}, "commit_oid": OID, "tree_oid": OID,
                           "entries": arr(obj({"source_path": S, "transport_path": PATH, "git_blob_oid": OID,
                                               "mode": {"enum": ["100644", "100755"]}, "sha256": SHA, "bytes": N}), minimum=1, maximum=2044)})
    package_manifest = obj({"scope": scope, "assignment_cut": typ("HistoryCut"), "members": arr(typ("Member"), minimum=1)})
    finding = obj({"finding_id": typ("LogicalId"), "severity": {"enum": ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                   "summary": S, "details": {"type": "string", "maxLength": 65536}, "source_paths": arr(S), "evidence_paths": arr(PATH)})
    payload = obj({"findings": arr(finding), "report_paths": arr(PATH, minimum=1), "evidence_paths": arr(PATH), "log_paths": arr(PATH),
                   "notes": arr({"type": "string", "maxLength": 65536}, maximum=256)})
    wire_bodies = {
        "SOURCE_MANIFEST": source_manifest,
        "PACKAGE_MANIFEST": package_manifest,
        "NORMALIZED_RESULT": payload,
        "RESULT_MANIFEST": obj({"scope": scope, "binding_ref": ref("assignment_package_binding"), "delivery_ref": ref("nf02_p0_delivery"),
                                 "package_raw_ref": raw("P0_PACKAGE_TRANSPORT_V1", "application/zip"), "members": arr(typ("Member"), minimum=1), "payload": payload}),
        "DELIVERY_ACK": obj({"domain": {"const": "BDB_P0_DELIVERY_ACK/1"}, "scope": scope, "release_id": SHA,
                              "binding_ref": ref("assignment_package_binding"), "start_event": typ("EventId"),
                              "package_raw_ref": raw("P0_PACKAGE_TRANSPORT_V1", "application/zip"), "auditor_certificate_sha256": SHA}),
        "AUDIT_RETURN": obj({"domain": {"const": "BDB_P0_AUDIT_RETURN/1"}, "scope": scope, "binding_ref": ref("assignment_package_binding"),
                              "delivery_ref": ref("nf02_p0_delivery"), "result_raw_ref": raw("P0_RESULT_TRANSPORT_V1", "application/zip"),
                              "auditor_certificate_sha256": SHA, "execution_declaration": {"const": "EXECUTED_ASSIGNED_AUDIT"}}),
        "RELEASE_JOB": obj({"domain": {"const": "BDB_P0_RELEASE/1"}, "scope": scope, "release_id": SHA,
                             "binding_ref": ref("assignment_package_binding"), "start_event": typ("EventId"), "authorized_cut": typ("HistoryCut"),
                             "installation_digest": SHA, "grant_digest": SHA, "package_raw_ref": raw("P0_PACKAGE_TRANSPORT_V1", "application/zip"),
                             "auditor_certificate_sha256": SHA, "status": {"enum": ["PREPARED", "SENT", "ACKNOWLEDGED"]}}),
        "AUTHORIZATION_TRACE": obj({"domain": {"const": "BDB_P0_AUTHORIZATION_TRACE/1"}, "command_ref": ref("command_envelope"),
                                     "command_signature_raw_ref": raw("P0_AUTHORIZATION_V1", "application/pkcs7-signature"),
                                     "root_raw_ref": raw("P0_AUTHORIZATION_V1", "application/json"),
                                     "installation_raw_ref": raw("P0_AUTHORIZATION_V1", "application/json"),
                                     "installation_signature_raw_ref": raw("P0_AUTHORIZATION_V1", "application/pkcs7-signature"),
                                     "grant_raw_ref": raw("P0_AUTHORIZATION_V1", "application/json"),
                                     "grant_signature_raw_ref": raw("P0_AUTHORIZATION_V1", "application/pkcs7-signature"),
                                     "verified_at_utc": UTC, "signer_certificate_sha256": SHA}),
    }
    for name, body in wire_bodies.items():
        register("urn:bdb:p0:wire:" + name + "/1", "wire", body, deps=[COMMON])

    files = arr(typ("FileEntry"), minimum=1, maximum=8192)
    evidence_files = arr(typ("FileEntry"), minimum=1, maximum=4096)
    qbindings = {"candidate_manifest_sha256": SHA, "normative_set_sha256": SHA, "machine_set_sha256": SHA}
    owner = {"owner_decision_sha256": SHA, "governance_actor_ref": S}
    external = {
        "ROOT": obj({"model_id": {"const": MODEL_ID}, "owner_certificate_sha256": SHA, "qualifier_certificate_sha256": SHA,
                     "installation_sha256": SHA, "root_id": typ("LogicalId"), "namespace_id": S, "namespace_authority_digest": SHA}),
        "CANDIDATE_MANIFEST": obj({"model_id": {"const": MODEL_ID}, "normative_files": files, "machine_files": files,
                                    "normative_set_sha256": SHA, "machine_set_sha256": SHA}),
        "OWNER_MODEL_DECISION": obj({**qbindings, "scope_graph_sha256": SHA, "owner_actor_ref": S,
                                      "decision": {"const": "APPROVE_LIMITED_P0_MODEL"}, "accepted_limits": arr(S, minimum=1)}),
        "AUTHOR_QUALIFICATION": obj({**qbindings, **owner, "readback_files": evidence_files, "final_audit_sha256": SHA,
                                      "mismatch_count": {"const": 0}, "independent_assurance": {"const": False},
                                      "verdict": {"const": "P0_AUTHOR_BASELINE_READY"}}),
        "INDEPENDENT_FREEZE": obj({**qbindings, **owner, "author_qualification_sha256": SHA, "independent_review_sha256": SHA,
                                    "qualifier_actor_ref": S, "verdict": {"const": "P0_INDEPENDENT_BASELINE_READY"}, "decision": {"const": "FREEZE"}}),
        "RUNTIME_QUALIFICATION": obj({**qbindings, "independent_freeze_sha256": SHA, "implementation_files": files,
                                       "environment_evidence_sha256": SHA, "test_evidence": evidence_files,
                                       "real_external_run_evidence_sha256": SHA, "qualification_namespace": S,
                                       "qualified_auditor_certificate_sha256": SHA, "executor_boundary_evidence_sha256": SHA,
                                       "qualifier_actor_ref": S, "mandatory_case_ids": {"const": sorted(QUALIFICATION_CASES["RQ"])},
                                       "verdict": {"const": "P0_RUNTIME_READY"}}),
        "INSTALLATION_RECORD": obj({**qbindings, "mode": {"enum": ["QUALIFICATION_ONLY", "PRODUCTION"]},
                                    "freeze_sha256": SHA, "runtime_qualification_sha256": {"anyOf": [{"type": "null"}, SHA]},
                                    "qualification_mandate_sha256": {"anyOf": [{"type": "null"}, SHA]}, "installed_files": files,
                                    "implementation_files": files, "namespace_authority_digest": SHA, "external_schema_root_sha256": SHA,
                                    "coordinator_os_identity": obj({"sid": S, "privilege_class": {"const": "NON_ADMIN_SERVICE_ACCOUNT"}}),
                                    "initial_root_refs": arr(ref(*roots), minimum=6, maximum=6)}),
        "PRINCIPAL_GRANT": obj({"installation_digest": SHA, "actor_ref": S, "certificate_sha256": SHA,
                               "role": {"enum": ["COORDINATOR", "AUDITOR", "OWNER_RECOVERY"]}, "campaign_id": typ("LogicalId"),
                               "source_scope_digest": SHA, "view_task_digest": SHA,
                               "assignment_scope_digest": {"anyOf": [{"type": "null"}, SHA]}, "operations": arr({"enum": commands + ["RELEASE_PACKAGE", "ACK_DELIVERY", "RETURN_AUDIT"]}, minimum=1),
                               "not_before": UTC, "not_after": UTC}),
        "QUALIFICATION_MANDATE": obj({**qbindings, "freeze_sha256": SHA, "implementation_files": files,
                                      "qualification_namespace": S, "permitted_mode": {"const": "QUALIFICATION_ONLY"},
                                      "owner_actor_ref": S, "qualifier_actor_ref": S, "not_before": UTC, "not_after": UTC}),
    }
    for name, body in external.items():
        register("urn:bdb:p0:external:" + name + "/1", "external", body, deps=[COMMON])
    installation_modes = {"if": {"properties": {"mode": {"const": "PRODUCTION"}}},
                          "then": {"properties": {"runtime_qualification_sha256": SHA, "qualification_mandate_sha256": {"type": "null"}}},
                          "else": {"properties": {"runtime_qualification_sha256": {"type": "null"}, "qualification_mandate_sha256": SHA}}}
    SCHEMA_NODES["urn:bdb:p0:external:INSTALLATION_RECORD/1"]["schema"]["allOf"] = [installation_modes]

    # Runtime schema edges and semantic object targets are deliberately separate;
    # a kind graph cycle is not permission for a same-commit prior reference.
    operations = [
        {"name": commands[0], "objects": [k + "/" + KINDS[k] for k in roots + ["nf02_p0_source_snapshot", "campaign_genesis"]], "precondition": "EMPTY_HISTORY; externally approved eight pins/source/view/mode", "effect": "GENESIS"},
        {"name": commands[1], "objects": ["attempt/3", "assignment_manifest/3"], "precondition": "GENESIS or prior ABORTED; current independent exact grant; no active/accepted attempt", "effect": "ASSIGNED"},
        {"name": commands[2], "objects": ["assignment_package_binding/3"], "precondition": "ASSIGNED; exact approved view and bytes", "effect": "BOUND"},
        {"name": commands[3], "objects": [], "precondition": "BOUND; earlier accepted B; exact AttemptStarted event", "effect": "STARTED"},
        {"name": commands[4], "objects": ["nf02_p0_delivery/1"], "precondition": "STARTED; release job SENT and exact current auditor ACK", "effect": "DELIVERED"},
        {"name": commands[5], "objects": ["lane_result_admission_evidence/4"], "precondition": "DELIVERED; current auditor return; retained exact original result raw", "effect": "EVIDENCE_ACCEPTED"},
        {"name": commands[6], "objects": ["bdb_audit_lane_result/4"], "precondition": "EVIDENCE_ACCEPTED in earlier commit; reread and rederive", "effect": "RESULT_ACCEPTED"},
        {"name": commands[7], "objects": ["nf02_p0_abort/1"], "precondition": "Any nonterminal assignment state; owner recovery authority; exact current cut", "effect": "ABORTED"},
    ]
    return {"model_id": MODEL_ID, "status": "PROPOSED_NOT_APPROVED_NOT_QUALIFIED_NOT_ACTIVE",
            "iteration": "ONE_CLOSED_OWNER_AUTHORIZED_DESIGN_ITERATION",
            "canonical_contracts": CONTRACTS, "profiles": {p: {"profile_id": p, **v} for p, v in PROFILES.items()},
            "operations": operations, "delivery_operation": {"name": "RELEASE_PACKAGE", "states": ["STARTED", "DELIVERED"],
                "writer": "EXISTING_STORE_SERIALIZED_LEASE_AND_PROTECTED_OUTBOX", "semantics": "AT_LEAST_ONCE_IDENTICAL_RETAINED_BYTES"},
            "schema_nodes": {k: {"category": v["category"], "semantic_dependencies": v["semantic_dependencies"]} for k, v in SCHEMA_NODES.items()},
            "qualification_stages": ["Q1_AUTHOR_NORMATIVE_BASELINE", "Q2_INDEPENDENT_REVIEW_AND_FREEZE", "RQ_RUNTIME_INDEPENDENT_REAL_EXTERNAL_RUN"],
            "qualification_case_ids": {stage: sorted(cases) for stage, cases in QUALIFICATION_CASES.items()},
            "excluded": ["GENERIC_ARTIFACT_IMPORT", "GENERAL_CHECKPOINT_GRAPH", "MULTI_STAGE_LANE_PLANNING", "SOURCE_SUCCESSION", "LEGACY_ASSURANCE_IMPORT",
                         "BLIND_KNOWLEDGE_ASSURANCE", "FINDING_TRUTH_PROMOTION", "COMPLETION_STOP_REPORT_ASSURANCE_RELEASE"]}


def refs_in(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref":
                found.add(item.split("#")[0])
            else:
                found.update(refs_in(item))
    elif isinstance(value, list):
        for item in value:
            found.update(refs_in(item))
    return found


def targets_in_schema(value: Any) -> set[str]:
    """Include typed target unions and profile IDs inside shared/wire grammar."""
    found: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties", {})
        target_domains: list[tuple[str, dict[str, Any], str]] = [("kind", KINDS, "urn:bdb:p0:canonical:"),
                                                              ("profile_id", PROFILES, "urn:bdb:p0:profile:")]
        for field, mapping, prefix in target_domains:
            constraint = properties.get(field, {})
            for key in constraint.get("enum", [constraint.get("const")]):
                if key in mapping:
                    found.add(prefix + key + ("/" + KINDS[key] if field == "kind" else ""))
        for child in value.values():
            found.update(targets_in_schema(child))
    elif isinstance(value, list):
        for child in value:
            found.update(targets_in_schema(child))
    return found


def artifacts() -> dict[str, bytes]:
    model = construct()
    payload_edges = {
        "nf02_p0_source_snapshot/1": ["SOURCE_MANIFEST"],
        "assignment_manifest/3": ["SOURCE_MANIFEST"],
        "assignment_package_binding/3": ["PACKAGE_MANIFEST"],
        "nf02_p0_delivery/1": ["DELIVERY_ACK", "RELEASE_JOB"],
        "lane_result_admission_evidence/4": ["RESULT_MANIFEST", "AUDIT_RETURN"],
        "commit_body/3": ["AUTHORIZATION_TRACE"],
    }
    for key, names in payload_edges.items():
        SCHEMA_NODES["urn:bdb:p0:canonical:" + key]["semantic_dependencies"] += ["urn:bdb:p0:wire:" + name + "/1" for name in names]
        model["schema_nodes"]["urn:bdb:p0:canonical:" + key]["semantic_dependencies"] = SCHEMA_NODES["urn:bdb:p0:canonical:" + key]["semantic_dependencies"]
    edges = []
    for key, node in SCHEMA_NODES.items():
        for target in sorted(set(node["semantic_dependencies"]) | refs_in(node["schema"]) | targets_in_schema(node["schema"])):
            assert target in SCHEMA_NODES, (key, target)
            reasons = []
            if target in node["semantic_dependencies"]:
                reasons.append("DECLARED_PREDICATE_OR_MATERIAL_DEPENDENCY")
            if target in refs_in(node["schema"]):
                reasons.append("EXECUTABLE_SCHEMA_REF")
            if target in targets_in_schema(node["schema"]):
                reasons.append("TYPED_TARGET_OR_PROFILE_DOMAIN")
            edges.append({"from": key, "to": target, "reasons": reasons})
    roots = ["urn:bdb:p0:canonical:" + key for op in model["operations"] for key in op["objects"]]
    roots += ["urn:bdb:p0:canonical:" + k + "/3" for k in ["command_envelope", "commit_body", "command_receipt"]]
    # Governance, installation and actual wire boundaries are mandatory roots,
    # not erased from the denominator because they are outside campaign history.
    roots += [k for k, n in SCHEMA_NODES.items() if n["category"] in {"external", "wire"}]
    seen = set(roots)
    queue = deque(sorted(seen))
    witnesses = {}
    while queue:
        parent = queue.popleft()
        for e in edges:
            if e["from"] == parent and e["to"] not in seen:
                seen.add(e["to"]); queue.append(e["to"]); witnesses[e["to"]] = parent
    assert seen == set(SCHEMA_NODES), sorted(set(SCHEMA_NODES) - seen)
    def encode(value: Any) -> bytes:
        return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = {"MODEL.json": encode(model)}
    for key, node in SCHEMA_NODES.items():
        category = node["category"]
        name = key.rsplit(":", 1)[-1].replace("/", "__")
        output["schemas/" + category + "/" + name + ".schema.json"] = encode(node["schema"])
    for p, v in model["profiles"].items():
        output["profiles/" + p + ".json"] = encode(v)
    graph = {"model_id": MODEL_ID, "authority": "DESIGN_ONLY", "roots": sorted(set(roots)),
             "nodes": sorted(seen), "edges": edges, "witnesses": witnesses,
             "counts": {"canonical_contracts": len(CONTRACTS), "profiles": len(PROFILES), "schemas": len(seen),
                        "schema_categories": dict(Counter(n["category"] for n in SCHEMA_NODES.values())),
                        "qualification_stages": len(model["qualification_stages"]), "canonical_operations": len(model["operations"]), "delivery_operations": 1},
             "declared_graph_closed": True, "semantic_qualification": False, "import": "BLOCKED"}
    graph["normative_dependencies"] = [
        {"file": PREFIX + "MODEL.md", "scope": "M01-M18_AND_EXPLICIT_NORMATIVE_DELTAS"},
        {"file": ADR, "scope": "PRIMITIVES_ONLY_2_3_4_6_9_AS_EXPLICITLY_DEFINED_IN_MODEL; other referenced foundation sources not imported"}]
    graph["operational_prerequisites_not_canonical_contracts"] = [
        "INDEPENDENT_REAL_OWNER_QUALIFIER_AND_AUDITOR_AUTHORITY",
        "QUALIFIED_OS_SID_ACL_CMS_CLOCK_AND_PROTECTED_CODE_STORAGE",
        "VERIFIED_AUTHORIZED_GIT_OBJECTS_AND_APPROVED_VIEW_TASK",
        "QUALIFIED_EXTERNAL_HOST_TRANSPORT_AND_ACTUAL_AUDIT_EXECUTION"]
    output["DEPENDENCY_GRAPH.json"] = encode(graph)
    output["QUALIFICATION_MATRIX.json"] = encode({"model_id": MODEL_ID, "status": "REQUIREMENTS_NOT_EXECUTION_OR_PASS",
                                                  "cases": QUALIFICATION_CASES,
                                                  "counts": {stage: len(cases) for stage, cases in QUALIFICATION_CASES.items()}})
    return output


def manifest(files: dict[str, bytes]) -> bytes:
    """Bind one proposal, with no self-hash or synthesized approval instance."""
    inputs = {PREFIX + name: raw_bytes for name, raw_bytes in files.items()}
    inputs[PREFIX + "MODEL.md"] = (OUT / "MODEL.md").read_bytes()
    inputs[ADR] = (ROOT / ADR).read_bytes()
    for name in ["tools/nf02_p0_limited_model.py", "tools/test_nf02_p0_limited_model.py"]:
        inputs[name] = (ROOT / name).read_bytes()
    normative = [PREFIX + name for name in ["MODEL.md", "MODEL.json", "DEPENDENCY_GRAPH.json", "QUALIFICATION_MATRIX.json"]]
    normative += [PREFIX + name for name in files if name.startswith(("schemas/", "profiles/"))]
    normative += [ADR]
    machine = [name for name in inputs if name != PREFIX + "MODEL.md" and name != ADR]
    def entries(names: list[str]) -> list[dict[str, Any]]:
        assert len(names) == len(set(names))
        return [{"file": name, "sha256": hashlib.sha256(inputs[name]).hexdigest(), "bytes": len(inputs[name])}
                for name in sorted(names)]
    def set_digest(domain: str, members: list[dict[str, Any]]) -> str:
        canonical = json.dumps(members, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(domain.encode("ascii") + b"\x00" + canonical).hexdigest()
    nset = entries(normative)
    mset = entries(machine)
    value = {"model_id": MODEL_ID, "normative_files": nset, "machine_files": mset,
             "normative_set_sha256": set_digest("BDB-NF02-P0-NORMATIVE-SET/1", nset),
             "machine_set_sha256": set_digest("BDB-NF02-P0-MACHINE-SET/1", mset)}
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = artifacts()
    files["CANDIDATE_MANIFEST.json"] = manifest(files)
    for name, raw_bytes in files.items():
        target = OUT / name
        if args.check:
            assert target.read_bytes() == raw_bytes, name
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw_bytes)
    print(json.dumps({"files": len(files), "bytes": sum(map(len, files.values())),
                      "counts": json.loads(files["DEPENDENCY_GRAPH.json"])["counts"], "qualification": False}))


if __name__ == "__main__":
    main()
