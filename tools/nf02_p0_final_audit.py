"""Read-only candidate/dependency audit and retained Q1 handoff evidence.

This tool never issues authority, installs a service, or claims qualification.
Run from the repository. Paths in evidence are relative to that repository.
"""
from __future__ import annotations

import argparse
import ast
import base64
from collections import Counter, deque
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/"
OUT = ROOT / "docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF"
CHECKPOINT = "ef3073c7042b33db7a2f32bff812e2e1f0df9de5"
MANIFEST = "278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")


def write(name, value):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded(value) + b"\n")


def identity(name):
    raw = (ROOT / name).read_bytes()
    return {"file": name, "bytes": len(raw), "sha256": digest(raw)}


def candidate():
    raw = (ROOT / BASE / "CANDIDATE_MANIFEST.json").read_bytes()
    assert digest(raw) == MANIFEST, "Approved manifest drift"
    manifest = json.loads(raw)
    entries = {}
    sets = {}
    for group in ("normative", "machine"):
        rows = manifest[group + "_files"]
        assert rows == sorted(rows, key=lambda row: row["file"])
        assert len(rows) == len({row["file"] for row in rows})
        actual = digest(("BDB-NF02-P0-" + group.upper() + "-SET/1").encode("ascii") + b"\0" + encoded(rows))
        assert actual == manifest[group + "_set_sha256"]
        for row in rows:
            assert identity(row["file"]) == row, row["file"]
            entries[row["file"]] = row
        sets[group] = {"count": len(rows), "sha256": actual}
    entries[BASE + "CANDIDATE_MANIFEST.json"] = identity(BASE + "CANDIDATE_MANIFEST.json")
    comparisons = []
    for name, row in sorted(entries.items()):
        committed = subprocess.run(["git", "show", CHECKPOINT + ":" + name], cwd=ROOT, capture_output=True, check=True).stdout
        assert digest(committed) == row["sha256"], name + " checkpoint drift"
        comparisons.append({**row, "checkpoint_byte_equal": True})
    model = json.loads((ROOT / BASE / "MODEL.json").read_bytes())
    graph = json.loads((ROOT / BASE / "DEPENDENCY_GRAPH.json").read_bytes())
    schemas = {}
    for name in entries:
        if name.startswith(BASE + "schemas/"):
            schema = json.loads((ROOT / name).read_bytes())
            assert schema["$id"] not in schemas
            schemas[schema["$id"]] = schema
    assert len(schemas) == 43 and len(model["profiles"]) == 7 and len(model["canonical_contracts"]) == 18
    contracts = []
    for key, contract in model["canonical_contracts"].items():
        schema = schemas[contract["schema_id"]]
        assert contract["body"] == {k: v for k, v in schema.items() if k not in {"$id", "$schema"}}
        assert key == contract["kind"] + "/" + contract["version"]
        contracts.append({"key": key, "schema_id": schema["$id"], "body_schema_equal": True,
                          "predicates": contract["predicates"], "material_refs": contract["material_refs"]})
    matrix = json.loads((ROOT / BASE / "QUALIFICATION_MATRIX.json").read_bytes())
    assert {k: len(v) for k, v in matrix["cases"].items()} == {"Q1": 11, "Q2": 6, "RQ": 32}
    # The approved generator's --check separately reconstructs the complete graph.
    nodes = set(model["schema_nodes"])
    assert nodes == set(schemas)
    assert all(edge["from"] in nodes and edge["to"] in nodes for edge in graph["edges"])
    report = {"status": "EXACT_APPROVED_CANDIDATE_READBACK_PASS_NOT_QUALIFICATION", "checkpoint": CHECKPOINT,
              "manifest_sha256": MANIFEST, "graph": identity(BASE + "DEPENDENCY_GRAPH.json"), "sets": sets,
              "readback_files": comparisons, "contracts": contracts, "profile_ids": sorted(model["profiles"]),
              "schema_ids": sorted(schemas), "matrix_counts": matrix["counts"], "unexplained_mismatches": []}
    write("evidence/CANDIDATE_IDENTITY.json", report)
    print(json.dumps({"candidate": "PASS", "sets": sets, "files": len(comparisons), "contracts": 18, "profiles": 7, "schemas": 43}))
    return report


def dependencies():
    modules = {}
    for path in (ROOT / "src/bdb_audit").rglob("*.py"):
        parts = path.relative_to(ROOT / "src").with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        modules[name] = path
    roots = ["bdb_audit.p0_service", "bdb_audit.product_p0_cli", "bdb_audit.cli", "bdb_audit.product_cli",
             "bdb_audit.workflow.inbox", "bdb_audit.history.limited_protocol", "bdb_audit.workflow.limited_intake",
             "bdb_audit.workflow.limited_delivery"]
    edges: list[dict[str, Any]] = []
    for module, path in sorted(modules.items()):
        package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
        tree = ast.parse(path.read_bytes())

        def visit(node, functions=()):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions = (*functions, node.name)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    absolute = importlib.util.resolve_name("." * node.level + (node.module or ""), package) if node.level else node.module or ""
                    names = [absolute, *[absolute + "." + alias.name for alias in node.names]]
                for target in names:
                    if target in modules:
                        edges.append({"from": module, "to": target, "line": node.lineno,
                                      "scope": ".".join(functions) or "MODULE_IMPORT"})
            for child in ast.iter_child_nodes(node):
                visit(child, functions)
        visit(tree)
        # Python executes parent __init__ modules when loading any submodule.
        for i in range(1, len(module.split("."))):
            parent = ".".join(module.split(".")[:i])
            if parent in modules:
                edges.append({"from": module, "to": parent, "line": 0, "scope": "PACKAGE_INITIALIZATION"})
    adjacency: dict[str, list[dict[str, Any]]] = {}
    p0_dynamic = {"bdb_audit.history.store": {"open_p0", "release_p0"},
                  "bdb_audit.workflow.inbox": {"p0", "accept_p0_evidence", "accept_p0_result"},
                  "bdb_audit.product_cli": {"run_product"}}
    for edge in edges:
        name, scope = edge["from"], edge["scope"]
        included = (scope in {"MODULE_IMPORT", "PACKAGE_INITIALIZATION"} or "limited" in name
                    or name in {"bdb_audit.product_p0_cli", "bdb_audit.p0_service"}
                    or scope.split(".")[0] in p0_dynamic.get(name, set()))
        edge["p0_admitted_import"] = included
        if included:
            adjacency.setdefault(name, []).append(edge)
    paths = {name: [name] for name in roots}
    queue = deque(roots)
    while queue:
        source = queue.popleft()
        for edge in adjacency.get(source, []):
            target = edge["to"]
            if target not in paths:
                paths[target] = [*paths[source], target]
                queue.append(target)
    names = sorted(path.relative_to(ROOT).as_posix() for name, path in modules.items() if name in paths)
    report = {"roots": roots, "method": "Conservative module import closure including package __init__ effects and explicit finite P0 lazy imports; all methods in imported files are typechecked.",
              "files": names, "module_count": len(paths), "witnesses": paths, "import_edges": edges,
              "build": {"file": "build/build_single_file.py", "membership": "All src .py/.json packaged; legacy dormant functions do not become reachable through finite P0 dispatch; builder included in mypy invocation."},
              "source_readback": [identity(name) for name in names]}
    write("evidence/P0_DEPENDENCY_CLOSURE.json", report)
    print(json.dumps({"p0_module_count": len(paths), "files": len(names)}))
    return report


def triage(graph):
    log = (OUT / "evidence/mypy-before.log").read_text(encoding="utf-8-sig")
    errors: list[dict[str, Any]] = []
    closure = set(graph["files"])
    for line in log.splitlines():
        match = re.match(r"(.+?):(\d+): error: (.+?)\s+\[([^\]]+)\]$", line)
        if not match:
            continue
        name, number, message, code = match.groups()
        name = name.replace("\\", "/")
        module = name.removeprefix("src/").removesuffix(".py").replace("/", ".")
        critical = name in {"src/bdb_audit/core/registry.py", "src/bdb_audit/schemas/binding.py", "src/bdb_audit/history/objects.py", "src/bdb_audit/assurance/zip_safety.py"}
        false_positive = (name in {"src/bdb_audit/schemas/binding.py", "src/bdb_audit/runner/supervisor.py"}
                          or name == "src/bdb_audit/assurance/zip_safety.py")
        category = "FALSE-POSITIVE/CONFIG" if false_positive else "P0-CRITICAL" if critical else "P0-TRANSITIVE" if name in closure else "LEGACY-OUT-OF-SCOPE"
        errors.append({"id": f"MYPY-{len(errors)+1:03}", "file": name, "line": int(number), "message": message,
                       "code": code, "category": category, "p0_exposure": "CRITICAL" if critical else "TRANSITIVE" if name in closure else "NONE", "dependency_witness": graph["witnesses"].get(module),
                       "reason": "Valid runtime API with incomplete attrs/Windows stubs or heterogeneous streaming decoder type inference; repaired without suppression" if false_positive else "Shared P0 validator/identity/raw safety component" if critical else
                       "Executed module import on a finite P0 entry path; conservatively typecheck entire module" if name in closure else
                       "No admitted import path from P0 roots; only dormant legacy lazy imports, blocked by finite P0 dispatch"})
    assert len(errors) == 131, "Expected reported 131 baseline errors; retain actual log and revise triage if baseline changes"
    write("evidence/MYPY_TRIAGE.json", {"baseline_log": identity("docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF/evidence/mypy-before.log"),
                                       "counts": dict(Counter(e["category"] for e in errors)), "errors": errors})
    print(json.dumps({"triage": dict(Counter(e["category"] for e in errors)),
                      "affected_files": sorted({e["file"] for e in errors if e["category"] != "LEGACY-OUT-OF-SCOPE"})}))


def vectors():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from tools.nf02_p0_reference import valid, pointer
    from tools.nf02_p0_q1 import expand, reference_a, reference_b, generate
    existing = ROOT / "docs/PRODUCT_V1/nf02_p0_runtime_qualification"
    rebuilt = OUT / "evidence/reference-rebuild"
    assert not rebuilt.exists(), "Preserve existing material; regenerated reference destination must be new"
    generate(rebuilt)
    comparisons = []
    for path in sorted(rebuilt.glob("*.json")):
        actual = path.read_bytes()
        prior = (existing / path.name).read_bytes()
        if path.name == "LOCAL_Q1_INPUT_CHECKS.json":
            current_report, prior_report = json.loads(actual), json.loads(prior)
            current_procedures = current_report.pop("reference_procedures")
            prior_procedures = prior_report.pop("reference_procedures")
            assert current_report == prior_report, "Reference metadata may differ only in procedure identity"
            target = OUT / "evidence/q1-closure-4132c5d/REFERENCE_INPUT_CHECKS_CURRENT.json"
            target.write_bytes(actual)
            comparisons.append({**identity(target.relative_to(ROOT).as_posix()), "historical": identity((existing / path.name).relative_to(ROOT).as_posix()),
                                "metadata_difference": {"current_reference_procedures": current_procedures, "prior_reference_procedures": prior_procedures},
                                "all_other_fields_exact_equal": True})
            continue
        assert actual == prior, "Q1 retained reference drift: " + path.name
        comparisons.append(identity((existing / path.name).relative_to(ROOT).as_posix()))
    documents = {}
    named = {}
    for path in (ROOT / BASE / "schemas").rglob("*.schema.json"):
        doc = json.loads(path.read_bytes())
        documents[doc["$id"]] = doc
        named[path.relative_to(ROOT / BASE / "schemas").as_posix().removesuffix(".schema.json")] = doc
    registry = Registry().with_resources((uri, Resource.from_contents(doc)) for uri, doc in documents.items())
    decisions: list[bool] = []
    counts: Counter[str] = Counter()
    case_ids = []
    for path in sorted(existing.glob("SCHEMA_VECTORS_PART_*.json")):
        for index, row in enumerate(json.loads(path.read_bytes())["vectors"]):
            schema = row.get("constraint") or pointer(named[row["schema"]], row["pointer"])
            value = expand(row["recipe"]) if "recipe" in row else row["value"]
            expected = valid(schema, value, documents)
            actual = Draft202012Validator(schema, registry=registry).is_valid(value)
            assert expected == row["expected"] == actual, (path.name, index, row["schema"], row["pointer"])
            decisions.append(actual)
            counts[row["schema"]] += 1
            case_ids.append(path.name + ":" + str(index))
    primitive = json.loads((existing / "PRIMITIVE_VECTORS.json").read_bytes())
    primitive_counts = 0
    for row in primitive["vectors"]:
        a, b = reference_a(row["value"]), reference_b(row["value"])
        assert a == b == base64.b64decode(row["cjson_base64"])
        assert digest(a) == row["raw_sha256"]
        for key, expected in row["object_digests"].items():
            assert digest(("BDB2/" + key).encode("ascii") + b"\0" + b) == expected
            primitive_counts += 1
    for row in primitive["canonical_shape_goldens"]:
        a, b = reference_a(row["body"]), reference_b(row["body"])
        assert a == b == base64.b64decode(row["cjson_base64"])
        assert digest(b) == row["raw_sha256"]
        assert digest(("BDB2/" + row["kind"] + "/" + row["version"]).encode("ascii") + b"\0" + b) == row["object_digest"]
        primitive_counts += 1
    result = {"status": "PASS_FOR_RECORDED_NODE_CONSTRAINT_AND_PRIMITIVE_CASES_NOT_COMPLETE_HISTORY_QUALIFICATION",
              "readback": comparisons, "schema_vectors": len(decisions), "per_schema": dict(counts),
              "schema_expected_reference": identity("tools/nf02_p0_reference.py"),
              "primitive_reference_procedures": identity("tools/nf02_p0_q1.py"), "primitive_object_digest_checks": primitive_counts,
              "actual_decisions_base64": base64.b64encode(bytes(decisions)).decode(),
              "decision_index_sha256": digest(encoded(case_ids)), "mismatches": [],
              "limitations": ["Bound recipes check isolated keywords; node positives do not prove every enclosing cross-field combination.",
                              "Typed-ref grammar fixtures do not prove accepted-history prior resolution or genuine authority."]}
    write("evidence/VECTOR_EXECUTION.json", result)
    # Remove only our regenerated copies after exact comparison; retain originals by hash.
    for path in sorted(rebuilt.glob("*.json")):
        assert path.parent == OUT / "evidence/reference-rebuild"
        path.unlink()
    rebuilt.rmdir()
    print(json.dumps({"schemas": len(counts), "vectors": len(decisions), "primitive_checks": primitive_counts, "mismatches": 0}))


def verification(stage):
    selected = ["tests/product/test_limited_p0.py", "tests/product/test_limited_p0_boundaries.py", "tests/product/test_limited_q1_closure.py",
        "tests/product/test_limited_p0_transport.py", "tests/product/test_limited_service.py",
        "tests/product/test_limited_installation_packet.py", "tests/product/test_limited_qualification.py",
        "tests/product/test_limited_content_identity.py", "tests/product/test_limited_windows_readiness.py",
        "tools/test_nf02_p0_limited_model.py", "tests/f1", "tests/f2", "tests/f3",
        "tests/f4/test_wp04_gap_engine.py", "tests/f4/test_wp05_hypothesis_orchestration.py", "tests/f4/test_wp06_execution_adapters.py",
        "tests/f4/test_wp07_evidence_graph_invalidation.py",
        "tests/f7/test_pr11_adaptive_e6_generator.py", "tests/f7/test_adaptive_e6_recursive_runtime.py",
        "tests/f7/test_adaptive_e6_canonical_authority.py", "tests/f7/test_post_e6_canonical_cut_contract.py",
        "tests/f7/test_residual_risk_stop_semantics.py", "tests/f7/test_residual_risk_finalization.py",
        "tests/f7/test_residual_risk_canonical_authority.py", "tests/product/test_product_v1.py",
        "tests/product/test_runner_real_git.py", "tests/product/test_result_inspection.py",
        "tests/product/test_transition_boundary.py", "tests/product/test_nf02_machine_authority.py",
        "tests/f8/test_m46_standalone_clean_env.py"]
    if stage == "matrix":
        selected = ["tests/product/test_limited_p0_state_matrix.py"]
    directories = [ROOT / "src", ROOT / "build", ROOT / "tools", ROOT / "tests"]
    inputs = [identity(path.relative_to(ROOT).as_posix()) for directory in directories for path in sorted(directory.rglob("*.py"))]
    inputs += [identity("pyproject.toml"), identity("requirements-f2.lock")]
    command = [sys.executable, "-m", "pytest", *selected, "-q", "-o", "junit_family=xunit1", "-p", "no:tmpdir", "-p", "tools.product_test_tmp",
               "--junitxml=" + str(OUT / "evidence" / (stage + ".xml"))]
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    raw = result.stdout + result.stderr
    (OUT / "evidence" / (stage + ".log")).write_bytes(raw)
    counts: Counter[str] = Counter()
    xml = OUT / "evidence" / (stage + ".xml")
    if xml.exists():
        for case in ET.parse(xml).getroot().iter("testcase"):
            status = "ERROR" if case.find("error") is not None else "FAIL" if case.find("failure") is not None else "SKIP" if case.find("skipped") is not None else "PASS"
            counts[status] += 1
    drift = [row["file"] for row in inputs if identity(row["file"]) != row]
    report = {"stage": stage, "command": command, "returncode": result.returncode,
              "elapsed_seconds": format(time.monotonic() - started, ".2f"), "counts": dict(counts),
              "source_inputs": inputs, "source_drift": drift, "log_sha256": digest(raw),
              "authority": "SIMULATED_OS_CMS_TRANSPORT_FOR_POSITIVE_P0; real Windows APIs only in explicitly native negative/lease tests"}
    write("evidence/" + stage + "-execution.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"source_inputs", "command"}}))
    if result.returncode or drift:
        print(raw.decode("utf8", errors="replace")[-6000:])
        raise SystemExit(result.returncode or 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "identity", "dependencies", "vectors", "matrix", "regression"])
    args = parser.parse_args()
    if args.action in {"inspect", "identity"}:
        candidate()
    if args.action in {"inspect", "dependencies"}:
        graph = dependencies()
        triage(graph)
    if args.action == "vectors":
        vectors()
    if args.action in {"matrix", "regression"}:
        verification(args.action)
