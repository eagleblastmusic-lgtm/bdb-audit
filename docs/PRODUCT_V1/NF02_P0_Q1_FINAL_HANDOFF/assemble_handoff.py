"""Assemble retained author audit metadata; never issue Q1/Q2/RQ authority."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/"
OLD = "docs/PRODUCT_V1/nf02_p0_runtime_qualification/"
LOCAL = HERE / "evidence/local-semantic-history-qualified-shapes"


def read(path):
    return json.loads((ROOT / path).read_bytes())


def info(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    raw = path.read_bytes()
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def save(name, value):
    (HERE / name).write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf8") + b"\n")


def text(name, value):
    (HERE / name).write_text(value, encoding="utf8", newline="\n")


def cases(path):
    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
    if path.exists():
        for case in ET.parse(path).getroot().iter("testcase"):
            status = "ERROR" if case.find("error") is not None else "FAIL" if case.find("failure") is not None else "SKIP" if case.find("skipped") is not None else "PASS"
            counts[status] += 1
    return counts


def generate():
    model = read(BASE + "MODEL.json")
    matrix = read(BASE + "QUALIFICATION_MATRIX.json")
    candidate = read("docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF/evidence/CANDIDATE_IDENTITY.json")
    semantic = json.loads((LOCAL / "SEMANTIC_EXECUTION.json").read_bytes())
    regression = cases(HERE / "evidence/regression.xml")
    triage = read("docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF/evidence/MYPY_TRIAGE.json")
    codes = {
        "artifact_contract_registry": "history/limited_protocol.py:validate_roots; history/limited_model.py:LimitedRegistry",
        "schema_registry": "history/limited_authority.py:lease; history/limited_protocol.py:validate_roots",
        "policy_revision": "history/limited_protocol.py:validate_step; history/limited_model.py:LimitedRegistry",
        "spec_revision": "history/limited_protocol.py:validate_step; history/limited_wire.py:LimitedCommand",
        "trust_profile": "history/limited_authority.py:lease/verify_service; history/limited_environment.py:verify_environment",
        "installation_bootstrap_profile": "history/limited_protocol.py:validate_roots/validate_step",
        "nf02_p0_source_snapshot": "workflow/limited_transport.py:approved_git_view/source; history/limited_protocol.py:validate_step",
        "campaign_genesis": "history/limited_protocol.py:validate_step INITIALIZE branch",
        "attempt": "history/limited_protocol.py:validate_step CREATE branch; workflow/limited_intake.py:draft_assignment",
        "assignment_manifest": "history/limited_protocol.py:context/validate_step; workflow/limited_transport.py:input_members",
        "assignment_package_binding": "history/limited_protocol.py:validate_step BIND branch; workflow/limited_transport.py:package",
        "nf02_p0_delivery": "history/store.py:release_p0; workflow/limited_delivery.py:deliver_installed; history/limited_protocol.py:validate_step",
        "lane_result_admission_evidence": "history/limited_protocol.py:validate_step; workflow/inbox.py:accept_p0_evidence",
        "bdb_audit_lane_result": "history/limited_protocol.py:validate_step ACCEPT_RESULT; workflow/limited_transport.py:result",
        "nf02_p0_abort": "history/limited_protocol.py:validate_step ABORT/CREATE; workflow/limited_intake.py:abort",
        "command_envelope": "history/limited_wire.py:LimitedCommand; history/limited_protocol.py:validate_step/auth_scope",
        "commit_body": "history/limited_protocol.py:order/build_acceptance/history; history/store.py:_accept",
        "command_receipt": "history/limited_protocol.py:history; history/store.py:_accept retry/index/receipt",
    }
    gaps = [
        {"id": "QG-01", "families": ["Q1-02", "Q1-05"], "requirement": "Every enclosing schema union/conditional and applicable cross-field combination",
         "missing": "8100 independently checked node/isolated-bound vectors are not a retained full enclosing-context product for every inline/nested branch.",
         "expected": "Each applicable positive context validates; wrong kind/version/extra/bounds/schema and incompatible context denies with exact retained expected/output.", "status": "OPEN"},
        {"id": "QG-02", "families": ["Q1-02", "Q1-04", "Q1-07"], "requirement": "Every material field/target/class temporal/context substitution and each supported entry-point branch",
         "missing": "322 direct field mutations and 72 operation-state cases do not establish every accepted cross-campaign/attempt/source/slot pool, same/future/own-cut variant, all commit/receipt replay mutations and full entry-point combinations.",
         "expected": "Typed identity/target/class/prior/content/cut/context matches exactly; denied variants leave DB/raw/receipt/head byte-identical; legal retries return original receipt.", "status": "OPEN"},
        {"id": "QG-03", "families": ["Q1-08", "Q1-09"], "requirement": "Exact legal signed inputs, source/view/task authority, initial pins and role/mode proof",
         "missing": "Positive author integration uses explicit simulated OS/CMS/transport, not genuinely provisioned owner/qualifier/Coordinator/auditor inputs. No real owner decision CMS, Q1/Q2/mandate or protected deployment exists.",
         "expected": "Actual independently controlled external inputs bind exact candidate/model/namespace/code/environment and fail closed on every mandatory role/mode/signature/context mismatch.", "status": "OPEN"},
        {"id": "QG-04", "families": ["Q1-11"], "requirement": "Complete retained final audit and valid external author qualification record",
         "missing": "QG-01..03 prevent all mandatory obligations being evidenced; AUTHOR_QUALIFICATION schema permits only READY, not OPEN. No record/signature is issued.",
         "expected": "All mandatory cases closed, final exact readback/zero unexplained mismatch, valid author-only record with actual owner decision/final-audit hashes and independent_assurance=false.", "status": "OPEN"},
    ]
    evidence_for_family = {
        "Q1-01": ["evidence/CANDIDATE_IDENTITY.json", "evidence/candidate-check.log"],
        "Q1-02": ["evidence/CANDIDATE_IDENTITY.json", "evidence/local-semantic-history-qualified-shapes/SEMANTIC_EXECUTION.json"],
        "Q1-03": ["evidence/CANDIDATE_IDENTITY.json", "evidence/candidate-check.log", "evidence/VECTOR_EXECUTION.json"],
        "Q1-04": ["evidence/matrix-execution.json", "evidence/matrix.xml", "evidence/regression.xml"],
        "Q1-05": ["evidence/VECTOR_EXECUTION.json"], "Q1-06": ["evidence/VECTOR_EXECUTION.json", "evidence/q1-history-readback.log"],
        "Q1-07": ["evidence/local-semantic-history-qualified-shapes/REFERENCE_HISTORY_CHECK.json", "evidence/local-semantic-history-qualified-shapes/SEMANTIC_EXECUTION.json"],
        "Q1-08": ["evidence/regression.xml", "evidence/targeted-source.xml", "evidence/targeted-installation-final.xml"],
        "Q1-09": ["evidence/targeted-installation-final.xml", "evidence/windows-readonly-preflight.log", "evidence/regression.xml"],
        "Q1-10": ["evidence/environment-regression.xml", "evidence/regression.xml", "evidence/CANDIDATE_IDENTITY.json"],
        "Q1-11": ["01_Q1_FINAL_REPORT.md", "02_Q1_COVERAGE_MATRIX.json", "EVIDENCE_MANIFEST.json"]}
    families = []
    pass_families = {"Q1-01", "Q1-03", "Q1-06", "Q1-10"}
    for family, requirement in matrix["cases"]["Q1"].items():
        families.append({"id": family, "mandatory_requirement": requirement, "verdict": "PASS_FOR_FAMILY_SCOPE" if family in pass_families else "OPEN",
            "evidence": evidence_for_family[family], "open_obligations": [g["id"] for g in gaps if family in g["families"]],
            "claim_boundary": "Author/local assessment; no independent Q2/RQ or production authority"})
    contracts = []
    material_cases = []
    for key, definition in model["canonical_contracts"].items():
        actual = [case for case in semantic["negative_cases"] if case["contract"] == key]
        contracts.append({"contract": key, "schema_id": definition["schema_id"], "body_schema_equal": True,
            "profile_dependencies": definition["profiles"], "producer_authority": definition["producer_authority"], "material_refs": definition["material_refs"],
            "predicates": [{"name": name, "source": "src/bdb_audit/" + codes[definition["kind"]],
                "review": "IMPLEMENTATION_SEMANTICS_REVIEWED; do not infer full case qualification from code presence",
                "retained_local_negative_ids": [c["id"] for c in actual], "mandatory_complete_case_closure": "OPEN_SEE_QG_01_02_03"} for name in definition["predicates"]]})
        for ref in definition["material_refs"]:
            mutations = ["ABSENT", "WRONG_KIND", "WRONG_VERSION", "WRONG_SCHEMA_RAW_DIGEST", "WRONG_LOGICAL_ID", "WRONG_REVISION",
                         "SAME_COMMIT_PRIOR", "FUTURE", "WRONG_CAMPAIGN", "WRONG_ATTEMPT", "WRONG_SOURCE", "WRONG_SLOT", "WRONG_CUT"]
            for mutation in mutations:
                matched = [c for c in actual if c["field"] == ref["field"] and c["mutation"] == mutation]
                material_cases.append({"id": key + "::" + ref["field"] + "::" + mutation, "contract": key, "ref": ref,
                    "variant": mutation, "expected": "DENY_WITHOUT_ACCEPTED_MUTATION_WHEN_APPLICABLE_TO_THIS_TARGET_CLASS",
                    "applicability": "Must expand target/null/array/history/context branches; initial nullable cases are not unconditional denials",
                    "executed_ids": [c["id"] for c in matched], "status": "LOCAL_CASE_EXECUTED_FULL_VARIANT_NOT_ESTABLISHED" if matched else "OPEN_NO_RETAINED_SPECIFIC_CASE",
                    "reference_basis": "MODEL.md M03/M04/M14/M15 and exact Registry target/class; expected not inferred from observed SUT acceptance"})
    duties = {
        "M01": ("Root/key separation, non-admin/external boundary", "history/limited_authority.py; p0_service.py; 06_AUTHORITY_AND_CERTIFICATE_PROVISIONING.md"),
        "M02": ("Signed root/install/grants/role/time/namespace/mode", "history/limited_authority.py; history/installation_authority.py"),
        "M03": ("CJSON/ObjectDigest/RawDigest/exact typed refs/set ordering", "core/canonical_json.py; core/hashing.py; history/limited_wire.py"),
        "M04": ("Kahn/content exact target and prior/cuts", "history/limited_protocol.py:order/resolve/validate_step/history"),
        "M05": ("Finite 8 commands/2 events/operation-state table", "history/limited_model.py; history/limited_protocol.py:validate_step"),
        "M06": ("7 profiles, fixed ZIP/JSON/CMS/IO bounds", "workflow/limited_transport.py; history/limited_model.py; history/installation_authority.py"),
        "M07": ("8 pins, actual approved Git/source and EMPTY_HISTORY", "workflow/limited_transport.py:approved_git_view/source; history/limited_protocol.py:validate_roots"),
        "M08": ("Single fixed task/view/slot/active assignment", "workflow/limited_intake.py:draft_assignment; history/limited_protocol.py:context"),
        "M09": ("Exact retained ZIP binding", "workflow/limited_transport.py:package; history/store.py:_accept"),
        "M10": ("Distinct later START", "history/limited_protocol.py:validate_step START branch"),
        "M11": ("Installed delivery/ACK/stable at-least-once release", "workflow/limited_delivery.py; history/store.py:release_p0"),
        "M12": ("Original signed return/ZIP/Evidence", "workflow/inbox.py:accept_p0_evidence; history/limited_protocol.py:validate_step"),
        "M13": ("Later Result, original raw rederivation, no truth promotion", "workflow/limited_transport.py:result; workflow/inbox.py:accept_p0_result"),
        "M14": ("Full joins/own input cuts/no laundering", "history/limited_protocol.py:validate_step/history"),
        "M15": ("Owner abort/5 nonterminal/retry lineage", "history/limited_protocol.py:validate_step; workflow/limited_intake.py:abort"),
        "M16": ("Single atomic Store CAS/current final rights/exact retry", "history/store.py:_accept; history/limited_protocol.py:recheck_authority"),
        "M17": ("Exact raw/trace/signatures/replay/new-process durability", "history/raw_artifacts.py; history/store.py; history/limited_protocol.py:history"),
        "M18": ("Fresh Q1/Q2/RQ/genuine mandate/production gate", "history/limited_authority.py:verify_qualification; history/limited_model.py:external"),
    }
    save("02_Q1_COVERAGE_MATRIX.json", {"model_id": model["model_id"], "status": "Q1_OPEN_AUTHOR_ASSESSMENT_NOT_INDEPENDENT_ASSURANCE",
        "candidate_identity": candidate["manifest_sha256"], "families": families, "obligations_M01_M18": [
            {"id": k, "requirement": v[0], "implementation": v[1], "evidence_scope": "LOCAL_AND_STATIC; real OS/PKI/external execution remains RQ"} for k, v in duties.items()],
        "contracts": contracts, "profiles": model["profiles"], "schema_nodes": model["schema_nodes"],
        "operation_branches": model["operations"], "delivery_operation": model["delivery_operation"], "explicit_exclusions": model["excluded"], "material_target_case_inventory": material_cases,
        "open_obligations": gaps, "actual_local_semantic_positive_steps": semantic["positive_steps"],
        "actual_local_negative_cases": semantic["negative_cases"], "author_record_issued": False, "production_import": "BLOCKED"})
    golden = []
    for area, files, claim in [
        ("canonical_serialization_object_identity_hash_separation", [OLD + "PRIMITIVE_VECTORS.json"], "Two reference encoders, 18 versions including Commit/3; shape goldens, not authority"),
        ("schema_nested_union_enum_bounds", [OLD + "SCHEMA_VECTORS.json", *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT / OLD).glob("SCHEMA_VECTORS_PART_*.json"))]], "8100 node/isolated-bound vectors, independent schema interpreter; enclosing combinations OPEN"),
        ("typed_references", [OLD + "REF_VECTORS.json"], "414 grammar/exact pin vectors; prior authority not established by shape"),
        ("deterministic_ordering", [OLD + "DAG_AND_STATE_VECTORS.json"], "9 ordering probes; 72 branch expectations have execution in matrix.xml"),
        ("accepted_history_source_binding_STARTED_delivery_evidence_result_raw_identity", [p.relative_to(ROOT).as_posix() for p in (LOCAL / "p0.sqlite", LOCAL / "EXPECTED_PAYLOAD.json", LOCAL / "REFERENCE_HISTORY_CHECK.json", LOCAL / "SEMANTIC_EXECUTION.json")], "7 real Store commits, 322 denied mutations, original bytes and independent digests/Kahn/receipts; OS/CMS/HTTPS explicitly simulated"),
        ("authorization_binding_retry_recovery_CAS_crash", ["docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF/evidence/regression.xml", "tests/product/limited_process_worker.py"], "Actual production predicates/writer and subprocess tests; genuine authority/physical durability/OS remains RQ"),
    ]:
        golden.append({"area": area, "artifacts": [info(f) for f in files if (ROOT / f).exists()], "claim": claim,
            "expected_basis": "Frozen MODEL.md/MODEL.json/profiles/schemas; reference_a/reference_b/independent schema and struct ZIP encoder; literal M05 chronology/expected denials",
            "independent_assurance": False})
    save("03_GOLDEN_VECTOR_REGISTER.json", {"model_id": model["model_id"], "status": "RETAINED_LOCAL_VECTOR_REGISTER_NOT_COMPLETE_Q1_Q2_RQ",
        "procedures": [info(p) for p in ("tools/nf02_p0_q1.py", "tools/nf02_p0_reference.py", "tools/nf02_p0_q1_semantics.py")],
        "execution": info(HERE / "evidence/VECTOR_EXECUTION.json"), "areas": golden, "open_obligations": [g["id"] for g in gaps]})
    lines = ["# Mypy — triage wszystkich 131 zgłoszeń", "", "Baseline odtworzony: **131 błędów / 39 plików / 266 source files**. Po naprawie: **83 błędy / 15 plików**, wszystkie poza P0 closure. Pełne `mypy src` nie jest PASS. Conservatively admitted module-import closure P0 ma 165 plików; z builderem i pięcioma narzędziami author/installer **171 files PASS**. Configured 56 files PASS. Nie dodano globalnego ignore_errors ani type: ignore.", "", "Kategorie baseline: " + str(triage["counts"]) + ". Wszystkie 48 zgłoszeń z ekspozycją P0 zostały naprawione, także 9 problemów modelowania API/Windows/streaming stubs. Poszczególne zgłoszenia zachowują oryginalną linię; po edycji numeracja może się różnić.", "", "Graf `evidence/P0_DEPENDENCY_CLOSURE.json` obejmuje module/package initialization, explicit finite P0 lazy imports i witnesses. Cały imported module jest typowany, także jego dormant metody. Wykluczone moduły nie mają admitted import path; ich lazy legacy branches nie są wybierane przez closed P0 command/service dispatch. Builder pakuje również legacy bytes, ale nie wykonuje tych dormant ścieżek. Build/source verification sprawdza ich zachowanie; lokalizacja pliku nie jest jedynym uzasadnieniem.", "", "| ID | Plik:linia baseline | Kategoria / ekspozycja | Kod | Zgłoszenie |", "|---|---|---|---|---|"]
    for row in triage["errors"]:
        lines.append(f"| {row['id']} | {row['file']}:{row['line']} | {row['category']} / {row['p0_exposure']} | {row['code']} | {row['message'].replace('|', '/')} |")
    lines += ["", "Pełne per-error witnesses i uzasadnienia są w MYPY_TRIAGE.json; baseline/after/closure/configured log exact hashes są w EVIDENCE_MANIFEST. Nie zmieniano 83 dormant legacy błędów ani zamrożonych schemas/normy w celu uzyskania typing PASS."]
    text("04_MYPY_TRIAGE.md", "\n".join(lines) + "\n")
    finding_text = """| Finding | Naprawa | Dowód |
|---|---|---|
| F01: M07 zero-based source mapping | Builder i parser liczą od 1; norma bez zmian | M07 positive/zero-denial/sha1/sha256/mode tests |
| F02: same-content wrong logical ID | Pełne typed target identity przed class admission | target regression i 322 semantic cases; retained pre-fix local counterexample |
| F03: missing command fields powodowały KeyError przed schema | Closed schema przed field access | Missing-field direct API regressions |
| F04: brak current certificate revocation w P0 | Native Online/ExcludeRoot/NoFlag, pin, expiry, fail-closed | Native malformed CMS + policy wrapper tests; real positive PKI remains RQ |
| F05/F06: secret-bearing diagnostic text i SCM stop bez checkpointów | Stałe log tokens, STOP/SHUTDOWN drain i periodic checkpoints | Native outside-SCM denial + explicit callback simulation; actual installed SCM remains RQ |
| F07: IO read-all przed quota | Bounded reads; signed JSON/CMS 2 MiB, assets 16 MiB | Native exact/over-bound lease test |
| F08: service prepared output poza campaign | Leased same campaign directory, create-new | Scoped-output/no-overwrite test |
| F09: lexical '..' namespace escape | Reject non-canonical resolved store path przed leases/DB | Parent traversal denial test |
| F10: 48 mypy P0 exposure findings | Annotations/narrowing, valid API modeling, ObjectRef digest bug fixed | 171-file closure + typed-ref graph regression |
"""
    report = "# Q1 — końcowy audyt autora\n\n**Q1 OPEN.** Przeprowadzono ocenę wszystkich 11 rodzin i całego scope 18/7/43/M01–M18. Nie stwierdzono pełnego mandatory closure i nie wydano AUTHOR_QUALIFICATION. Nie jest to niezależne Q2/RQ ani production approval.\n\n"
    report += "Tożsamość exact candidate, graph i obu set digests została odczytana niezależnie od SUT, porównana z checkpointem i approved generator `--check`. Body/schema parity wszystkich 18, 43 offline dependencies/representations i siedem profiles są zinwentaryzowane. MODELowych plików nie regenerowano ani nie zmieniano.\n\n"
    report += "Actual results: 8100 schema/node/bound vectors sprawdzone także niezależnym interpreterem; 72 primitive ObjectDigest checks; 414 typed-ref cases; 9 DAG probes; 72 operation-state branches (13 accept / 59 deny); 7-commit retained rich result history i 322 direct material/command mutations DENY bez mutacji. Source sha1/sha256 i modes 100644/100755 mają rzeczywiste Git fixtures. `REFERENCE_HISTORY_CHECK` wylicza exact raw/object/commit/receipt identity i Kahn/cuts z retained SQL bez production validatora. Oryginalny ZIP wygenerowano niezależnym struct/CRC encoderem.\n\n"
    report += "Wektorów shape-only, isolated bounds i ordering stubs nie traktuje się jako legal authority/history proof. Integration używa actual Store/Coordinator/inbox/predicates/ZIP/Git/CAS/replay/process code, z jawnie symulowanym OS/CMS/HTTPS. Native local probes obejmują malformed CMS, Windows leases, outside-SCM denial i bezpieczny parser/skrypt, bez instalacji/ACL zmian.\n\n"
    report += "| Rodzina | Ocena | Otwarte obowiązki |\n|---|---|---|\n" + "\n".join(f"| {f['id']} | {f['verdict']} | {', '.join(f['open_obligations']) or 'brak w zakresie rodziny'} |" for f in families) + "\n\n"
    report += "## Findings i poprawki\n\n" + finding_text + "\n## Brakujące mandatory evidence\n\n"
    for gap in gaps:
        report += f"- **{gap['id']} ({', '.join(gap['families'])})**: {gap['missing']} Wymagany wynik: {gap['expected']}\n"
    report += "\nFinal retained audit odróżnia wykonane cases, static parity i prerequisites. QG-01/02 są brakami coverage/retention, nie udowodnioną nową sprzecznością normy; QG-03 wymaga rzeczywistych zewnętrznych inputs/authority. Nie wolno ich zamknąć samą liczbą testów. Formalny author record o verdict READY byłby nieprawdziwy przy tych brakach.\n\n"
    report += f"Final regression JUnit: {regression}. Mypy closure/configured i Ruff oraz rebuild/readback są w evidence. Dawne 333/18 PASS nie są blanket proof nowego kodu. Sandboxowy przebieg miał 25 fixture access errors i 1 tempfile failure; normal Windows targeted rerun dał 33 PASS bez zmian expectations. Final native-context regression zastępuje ten przebieg.\n\n"
    report += "Zmiany R5.4.2/legacy/v1_4_4/approved norm są zabronione i final diff/readback ich nie wykazuje. Nie wykonano migracji, push, merge, release, kwalifikacji za drugą stronę ani production activation. EVIDENCE_MANIFEST wiąże final materiały i current implementation; sam manifest nie daje runtime authority.\n"
    text("01_Q1_FINAL_REPORT.md", report)
    text("00_STATUS.md", f"""# BDB NF02 P0 — final handoff

Stan: **Q1 OPEN; Q2 NOT_RUN; RQ NOT_RUN; production import BLOCKED**. NF02 OPEN, P0 produkcyjnie NOT_DELIVERED, E1–E6 NOT_COMPLETED. Pakiet obejmuje implementację i rzeczywiste lokalne dowody, nie niezależną kwalifikację.

Base checkpoint: `ef3073c7042b33db7a2f32bff812e2e1f0df9de5`, branch `work/nf02-runtime-completion`. Final delivery commit znajduje się w Git HEAD/raporcie końcowym; wpisanie własnego final commit hash do jego bytes tworzyłoby self-reference. Exact current code/files/artifacts wiąże EVIDENCE_MANIFEST.

Approved candidate: manifest `{candidate['manifest_sha256']}`, graph `{candidate['graph']['sha256']}`, normative `{candidate['sets']['normative']['sha256']}`, machine `{candidate['sets']['machine']['sha256']}`. Readback: 18 contracts / 7 profiles / 43 schemas, 57 unique set files + manifest; 55 entries na zbiór. Brak edycji normy i historycznych R5.4.2.

Bootstrap/assignment/BIND/later START, protected release/ACK, retained original ZIP/Evidence/later Result, abort/retry/CAS/replay/crash mają actual production code i local simulation evidence. Naprawiono source indexing, content identity, command schema ordering, PKI revocation policy, SCM/logging, IO quotas, output i namespace boundaries oraz 48 typing exposure findings.

Final regression: **{regression['PASS']} PASS / {regression['FAIL']} FAIL / {regression['ERROR']} ERROR / {regression['SKIP']} SKIP**; osobno matrix 72 cases (13 legal / 59 denied), 8100 schema vectors i 322 semantic denials. Final file hashes i execution/source bindings są w evidence. Typing closure **171 PASS**, configured **56 PASS**; full src **83 legacy errors**, bez P0 exposure w conservative import graph.

Windows: instalacyjne/verification/signing/SCM artifacts przygotowane, native safe negative/lease probes wykonane. **Real installed service/ACL/PKI/external execution UNQUALIFIED**. Nie instalowano nic ani nie zmieniano ACL na komputerze właściciela. Runbook wymaga dedykowanych kontrolowanych hostów i real keys/grants.

Pozostaje: QG-01..04 z 02 (pełne mandatory combinations/material-target/temporal/entry-point/legal-signed inputs i author record), niezależny Q2/freeze, real mandate/install/RQ i późniejszy signed PRODUCTION record. Od właściciela potrzebne są rzeczywiste role/hosty/public DER pins/key custody, source/view/task authority i osobne upoważnienie do instalacji na wskazanym hoście. Własne brakujące author cases nie są delegowane owner jako jego obowiązek techniczny.

    WIP i wcześniejsze untracked materiały zachowano. Nie wykonano push/merge/force-push/tag/release. Worktree końcowe opisuje finalny raport i Git status; `.product-test-tmp` to ignored test outputs, nie authority. Auto-review odrzucił usunięcie generated build/partial-history directories ze względu na ochronę WIP; zachowano je. Cache i nieukończone partial histories nie są finalnym evidence pakietu.
""")
    text("09_RELEASE_READINESS.md", """# Gotowość i granica aktywacji

**Production activation/import BLOCKED.** Implementacja i offline installation/review package są przygotowane; nie spełniono formalnego Q1, niezależnego Q2, real install/RQ ani production authority. Repo-only PASS nie otwiera importu.

Known P0 defects wykryte w tej pracy zostały naprawione i mają targeted regression; dependency closure P0 przechodzi typing. 83 full-src błędy pozostają poza admitted P0 import closure i nie są whole-repo PASS. Każda zmiana import graph/entry surface/build wykorzystująca te dormant branches wymaga ponownej klasyfikacji.

Q1 OPEN: QG-01..04 w 02 zawierają konkretne missing mandatory proof i expected. Nie wydano autora record READY. Q2 materiał review zawiera norm/code/goldens/source/evidence/findings, lecz freeze musi czekać na Q1 closure. RQ runbook obejmuje 32 rodziny i real external run, z osobnym qualification namespace; nie został wykonany za kwalifikatora.

Owner wskazuje independent qualifier, auditor, installer i hosty, ustala actual key controls/DER pins/PKI i approved source/view/task, oraz osobno upoważnia instalację na wyznaczonym hoście. Author uzupełnia brakujące cases/coverage i final record zgodnie z M18; owner podpisuje prawdziwe decyzje, qualifier własny review/freeze/mandate/RQ. Same nazwiska/flag/PASS strings/pins nie nadają praw.

Po real pozytywnym RQ owner instaluje signed PRODUCTION record wiążący same final code/dependencies i dopuszczone environment evidence. Powstaje nowy pusty production namespace/campaign. Runtime weryfikuje pełny qualification/authority/raw/code/environment chain przy install/restart/write/release. Brakujące/drifting/revoked inputs, invalid ACL, namespace/profile/model mismatch i caller override pozostają DENY. Qualified result/history nie jest migrowane ani kopiowane do produkcji.

Standalone i wheel w evidence są **UNQUALIFIED LOCAL BUILD ARTIFACTS**, bez release/publikacji. Same checksum/ABI/version/build powodzenie nie jest activation. Norm/model remains 18/7/43; full R5.4.2 i jego wcześniejsze approval nie są zmieniane ani zastępowane. Results nie ustanawiają finding truth, completion, STOP, release ani NF02 CLOSED.
""")
    entries = {}
    omitted_debug = {"local-semantic-history-fixed", "local-semantic-history-final"}
    for path in HERE.rglob("*"):
        if omitted_debug & set(path.parts):
            continue
        if path.is_file() and path.name != "EVIDENCE_MANIFEST.json" and "__pycache__" not in path.parts:
            entries[path.relative_to(ROOT).as_posix()] = info(path)
    for row in candidate["readback_files"]:
        entries[row["file"]] = info(row["file"])
    for directory in (ROOT / "src/bdb_audit", ROOT / OLD):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".md"} and "__pycache__" not in path.parts:
                entries[path.relative_to(ROOT).as_posix()] = info(path)
    for path in (ROOT / "tools").glob("nf02_p0*.py"):
        entries[path.relative_to(ROOT).as_posix()] = info(path)
    for path in [ROOT / "tools/nf02_p0_windows.ps1", ROOT / "build/build_single_file.py", ROOT / "requirements-f2.lock", ROOT / "pyproject.toml",
                 *[p for p in (ROOT / "tests/product").glob("*limited*.py")], ROOT / "tests/product/limited_process_worker.py", ROOT / "tools/product_test_tmp.py"]:
        entries[path.relative_to(ROOT).as_posix()] = info(path)
    save("EVIDENCE_MANIFEST.json", {"format": "BDB_P0_AUTHOR_HANDOFF_EVIDENCE/1", "model_id": model["model_id"],
        "Q1": "OPEN", "Q2": "NOT_RUN", "RQ": "NOT_RUN", "production_import": "BLOCKED", "independent_assurance": False,
        "path_base": "repository_root", "entries": [entries[n] for n in sorted(entries)],
        "manifest_self_excluded": "No self digest in its own preimage; validate manifest carrier hash externally/Git.",
        "historical_materials": "Existing runtime_qualification files are retained historical inputs, not blanket final-code proof.",
        "simulation": "All local positive authority/delivery/external execution fixtures remain TEST_ONLY; native probes do not install authority.",
        "excluded_preserved_debug": ["__pycache__", *sorted(omitted_debug)],
        "counterexample": "evidence/local-semantic-history/p0.sqlite is pre-F02-fix simulated acceptance evidence, not a qualified or legal campaign."})
    print("HANDOFF_ASSEMBLED", regression, "files", len(entries))


if __name__ == "__main__":
    generate()
