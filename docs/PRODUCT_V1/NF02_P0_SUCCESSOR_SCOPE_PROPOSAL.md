# NF02 P0 — konkretny zakres successor i decyzja o kwalifikacji

Data: 2026-10-11. **PROPOZYCJA DO DECYZJI WŁAŚCICIELA. Brak zatwierdzenia nowej normy, Q1/Q2 lub aktywacji. Import BLOCKED.**

## Wynik wymagany przed dalszą pracą

**Domknięcie P0 przy zachowaniu obecnych kontraktów obejmuje wszystkie 131 kontraktów.** Nie uzyskano mniejszego, odrębnie kwalifikowalnego zbioru przez samo wydzielenie pierwszego przyjęcia wyniku. Wynik jest taki sam dla zatwierdzonego grafu z 6 października i dla późniejszego, niezakwalifikowanego draftu Registry z poprawionymi wersjami, zamkniętymi events i material refs.

Zgodnie z decyzją właściciela o strategii 2 **nie rozpoczęto pełnego przeglądu semantycznego 131 kontraktów ani materializacji nowej normy**. Przeprowadzono odczyt istniejących deklaracji, przejście zależności oraz sprawdzenie zachowanych plików. Powrót po decyzję wynika z wyraźnego warunku właściciela: gdy closure nadal obejmuje 131, przed dalszą realizacją trzeba wybrać strategię. Nie można ogłosić mniejszego Q1, pozostawiając te same szerokie kontrakty.

Pełna, odtwarzalna lista wejść, hashy, wersji, referencji, świadków osiągalności, profili i schematów znajduje się w [NF02_P0_SUCCESSOR_DEPENDENCIES.json](NF02_P0_SUCCESSOR_DEPENDENCIES.json). Generator: [tools/nf02_p0_scope.py](../../tools/nf02_p0_scope.py). Pliki pełnego R5.4.2, jego graf, kwalifikacje historyczne i zatwierdzenie właściciela pozostają niezmienione.

## Jak wyznaczono zakres

Korzenie wynikają z żądanych operacji, a nie z założonej liczby kontraktów: binding, osobny STARTED, admission, późniejszy result, legalny genesis, instalowane authority/schema/policy/spec/source oraz trwałe command/commit/receipt. Dla każdego korzenia przejście obejmuje **wszystkie dozwolone material reference targets**, następnie ich zależności. Obejmuje również odwołania warunkowe i retry; cardinality `0..1` nie usuwa z kontraktu dozwolonej gałęzi. Oddzielnie domknięto profile, raw payload grammar i zależności schematów.

To domknięcie kontraktów obsługiwanych przez model. Jeden konkretny pierwszy commit może zawierać znacznie mniej obiektów. Taki przykład nie kwalifikuje innych wariantów, które te same publiczne kontrakty nadal dopuszczają. Nie wywnioskowano obowiązku wykonania całego E1–E6 przed pierwszym wynikiem wyłącznie z liczby osiągalnych typów.

| Korzeń obecnego draftu | Obowiązek P0 |
| --- | --- |
| assignment_package_binding/2 | Exact raw przydzielonego pakietu i wcześniejszy Assignment |
| lane_result_admission_evidence/3 | Autoryzowany odbiór retained raw po legalnym STARTED |
| bdb_audit_lane_result/3 | Późniejszy wynik wyłącznie z wcześniejszego evidence |
| campaign_genesis/2 | Nowa kampania; legalna inicjalizacja i source admission |
| installation_bootstrap_profile/1 | Nowa immutable revision ośmiu initial pins |
| artifact_contract_registry/1 | Exact semantyczna rejestracja i target domains |
| schema_registry/2 | Wszystkie wymagane executable bindings, external root first |
| policy_revision/2 | Governing predicates i scope autoryzacji |
| spec_revision/2 | Kolejność i dopuszczone wersje całego protokołu |
| trust_profile/2 | Coordinator authority, vault boundary, recovery i ograniczenia |
| source_identity/2 | Exact source; commit i tree jako różne typy obiektów |
| command_envelope/2 | Uwierzytelnione authority-changing requests, w tym STARTED |
| commit_body/2 | Jeden writer, jedna atomic closure i zgodność command/events |
| command_receipt/2 | Trwałe powiązanie command/commit i legalny retry |

Bootstrap i przydział dołączają m.in. build_manifest/2, source_generation/2, source_manifest/2, bootstrap_admission_decision/2, legacy admission assessments, assignment_manifest/2, attempt/2, stage_run/2, lane_run/2, stage_spec/2, lane_spec/2, executor_spec/2, delivery_spec/2, grant_body/2, view_manifest/2, potential_exposure_record/2, knowledge_state/2 oraz isolation qualification. Ich pełne referencje, warunki i źródłowe paragrafy są zapisane w JSON i tabeli na końcu.

## Konkretne zależności rozszerzające closure

| Ścieżka / pole | Exact zakres w obecnym draftcie | Dlaczego nie można pominąć |
| --- | --- | --- |
| command_envelope/2 → command_payload.proposed_object_refs | 128 registered target keys | Zamknięty inline command nadal dopuszcza pełny domenowy zbiór proposed artifacts |
| commit_body/2 → immutable_object_refs | 129 target keys | Accepted closure waliduje wszystkie deklarowane typy, command i artefakty |
| command_receipt/2 → result_object_refs | 131 target keys | Trwały sidecar nie ogranicza zbioru wynikowych referencji do trzech NF02 facts |
| command/commit events → target_ref oraz basis_refs | po 131 target keys | Wariant events, authority i klasy refs wymagają osobnych predykatów; samo pole nie kwalifikuje odbiorcy |
| binding → assignment → attempt → retry_reason_ref → checkpoint/2 → sealed_output_refs | checkpoint dopuszcza 127 target keys | Nie wolno uznać wariantu retry za wykluczony tylko dlatego, że pierwszy przykład nie używa retry |
| schema_registry/2 → pełny exact Registry i bindings | 131 canonical schemas | Schematy, body/Registry/profile parity oraz dostępny zakres commandów muszą się zgadzać |
| osiągalne kontrakty → profile; profile → payload_schema_ref | 127 profile contracts + 19 payload schemas | Schemat samego profilu nie zastępuje osobnego schematu walidacji raw payload |

Dla zatwierdzonego modelu można przejść od command_envelope/1.command_payload_ref do całego registered domain. Późniejsze OD-016 zamyka payload/events, lecz nie zmniejsza finite target domain. OD-024 dodatkowo wymaga bootstrap precedence V2. Domknięcie zaktualizowanego Registry policzono od nowa; wynik 131 nie pochodzi z bezkrytycznego przyjęcia historycznej deklaracji fixed point.

Źródła: Data §§14, 15.1–15.3, 17, 184, 187–188, 192.D3; [OD-016 i OD-024](../R5_4_2/OWNER_DELEGATED_DECISION_REGISTER.md); [COMMAND_EVENT_CONTRACT.md](../R5_4_2/autonomous_2026_10_07/design/COMMAND_EVENT_CONTRACT.md); aktualny Registry raw digest i exact field targets są w JSON. Opcjonalność pola, typed-ref dependency i obowiązek prior acceptance są zachowane w świadkach; nie zastąpiono ich samym kind/logical ID.

## Obowiązkowe zależności poza trzema facts NF02

| Warstwa | Zachowany obowiązek / źródło | Konkretne wejścia do nowego successor |
| --- | --- | --- |
| Globalna authority i historia | Data §§9.1, 14.6, 15–16; ADR-006; Registry global invariants | Niezależne installation/principal pins, finite producer/scope, campaign/HistoryCut, command equality, ObjectDigest/RawDigest separation, union-DAG, no self/future refs |
| Bootstrap i migracja | Data §192.D3/E/H; roadmap N4/N8; OD-024/027/040 | External schema root przed SchemaRegistry; qualified legacy/source input; EMPTY_HISTORY; exact osiem pins; tylko nowa kampania; dawny reader i wszystkie stare bytes pozostają |
| Assignment i disclosure | Data §192.E1–E4/E6; OD-025 | Exact assignment/attempt/source/slot/spec, pozytywny grant/view/exposure/knowledge/isolation; accepted B przed osobnym STARTED; delivery wyłącznie retained bound bytes |
| Admission/result | Data §192.D2/E2–E6 | Exact result ZIP, trwałość raw przed acceptance, deterministic normalization, osobne E i R, pełna chronologia i provenance; secret/capability poza canonical bodies |
| Replay i storage | Data §§14.6, 15–16, 192.E6; roadmap N5–N9 | CAS/idempotency, konflikt i concurrency, crash/restart/replay, integralność raw i receipts, bieżąca authority dla nowych writes, brak backfill |
| Kwalifikacja | Data §§187.1–187.2/192.2; roadmap N1–N4/N9 | Dokładny candidate manifest, oba set digests, immutable readback, końcowy audit, Registry/Golden/root refs, jawna decyzja właściciela, niezależny review/freeze i exact runtime evidence |

W JSON zachowano wszystkie 16 Registry global invariants, role, producer authority i required validation layers każdego kontraktu. Żaden istniejący globalny obowiązek bezpieczeństwa nie jest wyłączony przez nazwę P0. Nie dodano natomiast wymogu N11 jako warunku samego pierwszego wyniku. N10 jest osobnym warunkiem deklaracji NF02 CLOSED, a N11 deklaracji kwalifikacji całej aplikacji.

Normatywna paczka wymaga ośmiu Markdown sources oraz Registry i Golden (Data §192.2). W odrębnej propozycji trzeba zachować exact odziedziczone ADR-006, migration i vNext development plan; zmienione dokumenty wymagają osobnych successor bytes. Machine closure obejmuje exact canonical/profile/payload schemas, descriptor governance/AuthorBaselineQualificationRecord/2, root prerequisites, RawRef contracts, finite profiles i ich dependencies. Manifest ma dynamiczną membership/count, a nie ręcznie wybrany mianownik. Obecna inwentaryzacja schematów nie jest gotowym qualification manifestem.

## Zmiany wersji i wpływ na bezpieczeństwo

Żądana dodatnia implementacja w checkpointcie `7508d4fd5d0dc3e2f3cfa3fe5e07834c9e3b8298` obsługuje przygotowany protokół B/1 → STARTED → E/2 → R/2 i wcześniejszy closed schema context. Późniejszy pełny draft propaguje wersje. **Nie jest z nim kompatybilna przez zmianę etykiet lub fallback.** Zmiana wymaga actual codecs, pins i predykatów zgodnych z ostatecznie zatwierdzoną normą.

| Rodzina | Zachowane wejście / implementacja testowa | Obecny draft | Wpływ |
| --- | --- | --- | --- |
| Package binding | assignment_package_binding/1 | /2 | Target Assignment/2 i nowe dokładne profile/context refs |
| Admission evidence | lane_result_admission_evidence/2 | /3 | Binding/2, Assignment/2, exact slot/profile i HistoryCut context |
| Accepted result | bdb_audit_lane_result/2 | /3 | Wyłącznie prior E/3; bez przepisania historycznych E/2/R/2 |
| Command/commit/receipt | /1 | /2 | Closed inline payload/events, finite target domains, pełna zgodność trwałych envelopes |
| HistoryCut | zarejestrowany history_cut/1 / inline context | /2 i exact inline HistoryCut | Authority pochodzi z accepted cut; canonical key i inline representation nie są aliasami |
| TrustProfile | /1 declaration-only | /2 | Pełne Data §9.1 fields, independent principal pin, protected vault, recovery/anchor i jawne non-guarantees |
| Source/build/genesis | /1 | /2 | Actual source identity, provenance/build inputs, legalny pregenesis installation context |
| Spec/policy/assignment/attempt/specs/view/knowledge/grants | /1 | /2 | Propagacja typed targets, closed nested fields i pełnych predicate/profile obligations |
| SchemaRegistry, Registry, installation profile, legacy raw, projection policy | te same contract keys | te same keys, nowe exact immutable revisions gdzie zmienią się pins | Same key nie oznacza przeniesienia wcześniejszej kwalifikacji na inne bytes |

W obecnym draftcie: **21 nowych kinds, 105 successor kind versions i 5 zachowanych predecessor keys**. To klasyfikacja względem rzeczywistego qualified R5.4.1 Registry, nie liczenie samych zmian napisów w późniejszym grafie V2. Tabela końcowa podaje wszystkie 131 mappings. Zachowanie key pięciu kontraktów wymaga jeszcze wykazania pełnej own-body/schema parity; istniejący build oznacza te pięć jako pending. Wersje są projektowe, nie zatwierdzone nowym Q1.

Raw ZIP i source authority nie stają się zaufane przez manifest lub signature producenta. Runtime adapter używa niezależnych owner/qualifier pins, ograniczonych grants i osobnej command signature; caller nie wybiera root. Proces rzeczywistej instalacji opisuje [NF02_P0_QUALIFICATION_REQUEST.md](NF02_P0_QUALIFICATION_REQUEST.md). Żadnych nowych certyfikatów, rootów, qualification records ani PASS nie wytworzono.

## Formalna propozycja zmiany zakresu kwalifikacji

Decyzja strategiczna z tej rozmowy autoryzuje **przygotowanie** odrębnego minimalnego successor. Nie zastępuje zatwierdzenia modelu z 6 października, nie zatwierdza bieżących draft bytes i nie jest nowym owner risk acceptance z Data §187.2.

Proponowane brzmienie przyszłej decyzji, wymagające zatwierdzenia konkretnych nowych bytes:

> Kwalifikacja odrębnego P0 successor obejmuje dokładny zbiór kontraktów/profili/schematów i zależności wskazany w jego niezmiennym scope manifest oraz wszystkie odziedziczone globalne obowiązki bezpieczeństwa. Zastępuje zakres Q1 wyłącznie dla tej nowej linii. Pełny R5.4.2, jego 131 kontraktów, approval i historyczne evidence pozostają bez zmian. Fresh Q1, wymagane Q2, niezależna installation/producer authority i mandatory runtime tests poprzedzają aktywację. Żadne dotychczasowe PASS nie przechodzą na zmienione bytes automatycznie.

**Tego zastąpienia nie można obecnie przedstawić jako kwalifikacji mniejszej niż 131.** Dla zachowanych domen wynikowy scope manifest zawiera wszystkie 131. Mniejszy wariant wymaga dodatkowego zatwierdzenia innego, rzeczywiście ograniczonego modelu przed ustaleniem nowego closure. Nie ustalono dla niego fikcyjnej liczby kontraktów ani czasu.

Konkretny zakres dodatkowej decyzji dla ograniczonego modelu:

1. Oddzielne finite command/event/artifact domains dla legalnego bootstrap, assignment context, binding, STARTED, retained delivery, evidence/result i bezpiecznych odmów. Ograniczenie musi wystąpić w normie, Registry, codecs, executable schemas, installation profile i Store dispatch — nie tylko w UI.
2. Nowe successor contracts dla zmienionych CommandEnvelope/CommitBody/CommandReceipt oraz wszystkich rodziców zmienionych target domains; bez reinterpretacji zachowanych /1-/2 lub aliasów. Numery i exact target sets wymagają osobnego version-impact/closure po zatwierdzeniu modelu.
3. Jawna polityka retry/checkpoint: zachować całą legalną ścieżkę albo odrębnie zdefiniować dostępne bezpieczne stany i odmowy. Nie wolno wykreślić retry, resume, konfliktów, crash recovery lub disclosure tylko dla zmniejszenia wyniku.
4. Scoped policy/spec/transition/profiles muszą zachować wszystkie authority/source/isolation/knowledge/raw/recovery predicates P0. Niewspierane końcowe operacje pozostają fail-closed; przyjęty wynik nie tworzy Lane/StageCompletion, assurance PASS, STOP lub release.
5. Osobna, zatwierdzona interpretacja zakresu Q1/Q2 i N1–N9 dla nowej linii; dynamiczny exact manifest, global dependencies, namespace/migration, kwalifikacja wszystkich dostępnych przypadków, niezależny review i installation. Nie tworzyć nowego no-legacy bootstrap bez jego kontraktu i kwalifikacji.

To zmienia dostępne zachowanie i zgodność. Może zmniejszyć powierzchnię publicznych operacji, ale wymaga udowodnienia, że nie osłabia mandatory bezpieczeństwa. Same ograniczone grants producenta nie zmieniają gramatyki ani qualification domain szerszych kontraktów. Jeżeli nowe closure ponownie wyniesie 131 lub wykluczenie obowiązkowej zależności okaże się niedopuszczalne, trzeba ponownie wrócić po decyzję.

## Nakład w porównaniu z pełnym R5.4.2

| Praca | P0 przy obecnych kontraktach | Pełny R5.4.2 | Nowy ograniczony model |
| --- | --- | --- | --- |
| Q1 canonical contract denominator | 131 | 131 | Jeszcze nieustalony; wymaga dodatkowej decyzji normatywnej i closure |
| Profile / schematy aktualnego draftu | 127 / 277 (131 canonical + 127 profile + 19 payload) | Te same zachowane draft inputs | Muszą być wyprowadzone ponownie; brak uczciwej liczby przed modelem |
| Zmiany względem qualified predecessor | 21 new kinds, 105 versions, 5 keys do sprawdzenia parity | Ten sam zakres | Osobna propagacja i nowe wersje ograniczonych wrappers/parents |
| Normative inputs | 8 Markdown + Registry/Golden i exact machine/governance closure | To samo | Osobna linia: odpowiedni komplet źródeł i jawne zakresowe zmiany, zachowany predecessor |
| Reuse dotychczasowej implementacji | Store/CAS/raw/authority/normalizer/E1 plus testy; konieczna adaptacja finalnych wire versions | To samo dla P0, dalej pozostali consumers | Reuse wspólnego Store i granic, nowy scoped codec/dispatch/profile parity |
| Qualification/runtime proof | Fresh Q1/Q2 i wszystkie obowiązkowe N1–N9 dla pierwszego wyniku | Dodatkowo N10 dla NF02 CLOSED i N11 dla full application claim | Fresh Q1/Q2 i wszystkie obowiązki wynikające z zatwierdzonego nowego scope; nie wolno ich samodzielnie skrócić |
| Oszczędność w przeglądzie Q1 | **0 kontraktów** | Baza porównania | Nieudowodniona; dodatkowy koszt projektu i kwalifikacji nowej linii |

Rozdzielenie milestone pierwszego wyniku od zakończenia aplikacji może uporządkować wykonanie, ale nie zmniejsza obecnego Q1. Kopiowanie wszystkich 131 pod nową nazwą P0 dodałoby obsługę drugiej linii bez wykazanej oszczędności. Nie podano szacunku godzin na podstawie liczby plików; pending semantic parity i rzeczywista niezależna kwalifikacja nie mają tu zmierzonej wydajności.

## Dowody obecne, braki i rzeczywiste osoby zatwierdzające

| Warunek | Aktualny dowód | Brakujące wejście / kto odpowiada |
| --- | --- | --- |
| Zakres i normatywna authority | Owner approval 2026-10-06 dla full 131; obecna strategia 2 tylko prepare; zachowane exact hashes | Właściciel wybiera dalszą strategię po tym wyniku; dla zmiany modelu zatwierdza konkretną nową normę i jej bezpieczeństwo/zgodność |
| Fresh Q1 | R5.4.1 author-qualified predecessor; 131-key draft Registry, 277 read-back schemas; brak drift w source inputs zachowanych raportów | Complete approved candidate, oba set digests/manifest, parity/Golden, immutable readback/final audit, nowy authorized qualification/2 i jawne owner assurance decision; uprawniony kwalifikator oraz właściciel, Data §187.2 |
| Q2 / independent freeze | Nieuzyskane; pending drafts nie są decyzjami | Rzeczywiście niezależny reviewer READY dla exact manifest oraz authorized freeze decision/1 z §187.1; niezależny reviewer i uprawniony governance actor |
| Runtime authority | Production verifier/grants/leases/CMS i fail-closed granice gotowe; unit authority jest symulowana | Rzeczywisty owner/installer ustala cert pins niezależnym kanałem; niezależny qualifier podpisuje rzeczywiste dowody; uprawniony producent otrzymuje exact campaign/slot/operation/time grants; chroniona usługa i storage |
| Positive implementation | Checkpoint 7508d4fd; 16 nowych testów i 274 regresji PASS; exact raw/chronology/retry/race/crash/replay i E1 inbox | Zgodność z finalnymi successor codecs/pins, komplet mandatory frozen vectors, genuine process/crash/delivery trace i realny wynik rzeczywistego producenta; kwalifikator nie może zastąpić tego własnym lokalnym testem |
| Source identity | Osobny commit 4e4554dd naprawia zapis tree z verified resolver; regresja na rzeczywistym repo; HEAD i tree rozróżnione | Source/install authority dla przyszłej kampanii; dawne raporty pozostają niezmienione |

Obecny Golden build ma 167 inherited vectors, 2537 schema vectors i 182 canonical design vectors. Metadane oznaczają go NOT_FROZEN/NOT_QUALIFIED, canonical runtime NOT_RUN. Liczby nie są dowodem wykonania; 290 lokalnych testów z dwóch suites nie pokrywa automatycznie tych obowiązków. Sprawdzenie hashy i odtwarzalności tego pakietu jest inwentaryzacją, bez Q1/Q2/N9 PASS.

## Decyzja potrzebna teraz

Właściciel powinien wybrać **jedną** z dwóch dalszych strategii po ujawnieniu full closure:

- **A — zachować obecny model i kontynuować pełne Q1 R5.4.2 dla 131 kontraktów**, utrzymując pierwszy rzeczywisty wynik P0 jako najbliższy runtime milestone. Użyć istniejącej linii zamiast tworzyć jej kopię P0; późniejsze draft changes nadal wymagają exact approval/parity/qualification. Nie wykonywać N11 jako zastępstwa pierwszego wyniku.
- **B — autoryzować zaprojektowanie odrębnego, rzeczywiście ograniczonego modelu** z pięcioma normatywnymi granicami powyżej, a następnie przedstawić nowy konkretny scope/versions/closure do zatwierdzenia. To dodatkowa decyzja o zmianie modelu; nie zgoda na wdrożenie lub z góry ustalony mniejszy Q1.

Najmniejszy następny krok to ta decyzja. Żadna opcja nie ustanawia niezależnej authority, nie daje PASS i nie aktywuje importu. Produkcyjny import pozostaje BLOCKED. Nie wykonano push, merge ani release.

## Odtworzenie i pełny wykaz kontraktów

```powershell
$env:PYTHONUTF8='1'
.venv-f2/Scripts/python.exe tools/nf02_p0_scope.py --check
```

Generator porównuje exact retained inventory, actual schema hashes/length/IDs/dependencies oraz aktualne source hashes sześciu istniejących build readback reports. Nie edytuje historycznych wejść, nie kwalifikuje semantyki i nie zapisuje historii kampanii. W tabeli: **S** = nowa wersja istniejącego kind, **N** = nowy kind, **K** = zachowany predecessor key wymagający parity/nowych exact pins. Dokładne predecessor keys, powód propagacji, źródłowy paragraf, profile i świadek zależności są w JSON.

Kontrole przygotowanego pakietu: ponowne wygenerowanie i `--check` PASS; zero source drift w sześciu zachowanych build reports; exact 277 schema files (26 428 340 bytes) sprawdzonych bez modyfikacji; Ruff PASS i Mypy PASS dla generatora; `git diff --check` PASS. Lokalny niekwalifikowany build `3c372564abf4339e33a12b5d658ced25e68a7ed05334d0c131e400a4f297bf5d` ponownie przeszedł `--verify-payload` (402 pliki) i cztery ograniczone `--self-test`. Brak nowego Q1/Q2/N9 PASS. [Implementation evidence](NF02_P0_IMPLEMENTATION_EVIDENCE.json) dotyczy checkpointu implementacji 7508d4fd; późniejsze zmiany dokumentów decyzyjnych nie są dopisywane do jego historycznych hashy lub wyników.

<!-- CONTRACT_INVENTORY -->

| Exact key | Zmiana | Predecessor / źródłowy klucz projektu |
| --- | --- | --- |
| approval_decision/2 | S | approval_decision/1; projekt approval_decision/1 |
| artifact_contract_registry/1 | K | artifact_contract_registry/1; projekt artifact_contract_registry/1 |
| artifact_hash_manifest/2 | S | artifact_hash_manifest/1; projekt artifact_hash_manifest/1 |
| assignment_manifest/2 | S | assignment_manifest/1; projekt assignment_manifest/1 |
| assignment_package_binding/2 | S | assignment_package_binding/1; projekt assignment_package_binding/1 |
| assurance_claim_set/1 | N | nowy kind; projekt assurance_claim_set/1 |
| attempt/2 | S | attempt/1; projekt attempt/1 |
| bdb_audit_lane_result/3 | S | bdb_audit_lane_result/2; projekt bdb_audit_lane_result/2 |
| blind_origin_eligibility_assessment/2 | S | blind_origin_eligibility_assessment/1; projekt blind_origin_eligibility_assessment/1 |
| bootstrap_admission_decision/2 | S | bootstrap_admission_decision/1; projekt bootstrap_admission_decision/1 |
| build_manifest/2 | S | build_manifest/1; projekt build_manifest/1 |
| bundle_manifest/2 | S | bundle_manifest/1; projekt bundle_manifest/2 |
| campaign_conclusion/2 | S | campaign_conclusion/1; projekt campaign_conclusion/1 |
| campaign_genesis/2 | S | campaign_genesis/1; projekt campaign_genesis/1 |
| candidate_assurance_case/2 | S | candidate_assurance_case/1; projekt candidate_assurance_case/1 |
| challenger_assignment/2 | S | challenger_assignment/1; projekt challenger_assignment/1 |
| challenger_result/2 | S | challenger_result/1; projekt challenger_result/1 |
| checkpoint/2 | S | checkpoint/1; projekt checkpoint/1 |
| clean_control_assessment/1 | N | nowy kind; projekt clean_control_assessment/1 |
| cleanup_result/2 | S | cleanup_result/1; projekt cleanup_result/2 |
| command_envelope/2 | S | command_envelope/1; projekt command_envelope/1 |
| command_receipt/2 | S | command_receipt/1; projekt command_receipt/1 |
| commit_body/2 | S | commit_body/1; projekt commit_body/1 |
| compatibility_fixture_assessment/2 | S | compatibility_fixture_assessment/1; projekt compatibility_fixture_assessment/1 |
| compatibility_gate_result/2 | S | compatibility_gate_result/1; projekt compatibility_gate_result/1 |
| contamination_assessment/2 | S | contamination_assessment/1; projekt contamination_assessment/1 |
| contradiction_resolution_decision/2 | S | contradiction_resolution_decision/1; projekt contradiction_resolution_decision/1 |
| contradiction_revision/2 | S | contradiction_revision/1; projekt contradiction_revision/1 |
| corpus_manifest/2 | S | corpus_manifest/1; projekt corpus_manifest/1 |
| corpus_member_admission_assessment/2 | S | corpus_member_admission_assessment/1; projekt corpus_member_admission_assessment/1 |
| corpus_member_candidate/1 | N | nowy kind; projekt corpus_member_candidate/1 |
| coverage_obligation/2 | S | coverage_obligation/1; projekt coverage_obligation/1 |
| coverage_obligation_key/2 | S | coverage_obligation_key/1; projekt coverage_obligation_key/1 |
| coverage_obligation_qualification/2 | S | coverage_obligation_qualification/1; projekt coverage_obligation_qualification/1 |
| defect_unit/1 | N | nowy kind; projekt defect_unit/1 |
| delivery_spec/2 | S | delivery_spec/1; projekt delivery_spec/1 |
| dependency_independence_assessment/2 | S | dependency_independence_assessment/1; projekt dependency_independence_assessment/1 |
| discovery_confirmation_assessment/1 | N | nowy kind; projekt discovery_confirmation_assessment/1 |
| discovery_corpus_match_assessment/1 | N | nowy kind; projekt discovery_corpus_match_assessment/1 |
| discovery_novelty_assessment/1 | N | nowy kind; projekt discovery_novelty_assessment/1 |
| discovery_record/2 | S | discovery_record/1; projekt discovery_record/1 |
| discovery_tool_origin_assessment/1 | N | nowy kind; projekt discovery_tool_origin_assessment/1 |
| effort_results/1 | N | nowy kind; projekt effort_results/1 |
| environment_record/2 | S | environment_record/1; projekt environment_record/1 |
| evidence_applicability_assessment/2 | S | evidence_applicability_assessment/1; projekt evidence_applicability_assessment/1 |
| evidence_dependency_graph/1 | N | nowy kind; projekt evidence_dependency_graph/1 |
| evidence_invalidation/2 | S | evidence_invalidation/1; projekt evidence_invalidation/1 |
| evidence_qualification_assessment/2 | S | evidence_qualification_assessment/1; projekt evidence_qualification_assessment/1 |
| execution_descriptor/2 | S | execution_descriptor/1; projekt execution_descriptor/1 |
| execution_result/2 | S | execution_result/1; projekt execution_result/1 |
| executor_spec/2 | S | executor_spec/1; projekt executor_spec/1 |
| experiment_spec/2 | S | experiment_spec/1; projekt experiment_spec/1 |
| false_negative_relationship_assessment/1 | N | nowy kind; projekt false_negative_relationship_assessment/1 |
| fault_run_record/2 | S | fault_run_record/1; projekt fault_run_record/2 |
| fault_spec/1 | N | nowy kind; projekt fault_spec/1 |
| final_assurance_case/2 | S | final_assurance_case/1; projekt final_assurance_case/1 |
| final_technical_report/2 | S | final_technical_report/1; projekt final_technical_report/2 |
| finding_adjudication_decision/2 | S | finding_adjudication_decision/1; projekt finding_adjudication_decision/1 |
| finding_axis_assessment/2 | S | finding_axis_assessment/1; projekt finding_axis_assessment/1 |
| finding_claim_revision/2 | S | finding_claim_revision/1; projekt finding_claim_revision/1 |
| finding_defect_match_assessment/1 | N | nowy kind; projekt finding_defect_match_assessment/1 |
| gate_decision/1 | N | nowy kind; projekt gate_decision/1 |
| grant_body/2 | S | grant_body/1; projekt grant_body/1 |
| handoff_validation_result/1 | N | nowy kind; projekt handoff_validation_result/1 |
| history_anchor_receipt/2 | S | history_anchor_receipt/1; projekt history_anchor_receipt/1 |
| history_cut/2 | S | history_cut/1; projekt history_cut/1 |
| holdout_exposure_assessment/1 | N | nowy kind; projekt holdout_exposure_assessment/1 |
| hypothesis_revision/2 | S | hypothesis_revision/1; projekt hypothesis_revision/1 |
| input_disposition_record/2 | S | input_disposition_record/1; projekt input_disposition_record/2 |
| installation_bootstrap_profile/1 | K | installation_bootstrap_profile/1; projekt installation_bootstrap_profile/1 |
| invariant_revision/2 | S | invariant_revision/1; projekt invariant_revision/1 |
| inventory_revision/2 | S | inventory_revision/1; projekt inventory_revision/2 |
| isolation_baseline_profile/2 | S | isolation_baseline_profile/1; projekt isolation_baseline_profile/1 |
| isolation_qualification/2 | S | isolation_qualification/1; projekt isolation_qualification/1 |
| knowledge_state/2 | S | knowledge_state/1; projekt knowledge_state/1 |
| lane_completion/2 | S | lane_completion/1; projekt lane_completion/1 |
| lane_result_admission_evidence/3 | S | lane_result_admission_evidence/2; projekt lane_result_admission_evidence/2 |
| lane_run/2 | S | lane_run/1; projekt lane_run/1 |
| lane_spec/2 | S | lane_spec/1; projekt lane_spec/1 |
| legacy_exposure_reconstruction_assessment/2 | S | legacy_exposure_reconstruction_assessment/1; projekt legacy_exposure_reconstruction_assessment/1 |
| legacy_mechanical_validation_assessment/2 | S | legacy_mechanical_validation_assessment/1; projekt legacy_mechanical_validation_assessment/1 |
| legacy_observation_mapping_assessment/2 | S | legacy_observation_mapping_assessment/1; projekt legacy_observation_mapping_assessment/1 |
| legacy_observation_semantic_equivalence_assessment/2 | S | legacy_observation_semantic_equivalence_assessment/1; projekt legacy_observation_semantic_equivalence_assessment/1 |
| legacy_raw_ref/1 | K | legacy_raw_ref/1; projekt legacy_raw_ref/1 |
| lineage_admission_assessment/2 | S | lineage_admission_assessment/1; projekt lineage_admission_assessment/1 |
| materiality_assessment/2 | S | materiality_assessment/1; projekt materiality_assessment/1 |
| model_fidelity_assessment/2 | S | model_fidelity_assessment/1; projekt model_fidelity_assessment/1 |
| negative_evidence_record/2 | S | negative_evidence_record/1; projekt negative_evidence_record/1 |
| negative_opportunity_unit/1 | N | nowy kind; projekt negative_opportunity_unit/1 |
| obligation_applicability_decision/2 | S | obligation_applicability_decision/1; projekt obligation_applicability_decision/1 |
| observation/2 | S | observation/1; projekt observation/1 |
| observation_dependency/1 | N | nowy kind; projekt observation_dependency/1 |
| policy_revision/2 | S | policy_revision/1; projekt policy_revision/1 |
| potential_exposure_record/2 | S | potential_exposure_record/1; projekt potential_exposure_record/1 |
| projection_policy/1 | K | projection_policy/1; projekt projection_policy/1 |
| public_conclusion_statement/1 | N | nowy kind; projekt public_conclusion_statement/1 |
| release_qualification/2 | S | release_qualification/1; projekt release_qualification/1 |
| report_export_receipt/2 | S | report_export_receipt/1; projekt report_export_receipt/1 |
| residual_risk/1 | N | nowy kind; projekt residual_risk/1 |
| root_cause_revision/2 | S | root_cause_revision/1; projekt root_cause_revision/1 |
| run_manifest/2 | S | run_manifest/1; projekt run_manifest/1 |
| schema_registry/2 | K | schema_registry/1, schema_registry/2; projekt schema_registry/2 |
| scope_state_record/2 | S | scope_state_record/1; projekt scope_state_record/1 |
| snapshot/2 | S | snapshot/1; projekt snapshot/1 |
| snapshot_export_record/2 | S | snapshot_export_record/1; projekt snapshot_export_record/1 |
| sound_claim/2 | S | sound_claim/1; projekt sound_claim/1 |
| source_drift_impact_assessment/2 | S | source_drift_impact_assessment/1; projekt source_drift_impact_assessment/1 |
| source_drift_record/2 | S | source_drift_record/1; projekt source_drift_record/1 |
| source_generation/2 | S | source_generation/1; projekt source_generation/1 |
| source_identity/2 | S | source_identity/1; projekt source_identity/1 |
| source_manifest/2 | S | source_manifest/1; projekt source_manifest/1 |
| source_reconciliation_assessment/2 | S | source_reconciliation_assessment/1; projekt source_reconciliation_assessment/1 |
| spec_revision/2 | S | spec_revision/1; projekt spec_revision/1 |
| stage_completion/2 | S | stage_completion/1; projekt stage_completion/1 |
| stage_run/2 | S | stage_run/1; projekt stage_run/1 |
| stage_spec/2 | S | stage_spec/1; projekt stage_spec/1 |
| standalone_payload_manifest/2 | S | standalone_payload_manifest/1; projekt standalone_payload_manifest/1 |
| state_model/1 | N | nowy kind; projekt state_model/1 |
| stop_evaluation/2 | S | stop_evaluation/1; projekt stop_evaluation/1 |
| stop_input/2 | S | stop_input/1; projekt stop_input/1 |
| successor_campaign_genesis/2 | S | successor_campaign_genesis/1; projekt successor_campaign_genesis/1 |
| successor_campaign_selection_decision/2 | S | successor_campaign_selection_decision/1; projekt successor_campaign_selection_decision/1 |
| surface_collector_record/2 | S | surface_collector_record/1; projekt surface_collector_record/2 |
| surface_key/2 | S | surface_key/1; projekt surface_key/1 |
| surface_record/2 | S | surface_record/1; projekt surface_record/1 |
| tool_execution_record/2 | S | tool_execution_record/1; projekt tool_execution_record/2 |
| transition_authorization_proposal/2 | S | transition_authorization_proposal/1; projekt transition_authorization_proposal/1 |
| trust_profile/2 | S | trust_profile/1; projekt trust_profile/1 |
| trusted_predecessor_selection_decision/2 | S | trusted_predecessor_selection_decision/1; projekt trusted_predecessor_selection_decision/1 |
| validation_result/2 | S | validation_result/1; projekt validation_result/1 |
| view_manifest/2 | S | view_manifest/1; projekt view_manifest/1 |
