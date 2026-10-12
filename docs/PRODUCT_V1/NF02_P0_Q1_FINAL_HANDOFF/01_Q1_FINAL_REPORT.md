# Q1 — końcowy audyt autora

**Q1 OPEN.** Przeprowadzono ocenę wszystkich 11 rodzin i całego scope 18/7/43/M01–M18. Nie stwierdzono pełnego mandatory closure i nie wydano AUTHOR_QUALIFICATION. Nie jest to niezależne Q2/RQ ani production approval.

Tożsamość exact candidate, graph i obu set digests została odczytana niezależnie od SUT, porównana z checkpointem i approved generator `--check`. Body/schema parity wszystkich 18, 43 offline dependencies/representations i siedem profiles są zinwentaryzowane. MODELowych plików nie regenerowano ani nie zmieniano.

Actual results: 8100 schema/node/bound vectors sprawdzone także niezależnym interpreterem; 72 primitive ObjectDigest checks; 414 typed-ref cases; 9 DAG probes; 72 operation-state branches (13 accept / 59 deny); 7-commit retained rich result history i 322 direct material/command mutations DENY bez mutacji. Source sha1/sha256 i modes 100644/100755 mają rzeczywiste Git fixtures. `REFERENCE_HISTORY_CHECK` wylicza exact raw/object/commit/receipt identity i Kahn/cuts z retained SQL bez production validatora. Oryginalny ZIP wygenerowano niezależnym struct/CRC encoderem.

Wektorów shape-only, isolated bounds i ordering stubs nie traktuje się jako legal authority/history proof. Integration używa actual Store/Coordinator/inbox/predicates/ZIP/Git/CAS/replay/process code, z jawnie symulowanym OS/CMS/HTTPS. Native local probes obejmują malformed CMS, Windows leases, outside-SCM denial i bezpieczny parser/skrypt, bez instalacji/ACL zmian.

| Rodzina | Ocena | Otwarte obowiązki |
|---|---|---|
| Q1-01 | PASS_FOR_FAMILY_SCOPE | brak w zakresie rodziny |
| Q1-02 | OPEN | QG-01, QG-02 |
| Q1-03 | PASS_FOR_FAMILY_SCOPE | brak w zakresie rodziny |
| Q1-04 | OPEN | QG-02 |
| Q1-05 | OPEN | QG-01 |
| Q1-06 | PASS_FOR_FAMILY_SCOPE | brak w zakresie rodziny |
| Q1-07 | OPEN | QG-02 |
| Q1-08 | OPEN | QG-03 |
| Q1-09 | OPEN | QG-03 |
| Q1-10 | PASS_FOR_FAMILY_SCOPE | brak w zakresie rodziny |
| Q1-11 | OPEN | QG-04 |

## Findings i poprawki

| Finding | Naprawa | Dowód |
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

## Brakujące mandatory evidence

- **QG-01 (Q1-02, Q1-05)**: 8100 independently checked node/isolated-bound vectors are not a retained full enclosing-context product for every inline/nested branch. Wymagany wynik: Each applicable positive context validates; wrong kind/version/extra/bounds/schema and incompatible context denies with exact retained expected/output.
- **QG-02 (Q1-02, Q1-04, Q1-07)**: 322 direct field mutations and 72 operation-state cases do not establish every accepted cross-campaign/attempt/source/slot pool, same/future/own-cut variant, all commit/receipt replay mutations and full entry-point combinations. Wymagany wynik: Typed identity/target/class/prior/content/cut/context matches exactly; denied variants leave DB/raw/receipt/head byte-identical; legal retries return original receipt.
- **QG-03 (Q1-08, Q1-09)**: Positive author integration uses explicit simulated OS/CMS/transport, not genuinely provisioned owner/qualifier/Coordinator/auditor inputs. No real owner decision CMS, Q1/Q2/mandate or protected deployment exists. Wymagany wynik: Actual independently controlled external inputs bind exact candidate/model/namespace/code/environment and fail closed on every mandatory role/mode/signature/context mismatch.
- **QG-04 (Q1-11)**: QG-01..03 prevent all mandatory obligations being evidenced; AUTHOR_QUALIFICATION schema permits only READY, not OPEN. No record/signature is issued. Wymagany wynik: All mandatory cases closed, final exact readback/zero unexplained mismatch, valid author-only record with actual owner decision/final-audit hashes and independent_assurance=false.

Final retained audit odróżnia wykonane cases, static parity i prerequisites. QG-01/02 są brakami coverage/retention, nie udowodnioną nową sprzecznością normy; QG-03 wymaga rzeczywistych zewnętrznych inputs/authority. Nie wolno ich zamknąć samą liczbą testów. Formalny author record o verdict READY byłby nieprawdziwy przy tych brakach.

Final regression JUnit: {'PASS': 494, 'FAIL': 0, 'ERROR': 0, 'SKIP': 0}. Mypy closure/configured i Ruff oraz rebuild/readback są w evidence. Dawne 333/18 PASS nie są blanket proof nowego kodu. Sandboxowy przebieg miał 25 fixture access errors i 1 tempfile failure; normal Windows targeted rerun dał 33 PASS bez zmian expectations. Final native-context regression zastępuje ten przebieg.

Zmiany R5.4.2/legacy/v1_4_4/approved norm są zabronione i final diff/readback ich nie wykazuje. Nie wykonano migracji, push, merge, release, kwalifikacji za drugą stronę ani production activation. EVIDENCE_MANIFEST wiąże final materiały i current implementation; sam manifest nie daje runtime authority.
