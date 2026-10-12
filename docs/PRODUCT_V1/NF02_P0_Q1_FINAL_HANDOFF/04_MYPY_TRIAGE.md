# Mypy — triage wszystkich 131 zgłoszeń

Baseline odtworzony: **131 błędów / 39 plików / 266 source files**. Po naprawie: **83 błędy / 15 plików**, wszystkie poza P0 closure. Pełne `mypy src` nie jest PASS. Conservatively admitted module-import closure P0 ma 165 plików; poprzedni przebieg z builderem i pięcioma narzędziami obejmował 171 plików. Kontynuacja Q1 po checkpointcie 4132 obejmuje **184 files PASS**, z builderem, wszystkimi aktualnymi narzędziami P0/Q1 i nową regresją. Configured mypy również PASS. Nie dodano globalnego ignore_errors ani type: ignore.

Kategorie baseline: {'FALSE-POSITIVE/CONFIG': 9, 'LEGACY-OUT-OF-SCOPE': 83, 'P0-CRITICAL': 7, 'P0-TRANSITIVE': 32}. Wszystkie 48 zgłoszeń z ekspozycją P0 zostały naprawione, także 9 problemów modelowania API/Windows/streaming stubs. Poszczególne zgłoszenia zachowują oryginalną linię; po edycji numeracja może się różnić.

Graf `evidence/P0_DEPENDENCY_CLOSURE.json` obejmuje module/package initialization, explicit finite P0 lazy imports i witnesses. Cały imported module jest typowany, także jego dormant metody. Wykluczone moduły nie mają admitted import path; ich lazy legacy branches nie są wybierane przez closed P0 command/service dispatch. Builder pakuje również legacy bytes, ale nie wykonuje tych dormant ścieżek. Build/source verification sprawdza ich zachowanie; lokalizacja pliku nie jest jedynym uzasadnieniem.

Aktualne wejścia i dokładne komendy: `evidence/q1-closure-4132c5d/TYPE_AND_LINT_EXECUTION.json`, `mypy-final-closure.log`, `mypy-final-configured.log`, `ruff-final.log`. Import graph pozostał 165-modułowy. Nowy predykat same-create nie dodaje zależności. Dodatkowe błędy typowania narzędzi kwalifikacyjnych (list/str, list element annotation i modelowanie kontekstu stateless order/ref) naprawiono przez rzeczywisty obiekt protokołu dla pure predicate calls i poprawne anotacje, bez wyciszeń i bez zmiany expected vector bytes. Historyczny pełny `mypy src` nie był ponawiany ani rozszerzany na legacy; poniższe 131 wpisów zachowuje oryginalne linie i klasyfikację.

| ID | Plik:linia baseline | Kategoria / ekspozycja | Kod | Zgłoszenie |
|---|---|---|---|---|
| MYPY-001 | src/bdb_audit/schemas/stop.py:69 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-002 | src/bdb_audit/schemas/stop.py:72 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-003 | src/bdb_audit/schemas/stop.py:76 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-004 | src/bdb_audit/schemas/stop.py:80 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-005 | src/bdb_audit/schemas/stop.py:84 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-006 | src/bdb_audit/schemas/stop.py:88 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-007 | src/bdb_audit/schemas/stop.py:91 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-008 | src/bdb_audit/schemas/stop.py:94 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-009 | src/bdb_audit/schemas/inventory.py:46 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-010 | src/bdb_audit/schemas/inventory.py:49 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-011 | src/bdb_audit/schemas/inventory.py:52 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-012 | src/bdb_audit/schemas/inventory.py:55 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-013 | src/bdb_audit/schemas/inventory.py:59 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-014 | src/bdb_audit/schemas/inventory.py:63 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-015 | src/bdb_audit/schemas/inventory.py:67 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-016 | src/bdb_audit/schemas/hypothesis.py:33 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-017 | src/bdb_audit/schemas/hypothesis.py:36 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-018 | src/bdb_audit/schemas/hypothesis.py:39 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-019 | src/bdb_audit/schemas/hypothesis.py:42 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-020 | src/bdb_audit/schemas/experiment.py:41 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-021 | src/bdb_audit/schemas/experiment.py:44 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-022 | src/bdb_audit/schemas/experiment.py:47 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-023 | src/bdb_audit/schemas/experiment.py:50 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-024 | src/bdb_audit/schemas/evidence.py:40 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-025 | src/bdb_audit/schemas/evidence.py:43 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-026 | src/bdb_audit/schemas/evidence.py:46 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-027 | src/bdb_audit/schemas/evidence.py:48 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-028 | src/bdb_audit/schemas/evidence.py:50 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-029 | src/bdb_audit/schemas/coverage.py:44 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-030 | src/bdb_audit/schemas/coverage.py:47 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-031 | src/bdb_audit/schemas/coverage.py:50 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-032 | src/bdb_audit/schemas/coverage.py:52 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-033 | src/bdb_audit/schemas/coverage.py:55 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-034 | src/bdb_audit/schemas/coverage.py:58 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-035 | src/bdb_audit/schemas/coverage.py:61 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-036 | src/bdb_audit/schemas/coverage.py:63 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-037 | src/bdb_audit/schemas/bootstrap.py:52 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "int"; expected "str": "str" |
| MYPY-038 | src/bdb_audit/schemas/bootstrap.py:54 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "int"; expected "str": "str" |
| MYPY-039 | src/bdb_audit/schemas/bootstrap.py:57 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-040 | src/bdb_audit/schemas/bootstrap.py:66 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-041 | src/bdb_audit/schemas/adjudication.py:48 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-042 | src/bdb_audit/schemas/adjudication.py:51 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-043 | src/bdb_audit/schemas/adjudication.py:54 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-044 | src/bdb_audit/schemas/adjudication.py:56 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-045 | src/bdb_audit/schemas/adjudication.py:60 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-046 | src/bdb_audit/schemas/adjudication.py:68 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-047 | src/bdb_audit/schemas/adjudication.py:75 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "int"; expected "str": "str" |
| MYPY-048 | src/bdb_audit/schemas/adjudication.py:76 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 2 has incompatible type "str": "bool"; expected "str": "str" |
| MYPY-049 | src/bdb_audit/schemas/adjudication.py:80 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-050 | src/bdb_audit/schemas/adjudication.py:87 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-051 | src/bdb_audit/schemas/adjudication.py:93 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "int"; expected "str": "str" |
| MYPY-052 | src/bdb_audit/schemas/adjudication.py:94 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 2 has incompatible type "str": "bool"; expected "str": "str" |
| MYPY-053 | src/bdb_audit/schemas/assurance.py:93 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-054 | src/bdb_audit/schemas/assurance.py:96 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-055 | src/bdb_audit/schemas/assurance.py:103 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 1 has incompatible type "str": "int"; expected "str": "str" |
| MYPY-056 | src/bdb_audit/schemas/assurance.py:104 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-057 | src/bdb_audit/schemas/assurance.py:106 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-058 | src/bdb_audit/schemas/assurance.py:111 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-059 | src/bdb_audit/schemas/assurance.py:115 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-060 | src/bdb_audit/schemas/assurance.py:124 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-061 | src/bdb_audit/schemas/assurance.py:127 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-062 | src/bdb_audit/schemas/assurance.py:131 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-063 | src/bdb_audit/schemas/assurance.py:134 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 0 has incompatible type "str": "list[str]"; expected "str": "str" |
| MYPY-064 | src/bdb_audit/assurance/zip_safety.py:119 | FALSE-POSITIVE/CONFIG / CRITICAL | assignment | Incompatible types in assignment (expression has type "BZ2Decompressor", variable has type "_Decompress / None") |
| MYPY-065 | src/bdb_audit/assurance/zip_safety.py:129 | FALSE-POSITIVE/CONFIG / CRITICAL | assignment | Incompatible types in assignment (expression has type "LZMADecompressor", variable has type "_Decompress / None") |
| MYPY-066 | src/bdb_audit/assurance/zip_safety.py:148 | FALSE-POSITIVE/CONFIG / CRITICAL | attr-defined | "_Decompress" has no attribute "needs_input" |
| MYPY-067 | src/bdb_audit/assurance/zip_safety.py:151 | FALSE-POSITIVE/CONFIG / CRITICAL | assignment | Incompatible types in assignment (expression has type "memoryview[int]", variable has type "bytes") |
| MYPY-068 | src/bdb_audit/assurance/zip_safety.py:153 | FALSE-POSITIVE/CONFIG / CRITICAL | assignment | Incompatible types in assignment (expression has type "bytes", variable has type "memoryview[int]") |
| MYPY-069 | src/bdb_audit/assurance/legacy.py:28 | LEGACY-OUT-OF-SCOPE / NONE | var-annotated | Need type annotation for "errors" (hint: "errors: list[<type>] = ...") |
| MYPY-070 | src/bdb_audit/assurance/legacy.py:115 | LEGACY-OUT-OF-SCOPE / NONE | index | Value of type "Collection[str]" is not indexable |
| MYPY-071 | src/bdb_audit/assurance/legacy.py:309 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 1 to "range" has incompatible type "Any / None"; expected "SupportsIndex" |
| MYPY-072 | src/bdb_audit/assurance/legacy.py:309 | LEGACY-OUT-OF-SCOPE / NONE | operator | Unsupported operand types for + ("None" and "int") |
| MYPY-073 | src/bdb_audit/assurance/legacy.py:343 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 3 to "_parse_json_object_member" has incompatible type "str / None"; expected "str" |
| MYPY-074 | src/bdb_audit/assurance/legacy.py:788 | LEGACY-OUT-OF-SCOPE / NONE | union-attr | Item "None" of "Any / dict[Any, Any] / None" has no attribute "get" |
| MYPY-075 | src/bdb_audit/assurance/legacy.py:790 | LEGACY-OUT-OF-SCOPE / NONE | union-attr | Item "None" of "Any / dict[Any, Any] / None" has no attribute "get" |
| MYPY-076 | src/bdb_audit/assurance/legacy.py:1038 | LEGACY-OUT-OF-SCOPE / NONE | assignment | Incompatible types in assignment (expression has type "bytes / None", variable has type "bytes") |
| MYPY-077 | src/bdb_audit/orchestration/fsm.py:193 | P0-TRANSITIVE / TRANSITIVE | assignment | Incompatible types in assignment (expression has type "Any / None", variable has type "str") |
| MYPY-078 | src/bdb_audit/orchestration/fsm.py:194 | P0-TRANSITIVE / TRANSITIVE | assignment | Incompatible types in assignment (expression has type "Any / None", variable has type "str") |
| MYPY-079 | src/bdb_audit/core/registry.py:247 | P0-CRITICAL / CRITICAL | var-annotated | Need type annotation for "by_kind" (hint: "by_kind: dict[<type>, <type>] = ...") |
| MYPY-080 | src/bdb_audit/core/registry.py:255 | P0-CRITICAL / CRITICAL | var-annotated | Need type annotation for "edges" (hint: "edges: set[<type>] = ...") |
| MYPY-081 | src/bdb_audit/remediation/planner.py:113 | P0-TRANSITIVE / TRANSITIVE | misc | Generator has incompatible item type "dict[str, Any] / None"; expected "dict[str, Any]" |
| MYPY-082 | src/bdb_audit/schemas/binding.py:40 | FALSE-POSITIVE/CONFIG / CRITICAL | call-arg | Unexpected keyword argument "ref" for "NoSuchResource" |
| MYPY-083 | src/bdb_audit/schemas/binding.py:122 | FALSE-POSITIVE/CONFIG / CRITICAL | call-arg | Unexpected keyword argument "retrieve" for "Registry" |
| MYPY-084 | src/bdb_audit/history/objects.py:257 | P0-CRITICAL / CRITICAL | assignment | Incompatible types in assignment (expression has type "str / None", target has type "Sequence[str]") |
| MYPY-085 | src/bdb_audit/history/objects.py:259 | P0-CRITICAL / CRITICAL | dict-item | Dict entry 0 has incompatible type "str": "str / None"; expected "str": "Sequence[str]" |
| MYPY-086 | src/bdb_audit/history/objects.py:259 | P0-CRITICAL / CRITICAL | dict-item | Dict entry 1 has incompatible type "str": "int / None"; expected "str": "Sequence[str]" |
| MYPY-087 | src/bdb_audit/history/objects.py:260 | P0-CRITICAL / CRITICAL | dict-item | Dict entry 2 has incompatible type "str": "str / None"; expected "str": "Sequence[str]" |
| MYPY-088 | src/bdb_audit/history/objects.py:605 | P0-CRITICAL / CRITICAL | union-attr | Item "None" of "ObjectRef / None" has no attribute "as_dict" |
| MYPY-089 | src/bdb_audit/strategy/cli.py:151 | LEGACY-OUT-OF-SCOPE / NONE | dict-item | Dict entry 4 has incompatible type "str": "int"; expected "str": "Collection[Collection[str]]" |
| MYPY-090 | src/bdb_audit/runner/supervisor.py:42 | FALSE-POSITIVE/CONFIG / TRANSITIVE | attr-defined | Module has no attribute "killpg" |
| MYPY-091 | src/bdb_audit/runner/supervisor.py:42 | FALSE-POSITIVE/CONFIG / TRANSITIVE | attr-defined | Module has no attribute "SIGKILL"; maybe "SIGILL"? |
| MYPY-092 | src/bdb_audit/evidence/models.py:254 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument 1 to "dict" has incompatible type "dict[Any, Any] / None"; expected "SupportsKeysAndGetItem[Any, Any]" |
| MYPY-093 | src/bdb_audit/coverage/models.py:238 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument 1 to "dict" has incompatible type "dict[Any, Any] / None"; expected "SupportsKeysAndGetItem[Any, Any]" |
| MYPY-094 | src/bdb_audit/adjudication/models.py:96 | P0-TRANSITIVE / TRANSITIVE | union-attr | Item "None" of "str / None" has no attribute "startswith" |
| MYPY-095 | src/bdb_audit/attack/scheduler.py:134 | LEGACY-OUT-OF-SCOPE / NONE | var-annotated | Need type annotation for "candidate_obligations" (hint: "candidate_obligations: list[<type>] = ...") |
| MYPY-096 | src/bdb_audit/stop/residual_risk_evaluator.py:155 | P0-TRANSITIVE / TRANSITIVE | attr-defined | "_Wrapped[[VarArg(Any), KwArg(Any)], Any, [Any, VarArg(Any), KwArg(Any)], Any]" has no attribute "_bdb_residual_risk_evaluator" |
| MYPY-097 | src/bdb_audit/knowledge/quarantine.py:35 | P0-TRANSITIVE / TRANSITIVE | var-annotated | Need type annotation for "_views" (hint: "_views: dict[<type>, <type>] = ...") |
| MYPY-098 | src/bdb_audit/inventory/accounting.py:31 | P0-TRANSITIVE / TRANSITIVE | assignment | Incompatible types in assignment (expression has type "Any / None", variable has type "str") |
| MYPY-099 | src/bdb_audit/inventory/accounting.py:52 | P0-TRANSITIVE / TRANSITIVE | assignment | Incompatible types in assignment (expression has type "str", variable has type "InputDispositionRecord / Mapping[str, Any]") |
| MYPY-100 | src/bdb_audit/inventory/accounting.py:89 | P0-TRANSITIVE / TRANSITIVE | index | Invalid index type "str / Any / None" for "dict[str, int]"; expected type "str" |
| MYPY-101 | src/bdb_audit/inventory/accounting.py:89 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument 1 to "get" of "dict" has incompatible type "str / Any / None"; expected "str" |
| MYPY-102 | src/bdb_audit/execution/adapters.py:183 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument 1 to "validate_execution_dag" has incompatible type "list[tuple[str / None, str / None]]"; expected "Sequence[str / tuple[str, str]]" |
| MYPY-103 | src/bdb_audit/evidence/graph.py:72 | P0-TRANSITIVE / TRANSITIVE | union-attr | Item "ObjectRef" of "ObjectRef / CanonicalObject" has no attribute "digest" |
| MYPY-104 | src/bdb_audit/deepen/exploration.py:140 | LEGACY-OUT-OF-SCOPE / NONE | var-annotated | Need type annotation for "queue" |
| MYPY-105 | src/bdb_audit/deepen/adapters.py:177 | LEGACY-OUT-OF-SCOPE / NONE | assignment | Incompatible types in assignment (expression has type "list[Any]", variable has type "int") |
| MYPY-106 | src/bdb_audit/deepen/adapters.py:178 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 1 to "len" has incompatible type "int"; expected "Sized" |
| MYPY-107 | src/bdb_audit/deepen/adapters.py:179 | LEGACY-OUT-OF-SCOPE / NONE | index | Value of type "int" is not indexable |
| MYPY-108 | src/bdb_audit/hypothesis/orchestrator.py:147 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument 1 to "get" of "dict" has incompatible type "Any / str / None"; expected "str" |
| MYPY-109 | src/bdb_audit/coverage/gap_engine.py:159 | P0-TRANSITIVE / TRANSITIVE | assignment | Incompatible types in assignment (expression has type "CoverageObligationQualification / None", variable has type "CoverageObligationQualification") |
| MYPY-110 | src/bdb_audit/stop/authority.py:42 | LEGACY-OUT-OF-SCOPE / NONE | misc | Set comprehension has incompatible type Set[Any / None]; expected Set[str] |
| MYPY-111 | src/bdb_audit/stop/authority.py:135 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 1 to "get" of "dict" has incompatible type "tuple[Any / None, Any / None]"; expected "tuple[str, str]" |
| MYPY-112 | src/bdb_audit/stop/authority.py:492 | LEGACY-OUT-OF-SCOPE / NONE | assignment | Incompatible types in assignment (expression has type "str", variable has type "tuple[Any, Any]") |
| MYPY-113 | src/bdb_audit/stop/authority.py:495 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 2 to "ValidationError" has incompatible type "tuple[Any, Any]"; expected "str" |
| MYPY-114 | src/bdb_audit/stop/authority.py:496 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 2 to "_summary_int" has incompatible type "tuple[Any, Any]"; expected "str" |
| MYPY-115 | src/bdb_audit/stop/authority.py:497 | LEGACY-OUT-OF-SCOPE / NONE | arg-type | Argument 2 to "ValidationError" has incompatible type "tuple[Any, Any]"; expected "str" |
| MYPY-116 | src/bdb_audit/stop/operation.py:262 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument 3 to "CanonicalObject" has incompatible type "Any / None"; expected "str" |
| MYPY-117 | src/bdb_audit/stop/input_builder.py:69 | P0-TRANSITIVE / TRANSITIVE | misc | Set comprehension has incompatible type Set[Any / None]; expected Set[str] |
| MYPY-118 | src/bdb_audit/orchestration/stages.py:85 | P0-TRANSITIVE / TRANSITIVE | var-annotated | Need type annotation for "_by_digest" (hint: "_by_digest: dict[<type>, <type>] = ...") |
| MYPY-119 | src/bdb_audit/orchestration/stages.py:86 | P0-TRANSITIVE / TRANSITIVE | var-annotated | Need type annotation for "_by_key" (hint: "_by_key: dict[<type>, <type>] = ...") |
| MYPY-120 | src/bdb_audit/orchestration/stages.py:108 | P0-TRANSITIVE / TRANSITIVE | assignment | Incompatible types in assignment (expression has type "Any / None", variable has type "str") |
| MYPY-121 | src/bdb_audit/stop/e6.py:221 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument "variant" to "HistoryCut" has incompatible type "Any / None"; expected "str" |
| MYPY-122 | src/bdb_audit/stop/e6.py:226 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument "governing_policy_ref" to "HistoryCut" has incompatible type "Any / None"; expected "str" |
| MYPY-123 | src/bdb_audit/stop/e6.py:301 | P0-TRANSITIVE / TRANSITIVE | operator | Unsupported operand types for < ("int" and "None") |
| MYPY-124 | src/bdb_audit/stop/e6.py:301 | P0-TRANSITIVE / TRANSITIVE | operator | Unsupported operand types for > ("int" and "None") |
| MYPY-125 | src/bdb_audit/stop/e6.py:301 | P0-TRANSITIVE / TRANSITIVE | operator | Unsupported left operand type for < ("None") |
| MYPY-126 | src/bdb_audit/stop/e6.py:498 | P0-TRANSITIVE / TRANSITIVE | operator | Unsupported operand types for <= ("int" and "None") |
| MYPY-127 | src/bdb_audit/stop/e6.py:498 | P0-TRANSITIVE / TRANSITIVE | operator | Unsupported operand types for >= ("int" and "None") |
| MYPY-128 | src/bdb_audit/stop/e6.py:498 | P0-TRANSITIVE / TRANSITIVE | operator | Unsupported left operand type for <= ("None") |
| MYPY-129 | src/bdb_audit/report/builder.py:135 | P0-TRANSITIVE / TRANSITIVE | arg-type | Argument "report_scope" to "ReportModel" has incompatible type "str"; expected "Literal['PARTIAL', 'BOUNDED', 'FULL']" |
| MYPY-130 | src/bdb_audit/orchestration/e3_reveal.py:41 | P0-TRANSITIVE / TRANSITIVE | type-var | Value of type variable "SupportsRichComparisonT" of "sorted" cannot be "Any / None" |
| MYPY-131 | src/bdb_audit/assurance/residual_risk_finalization.py:26 | P0-TRANSITIVE / TRANSITIVE | misc | Set comprehension has incompatible type Set[Any / None]; expected Set[str] |

Pełne per-error witnesses i uzasadnienia są w MYPY_TRIAGE.json; baseline/after/closure/configured log exact hashes są w EVIDENCE_MANIFEST. Nie zmieniano 83 dormant legacy błędów ani zamrożonych schemas/normy w celu uzyskania typing PASS.
