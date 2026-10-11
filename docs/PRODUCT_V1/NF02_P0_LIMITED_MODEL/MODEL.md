# NF02 P0 — ograniczony model do decyzji właściciela

2026-10-11. Model `BDB_NF02_P0_LIMITED_1`. **PROPOSED — NOT_APPROVED — NOT_QUALIFIED — NOT_ACTIVE.** Jedna zamknięta iteracja projektu autoryzowana decyzją B w tej rozmowie. Zgoda na projektowanie nie zatwierdza poniższej normy, nie ustanawia authority i nie aktywuje importu.

**Rekomendacja: przyjąć ten odrębny zakres do dalszej implementacji i kwalifikacji.** Domknięcie wynosi **18 kontraktów canonical, 7 profili, 43 schematy i 3 obowiązkowe kwalifikacje: Q1 autora, Q2 niezależnego review/freeze oraz RQ runtime**. Redukcja wobec pełnego draftu R5.4.2 obejmuje 113 kontraktów, 120 profili i 234 schematy. Zmienia dostępne operacje oraz model bootstrap/source; wymaga jawnego zatwierdzenia. Nie jest podzbiorem pełnego R5.4.2 uruchamianym z pominiętymi zależnościami.

Rezultat użytkowy: przyjęta, podpisana odpowiedź wskazanego zewnętrznego audytora na jedno zatwierdzone zadanie dotyczące jednego zamrożonego widoku źródła Git. Właściciel otrzyma oryginalny ZIP, raport audytora, zaakceptowane evidence i wynik związany z tym evidence oraz odtwarzalną historię przyjęcia. Acceptance potwierdza producenta, uprawnienia, pochodzenie i chronologię; findings pozostają deklaracjami audytora. Model nie daje pełnego audit assurance, ukończenia E1–E6 ani NF02 CLOSED.

## 1. Dokładny pakiet i zasady jego użycia

| Materiał | Rola |
| --- | --- |
| Ten dokument, §§M01–M18 poniżej | Samodzielna proponowana norma i konkretna decyzja |
| [MODEL.json](MODEL.json) | Pełne bodies wszystkich 18 kontraktów, material targets, ref classes, profile dependencies, predicates, operacje i wykluczenia; proposed Registry descriptor |
| [DEPENDENCY_GRAPH.json](DEPENDENCY_GRAPH.json) | Zamknięty graf, wszystkie korzenie/krawędzie i świadkowie osiągalności, exact liczniki |
| [QUALIFICATION_MATRIX.json](QUALIFICATION_MATRIX.json) | 11 rodzin Q1, 6 rodzin Q2 i 32 rodziny RQ z wymaganymi wynikami; wymagania, nie wykonane testy |
| `schemas/` i `profiles/` | 43 executable draft schemas i 7 dokładnych profili; żadnego dynamicznego pluginu |
| [CANDIDATE_MANIFEST.json](CANDIDATE_MANIFEST.json) | Dokładne bajty dwóch zbiorów propozycji i ich digests; bez własnego hasha we własnym preimage |
| [LOCAL_VALIDATION.json](LOCAL_VALIDATION.json) | Lokalna kontrola propozycji, preservation i zachowane granice istniejącego evidence; bez qualification authority |

Normatywne są §§M01–M18, definitions/targets/predicates `MODEL.json`, siedem profili, schematy i wymagania kwalifikacji. Wszystkie obowiązki obowiązują łącznie. Przy rozbieżności tekstu/body/schema/predicate należy odmówić freeze i aktywacji oraz poprawić konkretną rozbieżność. Schemat nie zastępuje predykatu historii, podpisu, ACL ani rzeczywistego dowodu wykonania.

Algorytmy `BDB-CJSON-1`, `BDB-OBJECT-DIGEST-1`, RawDigest i Kahn ordering są zachowane z exact [ADR-006](../../../F1_QUALIFICATION/inputs/ADR-006_CANONICAL_SERIALIZATION_AND_IDENTITY_PROFILE.md), którego bajty wiąże manifest. Import dotyczy wyłącznie primitive rules §§2–4, exact-reference purpose §6 i zakazu reinterpretacji algorytmów §9, odtworzonych w M03–M04. **Nie importuje całego foundation modelu przez link „Powiązane”**, jego SourceGeneration/SurfaceKey (§8), legacy bootstrap ani całego historycznego Golden/freeze (§10). Ich zmiana zakresowa jest jawna w §4 tego pakietu; odpowiednie testy primitives nadal są obowiązkowe w Q1/Q2/RQ. To propozycja nowej normy, a nie wyjątek udzielony obecnemu R5.4.2.

Full R5.4.2, jego 131 kontraktów, approval, graf, drafty, checkpointy i historyczne dowody pozostają niezmienione. Odwołania do nich w porównaniu są informacyjne. Nowe bodies nigdy nie są aliasem /1–/2–/3, a stare qualification verdicts nie przechodzą na nowe bajty.

## 2. Pięć granic i zamknięcie zależności

| Granica wybrana przez właściciela | Konkretna zmiana modelu | Zachowana gwarancja |
| --- | --- | --- |
| Finite command/event/artifact domains | 8 komend, 2 event bodies; 15 domain/root kinds oraz 3 wrappers. Exact object count/type dla każdej komendy w schema i predykacie. Registry bez extensions i generic dispatcher. | Jeden Store, autoryzacja każdej operacji, pełne sprawdzenie proposed/basis/events/context |
| Successor wrappers/parents | Command/Commit/Receipt /3 oraz jawne nowe wersje wszystkich zmienionych rodziców; TypedRef wiąże kind/version/actual schema raw hash. | Niezmienność, digest separation, brak silent version fallback |
| Retry/recovery | Jeden aktywny attempt; owner-authorized abort i nowy attempt z exact prior abort. Brak ogólnego checkpoint graph. | Bezpieczny retry, CAS, konflikty, restart, crash recovery i zachowanie raw/facts |
| Scoped policy/spec/disclosure/isolation | Jeden source view/task, jeden audytor w danym attempt, jeden slot. Zewnętrzny host; nieblindny audyt. Właściciel zatwierdza widok i zadanie. | Exact scope, niezależne grants, brak executor write, no result code execution, jawny poziom wiedzy |
| Oddzielny bootstrap i kwalifikacja | Nowa pusta historia z independently approved Git; odrębny namespace/model, Q1/Q2/RQ, exact instalacja. Brak przenoszenia legacy assurance. | Legalny external root przed genesis, osiem pins, niezależny review/authority, brak backfill |

Korzenie grafu wynikają z każdej dostępnej operacji (§M05), trzech wrappers i wszystkich rzeczywistych wire/installation/governance boundaries. Algorytm przechodzi do material target contracts, ich profili oraz każdego `$ref`/payload schema, zachowując gałęzie warunkowe i retry. Zakres obejmuje wszystkie dopuszczone warianty modelu, nie tylko przykładowy pierwszy commit. Deklarowane listy profili/payloads są zamknięte; zawartość RawRef nie może otworzyć nowego kind/profile/validator. Predykaty M01–M18 korzystają tylko z tych typów, retained bytes, OS/CMS, Git i jednego Store. Nie delegują nierozstrzygniętej decyzji do kontraktu pełnego R5.4.2.

| Składnik | Dokładna liczba i membership |
| --- | --- |
| Canonical contracts | 18 — wszystkie w tabeli §3 |
| Profiles | 7 — wszystkie w §M06 |
| Canonical schemas | 18 — jeden na exact contract key |
| Profile schemas | 7 — exact const dla każdego profilu |
| Wire schemas | 9: COMMON/1, SOURCE_MANIFEST/1, PACKAGE_MANIFEST/1, RESULT_MANIFEST/1, NORMALIZED_RESULT/1, DELIVERY_ACK/1, AUDIT_RETURN/1, RELEASE_JOB/1, AUTHORIZATION_TRACE/1 |
| External schemas | 9: ROOT/1, CANDIDATE_MANIFEST/1, OWNER_MODEL_DECISION/1, AUTHOR_QUALIFICATION/1, INDEPENDENT_FREEZE/1, RUNTIME_QUALIFICATION/1, INSTALLATION_RECORD/1, PRINCIPAL_GRANT/1, QUALIFICATION_MANDATE/1 |
| Schemas łącznie | **43 = 18 + 7 + 9 + 9** |
| Inline grammar | COMMON jawnie zawiera TypedRef, ProfileRef, RawRef, Head, HistoryCut, EventId, LogicalId, FileEntry, Member, State, Event. Scope/finding/body representations są jawnie zawarte w powyższych schemas. COMMON nie jest publicznym payload dispatcherem. |
| Kwalifikacje | **3**: author baseline Q1; independent review/freeze Q2; runtime RQ. Owner model decision, konfiguracja root, grant i qualification mandate są decyzjami/authority, nie dodatkowymi kwalifikacjami. |

Registry descriptor jest jednym exact file `MODEL.json`, a nie ukrytym dziewiętnastym canonical kontraktem. Walidator odczytuje tylko jego manifest-pinned bajty. Po zatwierdzeniu nie przyjmuje nowych kontraktów przez edycję tego pliku. Graf jest domknięty na poziomie zaproponowanej normy; lokalny check nie stanowi semantycznej kwalifikacji normy lub kodu.

## 3. Wszystkie kontrakty i zmiany wersji

„Full draft” oznacza niezakwalifikowany Registry prześledzony w poprzednim [pakiecie closure](../NF02_P0_SUCCESSOR_SCOPE_PROPOSAL.md). Brak automatycznej zgodności wire. Wersje poniżej są proposal keys w osobnym namespace; wymagają zatwierdzenia/freeze exact bodies, a nie tylko numeru.

| Contract P0 | Full draft / poprzednia implementacja | Konkretna delta i bezpośrednie target kinds |
| --- | --- | --- |
| artifact_contract_registry/2 | /1 | 18 keys + exact MODEL descriptor; brak extension/all-registered dispatch |
| schema_registry/3 | /2 | Raw bindings wyłącznie dla tych 18; → Registry/2; external schema root first |
| policy_revision/3 | /2 / /1 | Scoped auth/recovery, finite ops; → profile pins |
| spec_revision/3 | /2 / /1 | Zamknięta tabela 8 operacji, transport i FSM; → profile pins |
| trust_profile/3 | /2 / /1 | Jawny separate-host/nonblind scope i non-guarantees; → auth/isolation profiles |
| installation_bootstrap_profile/2 | /1 | Osiem external initial pins; → Registry, SchemaRegistry, policy, spec, trust + serialization/source profile + namespace authority |
| nf02_p0_source_snapshot/1 | Nowy; zastępuje szerszy source/build/legacy graph wyłącznie w P0 | Verified Git commit/tree/blob + exact raw source manifest/archive i approved view. Brak SourceGeneration assurance. |
| campaign_genesis/3 | /2 / /1 | New empty namespace/mode, approved snapshot; → installation profile i source snapshot |
| attempt/3 | /2 / /1 | One active; initial null albo prior aborted retry; → genesis, source, prior attempt, abort |
| assignment_manifest/3 | /2 / /1 | One approved task/view/auditor/slot; → genesis/source/attempt + exact profiles/raw task/member list |
| assignment_package_binding/3 | /2 / /1 | Exact RawDigest i długość pakietu, bez semantic-checksum alias; → prior Assignment/3 |
| nf02_p0_delivery/1 | Nowy, w starej implementacji tylko callback | Real qualified transport SENT + signed ACK; → Assignment, Binding, prior start EventId + retained ACK/signature |
| lane_result_admission_evidence/4 | /3 / /2 | Signed return + exact retained ZIP; → prior Assignment, Binding, Delivery, cut |
| bdb_audit_lane_result/4 | /3 / /2 | Wyłącznie wcześniejsze E/4 + rederive exact raw; → prior evidence; brak Completion/finding truth |
| nf02_p0_abort/1 | Nowy; zastępuje generic checkpoint retry | Exact nonterminal attempt/assignment/cut; → prior attempt i assignment |
| command_envelope/3 | /2 / /1 | Explicit installation/grant/namespace/mode, exact finite op closure; → prior/pinned context + 15 finite proposed/basis kinds |
| commit_body/3 | /2 / /1 | One content Kahn, command/events/context equality + retained authorization trace; → command + 15 finite content kinds, roots |
| command_receipt/3 | /2 / /1 | Trwały post-acceptance sidecar; → own accepted command/commit + exact operation domain facts |

15 domain/root kinds to pierwsze 15 w tabeli. Command nie proponuje Commit lub Receipt; Commit nie może zawierać własnego Commit/Receipt. P0FactAccepted odwołuje się wyłącznie do dokładnych nowych facts danej operacji. Nie można tworzyć root revision po genesis, dołączyć dowolnego innego z 15 rodzajów w START ani przyjąć komendy nieobecnej w tabeli M05.

## 4. Jawne zmiany normatywne względem pełnego R5.4.2

| Obowiązujący pełny zakres / źródło zależności | Proponowana nowa norma P0 | Wpływ i obowiązkowa decyzja |
| --- | --- | --- |
| Data §§14–16, 184; OD-016: ogólne command/commit/receipt domains; retry → checkpoint/2 | M03–M05, M15–M17: finite wrappers i abort basis, 8 operacji | Usunięte zachowanie, nie skrócona walidacja szerszego zachowania; owner zatwierdza nowe keys i brak generic consumers |
| Data §192.D3/H; OD-024/027/040: legacy/source/build admission oraz exact initial pins | M02/M07: nowy approved-Git-only bootstrap, nowy SourceSnapshot i brak legacy assurance transfer | To **nowy kontrakt bootstrap**, obecnie niedozwolony przez starą ścieżkę. Wymaga approved norm, Q1/Q2/RQ i qualified source provenance; brak backfill/migracji faktów. |
| Data §192.E1–E4, OD-025: stage/lane/executor/delivery/grant/view/exposure/knowledge/isolation graphs | M08–M11: pojedynczy immutable view/task, finite roles/scopes i external host | Audit jest jawnie nonblind. Nie obiecuje knowledge reset ani blind independence. Nie wolno tak oznaczać jego wyniku. Owner zatwierdza to zastosowanie i poziom izolacji. |
| Data §192.D2/E2/E6: E/R plus szersze downstream consumers | M12–M14: E/4 oraz R/4 z pełnym join/chronology/raw, accepted auditor submission | Autoryzacja i provenance zachowane; result nie ustanawia finding truth, Lane/StageCompletion, STOP ani release. Te operacje są odrzucane. |
| Data §§187.1–187.2/192.2: full candidate, osiem Markdown/Registry/Golden i approved graph 131 | M18: samodzielna norma P0, exact two-set manifest, wszystkie 18/7/43, Q1/Q2/RQ | **Formalnie proponowana zmiana kwalifikowanego scope i pakowania dla nowej linii**, bez zmiany pełnego scope R5.4.2. Independent freeze i runtime proof pozostają obowiązkowe. |
| ADR-006 full source (§8) i foundation Golden/freeze (§10) | M03/M04/M07/M18: te same primitives, własny bounded source i complete P0 vectors | Nie zmienia hash/canonicalization algorytmu. SourceSnapshot nie jest aliasem source_identity/1; własne instance schemas i fresh vectors. Dwie reference procedures dla primitives nadal wymagane. |
| Data §9.1/global Registry: authority, provenance, raw, state, recovery | M01–M18 odtwarzają wszystkie właściwości konieczne P0 | Brak authority z actor_ref/ticket/manifest lub schematu; fail-closed, current grants i actual OS boundary są obowiązkowe. Pełny host rollback pozostaje jawnym non-guarantee. |

Nie jest to waiver z istniejącego Q1 ani reinterpretacja już zatwierdzonego full R5.4.2. Po przyszłym zatwierdzeniu modelu zakres zostanie zastąpiony **wyłącznie dla tej odrębnej linii P0**. Przeniesienie jej historycznych facts do pełnej linii wymagałoby przyszłej jawnej normy migracji; tutaj nie ma takiej operacji.

## 5. Proponowane obowiązki normatywne

### M01 — Threat model, niezależna authority i granica zaufania

Owner jest rzeczywistym właścicielem normy/instalacji; qualifier jest rzeczywiście niezależnym, uprawnionym podmiotem review/freeze i RQ. Coordinator i audytor nie posiadają ich kluczy. Same różne certificate hashes nie dowodzą niezależności; Q2/RQ sprawdzają osoby/podmioty, kontrolę kluczy i upoważnienia. Producent i niezaufany caller nie mogą wybierać root, wpisywać grants, zmieniać code/root/storage ACL ani kwalifikować samych siebie.

Rzeczywisty OS installer provisionuje root i rzeczywiste SHA-256 DER certificate pins niezależnym kanałem. Protected root/code są zapisywalne tylko przez zaufanego OS owner; Coordinator działa jako **NON_ADMIN_SERVICE_ACCOUNT**, czyta root/code i zapisuje wyłącznie chronione campaign DB/vault/outbox. Audytor pracuje na odrębnym hoście i nie zapisuje tych miejsc. Nie ma publicznego callbacku, HMAC issuera, env/path override ani API samowystawiania credentials. Authority nie wynika z danych wyniku, ACK, manifestu, actor_ref lub body `ROOT` dostarczonego przez caller.

Zakres zagrożeń obejmuje hostile callers/executors, błędne scope/bytes/chronology, races, utratę praw, restart, procesowy crash i partial storage writes. Zaufany owner/installer/OS/kernel/kwalifikator nie jest przeciwnikiem, który ma zostać powstrzymany przez swoje własne ACL. Pełne cofnięcie całego hosta wraz z root/DB/zegarem nie jest wykrywane; brak odrębnego external monotonic anchor jest jawny. Gdy ta gwarancja jest potrzebna zastosowaniu, owner nie może aktywować tego modelu bez zmiany zatwierdzonej normy.

### M02 — Prawdziwy root, signed installation, grants i modes

Root leży wyłącznie w OS CommonAppData `BDB Audit/NF02-P0-Limited`, niezależnie ustalonym przez installer, bez argumentu/env od caller. To proposed miejsce; obecny adapter używa `BDB Audit/NF02` i nie obsługuje tej nowej normy. ROOT/1 jest chronionym wejściem OS, **nie staje się zaufany przez samoweryfikację schematu/podpisu swoim kluczem**. Pin owner/qualifier sprawdza się out of band. Installation i grants mają oddzielne detached CMS/SHA-256 signatures od owner; Q2/RQ attestation podpisuje niezależny qualifier, qualification mandate podpisują owner i qualifier. Wszystkie dokładne payload bytes i signatures są retained. Records muszą odpowiadać swoim frozen external schemas, obu candidate set digests i exact model/namespace/code/environment. Signature verification sprawdza exact signer DER hash, SHA-256, real validity interval/current revocation i podpis dokładnych bajtów. Brak/expiry/revocation/unknown provider/clock error powoduje odmowę nowego write/byte release.

`namespace_authority_digest` to SHA256(`BDB-NF02-P0-NAMESPACE/1` + NUL + CJSON `{model_id,root_id,namespace_id,owner_certificate_sha256,qualifier_certificate_sha256}`). Preimage nie zawiera installation digest ani canonical root refs. Installation wskazuje sześć independently approved root refs; bootstrap zawiera namespace digest. Po finalizacji installation ROOT wskazuje jego actual raw digest. **Installation nie wskazuje grants**, gdyż grant wskazuje installation digest. Aktualny zbiór independently signed grants jest w protected owner-managed directory, odczytywanej pod leases; usunięty/revoked grant nie autoryzuje write. Nie istnieje cykl installation→grant→installation ani namespace→installation→namespace.

Grant zawiera rzeczywisty signer pin, role, exact installation, campaign, source scope, approved view/task, assignment scope, operations i UTC `[not_before,not_after)` bez heurystyki. Source scope jest SHA256(`BDB-NF02-P0-SOURCE-SCOPE/1` + NUL + CJSON `{repository_id,git_object_algorithm,git_commit_object_id,git_tree_object_id,source_manifest_raw_ref}`). `repository_authority_digest` identyfikuje repo w namespace: SHA256(`BDB-NF02-P0-REPOSITORY/1` + NUL + CJSON `{namespace_authority_digest,repository_id}`); sam nie ustanawia prawa. `approved_view_digest` jest RawDigest transport bytes SOURCE_MANIFEST/1. View/task digest: SHA256(`BDB-NF02-P0-VIEW-TASK/1` + NUL + CJSON `{source_scope_digest,approved_view_digest,task_raw_ref}`). Assignment scope: SHA256(`BDB-NF02-P0-ASSIGNMENT-SCOPE/1` + NUL + CJSON `{assignment_ref,slot_id,auditor_certificate_sha256}`). Te wartości są porównywane z independently signed grants; własne wyliczenie caller nie jest uprawnieniem.

Owner może zatwierdzić przygotowane dokładne future assignment bytes/grants poza historią; nie nadaje to obiektowi prior acceptance. CREATE i kolejne assignment operations wymagają exact nonnull assignment scope; bootstrap wymaga source/view/task i null assignment scope. Audytor jest wskazany w owner-approved grant dla tego exact assignment; nie wybiera go dowolnie Coordinator. Role matrix jest stała: COORDINATOR → initialize/create/bind/start/confirm delivery/ingest evidence/accept result/release package; AUDITOR → ACK_DELIVERY/RETURN_AUDIT; OWNER_RECOVERY → ABORT_ATTEMPT. Każda rola wymaga właściwego signer pin. Owner, qualifier, Coordinator i audytor używają czterech różnych certyfikatów; OWNER_RECOVERY może być osobno uprawnionym owner. Grant z inną rolą, campaign, source, task, slot/assignment lub operation zostaje odrzucony.

Mode PRODUCTION wymaga signed Q1, Q2 i RQ oraz qualified installation. Mode QUALIFICATION_ONLY wymaga Q1, Q2 oraz independently signed czasowego mandate dla exact code/namespace; RQ jeszcze nie istnieje. Tylko rzeczywista authority może zainstalować ten mode. Caller flag nie zmienia mode. Qualification namespace nie jest produkcyjną historią, wynik/receipt nie mogą być przeniesione między nimi. Qualified production installation powstaje po RQ i wymaga nowej pustej campaign. Q1/Q2/RQ, signatures i grants są zewnętrznymi immutable records, nigdy self-accepting facts tej kampanii.

### M03 — Bytes, digests, refs i zamknięte gramatyki

CJSON: UTF-8 bez BOM, ASCII schema keys sortowane rosnąco, bez whitespace/LF w preimage, poprawny Unicode bez lone surrogates, bez duplicate keys/float/NaN/Infinity/negative-zero, integers w zakresie ±(2^53−1). Nie normalizuje evidence strings. `.json` transport to CJSON + LF; raw hash obejmuje LF. Żaden pretty-printed proposal file nie jest automatycznie instance canonical bytes. `BDB_CJSON_1` to descriptor profilu transportu w pakiecie; algorytm zachowuje nazwę `BDB-CJSON-1`.

RawDigest = SHA256(exact bytes). ObjectDigest = SHA256(ASCII `BDB2/` + exact registry kind + `/` + version + NUL + CJSON(body)). `commit_hash` to ObjectDigest(`commit_body`, `3`, body), zgodnie z istniejącym Store; nie wprowadza nowego hash algorithm. TypedRef zawiera exact kind/version/ObjectDigest, `BDB-OBJECT-DIGEST-1`, logical ID oraz `{schema_id,raw_digest}` exact frozen schema bytes. Field target i prior/content class wynikają z Registry/modelu, a nie caller `ref_class`. Wrong digest type, wrong schema revision lub unknown kind/version odmowa.

Canonical `object_id` ma exact `<wire-kind>_<uuidv4-lowercase>`, logical_id TypedRef jest równy object_id jego targetu; command_id jest równy object_id CommandEnvelope. To jawna nowa reprezentacja command/3, bez aliasu historycznego `command_...`. UUID nie ustanawia authority. Campaign ID równa się object_id Genesis. Finding ID wewnątrz raw payload jest opaque identifier, nie canonical finding kind/ref ani kwalifikowane finding.

Wszystkie bodies/nested objects są closed. Set-like fields mają duplicate rejection i sort: registry keys/schema bindings/profiles według exact ID; file/member/path lists według exact ASCII transport path; findings według finding_id; basis/result refs według `(kind,logical_id,revision_digest)`; source entries i finding.source_paths według raw UTF-8 source_path; notes zachowują kolejność. Unikatowość ID/path sprawdza predykat nawet jeśli dwa wpisy różnią się innymi polami. Wyjątki: immutable_object_refs to canonical Kahn sequence (M04), events to sequence M05, nie unordered set. Nie ma zewnętrznego network schema fetch, pliku wybieranego przez caller ani dynamicznego walidatora.

### M04 — Jeden content DAG i prior history

Każdy material ref musi rozwiązać exact immutable target, version/schema/digest/logical ID/class. Prior target był accepted w tej samej campaign/model/namespace przed input head; obecność w Store/proposed refs nie jest prior acceptance. Wyjątki content: root/source/genesis w first initialization, attempt w tym samym CREATE i command/facts w ich content closure. Spec/policy/schema context pierwszego commitu musi być exact approved external pins. Później wszystkie governing pins są wcześniejsze i stałe.

Nowe content dependencies nie mogą być self/future/cyclic/duplicate. Kahn sort wybiera najmniejsze `(kind,logical_id_or_empty,revision_digest)` z zero-indegree nodes. Command ma zależności do proposed refs; może wystąpić po nich. Receipt powstaje po acceptance i nigdy nie wchodzi do własnego accepting preimage. AUTHORIZATION_TRACE zawiera już obliczony command_ref i raw signature/context; dopiero CommitBody wskazuje trace RawRef. Command nie wskazuje trace lub własnej signature. Body/raw manifest nie zawiera własnego final hash, accepting head/commit/event ani post-cut. Missing raw/ref blokuje reader/replay/new acceptance, bez backfill lub „naprawy” innymi bajtami.

HistoryCut jest closed inline value: exact input accepted head oraz governing policy/spec/schema registry/source refs. To nie canonical HistoryCut kind ani hash/alias. Zgadza się z prawdziwym input head/context, nie future/post-head. Chronologia liczy `(commit_seq,event_ordinal)`, a wymagane „później” w M09–M14 wymaga większego commit_seq. Każdy command.expected_parent, body cut, campaign/attempt/source/slot i event input muszą zgadzać się z rzeczywistą historią; nie wystarczy sprawdzenie samej FSM edge.

### M05 — Wszystkie dostępne komendy i events

| Komenda | Exact nowe domain objects | Dokładne events / warunek |
| --- | --- | --- |
| INITIALIZE_P0_FROM_APPROVED_GIT | 6 roots z §3 + SourceSnapshot + Genesis, każdy raz | EMPTY_HISTORY, seq=1; P0FactAccepted w kolejności tych facts w Kahn content closure; M02/M07 |
| CREATE_ASSIGNMENT | Attempt + Assignment | Prior Genesis albo exact prior ABORTED, M08/M15; dwa P0FactAccepted w content order |
| BIND_PACKAGE | Binding | ASSIGNED; jedno P0FactAccepted, M09 |
| START_ATTEMPT | Brak domain objects | BOUND; dokładnie jeden P0AttemptStarted z prior Attempt/Assignment/Binding, M10 |
| CONFIRM_DELIVERY | Delivery | STARTED, trusted job SENT i real signed ACK; jedno P0FactAccepted, M11 |
| INGEST_EVIDENCE | Evidence | DELIVERED; retained original ZIP/signed return; jedno P0FactAccepted, M12 |
| ACCEPT_RESULT | Result | Prior EVIDENCE_ACCEPTED; jedno P0FactAccepted, M13 |
| ABORT_ATTEMPT | Abort | Jeden z 5 nonterminal states; owner recovery grant; jedno P0FactAccepted, M15 |

W każdej operacji nowe objects są dokładnie powyższym zbiorem; receipt.result_object_refs dokładnie tymi objects w sort order M03; events dokładnie powyższą sequence. `basis_refs` to sorted unique union wszystkich PRIOR references użytych przez nowe bodies i events, włącznie z ich cuts; przy bootstrap EMPTY_HISTORY nie ma prior refs. Pinned/SAME_CONTENT refs nie stają się prior przez dopisanie do basis. Predykat pełnego join rozwiązuje również cały wcześniejszy assignment context. Podpis komendy to detached CMS/SHA-256 nad ASCII `BDB_NF02_P0_COMMAND/1` + NUL + CJSON całego CommandEnvelope/3, który już zawiera mode/namespace/installation/grant. Context, actor, command digest, proposed refs i events CommitBody muszą być byte-equal do accepted signed CommandEnvelope, previous_head = expected_parent; commit_seq poprzednika +1. Command musi być w closure i nowy. Żadna publiczna droga generic command/event/generator nie omija tej tabeli.

### M06 — Siedem finite profiles i stałe limity

`BDB_CJSON_1`, `P0_AUTHORIZATION_V1`, `P0_BOOTSTRAP_SOURCE_V1`, `P0_PACKAGE_TRANSPORT_V1`, `P0_RESULT_TRANSPORT_V1`, `P0_EXECUTION_ISOLATION_V1`, `P0_HISTORY_RECOVERY_V1`. Exact descriptor bytes/rules/quotas są w `profiles/`; ProfileRef.revision_digest = RawDigest exact frozen descriptor bytes, zgodnie z istniejącym profile-pinning adapterem; to nie ObjectDigest canonical contract. Installation/freeze binds descriptor raw bytes i ten digest. Profile pin nie wskazuje ad hoc pluginu, producer-podpisanego „bezpiecznego profilu” ani all-registered contract set.

Package/source ZIP: 64 MiB raw i total expanded, ≤2048 entries, ≤32 MiB/entry. Result ZIP: 32 MiB raw/expanded, ≤2048 entries, ≤16 MiB/entry. JSON ≤2 MiB i depth ≤32, przed schema/CJSON; signed governance/trace/command/commit także ≤2 MiB, code assets mają osobne exact manifest sizes. Arrays/strings dodatkowo ograniczają schemas; raport obecny, payload findings ≤4096, notes ≤256. Manifest membership + task/source metadata musi mieścić się w quota, nawet gdy schema dopuszcza więcej entries niż końcowy ZIP. Raw read jest bounded przed allocation/decompression; limity signed CMS/cert inputs ≤2 MiB. Unsupported odmowa, nie auto-konwersja.

ZIP jest ZIP_STORED, bez szyfrowania, symlinks, dirs, extra/comment/hidden trailing records; entries sortowane po safe ASCII POSIX path. Stałe timestamp 1980-01-01 00:00:00, local/central flags=0, create_system=3, create_version=20, extract_version=20, external_attr=(0o100644<<16), internal_attr=0, volume=0, reserved=0; bez ZIP64 i data descriptors, CRC/size local i central równe actual bytes, bez gaps/records poza zadeklarowaną strukturą; całe raw bytes są identity niezależnie od semantic equality. Duplicate/case-fold/NFC/Win32 reserved-name/path collision, dot segments, absolute/drive/UNC/backslash/NUL/colon, traversal i brak/extra member powodują odmowę. Original bytes nie są naprawiane/repackowane. Member MIME wyznacza exact profile mapping: .json→application/json, .md→text/markdown, .txt/.log→text/plain, .png→image/png, pozostałe→application/octet-stream. Required raport to retained .md lub .txt i poprawny UTF-8 text; task także UTF-8. Source blobs mogą być binarne. Report rendering jest inert/escaped, bez uruchamiania embedded HTML/script. Package i result parsuje ten sam strict bounded adapter, bez wykonywania zawartości.

### M07 — Legalny approved-Git-only bootstrap

Przed genesis rzeczywisty owner zatwierdza repository identity, actual algorithm/commit/tree, pełny **przydzielony** source view i raw task przez independent grant source/view/task. Resolver używa rzeczywistego repository i Git object plumbing, weryfikuje oddzielnie commit type, tree type i blob bytes/modes. `HEAD` i `HEAD^{tree}` nie są jednym polem mapowanym dwa razy. OIDs muszą odpowiadać sha1/sha256 repo. Nie checkoutuje/nie wykonuje hooks/skryptów źródła w Coordinator.

SOURCE_MANIFEST/1 zachowuje exact UTF-8 POSIX `source_path`, Git blob ID/mode, raw digest/length i deterministic safe transport path `source/<8-digit-index>.bin`, index od 1 wg UTF-8 path sort. Puste/absolute/parent/NUL/ambiguous duplicate paths odrzuca; unsupported non-UTF8 Git names, selected symlink/submodule/LFS pointer lub nierozwiązany content odrzuca. Właściciel zatwierdza view przed bootstrap; Coordinator nie wybiera mniejszej części. Source archive zawiera `MANIFEST.json` równy exact retained SOURCE_MANIFEST/1 transport bytes i dokładnie jego entries; manifest nie zawiera własnego final raw hash. View jest kompletny dla zatwierdzonego task scope, nie deklarowany COMPLETE_SOURCE całego repo. Ograniczenie scope jest widoczne audytorowi i w raporcie.

Installation.external_schema_root_sha256 jest RawDigest dokładnych frozen bytes `schemas/canonical/schema_registry__3.schema.json`. Loader otrzymuje ten schema i jego offline dependencies z independently signed manifest/installation, zanim przyjmie canonical SchemaRegistry; cały zbiór 43 schema bytes również mają exact installed readback. External installed schema root waliduje Registry/SchemaRegistry bez samoustanowienia authority. Osiem pins: Registry, SchemaRegistry, policy, spec, trust, serialization profile, source profile, namespace authority digest. Root/body refs i schema/profile/descriptor actual readback odpowiadają independent freeze/installation. INITIALIZE atomowo przyjmuje dokładnie osiem objects, raw inputs, command/trace/commit/receipt/head przy EMPTY_HISTORY. Genesis.task_raw_ref utrwala exact raw zadanie już sprawdzone z grant view/task digest; Assignment.task_raw_ref musi być identyczny. Po genesis initializer i zmiana source/roots/task/mode są odrzucane. Nie ma legacy selection/admission, synthetic predecessor, upgrade, copied authority ani stage run graph.

### M08 — Assignment i odpowiedni poziom izolacji

Jedna campaign ma jeden immutable source/task i jeden result slot `EXTERNAL_AUDIT_RESULT`. Attempt i Assignment powstają w CREATE atomowo; assignment wskazuje same-commit Attempt i prior source/genesis. Attempt/Assignment cuts odnoszą się do input head. Owner-approved grants wiążą exact assignment/auditor/view/task; member list zawiera dokładnie source entries i transport metadata/task wymagane M07/M09. Jeden assignment na attempt, jeden aktywny attempt. Nie ma innych lanes/slots ani równoległego wykluczającego kontekstu.

Audytor otrzymuje tylko owner-approved fixed view/task i package metadata potrzebne do provenance. Może mieć prior knowledge; nie twierdzimy BLIND/RESET/zero knowledge. Kwalifikacja rzeczywiście sprawdza external host, transport i jego brak dostępu do root/code/history/vault, prywatnych governance keys oraz brak result code execution. Deklaracja audytora o izolacji nie dowodzi OS boundary. Jeśli task wymaga blind-audit assurance lub repo nie spełnia supported source/transport limits, ten model odmawia takiego zastosowania.

### M09 — Binding dokładnych przydzielonych bajtów

Po prior Assignment i current grant builder przygotowuje bounded fixed ZIP zawierający `MANIFEST.json` (PACKAGE_MANIFEST/1), `SOURCE_MANIFEST.json`, `TASK.md` i dokładne source view members. `members` manifestu obejmuje wszystkie poza samym MANIFEST.json; Assignment.input_members obejmuje source manifest/task/source bytes, bez przyszłego package manifest/hash. Scope wiąże campaign, attempt, assignment, source, slot i assignment_cut. Member SHA/length/profile/content porównuje się z assignment/source/raw task oraz rzeczywistym odczytem. Brak semantic checksum alias, dowolnego repack, filename/mtime identity.

Raw ZIP i wymagane raw source/task są durable w dotychczasowym vault/Store przed canonical acceptance. B/3 jest pojedynczy dla tego assignment; binding_cut = aktualny input cut. Retention jest atomic z jego objects/commit/receipt/head. Nielegalny/konkurencyjny inny binding nie dodaje raw ani historii. Same operation retry nie tworzy drugiego bindingu.

### M10 — Osobny, późniejszy STARTED

START jest nowym signed command po commitcie B/3. Wskazuje wcześniejsze accepted Assignment, Attempt i Binding; source/auditor/slot/state/cut zgodne. Nie zawiera nowego Binding, Delivery, Evidence ani Result. Jedyny P0AttemptStarted event ustanawia STARTED w tym exact attempt. Generic/legacy AttemptStarted, same-commit B+START, stan inny niż BOUND, powtórny event pod nowym command ID lub revoked grant odrzuca bez append. START oznacza autoryzowany początek attempt; nie dowodzi jeszcze wydania bytes lub rzeczywistego audytu.

### M11 — Rzeczywista dostawa, ACK i crash-safe outbox

RELEASE_PACKAGE jest jedyną operacją I/O obok ośmiu komend. Korzysta z tego samego Store writer serialization, retained bound bytes i current grants. Jest dozwolona tylko w STARTED lub DELIVERED tego attempt; nie po Evidence/Result/Abort. Destination i transport to qualified installed configuration dla exact audytora; caller nie dostarcza trusted sink/destination ani nie ustawia SENT. Release ID = SHA256(`BDB-NF02-P0-RELEASE/1` + NUL + CJSON `{campaign_id,assignment_ref,binding_ref,start_event,package_raw_ref,auditor_certificate_sha256}`). Nie obejmuje status/cut/attempting process, więc retry wydaje identyczne bytes pod tym samym ID.

RELEASE_JOB/1 jest chronionym operacyjnym sidecar w tym samym Store, nie drugim head ani authority. Pod writer lock/leases sprawdza current cut/state/grant/code/raw, utrwala PREPARED, przed rzeczywistym I/O ponownie weryfikuje authority i wydaje exact bytes. SENT ustawia tylko qualified transport po potwierdzonym zakończeniu wysyłki, ACKNOWLEDGED po retained verified ACK. Żądanie wydania podpisuje Coordinator CMS nad domain `BDB_P0_RELEASE_REQUEST/1`, model/mode/namespace/installation/grant i CJSON job z current authorized_cut/status PREPARED. Signature/context pozostają protected operational evidence; status nie jest podpisem producenta wyniku.

Crash przed wysyłką, po wysyłce lub ACK loss może wymagać retransmisji **tych samych bajtów** pod tym samym ID, po nowym sprawdzeniu current rights/state. Nie obiecujemy exactly-once sieci. Already released bytes nie da się cofnąć po revocation; dalsze wydanie/acceptance zostaje odmówione. Delivery/1 wymaga wcześniejszego START, protected job SENT oraz actual auditor CMS ACK nad transport bytes DELIVERY_ACK/1 z exact scope/B/start/package/release ID. ACK nie nadaje authority audytorowi; current AUDITOR grant musi już istnieć. CONFIRM_DELIVERY jest późniejszym committem i daje DELIVERED, jedno acknowledged Delivery. Same ACK read retry nie emituje nowego faktu.

### M12 — Rzeczywisty audyt i admission evidence

Audytor wykonuje zatwierdzone zadanie na dostarczonym widoku i zwraca oryginalny fixed ZIP z `MANIFEST.json` RESULT_MANIFEST/1 oraz wszystkimi declared reports/evidence/logs. Manifest nie zawiera finalnego ZIP hash ani własnego member hash. Jawny payload NORMALIZED_RESULT/1 ma findings/report_paths/evidence_paths/log_paths/notes; findings zachowują niekwalifikowany tekst. source_paths znajdują się w original SOURCE_MANIFEST, output paths w result members; każdy required raport istnieje. Brak/extra/ambiguous path, nieznany profil/schemat lub quota violation powoduje odmowę. Bez ładowania scripts, HTML active content lub pickle z wyniku.

Audytor osobno podpisuje exact AUDIT_RETURN/1, zawierający exact ZIP RawRef, scope/B/Delivery i własny certificate pin. Jego execution_declaration jest odpowiedzialną deklaracją uprawnionego producenta, nie samowystawioną qualification ani dowodem truth. Pierwsze rzeczywiste wykonanie w RQ wymaga niezależnej obserwacji/trace wykonania, a nie fixture. Current grant musi autoryzować RETURN_AUDIT tego exact assignment/slot. Coordinator osobno autoryzuje signed INGEST_EVIDENCE command. Spoofed/root-owner-as-auditor/same-certificate/unknown/revoked producer zostaje odrzucony.

E/4 wymaga wcześniejszego B, START i acknowledged Delivery, current DELIVERED, exact input cut i wszystkich joins M14. ZIP/return/CMS są w całości snapshotowane i zachowane przed canonical acceptance, potem strict-validated/rederived; raw digest/length liczone z oryginalnego snapshotu. E jest unique per slot/attempt. Samo otrzymanie poprawnego ZIP nie tworzy E, R ani praw.

### M13 — Późniejszy accepted result

ACCEPT_RESULT to nowy signed command w późniejszym commitcie niż E/4. Input cut i current rights ponownie sprawdzone. Writer czyta original retained ZIP i return/CMS/assignment/package, weryfikuje E i jego acceptance context, normalizuje deterministycznie payload oraz porównuje exact CJSON proposed result_payload. R/4 wskazuje wyłącznie prior E/4; context/slot/source wynikają z jego pełnego chain, bez caller override. Stan RESULT_ACCEPTED jest terminalny dla campaign/task. Brak original raw, payload substitution, same-commit E+R lub drugi wynik innego digest w tym slocie powoduje odmowę. Read-only raport eksponuje accepted provenance i niekwalifikowane findings; brak automatycznego PASS/Completion.

### M14 — Pełne joins i zakaz laundering

Wszystkie refs rozwiązuje się po exact identity, nie „current by logical ID”. Campaign/model/namespace/mode są te same dla genesis/attempt/assignment/B/start/Delivery/E/R/command/commit/receipt/raw auth contexts. Source/view/task/auditor oraz jedyny slot są identyczne z independently approved assignment. Każdy prior target ma history position < input head; wskazany START event należy do dokładnego earlier commit i tego attempt. Kolejność: Genesis → Assignment → B → **later START → later Delivery → later E → later R**. Attempt i Assignment mogą być w jednym CREATE; root/source/genesis w jednym legal initialize. Innych wyjątów chronologii nie ma.

Cuts każdego historical fact porównuje się z jego **własnym** zapisanym input parent/context, nie dzisiejszym head. Nowy write używa aktualnego input cut. Chronologia przez aliases/events/generator/proposed refs, historical fixture grant, wstawienie „wcześniejszego” E do tego samego commitu lub kopiowanie correct bytes do innej campaign/slot/attempt/source odrzucane. AUTHORIZATION_TRACE musi odpowiadać command CMS, signed grant/installation/root, pins i czasowi rzeczywistej weryfikacji przy acceptance; trace body sam nie jest authority.

### M15 — Abort i bezpieczny nowy attempt

Wyłącznie independently authorized OWNER_RECOVERY może przyjąć ABORT w ASSIGNED/BOUND/STARTED/DELIVERED/EVIDENCE_ACCEPTED, ze zgodnym current cut/from_state/attempt/assignment. Powód z closed enum. Utrata praw audytora nie daje mu prawa abort. Abort kończy attempt, blokuje jego dalsze delivery/evidence/result i zachowuje wszystkie raw/facts/receipt, także E. Nie edytuje starszego stanu.

Nowy CREATE po ABORT wymaga nowego Attempt/Assignment IDs i independently approved grants dla exact new assignment, prior retry_of_attempt i prior abort_basis dla tego samego bezpośredniego poprzednika. Null refs tylko dla initial attempt, oba ustawione dla retry. Source/task/slot bez zmian; audytor może zmienić się wyłącznie przez nowy owner-approved grant. Poprzedni package/result nie staje się bindingiem/evidence nowego attempt. Brak retry po RESULT_ACCEPTED oraz wielu active attempts. Resume jest replayem tych samych facts, nie dopisywaniem checkpoint authority.

### M16 — Jeden writer, atomowość, retry i konflikt

Store pozostaje jedynym writerem/head. Staging/raw/immutable objects/command/trace/commit/receipt/head CAS tworzą jedną atomic durable acceptance. Walidacja jest przed mutation; protected operation admission nielegalnych raw także nie pozostawia accepted raw rows. In-memory parsing/rejection diagnostics mogą istnieć poza historią; nie wolno mutować campaign files/receipt/vault. Snapshot command/events/raw od caller jest deep immutable po weryfikacji; generator nie może zmienić później zapisanych bytes.

Pod writer lock ponownie weryfikuje się expected head, legal state/joins i independently leased current authority tuż przed COMMIT. Concurrent requests: jeden winner, exact same command bytes/ID mogą dostać jego oryginalny receipt; różne bytes przy tym samym ID = konflikt, competing non-identical binding/evidence/result = konflikt bez mutacji. Operation retry ze świeżym command ID nie dodaje nowego fact w terminalnym state. Authenticated exact command retry wymaga current authority dla tego scope i odczytu original retained context/raw; zwraca original receipt, nie zmienia head ani cuts. Nieznana/błędna utrwalona integralność fail-closed.

### M17 — Trwałość, replay i audit auth context

Raw source/task/package/result, ACK/return, wszystkie CMS signatures i signed authority inputs użyte przy write są retained exact before acceptance. TraceRawRef w CommitBody wiąże command CMS, root, installation/grant bytes/signatures, actual signer i verified_at UTC. Łańcuch przetwarza się przed commit hash, bez signature/hash cycle. Read/replay sprawdza commit chain/CAS sequence, objects/refs/schema/profile/raw digest/length, historical command signature/valid-at-acceptance grant/context/cuts/events/receipts i rederivation wyników. Grant/cert expiry dziś nie przepisuje accepted history; nowy write/delivery/retry wymaga current rights. Rzeczywisty protected zegar/environment jest częścią RQ; trace timestamp nie daje niezależnego timestamping ani host-rollback guarantee.

Real new-process crash/restart tests obejmują raw staging/write/readback, object insertion, command/trace/commit, receipt, head CAS i flush/COMMIT boundaries. Po crash widoczny cały accepted transaction albo żaden jego nowy fact/raw/receipt/head. Outbox M11 ma osobną uczciwą at-least-once I/O semantykę i recovery bez słabszego canonical writer. Missing/corrupt accepted raw lub schemas blokuje obsługę; nie regeneruje historycznych ZIP/dowodów.

### M18 — Fresh Q1, Q2, RQ i aktywacja

Owner model decision musi wskazać **actual raw SHA256 CANDIDATE_MANIFEST.json, oba set digests i raw SHA256 DEPENDENCY_GRAPH.json**, oraz jawnie zaakceptować zmiany zakresu/bootstrapa, nonblind/source/task limits, result semantics, at-least-once delivery i brak full-host rollback guarantee. Bez tej decyzji nie rozpoczyna się następny długi etap formalizacji. Zatwierdzenie scope nie jest Q1/Q2/RQ ani grantem.

Manifest przekazany właścicielowi wiąże proponowaną normę/machine definitions i narzędzia kontroli, **nie zawiera jeszcze wykonanej kwalifikacji, finalnego runtime code ani materializowanego pełnego Golden evidence**. W kolejnym autoryzowanym etapie każda rodzina matrix musi zostać rozwinięta do wszystkich konkretnych supported branches/positive/negative cases, z independently checked expected bytes/digests/decisions. Q1 readback/final audit i Q2 review wiążą exact retained vector/reference-procedure inputs i outputs jako external qualification evidence. Żaden expected result nie może pochodzić wyłącznie z aktualnie badanej implementacji. Normative model/schemas/profiles pozostają tymi zatwierdzonymi bajtami; ich zmiana albo zmiana candidate membership wymaga nowej exact decyzji owner przed freeze, nie samodzielnego rozszerzenia scope. To brakująca praca kwalifikacji, a nie gotowy Q1 PASS lub kolejny model.

Q1 autor: cały exact 18/7/43 package, wszystkie M01–M18 i 11 rodzin Q1 z matrix; komplet body/Registry/schema/profile parity, każda union/branch, wszystkie required Golden/negative cases i dwa niezależnie sprawdzalne reference procedures primitives; oba final set digests, immutable file readback i retained końcowy audit bez niewyjaśnionych mismatches. Author record jest zewnętrzny, `independent_assurance=false`; nie autoryzuje runtime.

Q2: rzeczywiście niezależny uprawniony reviewer ocenia dokładnie ten sam manifest/scope i wszystkie 6 rodzin Q2, rozstrzyga material findings, potwierdza zgodność nowych granic i podpisuje review/freeze; owner podpisuje exact norm/limit assurance decision. Historyczny full-model author PASS albo własny lokalny pytest nie zastępuje tego etapu. Unresolved mandatory safety finding blokuje freeze. Q2 nie jest kwalifikacją runtime.

RQ: independently authorized qualifier sprawdza **wszystkie 32 rodziny RQ**, exact final deployed implementation/dependencies/code bytes/OS/service SID/ACL/cert/principal/transport/auditor environment oraz zachowane mandatory subprocess/crash/race/replay/negative tests na qualified normative inputs. Dowód zawiera real external execution/report/ACK/return ZIP i accepted trace w qualification namespace. Nie jest to callback/fixture/symulowana MachineAuthority. Same wersje/hash code/dependency i te same predicates/Store stosuje qualification mode i produkcja; środowiskowe różnice wymagają dopuszczonego przez qualifier bound production evidence, nie deklaracji równoważności.

Q1+Q2 poprzedzają genuine owner+qualifier time-scoped QUALIFICATION_ONLY mandate. Dzięki temu RQ może uzyskać prawdziwy legalny wynik przed produkcyjną aktywacją **bez błędnego koła „RQ wymaga produkcji przed RQ”**. Po positive RQ owner instaluje signed PRODUCTION record; importer ponownie weryfikuje pełne qualification/evidence/implementation/authority chain i otwiera tylko nową pustą produkcyjną campaign. Same PASS strings, certificate hashes, ROOT schema, owner-typed wiadomość lub local test nie spełniają gate. Każdy mandatory przypadek pokrywa wszystkie applicable operations/entry points; „32 rodziny” nie jest sztucznym licznikiem tylko 32 przykładów. Większa liczba konkretnych vectors może wynikać z pełnego branch closure, ale nie z 131 wykluczonych kontraktów.

## 6. Ryzyka, ograniczenia i ich kontrola

| Ryzyko | Kontrola / ujawniony limit | Skutek dla decyzji |
| --- | --- | --- |
| Ukryta zależność od pełnej normy | Self-contained bodies/targets/profiles/M01–M18, brak generic domains; closed graph i independent Q1/Q2 review | Gdy qualifier wykaże konieczność wykluczonego obowiązku, brak activation; owner wraca do decyzji, bez samodzielnych następnych modeli. |
| Bootstrap without legacy/source assurance | New owner-approved Git snapshot, actual resolver/blob manifest, complete assigned view, no assurance transfer | Owner zatwierdza nowy rodzaj aplikacji; nie udajemy starego legalnego bootstrap. |
| Nonblind audyt / prior knowledge | Wyraźny poziom wiedzy; fixed view i external write boundary | Wynik nie nadaje blind/independent reasoning assurance; task wymagający go poza zakresem. |
| Producer/Coordinator uzurpuje root | Non-admin service, independently managed root/grants, actual CMS + key/person separation | Obecne adaptery wymagają poprawnej ACL/grants integracji, nie tylko schema update. |
| Dostawa/komunikacja nie jest exactly-once | Stable release ID, retained bytes/outbox, actual signed ACK, at-least-once retry | Already delivered source cannot be recalled; owner akceptuje ekspozycję. |
| Dowód podpisanego audytora ≠ prawda findings | Real observed first qualification run, report+signed return+provenance; brak promotion | Nie reklamować jako full automated audit assurance lub Completion PASS. |
| Nowa gramatyka nie pokrywa kodu checkpointu | Explicit versions + named implementation delta w §7 | 290 dawnych lokalnych tests nie daje P0 model PASS; final affected tests/qualification muszą wiązać nowy kod. |
| Full-host/root rollback | Brak external monotonic anchor; actual protected local replay | Owner musi jawnie zaakceptować ten limit; historia chroni przed scoped caller/executor, nie zaufanym OS admin. |
| Inna implementacja qualification/production | Same Store/path/code hashes, model/pins; RQ binds real deployment/principal environment | Production nie może korzystać z fixture/factory injection/słabszej konfiguracji. |
| Unsupported source/output sizes/types | Exact supported types i quotas, odmowa zamiast lossy repair | Mniejsza użyteczność pierwszej wersji; powiększanie limitów wymaga norm/qualification zmienionych bytes. |

Nie ustanowiono real root, signer, qualifier, grant lub execution environment; nie wygenerowano kwalifikacji. Pakiet external schemas opisuje wymagane prawdziwe wejścia, nie wystawia ich.

## 7. Rzeczywista delta implementacyjna i nakład

Checkpoint dodatnich komponentów: `7508d4fd5d0dc3e2f3cfa3fe5e07834c9e3b8298`; poprawka commit/tree: `4e4554dd6ea955f8669e63ea8b6b982200691396`. Ten projekt **nie zmienia produkcyjnych plików**. Obecny protokół B/1→E/2→R/2 jest inactive i nie implementuje nowych bodies/transport/ACL/outbox/modes przez relabel.

| Istniejący komponent | Reuse | Konkretny brak dla zatwierdzonego modelu P0 |
| --- | --- | --- |
| `history/store.py`, `history/closure.py`, `history/raw_artifacts.py` | Jeden SQL writer/head/CAS, content DAG, raw retention, receipt durability | Finite model dispatch i new command/trace/receipt fields; protected outbox w tym samym Store; actual process recovery/replay tests |
| `history/installation_authority.py` | Real read-only CMS/OS root, certificate pins, ACL/reparse/readback/leases; brak lokalnego issuera | Nowe 9 external schemas, independent grant directory i revocation, non-admin service SID history write ACL, root/code read-only, Q1/Q2/RQ/modes/mandate oraz historical auth trace |
| `history/successor_wire.py` | Existing ObjectDigest/CJSON/ref/codecs i schema call boundary | Explicit version/schema raw-ref/ID shapes /3–/4, exact 18/7/43 pins; zachowane readers wcześniejszej linii |
| `history/nf02_protocol.py` | Prior resolution/context/raw, chronology/predicate integration ze Store | Finite source/assignment/retry/event/operations, root precedence, exact eight pins; no legacy/base graph fallback |
| `workflow/nf02_transport.py`, source resolver | Strict ZIP/JSON, member validation/quotas i actual separate Git commit/tree | New source view manifest/path mapping, package/result wire schemas/profiles; signed ACK/return payload equality |
| `workflow/nf02_intake.py`, `workflow/inbox.py`, Coordinator/Registry/SchemaRegistry | E1 inbox/command path, single accept boundary, signing/normalizer integration | Scoped initializer/CREATE/abort, protected qualified transport/outbox i real audit handoff; qualification mode bez słabszego writera |
| Existing standalone builder i tests | Packaging w jednej aplikacji i negative blocked-import checks | Final installed limited model assets/code environment, new mandatory vectors/entry-point coverage i actual real runtime qualification |

To siedem spójnych obszarów integracji, nie siedem szacowanych jednodniowych zadań. Największy nowy koszt to legalny Git-only bootstrap, nieadmin service ACL/independent grants oraz real transport/ACK/outbox/return and qualification modes. Przy pełnej linii authority/OS/real delivery i real RQ nadal byłyby potrzebne; obecny kod ich rzeczywistej kwalifikacji nie ma. Odrębny model dodaje finite codec/scope/bootstrapping review, ale usuwa generic checkpoint consumers, source/legacy/build assurance graph, multidomain stage/lane/spec/exposure/knowledge artifacts, finding adjudication/Completion/STOP/release dependencies dla tego milestone.

| Mierzony zakres / praca | Pełny obecny R5.4.2 | Odrębny P0 | Ocena kosztu |
| --- | --- | --- | --- |
| Canonical Q1 surface | 131 | 18 (**−86,3%**) | Rzeczywiste usunięcie 113 kinds wraz z dispatch i consumers |
| Profile contracts | 127 | 7 (**−94,5%**) | Profiles scalają tylko jawne konieczne predicates, nie przechowują ukrytych 127 variants |
| Machine schema surface | 277 | 43 (**−84,5%**) | P0 licznik obejmuje także 9 governance i 9 wire; pełny licznik z poprzedniego inventory miał inny podział (131+127+19), więc nie jest równoważnością kosztu per schema. |
| Fresh author + independent semantic qualification | Wszystkie 131 i ich profile/raw/body/Golden parity | Wszystkie 18/7/43 i każde M01–M18/Q1/Q2 | Znacznie mniejsza powierzchnia review; brak automatycznego PASS ze starych rekordów |
| Core Store/CJSON/CMS/raw/chronology/authority | Obowiązkowe | Te same obowiązkowe guarantees | Zysk nie pochodzi z usunięcia bezpieczeństwa |
| Bootstrap/domain integration | Legacy/source/build/general execution assurance i generic retry domains | Nowy bounded source + 8 op FSM + finite abort retry | Nowy koszt wzoru bootstrap, dużo mniej consumers; wymaga zatwierdzenia zmiany produktu |
| Real external identity/OS/isolation/transport/execution | Nadal brak real authority i kwalifikacji | Nadal wymagane w Q2/RQ | Stały zewnętrzny critical path; norm scope go nie skraca automatycznie |
| Qualification/production activation | Fresh Q1/Q2 i applicable N4–N9, full-model pins | Q1/Q2/RQ, same-code qualification mandate i production install | Brak ukrycia obowiązków runtime przez zmianę nazw; 32 rodzin RQ odpowiada bezpieczeństwu pierwszego wyniku |
| Dalszy pełny lifecycle | Zgodny z pełną linią po jej kwalifikacji | Poza tym modelem | Brak obietnicy oszczędności przy późniejszej implementacji całego E1–E6 |

**Ocena:** model powinien istotnie skrócić **przegląd normatywny i implementację zależnych domains potrzebnych pierwszemu wynikowi**. Closure nie wraca do 131; dodatkowe formy zewnętrzne są policzone. Nie ma podstaw, aby uznać go za bardziej kosztowny od pełnego modelu dla tego ograniczonego milestone. Nie podano fikcyjnych godzin/proporcji czasu na podstawie liczby plików: brak zmierzonej wydajności semantic review i terminów rzeczywistych owner/qualifier/auditor. Jeśli dostępność tych osób jest wąskim gardłem, sama redukcja contracts nie przyspieszy kalendarza. Dla pełnego lifecycle utrzymanie dwóch jawnie osobnych norm ma dodatkowy koszt; P0 nie rozwiązuje przyszłej migracji.

## 8. Lokalne sprawdzenie, istniejące dowody i brakujące kwalifikacje

Lokalne schema/graph checks w [LOCAL_VALIDATION.json](LOCAL_VALIDATION.json): 18 tests PASS, Draft 2020-12 wszystkich 43 schemas, offline `$ref`/fragment resolution, finite typed version/schema/ID domains, 8 command branches, START shape, closed profiles, modes/abort/result restrictions i deterministic generation; Ruff i mypy 2 files PASS. Znaleziony przy sprawdzeniu problem relative schema IDs usunięto przez absolute `urn:bdb:p0:*`; nie luzowano schema criteria.

Te sprawdzenia nie wykonują niezaimplementowanych semantic/OS/history predicates i nie są Q1/Q2/RQ. Shape-only `000…` values w testach są jawnymi nieutrwalanymi placeholderami; nie utworzono installation/grants lub certificate instances. Dotychczasowe 16 targeted i 274 broader tests PASS oraz source identity regression pozostają evidence checkpointu 7508; exact source/test hashes porównano bez drift. Brak zmian production code/inputs tych suites oznacza brak powodu do ponowienia 274 po zapisie propozycji. Nie przypisano im pokrycia nowego modelu.

| Gate / działanie | Wykonane teraz | Rzeczywisty brak i zatwierdzający |
| --- | --- | --- |
| Jedna zamknięta propozycja, complete closure, wersje, ryzyka/nakład | Gotowy exact package, all 18/7/43, Q1/Q2/RQ matrix | Owner zatwierdza lub odrzuca konkretne bytes i zmiany produktu |
| Nowa norma P0 | Proposed bodies/schemas/predicates | Brak OWNER_MODEL_DECISION/1 dla exact manifest; owner |
| Fresh Q1 | Lokalne checks bez qualification claim | Full P0 parity/Golden/readback/final audit/actual author record; uprawniony autor + owner |
| Q2 independent freeze | Nieuzyskane | Genuine independent review, finding closure, approved assurance decision i FREEZE; independent reviewer/authorized qualifier + owner |
| Model runtime integration | Reusable inactive checkpoint 7508, bez zmian | Wymienione siedem obszarów zgodności z approved norm; implementacja po następnej decyzji owner |
| RQ i real external run | Nieuzyskane, pierwszy ZIP fixture nie jest real audited result | True qualification namespace mandate, final code/environment, wszystkie 32 rodziny i real producer run; independent qualifier/owner/installer/auditor |
| Production authority/import | BLOCKED | Independently provisioned root/pins/keys/grants, Q1/Q2/RQ bound installation, new production campaign; owner/installer |

## 9. Konkretna decyzja właściciela — następny i ostatni krok tej iteracji

Proponowane brzmienie do zatwierdzenia **z actual manifest/graph hashes**, nie do podpisania w ciemno:

> Zatwierdzam normatywny model BDB_NF02_P0_LIMITED_1 z exact CANDIDATE_MANIFEST.json i DEPENDENCY_GRAPH.json wskazanymi w przekazanym checkpointcie oraz z oboma zawartymi w nim set digests. Dla tej odrębnej linii zastępuję pełny zakres kwalifikacji zakresem 18 canonical contracts, 7 profiles i 43 schemas, obejmującym wszystkie M01–M18 i obowiązkowe Q1/Q2/RQ. Zatwierdzam legalny approved-Git-only bootstrap bez legacy assurance transfer, finite operations/abort retry, one source/task/slot, nonblind external-host isolation, accepted auditor submission bez finding truth/Completion, at-least-once identical-byte delivery oraz jawny brak full-host rollback guarantee. Full R5.4.2/131/approval/checkpoints pozostają niezmienione. Zezwalam na implementację i przygotowanie dokładnie tej kwalifikacji. Ta decyzja nie ustanawia authority, nie stwierdza Q1/Q2/RQ PASS i nie aktywuje importu; activation wymaga niezależnej kwalifikacji, real installation/producer authority i signed production installation opisanych w M18.

Owner może przyjąć albo odrzucić ten jeden konkretny model. Jeśli nie akceptuje limitów task/view/knowledge/bootstrap lub qualifier wykaże mandatory zależności uniemożliwiające tę odrębność, nie należy samodzielnie tworzyć kolejnej generacji. **Po dostarczeniu pakietu praca zatrzymuje się na tej decyzji właściciela**, zgodnie z jego poleceniem. Nie rozpoczyna się kolejny etap formalizacji/implementacji/Q1 ani aktywacja na podstawie samej wcześniejszej strategii B.

Odtworzenie lokalnego pakietu, bez authority/instalacji:

```powershell
$env:PYTHONUTF8='1'
.venv-f2/Scripts/python.exe tools/nf02_p0_limited_model.py --check
.venv-f2/Scripts/python.exe -m unittest tools.test_nf02_p0_limited_model
.venv-f2/Scripts/python.exe -m ruff check tools/nf02_p0_limited_model.py tools/test_nf02_p0_limited_model.py
.venv-f2/Scripts/python.exe -m mypy tools/nf02_p0_limited_model.py tools/test_nf02_p0_limited_model.py --ignore-missing-imports
```

Produkcyjny import pozostaje **BLOCKED**, NF02 OPEN, P0 NOT_DELIVERED, E1–E6 NOT_COMPLETED, brak nowego qualification PASS. Nie wykonano push, merge ani release.
