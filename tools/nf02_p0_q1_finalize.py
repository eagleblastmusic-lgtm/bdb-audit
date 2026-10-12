"""Finish exact Q1 evidence, without issuing authority or changing the norm."""
import argparse
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from tools.nf02_p0_q1 import reference_a
from tools.nf02_p0_q1_readback import info, read, jsonl, ROOT, HERE, RUN
from tools.nf02_p0_reference import sha, history


def save(path, value):
    path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf8") + b"\n")


def command(args, log, *, cwd=ROOT, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True)
    raw = result.stdout + result.stderr
    log.write_bytes(raw)
    if result.returncode:
        print(raw.decode("utf8", errors="replace")[-6000:])
        raise AssertionError((args, result.returncode))
    return raw


def checks():
    from tools.nf02_p0_final_audit import candidate, dependencies
    candidate()
    closure = dependencies()
    procedures = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("nf02_p0*.py"))
    files = closure["files"] + ["build/build_single_file.py", *procedures, "tests/product/test_limited_q1_closure.py"]
    args = [sys.executable, "-m", "mypy", *files, "--follow-imports=silent"]
    command(args, RUN / "mypy-final-closure.log")
    command([sys.executable, "-m", "mypy"], RUN / "mypy-final-configured.log")
    command([sys.executable, "-m", "ruff", "check", "src", "build/build_single_file.py", *procedures,
             "tests/product/test_limited_q1_closure.py"], RUN / "ruff-final.log")
    command([sys.executable, "tools/nf02_p0_limited_model.py", "--check"], RUN / "candidate-final-check.log")
    # The historical 131-error triage remains intact. No legacy scope expansion.
    save(RUN / "TYPE_AND_LINT_EXECUTION.json", {"status": "PASS", "p0_module_count": closure["module_count"],
        "checked_files": len(files), "command": args, "inputs": [info(ROOT / name) for name in files],
        "logs": [info(RUN / name) for name in ("mypy-final-closure.log", "mypy-final-configured.log", "ruff-final.log", "candidate-final-check.log")],
        "legacy_full_src": "83 previously triaged remaining errors; full legacy source not rerun or expanded by this Q1 continuation"})
    print("FINAL_TYPES_LINT_CANDIDATE_PASS", len(files), flush=True)


def build():
    out = RUN / "build-current-v2"
    out.mkdir(parents=True, exist_ok=False)
    builder = runpy.run_path(str(ROOT / "build/build_single_file.py"))
    artifact = out / "bdb_p0_unqualified.py"
    first = builder["build_standalone"](artifact)
    second = builder["build_standalone"](out / "determinism-repeat.py")
    assert first[1:] == second[1:] and artifact.read_bytes() == (out / "determinism-repeat.py").read_bytes()
    namespace = runpy.run_path(str(artifact))
    payload = namespace["get_payload_bytes"]()
    verified = namespace["verify_embedded_payload"]()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        payload_sources = {}
        for name in archive.namelist():
            source = ROOT / "src" / name
            if name.startswith("bdb_audit/"):
                assert source.is_file(), name
                original = source.read_bytes()
                normalized = original.decode("utf8").replace("\r\n", "\n").replace("\r", "\n").encode("utf8") if source.suffix in {".py", ".json", ".md", ".txt"} else original
                assert normalized == archive.read(name), name
                payload_sources[name] = {"source_raw_sha256": sha(original), "payload_lf_sha256": sha(normalized)}
    # Isolate setuptools output so existing build/lib and egg-info WIP is untouched.
    stage = out / "wheel-staging"
    stage.mkdir()
    shutil.copytree(ROOT / "src/bdb_audit", stage / "src/bdb_audit", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(ROOT / "pyproject.toml", stage / "pyproject.toml")
    command([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--no-index", "-w", str(out)], out / "wheel-build.log", cwd=stage)
    wheel, = out.glob("*.whl")
    wheel_sources = {}
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith("bdb_audit/") and not name.endswith("/"):
                source = ROOT / "src" / name
                assert source.is_file() and source.read_bytes() == archive.read(name), name
                wheel_sources[name] = sha(source.read_bytes())
    native_env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    command([sys.executable, "-I", str(artifact), "--verify-payload"], out / "payload-verify.log", cwd=out, env=native_env)
    target = out / "MUST_NOT_EXIST.sqlite"
    result = subprocess.run([sys.executable, "-I", str(artifact), "product", "p0", "status", "--store", str(target)],
                            cwd=out, env=native_env, capture_output=True)
    (out / "production-denial.log").write_bytes(result.stdout + result.stderr)
    denial = json.loads(result.stdout + result.stderr)
    assert result.returncode == 2 and denial["error"] == "P0_INSTALLATION_AUTHORITY_NOT_ESTABLISHED" and not target.exists()
    report = {"status": "UNQUALIFIED_LOCAL_BUILD_READBACK_PASS_NOT_RELEASE_OR_AUTHORITY", "deterministic_repeat": True,
              "standalone": info(artifact), "wheel": info(wheel), "verified_payload_files": len(verified),
              "verified_wheel_source_files": len(wheel_sources), "payload_source_manifest": payload_sources,
              "wheel_source_manifest": wheel_sources, "production_denial": {"exit_code": result.returncode, "error": denial["error"], "database_created": False},
              "inputs": [info(ROOT / "build/build_single_file.py"), info(ROOT / "pyproject.toml"), info(ROOT / "requirements-f2.lock")],
              "protected_wip": "Existing repository build/lib and src/*.egg-info were not used as build output"}
    save(out / "BUILD_READBACK.json", report)
    print("CURRENT_BUILD_READBACK_PASS", len(verified), len(wheel_sources), first[1], flush=True)


def counts(path):
    result = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
    for case in ET.parse(path).getroot().iter("testcase"):
        key = "ERROR" if case.find("error") is not None else "FAIL" if case.find("failure") is not None else "SKIP" if case.find("skipped") is not None else "PASS"
        result[key] += 1
    return result


def assemble():
    audit = read(RUN / "FINAL_Q1_AUDIT.json")
    assert not audit["unexplained_mismatches"] and len(audit["per_schema"]) == 43
    regression = counts(HERE / "evidence/regression.xml")
    assert regression["PASS"] >= 568 and not sum(regression[k] for k in ("FAIL", "ERROR", "SKIP"))
    for stage in ("regression", "matrix"):
        execution = read(HERE / "evidence" / (stage + "-execution.json"))
        assert execution["returncode"] == 0 and not execution["source_drift"]
        for row in execution["source_inputs"]:
            assert info(ROOT / row["file"]) == row
    model = read(ROOT / "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/MODEL.json")
    matrix = read(HERE / "02_Q1_COVERAGE_MATRIX.json")
    ctx = read(RUN / "contexts-final/CONTEXT_EXECUTION.json")
    results = [info(RUN / path) for path in ("FINAL_Q1_AUDIT.json", "contexts-final/CONTEXT_EXECUTION.json", "contexts-final/CONTEXT_CASES.jsonl",
        "adversarial-current-v2/ADVERSARIAL_EXECUTION.json", "adversarial-current-v2/ADVERSARIAL_CASES.jsonl", "replay-current/REPLAY_EXECUTION.json",
        "replay-current/REPLAY_CASES.jsonl", "entrypoints-current/ENTRYPOINT_EXECUTION.json", "entrypoints-current/ADVERSARIAL_CASES.jsonl",
        "supplement-current/SUPPLEMENT_EXECUTION.json", "supplement-current/ADVERSARIAL_CASES.jsonl", "same-create-fixed/EXECUTION.json",
        "TYPE_AND_LINT_EXECUTION.json", "build-current-v2/BUILD_READBACK.json")]
    old_gaps = {g["id"]: g for g in matrix["open_obligations"]}
    gaps = []
    descriptions = {
        "QG-01": ("CLOSED_LOCAL_Q1", "Full enclosing 43-schema contexts and branch/conditional products executed; every exact full input reconstructed and independently rechecked in final audit"),
        "QG-02": ("CLOSED_LOCAL_Q1", "Actual accepted foreign/prior/future/other-attempt target pools, own/future/stale cuts, wrapper replay mutations and applicable entry points executed on final code; same-create defect fixed and exact counterexample regressed"),
        "QG-03": ("OPEN_EXTERNAL_INPUT", "PENDING_OWNER_PROVISIONING: actual owner_actor_ref, public DER SHA-256 independently confirmed, exact owner decision plus real detached CMS are absent; native positive legal authority input proof cannot be manufactured. Q2/RQ/mandate are subsequent gates, not prerequisites invented for Q1"),
        "QG-04": ("OPEN_DEPENDS_ON_QG_03", "Final retained readback completed with zero unexplained mismatch. AUTHOR_QUALIFICATION only permits READY; no real owner_decision_sha256 exists, so no author record or signature is issued"),
    }
    for gid, (status, actual) in descriptions.items():
        gap = dict(old_gaps[gid])
        gap.update(status=status, actual=actual, missing=None if gid in {"QG-01", "QG-02"} else actual,
                   evidence=results if gid in {"QG-01", "QG-02"} else [info(HERE / "10_EXTERNAL_INPUT_REQUEST.md"), info(HERE / "OWNER_MODEL_DECISION_TEMPLATE.md"), info(RUN / "FINAL_Q1_AUDIT.json")])
        gaps.append(gap)
    matrix.update(open_obligations=gaps, status="Q1_OPEN_ONLY_REAL_OWNER_INPUT_AND_AUTHOR_RECORD_REMAIN", final_readback=info(RUN / "FINAL_Q1_AUDIT.json"),
                  continuation_checkpoint="4132c5d81599042ccaef21e9a92f7bb84ac88645", current_regression=regression, author_record_issued=False)
    for family in matrix["families"]:
        family["open_obligations"] = [g for g in family["open_obligations"] if g not in {"QG-01", "QG-02"}]
        family["verdict"] = "OPEN" if family["open_obligations"] else "PASS_FOR_Q1_AUTHOR_LOCAL_FAMILY_SCOPE"
        family["current_evidence"] = results
    proof_map = {
        "artifact_contract_registry": ["test_approved_corpus_exact_and_immutable", "test_initial_root_order_is_semantic_not_only_schema"],
        "schema_registry": ["test_each_initial_schema_binding_rejects_other_actual_schema_bytes", "test_initial_root_order_is_semantic_not_only_schema", "test_offline_root_packet_has_all_six_objects_and_exact_eight_pins"],
        "policy_revision": ["test_service_has_only_finite_p0_commands", "test_no_generic_or_same_commit_transition_bypass"],
        "spec_revision": ["test_no_generic_or_same_commit_transition_bypass", "test_legal_bootstrap_binding_then_later_started"],
        "trust_profile": ["test_real_authority_absent_does_not_create_database", "test_current_rights_lost_at_final_commit_roll_back"],
        "installation_bootstrap_profile": ["test_offline_root_packet_has_all_six_objects_and_exact_eight_pins", "test_history_namespace_cannot_be_escaped_by_parent_segments"],
        "nf02_p0_source_snapshot": ["test_m07_full_algorithm_oid_lengths_and_mode_product", "test_git_replace_cannot_change_the_tree_of_an_approved_commit", "test_m07_zero_based_source_cannot_be_accepted"],
        "campaign_genesis": ["test_legal_bootstrap_binding_then_later_started", "test_incomplete_or_conflicting_qualification_fails_closed", "test_chain_predicates_do_not_conflate_production_and_qualification"],
        "attempt": ["test_abort_retry_and_terminal_release_denial", "test_assignment_requires_attempt_from_same_create_with_exact_scoped_grant"],
        "assignment_manifest": ["test_assignment_context_with_correctly_scoped_signed_test_grant", "test_assignment_requires_attempt_from_same_create_with_exact_scoped_grant"],
        "assignment_package_binding": ["test_binding_denial_has_no_file_mutation", "test_cas_equal_command_retry_and_competing_binding", "test_acceptance_crash_rolls_back_all_raw_facts_receipts_and_head"],
        "nf02_p0_delivery": ["test_release_crash_retry_has_same_id_and_bytes", "test_signed_ack_evidence_later_result_real_store_e1_inbox_restart"],
        "lane_result_admission_evidence": ["test_evidence_or_result_substitution_denied_without_mutation", "test_auditor_revocation_at_final_commit_rolls_back_evidence", "test_signed_ack_evidence_later_result_real_store_e1_inbox_restart"],
        "bdb_audit_lane_result": ["test_evidence_or_result_substitution_denied_without_mutation", "test_signed_ack_evidence_later_result_real_store_e1_inbox_restart"],
        "nf02_p0_abort": ["test_abort_retry_and_terminal_release_denial", "test_current_rights_lost_at_final_commit_roll_back"],
        "command_envelope": ["test_no_generic_or_same_commit_transition_bypass", "test_generator_events_are_snapshotted_once_by_same_store", "test_missing_command_field_is_schema_denial_before_field_access"],
        "commit_body": ["test_acceptance_crash_rolls_back_all_raw_facts_receipts_and_head", "test_real_process_exit_and_new_process_replay", "test_cas_equal_command_retry_and_competing_binding"],
        "command_receipt": ["test_cas_equal_command_retry_and_competing_binding", "test_signed_ack_evidence_later_result_real_store_e1_inbox_restart"],
    }
    testcases = list(ET.parse(HERE / "evidence/regression.xml").getroot().iter("testcase"))
    for contract in matrix["contracts"]:
        kind = contract["contract"].split("/")[0]
        tests = [{"name": tc.attrib["name"], "classname": tc.attrib["classname"], "expected": "PASS normative assertions", "actual": "PASS"}
                 for tc in testcases if any(tc.attrib["name"].split("[")[0] == name for name in proof_map[kind])]
        assert all(any(tc["name"].split("[")[0] == name for tc in tests) for name in proof_map[kind]), kind
        for predicate in contract["predicates"]:
            predicate.update(mandatory_complete_case_closure="LOCAL_Q1_EXECUTED_REAL_AUTHORITY_REMAINS_QG_03_OR_RQ",
                tests=tests, test_evidence=info(HERE / "evidence/regression.xml"), concrete_history_and_mutation_cases=results,
                expected_basis="Exact frozen MODEL predicate plus literal test assertions and independent SQL/primitive procedures; not observed SUT output as oracle")
    # Each material field is indexed separately; array dispatch is constrained by the eight frozen operations.
    examples: dict[str, list[dict[str, Any]]] = {}
    sources = [RUN / "adversarial-final/CAMPAIGN_A/p0.sqlite", RUN / "adversarial-verified/CAMPAIGN_B/p0.sqlite", RUN / "supplement-current/THREE_ATTEMPTS.sqlite"]
    for source in sources:
        with sqlite3.connect(source) as con:
            bodies = [(kind, version, raw) for kind, version, raw in con.execute("SELECT kind,version,body FROM immutable_objects")]
            bodies += [(kind, "3", raw) for kind, table in (("commit_body", "commits"), ("command_receipt", "receipts")) for raw, in con.execute("SELECT body FROM " + table)]
            for kind, version, raw in bodies:
                body = json.loads(raw)
                key = kind + "/" + version
                for spec in model["canonical_contracts"][key]["material_refs"]:
                    field = spec["field"]
                    value = body[field]
                    refs = value if isinstance(value, list) else [] if value is None else [value]
                    examples.setdefault(key + "::" + field, []).append({"source": info(source), "body_cjson_sha256": sha(raw),
                        "field_cjson_sha256": sha(reference_a(value)), "actual_target_keys": sorted({r["kind"] + "/" + r["version"] for r in refs}),
                        "operation": body.get("operation"), "expected": "NORMATIVE_EXACT_REFERENCE_AND_CLASS", "actual": "ACCEPTED_TEST_HISTORY_INDEPENDENTLY_READBACK"})
    inventory = []
    for key, definition in model["canonical_contracts"].items():
        for spec in definition["material_refs"]:
            field = spec["field"]
            coverage_key = key + "::" + field
            positive = examples[coverage_key]
            cases = audit["material_field_case_index"].get(definition["kind"] + "::" + field, [])
            replay_cases = [{"id": r["id"], "input_database_sha256": r["input_database_sha256"], "recipe": r["input_recipe"]}
                            for r in jsonl(RUN / "replay-current/REPLAY_CASES.jsonl") if r["input_recipe"].get("remove") == field or r["input_recipe"].get("last_commit_field") == field or field in r["input_recipe"].get("replace", {})]
            assert cases or replay_cases, coverage_key
            inventory.append({"id": coverage_key, "contract": key, "ref": spec, "status": "LOCAL_Q1_EXECUTED_WITH_FINITE_APPLICABILITY",
                "positive_examples": positive, "negative_cases": cases, "replay_cases": replay_cases,
                "schema_contexts": {**info(RUN / "contexts-final/CONTEXT_CASES.jsonl"), "schema": "canonical/" + definition["kind"] + "__" + definition["version"], "path_prefix": [field]},
                "applicability": "Only operation-defined content/basis/result targets may occur. Root pins cannot become per-campaign prior objects; null predecessors apply only to initial attempt; terminal result cannot become a basis for a later operation. Union shape alternatives are executed separately from actual accepted targets.",
                "independent_expected": "Frozen Registry allowed_keys/ref_class, independent history check and exact expected/actual cases; no inferred blanket denial"})
    assert len(inventory) == 37
    matrix["material_target_case_inventory_previous_481"] = "Historical planning rows superseded by the 37 complete field records and concrete linked case streams"
    matrix["material_target_case_inventory"] = inventory
    matrix["full_enclosing_contexts"] = {"report": info(RUN / "contexts-final/CONTEXT_EXECUTION.json"), "count": ctx["case_count"], "per_schema": ctx["per_schema"]}
    save(HERE / "02_Q1_COVERAGE_MATRIX.json", matrix)
    finish_documents(matrix, audit, regression, results)
    manifest()
    print("Q1_FINAL_ASSEMBLED_OPEN_EXTERNAL_OWNER", regression, flush=True)


def finish_documents(matrix, audit, regression, results):
    def document(name, content):
        (HERE / name).write_text(content, encoding="utf8", newline="\n")
    rows = {g["id"]: g for g in matrix["open_obligations"]}
    detail = "\n".join(f"| {gid} | {g['status']} | {g['actual']} |" for gid, g in rows.items())
    outcomes = audit["cases"]
    count_text = f"{regression['PASS']} PASS / {regression['FAIL']} FAIL / {regression['ERROR']} ERROR / {regression['SKIP']} SKIP"
    local = f"{audit['contexts']} full-document schema cases / 43 schemas; {outcomes['adversarial-current-v2']} material/context/entry/retry cases; {outcomes['supplement-current']} joint role/prepare/release/retry cases; {outcomes['entrypoints-current']} alternate entry cases; {audit['replay_cases']} replay corruption cases"
    fix = read(RUN / "same-create-fixed/EXECUTION.json")
    document("00_STATUS.md", f"""# BDB NF02 P0 — końcowy pakiet Q1

**Q1 OPEN. QG-01 i QG-02 CLOSED_LOCAL_Q1; QG-03 OPEN_EXTERNAL_INPUT; QG-04 OPEN_DEPENDS_ON_QG_03.** Nie wydano AUTHOR_QUALIFICATION. Q2/RQ NOT_RUN, produkcyjny import BLOCKED.

Kontynuacja checkpointu `4132c5d81599042ccaef21e9a92f7bb84ac88645`, gałąź `work/nf02-runtime-completion`. Zamrożony model BDB_NF02_P0_LIMITED_1 pozostaje 18/7/43. Manifest `278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9`; oba set digests i graph ponownie zweryfikowano względem zatwierdzonych bajtów. Finalny commit jest wskazany w końcowym raporcie i terminalnym POST_COMMIT_READBACK_CURRENT.json; nie wpisujemy samoodnoszącego SHA do jego własnego preimage.

Końcowa regresja: **{count_text}**. Oddzielnie 72 pary operacja–stan: 13 dozwolonych i 59 odmów. Nowe dowody: {local}. Te strumienie nie są sumowane jako liczba pytest. Każdy ma expected/actual i dokładne hashe wejść albo odtwarzalne recepty. 8100 wcześniejszych wektorów i 72 primitive checks zostały ponownie sprawdzone dwoma koderami/reference interpreterem.

Naprawiono rzeczywisty błąd: Assignment mógł wskazać wcześniejszy Attempt mimo nowego Attempt w CREATE_ASSIGNMENT. Dodano dokładne powiązanie z obiektem tej komendy; te same bajty są teraz DENY bez mutacji, a wadliwa historia jest odrzucana przy replay. Pozostałe predykaty runtime, Store, Coordinator, E1, CLI, source Git i parsers wykonują prawdziwy kod. OS/CMS/HTTPS w dodatnich testach są jawnie lokalną symulacją.

Pełny rzeczywisty import closure P0 przechodzi mypy; Ruff/configured mypy i rebuild/readback PASS. Nie rozszerzano prac na legacy: historyczna klasyfikacja 131 pozostaje w 04; 83 pozostałe błędy legacy nie należą do admitted closure. Nowe narzędzia Q1 sprawdzono osobno wraz z closure.

Windows: artefakty instalatora/usługi i bezpieczne lokalne kontrole przygotowane; **rzeczywista instalacja, ACL, niezależna PKI i audyt zewnętrzny UNQUALIFIED**. Nie wykonano instalacji ani zmiany ACL. Nowy standalone/wheel mają dokładny source readback i zamkniętą bramkę bez authority.

Od owner potrzebne są rzeczywisty identyfikator, publiczny DER i niezależnie potwierdzony SHA-256 oraz podpisana exact decyzja. Procedura: 10_EXTERNAL_INPUT_REQUEST.md; jawny rejestr: EXTERNAL_DEPENDENCIES.json. Template pozostaje niekompletnym Markdownem, nie rekordem authority. Pozostałe rzeczywiste role/hosty/mandate należą do późniejszych Q2/RQ.

WIP zachowano. Nie wykonano push, merge, release, migracji ani aktywacji produkcyjnego importu.
""")
    family_table = "\n".join(f"| {f['id']} | {f['verdict']} | {', '.join(f['open_obligations']) or 'brak'} |" for f in matrix["families"])
    document("01_Q1_FINAL_REPORT.md", f"""# Końcowa ocena autora Q1

**Q1 OPEN — pozostały rzeczywiste wejścia owner i zależny author record.** Pełny zakres 18 kontraktów / 7 profili / 43 schematów, M01–M18 i 11 rodzin został oceniony. Zakończono lokalne brakujące przypadki QG-01 i QG-02. Nie utożsamiamy tej oceny z niezależnym Q2/RQ ani produkcyjną authority.

| Blocker | Status | Wynik i pozostały obowiązek |
|---|---|---|
{detail}

| Rodzina | Ocena w granicy Q1 | Pozostałe obowiązki |
|---|---|---|
{family_table}

QG-01: {audit['contexts']} pełnych enclosing documents obejmuje każdą osiągalną nested union/enum/required/type/closed/bound gałąź, pary initial/retry oraz iloczyn mode/RQ/mandate i operation/mode/parent. Wartości max±1 są odtwarzane z recept; legalna/nielegalna kombinacja wynika z zamrożonego schematu i niezależnego interpretera. Schema-only acceptance nie jest legalną authority/history. Finalny readback rekonstruuje całe wejścia, weryfikuje dwa kodery, dokładne SHA/length/schema bytes i ponownie ustala expected niezależną procedurą.

QG-02: {local}. Wszystkie 37 material fields mają oddzielne wiersze z positive history, target/class i negative case IDs; wrapper arrays mają finite dispatch zgodny z ośmioma komendami. Accepted foreign-campaign i inne-attempt targets pochodzą z rzeczywiście przyjętych testowych historii. Future/self/same-commit/own-cut/stale substitutions, immediate predecessor, raw durability, authorization/current scope, command/commit/receipt equality i dokładny retry mają rzeczywiste wyniki. Root pins są wspólne dla instalacji; result po stanie terminalnym nie jest legalnym basis target dla następnej komendy. Wykluczenia wynikają z M05/Registry, nie lokalizacji pliku ani arbitralnego pominięcia wariantu.

Znaleziono i naprawiono F11: SAME_CREATE_ASSIGNMENT_CONTENT nie był egzekwowany, gdy ref rozwiązywał się do prior accepted Attempt. Test miał poprawnie dopasowany testowy grant i CMS, dlatego nie maskował problemu na authority. Exact input DB SHA-256 `{fix['source_database_sha256']}`; packet SHA-256 `{fix['proposal_transport_sha256']}`; signing preimage SHA-256 `{fix['command_signing_sha256']}`. Przed poprawką actual ACCEPTED_COUNTEREXAMPLE przy expected DENY; po poprawce te same bajty dają DENY_WITHOUT_MUTATION, a reader odrzuca wadliwy accepted DB. Historyczny kontrprzykład jest oznaczony jako nieważna testowa historia. Regresja i niezależny history oracle obejmują tę klasę.

Dodatkowe 33 kontrole semantyczne sprawdzają wszystkie 18 schema bindings przeciw innym rzeczywistym schema bytes, semantyczną kolejność Registry/SchemaRegistry, siedem exact profile pins i sześć Assignment contexts z dopasowanymi grantami. 32 kombinacje Git SHA1/SHA256 × mode 100644/100755 × commit/tree/blob length korzystają z rzeczywistych repozytoriów, niezależnie wyliczonych typed Git hashes i struct/CRC ZIP. JUnit zachowuje raw Git objects i exact source transport inputs.

Końcowy pytest: **{count_text}**. Matrix 72 cases wykonano osobno; nie zwiększa sztucznie licznika pytest o 72. 8100 node/bounds vectors, 414 typed-ref vectors, dziewięć strukturalnych DAG probes i 72 primitive checks zachowują swoje ograniczone znaczenie. Pełne accepted DAG/history mają osobny niezależny readback; syntetyczne DAG inputs są wyłącznie danymi testującymi prawdziwą funkcję ordering.

QG-03: user potwierdził PENDING_OWNER_PROVISIONING. Brakuje formalnego owner_actor_ref, niezależnie potwierdzonego publicznego SHA-256 DER oraz podpisanych exact OWNER_MODEL_DECISION bytes. Nie można wykonać prawdziwego pozytywnego native CMS/readback ani przypisać owner authority na podstawie stringów/testowych cert pinów. Negatywne native CMS i lokalne role/scope/mode/grant cases są wykonane. Żądanie wejść i procedura public DER, oddzielnego potwierdzenia i podpisu są w 10. Brak realnego Q2 freeze lub RQ przed Q1 nie jest błędnie ustanowionym warunkiem; te etapy pozostają późniejsze.

QG-04: pełny retained final audit wykonano, brak niewyjaśnionych mismatches. Schemat AUTHOR_QUALIFICATION/1 dopuszcza wyłącznie P0_AUTHOR_BASELINE_READY i wymaga prawdziwego owner_decision_sha256. Dlatego nie powstał rekord OPEN ani placeholder READY. Po realnym ustanowieniu danych konieczne są native verification, exact final readback, zamknięcie QG-03 i dopiero zewnętrzny author-only record z independent_assurance=false.

Macierz 02 mapuje każde wymaganie/predykat do źródeł normy, actual testów lub niezależnych dowodów. Rejestr 03 oraz EVIDENCE_MANIFEST wiążą hashe i lokalizacje. Materiały starych przebiegów są provenance/construction, a bieżące execution directories dowodzą końcowego predykatu. Mypy obejmuje conservative rzeczywisty import closure; brak zmian import graph i dwóch linii predykatu nie uzasadnia napraw legacy.

Nie zmieniono zatwierdzonej normy, R5.4.2 ani zakresu 18/7/43. Produkcyjny import pozostaje BLOCKED. Q2/RQ nie wykonano za kwalifikatora. Windows jest przygotowany do późniejszej kwalifikacji, bez twierdzenia o realnej instalacji/PKI/ACL PASS.
""")
    deps = {"format": "Q1_EXTERNAL_INPUT_REQUEST_DOCUMENTATION_ONLY", "status": "PENDING_OWNER_PROVISIONING", "canonical_record": False,
            "missing": [
                {"id": "OWNER_IDENTITY", "requirement": "M18 OWNER_MODEL_DECISION.owner_actor_ref; Q1-09/Q1-11", "status": "PENDING_OWNER_PROVISIONING", "required": "Actual owner designation, nonempty 1..4096 string and retained authenticated mapping to the real owner"},
                {"id": "OWNER_PUBLIC_DER_PIN", "requirement": "M01/M02, Q1-08/Q1-09 exact signer and independently approved inputs", "status": "PENDING_OWNER_PROVISIONING", "required": "Public DER certificate, SHA-256 confirmed through an independent authenticated channel, operators/time/channel confirmation; no private key/PFX/password"},
                {"id": "SIGNED_EXACT_OWNER_DECISION", "requirement": "M18, Q1-09/Q1-11 and author owner_decision_sha256", "status": "PENDING_OWNER_PROVISIONING", "required": "Schema-valid actual owner decision binding manifest, graph, both set digests and all eight accepted limits; detached CMS/SHA-256 with valid chain/current revocation"}],
            "blocked": {"QG-03": ["positive genuine owner CMS/authority input verification", "legal independently approved initial source/view/task/root/pins authority proof"], "QG-04": ["author-only READY record after QG-03 and fresh final exact readback"]},
            "later_not_q1_prerequisites": ["Q2 independent review/FREEZE", "owner+qualifier mandate", "real qualified installation, scoped grants, separated service/auditor hosts", "RQ 32 families and real original ZIP/ACK/return", "signed PRODUCTION installation"],
            "procedure": info(HERE / "10_EXTERNAL_INPUT_REQUEST.md"), "template": info(HERE / "OWNER_MODEL_DECISION_TEMPLATE.md"), "author_record_issued": False}
    save(HERE / "EXTERNAL_DEPENDENCIES.json", deps)
    document("09_RELEASE_READINESS.md", """# Granica gotowości

**Production import BLOCKED; Q1 OPEN (QG-03/QG-04); Q2/RQ NOT_RUN.** QG-01/QG-02 są zamknięte w granicy autora/lokalnych testów. Rzeczywisty błąd same-create naprawiono. Pełny P0 dependency closure, final regression, exact norm/readback i niekwalifikowany rebuild są zweryfikowane.

Pozostałe zewnętrzne działania owner opisuje 10_EXTERNAL_INPUT_REQUEST.md i EXTERNAL_DEPENDENCIES.json. Brak identyfikatora/certyfikatu nie został zastąpiony placeholderem. Po odbiorze realnych signed inputs następują native CMS/current PKI verification i nowy final audit; author record READY powstaje tylko przy pełnym Q1. Q2 review/freeze wykonuje uprawniony niezależny kwalifikator, potem legalny owner+qualifier mandate umożliwia RQ w osobnym qualification namespace. Instalacja na hoście wymaga osobnego upoważnienia.

Windows artifacts/runbook są przygotowane, real SCM/ACL/PKI/external audit pozostają UNQUALIFIED. Nowy standalone i wheel są UNQUALIFIED LOCAL BUILD, z kontrolą źródeł i odmową bez authority. Nowy build nie jest release ani produkcyjną instalacją. Realny RQ i podpisana instalacja PRODUCTION są konieczne do aktywacji wyłącznie nowej pustej campaign. Qualification history/results nie są migrowane do produkcji.

Nie ma znanego otwartego lokalnego defektu krytycznego P0 w wykonanym zakresie. Historycznych 83 legacy typing errors nie ukryto; conservative import graph wyklucza ich udział w finite P0 path. Zmiana tego grafu wymaga ponownej oceny. Brak niezależnej authority i Q2/RQ jest realnym ograniczeniem obecnej gotowości, nie lokalnym PASS do obejścia.
""")
    register = read(HERE / "03_GOLDEN_VECTOR_REGISTER.json")
    register["continuation_checkpoint"] = matrix["continuation_checkpoint"]
    register["current_closure"] = {"QG-01": rows["QG-01"]["status"], "QG-02": rows["QG-02"]["status"], "artifacts": results,
        "expected_basis": "Frozen literal normative predicates; independent schema interpreter, two CJSON procedures, independent SQL history/class/receipt checks, typed Git objects and struct ZIP",
        "authority": "SIMULATED_OS_CMS_HTTPS_FOR_LOCAL_POSITIVE_CASES; no independent assurance", "full_input_recipes": info(RUN / "contexts-final/CONTEXT_BASES.json")}
    for area in register.get("areas", []):
        if area.get("area") == "schema_nested_union_enum_bounds":
            area["claim"] = "8100 node cases plus complete current enclosing document execution/readback linked in current_closure; not authority"
    save(HERE / "03_GOLDEN_VECTOR_REGISTER.json", register)
    document("11_Q1_REPRODUCTION.md", """# Odtworzenie końcowego Q1

Start: dokładny checkout, Windows, zamrożone dependencies requirements-f2.lock, bez instalacji usługi/ACL. Manifest entries są względem repository_root. Najpierw SHA-256 wszystkich entries, następnie `tools/nf02_p0_limited_model.py --check`. Nie traktować historycznego wadliwego DB jako valid campaign.

```powershell
$env:PYTHONPATH = 'src'
.\\.venv-f2\\Scripts\\python.exe -m tools.nf02_p0_q1_finalize checks
.\\.venv-f2\\Scripts\\python.exe -m tools.nf02_p0_final_audit vectors
.\\.venv-f2\\Scripts\\python.exe -m tools.nf02_p0_final_audit matrix
.\\.venv-f2\\Scripts\\python.exe -m tools.nf02_p0_final_audit regression
.\\.venv-f2\\Scripts\\python.exe -m tools.nf02_p0_q1_readback
```

Long-running harness CLI: `nf02_p0_q1_contexts --output NEW_DIRECTORY`; `nf02_p0_q1_adversarial --replay-templates RETAINED_TEMPLATES --output NEW_DIRECTORY`; `nf02_p0_q1_history --source RETAINED_SQLITE --output NEW_DIRECTORY`; `nf02_p0_q1_supplement` i `nf02_p0_q1_entrypoints` przyjmują `--source`, `--templates`, `--output`. Wszystkie moduły uruchamia się przez `python -m tools.<nazwa>`. Nowe katalogi są wymagane, aby zachować stare dowody. Nie używać opcji reuse-cases do twierdzenia, że runtime ponownie wykonał te przypadki.

Retained integration inputs wiążą rzeczywistą lokalizację approved Git repository wpisaną w testowym SOURCE_REPOSITORIES.json. Exact replay wymaga tego samego checkout path i retained Git bytes. Na nowym hoście `nf02_p0_q1_adversarial --output NEW_DIRECTORY` buduje od nowa rzeczywiste repozytoria, historie i testowe authority; nowe UUID i verified_at dają nowe exact hashes. Expected predicates nadal wynikają z zamrożonej normy. Local simulated OS/CMS/HTTPS nie stają się real authority przez regenerację.

Finalny readback odtwarza full schema inputs i replay recipes, ponawia independent expected checks oraz wiąże inputs/outputs. Material-field case index jest w FINAL_Q1_AUDIT.json, szczegóły 37 pól i wszystkich kontraktowych predykatów w 02. Exact input hashes są w każdym JSONL wierszu; duże ciągi/tablice są receptami bez redundantnych kopii. Regression JUnit zawiera raw Git object/manifest/archive properties.

Realne owner inputs: wyłącznie procedura 10, bez zastępowania braków testowym podpisem. Q1/Q2/RQ i authority pozostają odrębnymi bramkami. Narzędzia checks/build/readback/assemble nie tworzą kwalifikacyjnego podpisu ani produkcyjnej authority.
""")


def manifest():
    # Preserve failed/partial/debug material in place, but never label it final proof.
    excluded_runs = {"adversarial", "adversarial-complete", "adversarial-current", "contexts", "contexts-v2", "contexts-v3",
                     "same-create-counterexample", "supplement", "supplement-final", "supplement-verified", "entrypoints", "replay", "replay-verified", "build-current"}
    excluded_parts = {"__pycache__", "working", "inputs", "wheel-staging"}
    entries = {}
    for path in HERE.rglob("*"):
        rel = path.relative_to(HERE)
        if not path.is_file() or path.name in {"EVIDENCE_MANIFEST.json", "POST_COMMIT_READBACK_CURRENT.json", "readback-replay.sqlite", "determinism-repeat.py"}:
            continue
        if set(rel.parts) & excluded_parts or any(part in {"local-semantic-history-fixed", "local-semantic-history-final"} for part in rel.parts):
            continue
        if "q1-closure-4132c5d" in rel.parts and set(rel.parts) & excluded_runs:
            continue
        entries[path.relative_to(ROOT).as_posix()] = info(path)
    candidate = read(HERE / "evidence/CANDIDATE_IDENTITY.json")
    for row in candidate["readback_files"]:
        entries[row["file"]] = info(ROOT / row["file"])
    for directory in (ROOT / "src/bdb_audit", ROOT / "docs/PRODUCT_V1/nf02_p0_runtime_qualification"):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".json"} and "__pycache__" not in path.parts:
                entries[path.relative_to(ROOT).as_posix()] = info(path)
    for path in [*(ROOT / "tools").glob("nf02_p0*.py"), *(ROOT / "tests/product").glob("*limited*.py"),
                 ROOT / "tools/nf02_p0_windows.ps1", ROOT / "build/build_single_file.py", ROOT / "requirements-f2.lock", ROOT / "pyproject.toml",
                 ROOT / "tests/product/limited_process_worker.py", ROOT / "tools/product_test_tmp.py"]:
        entries[path.relative_to(ROOT).as_posix()] = info(path)
    save(HERE / "EVIDENCE_MANIFEST.json", {"format": "BDB_P0_AUTHOR_HANDOFF_EVIDENCE/1", "model_id": "BDB_NF02_P0_LIMITED_1",
        "Q1": "OPEN", "Q2": "NOT_RUN", "RQ": "NOT_RUN", "production_import": "BLOCKED", "independent_assurance": False,
        "path_base": "repository_root", "entries": [entries[n] for n in sorted(entries)],
        "manifest_self_excluded": "Carrier SHA-256 recorded in post-commit readback/Git; no circular self digest",
        "excluded_preserved_debug": sorted(excluded_runs | excluded_parts | {"determinism-repeat.py", "readback-replay.sqlite"}),
        "source_binding": "Only *current execution directories prove the final runtime predicate; prior executions are retained construction/provenance evidence",
        "counterexample": "same-create-counterexample-v2/ACCEPTED_COUNTEREXAMPLE.sqlite and local-semantic-history/p0.sqlite are historical defective test acceptances, never valid authority/history",
        "simulation": "All positive OS/CMS/HTTPS authority is SIMULATED_TEST_ONLY; no keys, real signatures, Q2/RQ or production authority were manufactured"})
    print("FINAL_MANIFEST", len(entries), flush=True)


def post_commit():
    import hashlib
    data = read(HERE / "EVIDENCE_MANIFEST.json")
    for row in data["entries"]:
        assert info(ROOT / row["file"]) == row, row["file"]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    diff = subprocess.check_output(["git", "diff", "HEAD", "--", "src", "tools", "tests/product/test_limited_q1_closure.py", "docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF"], cwd=ROOT)
    assert not diff, "Task files differ from intended committed state"
    changed = subprocess.check_output(["git", "diff", "4132c5d81599042ccaef21e9a92f7bb84ac88645", "HEAD", "--name-only"], cwd=ROOT).decode().splitlines()
    assert not any(n.startswith(("docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/", "docs/R5_4_2/", "legacy/")) for n in changed)
    save(RUN / "POST_COMMIT_READBACK_CURRENT.json", {"status": "PASS_EXACT_COMMITTED_READBACK_Q1_OPEN", "commit": revision,
        "manifest": info(HERE / "EVIDENCE_MANIFEST.json"), "files": len(data["entries"]), "task_source_diff": False,
        "approved_norm_changed": False, "historical_material_changed": False, "Q1": "OPEN", "Q2": "NOT_RUN", "RQ": "NOT_RUN", "production_import": "BLOCKED",
        "self_exclusion": "This terminal carrier verification is intentionally outside the evidence manifest it verifies"})
    print("POST_COMMIT_READBACK_PASS", revision, len(data["entries"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("checks", "build", "assemble", "manifest", "post-commit"))
    args = parser.parse_args()
    if args.action == "checks":
        checks()
    elif args.action == "build":
        build()
    elif args.action == "manifest":
        manifest()
    elif args.action == "post-commit":
        post_commit()
    else:
        assemble()
