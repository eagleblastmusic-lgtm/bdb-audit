"""Final exact readback of extra finite cases and concrete target applicability."""
from pathlib import Path

from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_q1_readback import ROOT, HERE, RUN, read, info, jsonl
from tools.nf02_p0_q1_finalize import assemble, manifest, save
from tools.nf02_p0_reference import sha

audit = read(RUN / "FINAL_Q1_AUDIT.json")
assert audit["cases"]["distinct-source"] == 38 and not audit["unexplained_mismatches"]
expected_states = {
    "INITIALIZE_P0_FROM_APPROVED_GIT": {"EMPTY_HISTORY"}, "CREATE_ASSIGNMENT": {"GENESIS", "ABORTED"},
    "BIND_PACKAGE": {"ASSIGNED"}, "START_ATTEMPT": {"BOUND"}, "CONFIRM_DELIVERY": {"STARTED"},
    "INGEST_EVIDENCE": {"DELIVERED"}, "ACCEPT_RESULT": {"EVIDENCE_ACCEPTED"},
    "ABORT_ATTEMPT": {"ASSIGNED", "BOUND", "STARTED", "DELIVERED", "EVIDENCE_ACCEPTED"},
}
states = list(jsonl(RUN / "state-retained/STATE_CASES.jsonl"))
assert len(states) == 72 and len({(r["operation"], r["input_state"]) for r in states}) == 72
for row in states:
    expected = "ACCEPT_ONE_COMMIT" if row["input_state"] in expected_states[row["operation"]] else "DENY_WITHOUT_MUTATION"
    assert row["expected"] == row["actual"] == expected
    assert info(ROOT / row["input_database"]["file"]) == row["input_database"]
    raw = reference_a(row["input_packet"])
    assert raw == reference_b(row["input_packet"]) and sha(raw) == row["input_packet_cjson_sha256"]
assert sum(r["actual"] == "ACCEPT_ONE_COMMIT" for r in states) == 13
basis = list(jsonl(RUN / "basis-applicability/BASIS_CASES.jsonl"))
assert len(basis) == 56 and len({(r["operation"], r["target_kind"]) for r in basis}) == 56
for row in basis:
    assert row["expected"] == row["actual"] == "DENY_P0_COMMAND_PRIOR_BASIS_WITHOUT_MUTATION"
    assert info(ROOT / row["input_database"]["file"]) == row["input_database"]
    raw = reference_a(row["input_command"])
    assert raw == reference_b(row["input_command"]) and sha(raw) == row["input_command_cjson_sha256"]
case_info = info(RUN / "basis-applicability/BASIS_CASES.jsonl")
index = audit["material_field_case_index"].setdefault("command_envelope::basis_refs", [])
index.extend({"file": case_info["file"], "case_id": row["id"], "variant": "OPERATION_INAPPLICABLE_SCHEMA_TARGET/" + row["target_kind"],
              "input_sha256": row["input_command_cjson_sha256"]} for row in basis)
audit["cases"].update({"state-retained": 72, "basis-applicability": 56})
new_inputs = [info(RUN / name) for name in ("state-retained/STATE_CASES.jsonl", "state-retained/STATE_EXECUTION.json", "basis-applicability/BASIS_CASES.jsonl",
              "basis-applicability/BASIS_EXECUTION.json", "FINAL_EXECUTION_BINDINGS.json")]
audit["inputs"].extend([*new_inputs, info(Path(__file__))])
audit["additional_final_readback"] = {"expected": "All 72 state inputs and 56 inapplicable target combinations reproduce exact SHA and literal expected/actual",
                                     "actual": "PASS", "unexplained_mismatches": [], "inputs": new_inputs}
(RUN / "FINAL_Q1_AUDIT.json").write_bytes(reference_a(audit) + b"\n")
assemble()
matrix = read(HERE / "02_Q1_COVERAGE_MATRIX.json")
for row in matrix["material_target_case_inventory"]:
    actual = {k for example in row["positive_examples"] for k in example["actual_target_keys"]}
    alternatives = []
    for target in row["ref"]["allowed_keys"]:
        kind = target.split("/")[0]
        if target in actual:
            alternatives.append({"target": target, "status": "ACTUAL_ACCEPTED_TARGET_EXECUTED_AND_INDEPENDENTLY_READBACK",
                "expected": "ACCEPT_IN_EXACT_CLASS_OPERATION_CONTEXT", "actual": "ACCEPTED_TEST_HISTORY", "evidence": [p for p in row["positive_examples"] if target in p["actual_target_keys"]]})
        else:
            assert row["id"] == "command_envelope/3::basis_refs" and kind in {r["target_kind"] for r in basis}
            cases = [r for r in basis if r["target_kind"] == kind]
            assert len(cases) == 8
            alternatives.append({"target": target, "status": "NOT_ADMISSIBLE_AS_BASIS_FOR_ANY_FROZEN_OPERATION_ACTUAL_DENIALS_EXECUTED",
                "expected": "DENY_P0_COMMAND_PRIOR_BASIS_WITHOUT_MUTATION", "actual": "DENY_P0_COMMAND_PRIOR_BASIS_WITHOUT_MUTATION",
                "reason": "Initial pins/content never become prior basis; accepted terminal result permits no next operation", "case_file": case_info, "cases": [r["id"] for r in cases]})
    row["target_alternatives"] = alternatives
matrix["additional_case_results"] = {"actual_distinct_commit_view_task": {"count": 38, "evidence": info(RUN / "distinct-source/DISTINCT_SOURCE_EXECUTION.json")},
    "all_state_pairs_retained": {"count": 72, "allowed": 13, "denied": 59, "evidence": info(RUN / "state-retained/STATE_EXECUTION.json")},
    "all_inapplicable_basis_targets": {"count": 56, "evidence": info(RUN / "basis-applicability/BASIS_EXECUTION.json")}}
matrix["exact_external_input_boundary"] = "Real OWNER_MODEL_DECISION/CMS/public DER/out-of-band pin are missing. Q2/FREEZE/RQ/mandate/installed authority are later gates and are not demanded as a circular prerequisite for author Q1."
save(HERE / "02_Q1_COVERAGE_MATRIX.json", matrix)
register = read(HERE / "03_GOLDEN_VECTOR_REGISTER.json")
register["current_closure"]["additional_results"] = matrix["additional_case_results"]
register["current_closure"]["final_audit"] = info(RUN / "FINAL_Q1_AUDIT.json")
save(HERE / "03_GOLDEN_VECTOR_REGISTER.json", register)
addition = "\nDodatkowe finalne dowody: **38** przypadków rzeczywiście innego commitu Git, view i task; **72** osobno zachowane pary operacja–stan (13 accept / 59 deny) z dokładnym SHA-256 bazy i pełnego packetu; **56** faktycznych odmów dla siedmiu schema-allowed, lecz operation-inapplicable basis targets we wszystkich ośmiu komendach. Każda alternatywa target 37 material fields ma teraz osobny wynik albo normatywnie uzasadnioną, wykonaną odmowę. Są to przypadki kwalifikacyjne, nie dodatkowe liczniki pytest.\n"
for name in ("00_STATUS.md", "01_Q1_FINAL_REPORT.md"):
    path = HERE / name
    path.write_text(path.read_text(encoding="utf8") + addition, encoding="utf8", newline="\n")
with (HERE / "05_WINDOWS_INSTALLATION_GUIDE.md").open("a", encoding="utf8", newline="\n") as stream:
    stream.write("\nAktualny rebuild po poprawce same-create: `evidence/q1-closure-4132c5d/build-current-v2/BUILD_READBACK.json`, `bdb_p0_unqualified.py` i wheel w tym samym katalogu. Starszy `evidence/build/` jest historycznym niekwalifikowanym buildem; nie stanowi dowodu naprawionego runtime. Źródła i payload LF normalization mają oddzielne exact SHA-256. Nadal nie wolno instalować ani aktywować bez właściwego upoważnienia i qualified authority.\n")
with (HERE / "11_Q1_REPRODUCTION.md").open("a", encoding="utf8", newline="\n") as stream:
    stream.write("\nPełny zakres kontekstów jest kompozycją `contexts-final/EXECUTED_PROCEDURE.py` oraz `EXECUTED_COMMON_ROOT_COMPLEMENT.py`: COMMON/1 jest celowo `not:{}` library root, ma siedem wykonanych odmów, a jego inline definitions mają enclosing contexts; State enum ma 14 node cases i pełną FSM. `EXECUTED_READBACK_PROCEDURE.py` przyspiesza jedynie konstrukcję inputów niezależnym interpreterem, zawsze sprawdzając ich pierwotne exact hashes; nie zastępuje runtime/SUT. Dodatkowe case scripts i FINALIZE_EXTRA_EVIDENCE.py zapisują końcowe source/state/target proofs. Każdy wymaga nowego output directory lub świeżego checkoutu evidence; nie nadpisywać zachowanych wyników.\n")
deps = read(HERE / "EXTERNAL_DEPENDENCIES.json")
deps["subsequent_author_record_input"] = "After genuine owner inputs and full Q1 closure, designate the actual authorized author governance_actor_ref and obtain owner's signature on exact author-only record. No fictitious author identity is issued by this package."
save(HERE / "EXTERNAL_DEPENDENCIES.json", deps)
manifest()
print("ALL_EXTRA_CASES_FINAL_READBACK_PASS", len(states), len(basis), "distinct", 38, flush=True)
