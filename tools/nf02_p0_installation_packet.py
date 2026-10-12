"""Prepare unsigned installation bytes. Never sign, install or grant authority.

Run on the final isolated runtime, after real Q1/Q2 and signed mandate/RQ exist.
The output is a review packet; only an independent owner/installer can activate it.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace

from bdb_audit.core.canonical_json import canonical_bytes
from bdb_audit.history.limited_environment import snapshot
from bdb_audit.history.limited_model import BASE, MODEL_ID, GRAPH_SHA, LimitedCorpus, domain_hash, sha, strict_json
from bdb_audit.history.limited_wire import LimitedObject, identifier, value_body


def root_objects(corpus, namespace):
    definitions = SimpleNamespace(schema_ref=corpus.schema_ref, schemas=corpus.schemas, registry=corpus.registry)

    def obj(kind, fields):
        body = value_body(kind, fields)
        return LimitedObject(kind, body, corpus.schema_ref(kind), body["object_id"], corpus.versions[kind], definitions)

    registry = obj("artifact_contract_registry", {"contracts": sorted(corpus.descriptor["canonical_contracts"]),
        "model_descriptor_raw_ref": corpus.raw_ref(corpus.files[BASE + "MODEL.json"], "BDB_CJSON_1", "application/json")})
    bindings = [{"schema_id": corpus.schema_ref(kind)["schema_id"], "schema_raw_ref": corpus.raw_ref(
        corpus.files[BASE + "schemas/canonical/" + kind + "__" + version + ".schema.json"], "BDB_CJSON_1", "application/schema+json")}
        for kind, version in corpus.versions.items()]
    schemas = obj("schema_registry", {"registry_ref": registry.ref.as_dict(), "bindings": sorted(bindings, key=lambda b: b["schema_id"])})
    policy = obj("policy_revision", {"authorization_profile_ref": corpus.pin("P0_AUTHORIZATION_V1"),
        "recovery_profile_ref": corpus.pin("P0_HISTORY_RECOVERY_V1"), "allowed_model": MODEL_ID})
    spec = obj("spec_revision", {"source_profile_ref": corpus.pin("P0_BOOTSTRAP_SOURCE_V1"), "package_profile_ref": corpus.pin("P0_PACKAGE_TRANSPORT_V1"),
        "result_profile_ref": corpus.pin("P0_RESULT_TRANSPORT_V1"), "history_profile_ref": corpus.pin("P0_HISTORY_RECOVERY_V1")})
    trust_fields = corpus.schemas.documents["canonical/trust_profile__3"]["properties"]
    trust = obj("trust_profile", {"authorization_profile_ref": corpus.pin("P0_AUTHORIZATION_V1"), "isolation_profile_ref": corpus.pin("P0_EXECUTION_ISOLATION_V1"),
        **{k: trust_fields[k]["const"] for k in ("executor_write_boundary", "assurance", "explicit_non_guarantees")}})
    bootstrap = obj("installation_bootstrap_profile", {"registry_ref": registry.ref.as_dict(), "schema_registry_ref": schemas.ref.as_dict(),
        "policy_ref": policy.ref.as_dict(), "spec_ref": spec.ref.as_dict(), "trust_ref": trust.ref.as_dict(), "namespace_authority_digest": namespace,
        "serialization_profile_ref": corpus.pin("BDB_CJSON_1"), "source_profile_ref": corpus.pin("P0_BOOTSTRAP_SOURCE_V1"),
        "initial_command": "INITIALIZE_P0_FROM_APPROVED_GIT"})
    return {o.kind: o for o in (registry, schemas, policy, spec, trust, bootstrap)}


def prepare(assets, configuration, output):
    config = strict_json(configuration.read_bytes())
    required = {"owner_certificate_sha256", "qualifier_certificate_sha256", "namespace_id", "coordinator_service_sid",
                "mode", "freeze_file", "qualification_file"}
    if set(config) != required or config["owner_certificate_sha256"] == config["qualifier_certificate_sha256"]:
        raise ValueError("Explicit independent owner/qualifier and exact configuration required")
    if output.exists():
        raise ValueError("Output must be a new directory; no overwrite of WIP or installed authority")
    files = {}
    for path in sorted(assets.rglob("*")):
        if path.is_symlink():
            raise ValueError("No linked installation assets")
        if path.is_file():
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Installation asset too large")
            files[path.relative_to(assets).as_posix()] = path.read_bytes()
    corpus = LimitedCorpus(files)
    root = {"model_id": MODEL_ID, "root_id": identifier("installation_root"), "namespace_id": config["namespace_id"],
            "owner_certificate_sha256": config["owner_certificate_sha256"], "qualifier_certificate_sha256": config["qualifier_certificate_sha256"]}
    root["namespace_authority_digest"] = domain_hash("BDB-NF02-P0-NAMESPACE/1", root)
    roots = root_objects(corpus, root["namespace_authority_digest"])
    for kind, obj in roots.items():
        files["objects/" + kind + ".json"] = canonical_bytes(obj.body) + b"\n"
    files["ENVIRONMENT.json"] = canonical_bytes(snapshot()) + b"\n"
    # Fail during preparation if the final clean runtime inventory cannot fit
    # the frozen signed-input quota; never prepare an unusable installation.
    strict_json(files["ENVIRONMENT.json"])
    if any(n in files for n in ("root.json", "installation.json", "installation.p7s")) or any(n.startswith("grants/") for n in files):
        raise ValueError("Root/installation/grants cannot be qualification input assets")
    for name in ("SOURCE_REPOSITORIES.json", "AUDITOR_TRANSPORT.json"):
        if name not in files:
            raise ValueError("Owner-reviewed operational configuration required: " + name)
        strict_json(files[name])
    freeze = corpus.external("INDEPENDENT_FREEZE", files[config["freeze_file"]])
    decision_raw = next(raw for raw in files.values() if sha(raw) == freeze["owner_decision_sha256"])
    decision = corpus.external("OWNER_MODEL_DECISION", decision_raw)
    if decision["scope_graph_sha256"] != GRAPH_SHA:
        raise ValueError("Owner decision does not bind the approved graph")
    # Use the actual imported code location, not a caller-selected implementation.
    import bdb_audit
    code_root = Path(bdb_audit.__file__).resolve().parent
    code = [{"file": p.relative_to(code_root).as_posix(), "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
            for p in sorted(code_root.rglob("*")) if p.is_file() and p.suffix in {".py", ".json"}]
    qualification_name = "QUALIFICATION_MANDATE" if config["mode"] == "QUALIFICATION_ONLY" else "RUNTIME_QUALIFICATION"
    qualified = corpus.external(qualification_name, files[config["qualification_file"]])
    if qualified["implementation_files"] != code or qualified["qualification_namespace"] != root["namespace_id"] and qualification_name == "QUALIFICATION_MANDATE":
        raise ValueError("Qualification/mandate does not bind this exact code/namespace")
    install = {**corpus.bindings(), "mode": config["mode"], "freeze_sha256": sha(files[config["freeze_file"]]),
        "runtime_qualification_sha256": sha(files[config["qualification_file"]]) if qualification_name == "RUNTIME_QUALIFICATION" else None,
        "qualification_mandate_sha256": sha(files[config["qualification_file"]]) if qualification_name == "QUALIFICATION_MANDATE" else None,
        "installed_files": [{"file": n, "sha256": sha(raw), "bytes": len(raw)} for n, raw in sorted(files.items())],
        "implementation_files": code, "namespace_authority_digest": root["namespace_authority_digest"],
        "external_schema_root_sha256": sha(files[BASE + "schemas/canonical/schema_registry__3.schema.json"]),
        "coordinator_os_identity": {"sid": config["coordinator_service_sid"], "privilege_class": "NON_ADMIN_SERVICE_ACCOUNT"},
        "initial_root_refs": [o.ref.as_dict() for _, o in sorted(roots.items())]}
    raw = canonical_bytes(install) + b"\n"
    corpus.external("INSTALLATION_RECORD", raw)
    root["installation_sha256"] = sha(raw)
    root_raw = canonical_bytes(root) + b"\n"
    corpus.external("ROOT", root_raw)
    output.mkdir(parents=True)
    for name, data in {**files, "installation.json": raw, "root.json": root_raw}.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as out:
            out.write(data)
    print("PREPARED_UNSIGNED_NOT_AUTHORITY", str(output.resolve()), sha(raw))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.assets, args.configuration, args.output)
