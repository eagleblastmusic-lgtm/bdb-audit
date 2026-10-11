# BDB_NF02_P0_LIMITED_1 — przekazanie implementacji do Q1/Q2/RQ

Stan końcowej weryfikacji 2026-10-12: protokół zaimplementowany; lokalne przyjęcie przez produkcyjny Store i E1 inbox sprawdzone przy **symulowanej OS authority/CMS i dostawie**. Nie wykonano uprawnionego audytu zewnętrznego. **Production import BLOCKED; Q1/Q2/RQ niewystawione; NF02 OPEN; P0 produkcyjnie NOT_DELIVERED; E1–E6 NOT_COMPLETED.**

Checkpointy kodu: `39b2309101b3a5b3528de4aef25ae5e7db55006c`, następnie `6c79aa049ab84cc1d22c53ac4e595947702d0e68`. Macierz/harness i końcowe materiały Q1: `a2c1a4bc974cd88956c9492c3b48a37562024b1b`. Ten pakiet jest materiałem do wykonania kwalifikacji, bez podpisanych decyzji lub fikcyjnej authority. Nie zmienia zatwierdzonej normy, zakresu ani historycznych dowodów.

## 1. Dokładne wejście i uzyskane rezultaty

Zatwierdzenie właściciela otrzymano w rozmowie po sprawdzeniu actual bytes; niepodpisany zapis: [OWNER_APPROVAL_RECEIVED.md](../NF02_P0_LIMITED_MODEL/OWNER_APPROVAL_RECEIVED.md). Runtime nadal wymaga rzeczywistego owner CMS nad `OWNER_MODEL_DECISION/1`. Nie wystawiono tego podpisu za właściciela.

| Tożsamość niezmienionego kandydata z `63256bf` | SHA-256 |
| --- | --- |
| CANDIDATE_MANIFEST.json | `278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9` |
| DEPENDENCY_GRAPH.json | `7ad1c90ee72634b633e2a9c260e5d7b93d69fc9a1bcca76632291a047f15f27e` |
| normative_set_sha256 | `f4aeeadd96314ef7854f61747fdf3f72caf5dfb599c4977a78170aa3620165df` |
| machine_set_sha256 | `7449d5eb45ca2aa49b065318d1287ac473fed54dc0e8359bcc32033215f5709d` |

Zakres: **18 canonical, 7 profili, 43 schematy, M01–M18, Q1/Q2/RQ**. Każdy zbiór ma 55 wpisów; ich unia ma 57 plików, manifest to dodatkowy plik. External/wire schemas są już w tych 43. Pełny R5.4.2/131 i wcześniejsze approvals pozostają bez zmian. Nazwy wersji tej linii to między innymi Binding/3, Evidence/4 i Result/4; nie są aliasami wcześniejszych /1–/2.

| Część P0 | Kod oraz lokalny rezultat | Warunek rzeczywistego użycia |
| --- | --- | --- |
| Authority | Read-only OS root, exact owner/qualifier certificate DER pins, CMS/SHA-256, scoped signed grants, lease i final rights recheck | Real identity/key control, protected install/service i Q2/RQ |
| Bootstrap | Nowy namespace, empty history, sześć canonical roots/osiem pins, rzeczywisty Git commit/tree/blob readback | Owner-approved repository/view/task oraz Q1/Q2 + mandate albo RQ |
| Assignment/binding | CREATE/3, immutable task/source/slot, exact assigned ZIP retained w tej samej transakcji Store, Binding/3 | Exact nowe grants dla konkretnego Assignment/audytora |
| STARTED | Oddzielny późniejszy commit i jeden exact event | Aktualna authority i prior accepted Binding |
| Delivery/ACK | Protected outbox, stable release ID, installed HTTPS/CA + server DER pin, at-least-once recovery, osobny signed ACK | Real endpoint, audytor i external-host boundary |
| Raw/Evidence | Oryginalny result ZIP retained przed acceptance; auditor CMS nad exact return; Evidence/4 w późniejszej komendzie | Rzeczywisty audyt i current auditor grant |
| Result | Result/4 w kolejnym commicie, prior accepted Evidence, ponowny odczyt/normalizacja original ZIP | Ten sam kwalifikowany Store i bieżące prawa |
| Atomicity/replay | Jedna SQLite transakcja/CAS; exact retries, conflict, fault rollback, new-process exit/restart, historical auth/raw replay | Real qualified filesystem/Windows runtime i RQ-27/28 |

Nie ustanawia to prawdziwości findings, Completion/STOP, blind assurance ani full-host rollback guarantee. Retry attempt wymaga owner abort i nowych exact grants; wznowienie tego samego żądania zwraca pierwotny receipt. Outbox może zachować PREPARED po nieznanym wyniku rzeczywistego I/O; retry wysyła ten sam release ID i te same bajty, bez dopisywania canonical fact.

## 2. Produkcyjne pliki i pełne mapowanie M01–M18

Ścieżki w tabelach są względem korzenia repozytorium.

| Plik produkcyjny | Odpowiedzialność |
| --- | --- |
| `src/bdb_audit/history/limited_model.py` | Exact candidate/readback/set digests, closed Registry/18 i offline schemas/43 |
| `src/bdb_audit/history/limited_wire.py` | Finite versions, exact refs, Command/Commit/Receipt, signing preimage |
| `src/bdb_audit/history/limited_authority.py` | Independently installed authority, Q chain, grants, non-admin service/storage, RQ auditor pin |
| `src/bdb_audit/history/limited_environment.py` | Actual interpreter/Git/dependency tree readback i protected leases |
| `src/bdb_audit/history/installation_authority.py` | Wspólny Windows OS/CMS/file-lease adapter; historical acceptance time; P0 limit 2 MiB, legacy default 64 KiB |
| `src/bdb_audit/history/limited_protocol.py` | Wszystkie finite predicates/joins/cuts, authorization traces i history replay |
| `src/bdb_audit/history/store.py` | Istniejący jedyny writer, installed P0 loader, atomic acceptance/CAS, protected outbox |
| `src/bdb_audit/workflow/limited_transport.py` | Actual typed Git bytes; fixed source/package/result ZIP, bounded parsing i rederivation |
| `src/bdb_audit/workflow/limited_delivery.py` | Tylko independently installed HTTPS destination/pin |
| `src/bdb_audit/workflow/limited_intake.py` | Przygotowanie exact unsigned requests i przyjęcie przez istniejący Coordinator |
| `src/bdb_audit/workflow/inbox.py` | E1 inbox dla oddzielnych Evidence i Result, ten sam Store |
| `src/bdb_audit/product_p0_cli.py` | Installed `product p0` prepare/accept/release/status, bez caller root/issuer/mode |
| `src/bdb_audit/product_cli.py` | Włączenie finite P0 surface w istniejącą aplikację |
| `src/bdb_audit/p0_service.py` | Windows SCM one-command host pod rzeczywistym non-admin service account |

| Obowiązek normy | Główna implementacja | Lokalne dowody; rzeczywisty element pozostający do RQ |
| --- | --- | --- |
| M01 | limited_authority, installation_authority | Denial bez root; tożsamość/niezależność ludzi i kontrola kluczy do potwierdzenia |
| M02 | limited_authority, limited_environment | Qualification-chain i scoped rights tests; real OS ACL/CMS/service/clock wymagane |
| M03 | limited_model, limited_wire, limited_transport, core canonical/hash | 8100 schema vectors, 414 ref vectors, primitive goldens; independent expected review wymagany |
| M04 | limited_protocol.order/basis/resolve/history | 9 ordering probes, actual init DAG i prior-only refusals; pełny field-target worklist do Q1 |
| M05 | limited_protocol.validate_step, Store, CLI, inbox | Wszystkie 72 operation/state cases: 13 legalnych acceptance, 59 odmów bez mutation; również generic/event denials |
| M06 | strict_json, limited_transport, CLI, CMS wrapper | JSON number/depth, raw substitution/traversal, ZIP metadata/member i signature quota tests |
| M07 | approved_git_view, validate_roots/initialize | Actual commit/tree/blob, separate OIDs, git replace denial, six roots/eight pins; owner approval scope wymagany |
| M08 | context/auth_scope, LimitedIntake.draft_assignment | Single source/task/slot, initial/retry; external host/isolation do realnego sprawdzenia |
| M09 | bind + transport.package + Store raw table | Exact package/member binding, duplicate/substitution/CAS/rollback tests |
| M10 | start + validate_step | Binding w seq=3, START w seq=4; same-commit/typed/generator bypass odmówiony |
| M11 | Store.release_p0, limited_delivery, Delivery predicate | Stable retry po I/O fault i ACK fixture; real HTTPS handoff/ACK niewykonane |
| M12 | Evidence predicate, E1ResultInbox | Original ZIP/return/signature retained, negative binding/raw/signer/rights cases; actual execution brak |
| M13 | result + rederivation predicate | Późniejszy Result oraz payload substitution denial; accepted submission bez truth promotion |
| M14 | context/cut/validate_step/history | Campaign/attempt/source/slot/A/B/Delivery joins; current i own historical cuts; expanded target worklist |
| M15 | abort + CREATE retry predicates | Owner recovery, prior abort basis, preserved raw, terminal release denial; pięć nonterminal abort branches lokalnie PASS; real qualification pozostaje wymagana |
| M16 | Store._accept, final recheck_authority | Same-command one winner, competing binding, hook rollback, Co i auditor revocation at COMMIT |
| M17 | history/trace/raw reader, Store transaction | Actual child-process termination i new-process replay; true durable host boundaries do RQ |
| M18 | verify_qualification, offline installation tool, Q1 inputs | Exact manifests + qualification chain denials; żaden signed Q1/Q2/RQ nie został wystawiony |

## 3. Materiały Q1 i warunki jego wystawienia

`tools/nf02_p0_q1.py` odczytuje zatwierdzone bajty bez ich regenerowania. Uruchomienie w lokalnym środowisku repo:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
.venv-f2/Scripts/python.exe tools/nf02_p0_q1.py --output-dir docs/PRODUCT_V1/nf02_p0_runtime_qualification
```

| Plik | Co dokładnie sprawdzono / co zawiera |
| --- | --- |
| `LOCAL_Q1_INPUT_CHECKS.json` | Readback wszystkich 57 entries, manifest/graf/two-set identity, hashes narzędzia i materiałów; `author_record_issued=false` |
| `SCHEMA_VECTORS.json` + `SCHEMA_VECTORS_PART_*.json` | Indeks i shardy ≤2 MiB: **8100** positive/negative node/union/enum/required/closed/type/bounds cases, compact recipes dla dużych limitów; wszystkie 43 schemas |
| `PRIMITIVE_VECTORS.json` | CJSON/RawDigest/ObjectDigest dla 18 versions, 18 canonical shape goldens w tym Commit/3; stdlib encoder oraz osobny ręczny UTF-8 encoder |
| `REF_VECTORS.json` | **414** exact typed grammar/schema raw pin cases; celowo nie dowodzi prior acceptance ani authority |
| `DAG_AND_STATE_VECTORS.json` | **9** sprawdzonych ordering probes; **72** finite operation/state expectations; wszystkie lokalnie wykonane z real Store, przy symulowanym OS/CMS/transport; nadal wymagają real qualification |
| `QUALIFICATION_WORKLIST.json` | Pełne definitions/targets/predicates wszystkich 18, siedem profili, 43 schemas; wszystkie material ref fields i mutations; wszystkie Q1/Q2/RQ requirements i public entry points |
| `IMPLEMENTATION_EVIDENCE.json` | Faktyczne komendy/test outcomes, code/test/material hashes, frozen-byte preservation, unqualified build i fail-closed smoke |

Expected primitive bytes powstają poza kodem SUT. Expected schema decisions wynikają z frozen schemas; ręcznie rozpisane DAG/state expectations wynikają z M04/M05. Te dwie lokalne procedury są independently checkable, lecz nie zostały zatwierdzone przez niezależny podmiot. Schema-only/ordering-only cases nie są accepted-history fixtures. Nie wolno użyć ich placeholderów jako qualified root/grant.

| Rodzina Q1 | Dokładne domknięcie i brak do formalnego rekordu |
| --- | --- |
| Q1-01 | Wszystkie manifest entries oraz oba digests/readback sprawdzone; autor utrwala końcowy audit |
| Q1-02 | 18 body definitions równe exact schema fields; autor ocenia każdy material target/class i każdy predicate z worklist względem M01–M18/kodu |
| Q1-03 | 7 profiles, 43 schemas/offline refs i wszystkie external/wire/inline reprezentacje; potwierdzić brak ukrytych dependencies |
| Q1-04 | Wszystkie 72 operation/state cases: legalne branches z pełnym context/authority; wszystkie pozostałe odmówione; 5 abort states, initial i retry, delivery PREPARED/SENT/ACKNOWLEDGED/unknown outcome |
| Q1-05 | Wszystkie 8100 schema cases i 414 exact-ref cases, każde nullable/union/enum/bounds; niezależnie sprawdzić expected outputs |
| Q1-06 | Obie reference procedures, wszystkie versions w tym Commit/3, actual expected bytes/digests zachowane; osoba dokonująca review potwierdza wyniki |
| Q1-07 | Ordering probes + każdy field-target/prior/content branch z worklist; missing/wrong/future/self/same-commit/cycle/duplicate/cut/context substitutions; ordering probe sam nie dowodzi resolve |
| Q1-08 | External schema root przed Registry, exact eight pins i new-empty-history initializer; rzeczywiste source/view/task proof bez legacy transfer |
| Q1-09 | Q1 autora, niezależne Q2, dual-signed mandate albo RQ; current roles/scopes/time; cross-mode/namespace/install tampering odmówione |
| Q1-10 | Jawne limity §9, brak Completion/truth/blind/host rollback promise; frozen R5.4.2 i historyczne materiały niezmienione |
| Q1-11 | Zachowany final audit wszystkich powyższych przypadków, brak niewyjaśnionych mismatches, rzeczywisty author/governance record i owner CMS |

**Q1 nie ma obecnie formalnego PASS.** Nie zastępować końcowego semantic audit ani niezbędnych qualified fixtures samym licznikiem schema vectors lub lokalną regresją. Materiały wskazują konkretne branches do domknięcia; nie twierdzą, że wykonano je w prawdziwym qualified environment.

## 4. Niezależne Q2 i rzeczywiste RQ

Q2-01–06 wymagają rzeczywistego uprawnionego reviewer/qualifier, niezależnego od implementatora, Coordinatora i audytora, oraz oddzielnej kontroli kluczy. Reviewer sprawdza exact scope 18/7/43/M01–M18, cały Q1/final audit, nowe granice authority/bootstrap/isolation, wszystkie findings i zgodę właściciela na limity. Retained independent review i external FREEZE podpisuje qualifier. Nie ma podstawy do review 131 wykluczonych kinds bez konkretnej wykazanej zależności.

Poniżej konkretne wejścia/oczekiwania dla wszystkich 32 rodzin RQ. Każda obejmuje wszystkie applicable operations, role, field targets i entry points z worklist. Numery oznaczają rodziny, a nie 32 pojedyncze przykłady. Mutacje bada się pojedynczo na otherwise-valid qualified fixture; expected decisions kwalifikator zatwierdza przed przebiegiem. Dla odmowy porównuje head, receipts, objects/raw i bajty wszystkich campaign files przed/po. Wyjątek uczciwej trwałości operational outbox po rzeczywistym I/O opisano w M11.

| RQ | Wejście/procedura i wymagany wynik |
| --- | --- |
| 01 | Zidentyfikować owner/qualifier/Coordinator/audytora, real DER cert pins, uprawnienia i posiadaczy private keys. Wspólny lub caller-controlled root/key: odmowa |
| 02 | Rzeczywistymi tokenami próbować zapisu/rename/delete root/code przez service oraz root/code/history/vault/outbox przez audytora. Service ma zapis tylko do chronionego campaign storage; audytor nie ma żadnego z tych zapisów |
| 03 | Dla command, release, installation, grants, ACK/return i governance: wrong signer/content/domain/install/namespace/scope/algorithm, expiry, brak/revocation praw, oversized/invalid CMS. Wszystkie applicable odmowy bez acceptance/release |
| 04 | Podczas lease równolegle revoke/replace/rename/grant/root/code/storage/reparse. Nie można podmienić sprawdzonych bajtów przed COMMIT ani real byte release |
| 05 | Usunąć/podmienić każdy required model/schema/code/qualification file i podpis. Install/restart/write fail-closed; brak synthetic repair/backfill |
| 06 | Dual-signed mandate: wrong/missing signer, expired, wrong code/freeze/namespace/mode; caller PRODUCTION oraz qualification receipt transfer odmówione |
| 07 | Real repository: commit/tree/blob typed hashes i approved view; oddzielne HEAD/tree. Git replace/config/object substitution nie może zmienić approved content |
| 08 | Unsupported source path/mode/symlink/submodule/LFS, extra/missing/substituted manifest/task/blob. Bootstrap odmówiony bez historii; binarne supported blobs zachowują bytes |
| 09 | Prawdziwy EMPTY_HISTORY INIT z ośmioma exact pins; Kahn content order i external schema root. Repeated init, changed roots/schema/profile/source/task po genesis odmówione |
| 10 | CREATE initial i po każdym z pięciu legalnych ABORT states, exact new grants/A/Attempt/source/task/auditor/slot. Dwa active, wrong prior abort, reused IDs lub retry po Result odmówione |
| 11 | Exact ZIP hash/length/member/body/metadata/profile. Zmienić/repackować/kompresować/dodać member, duplicate/collision/unsafe path/trailing/gap/ZIP64; odmowa |
| 12 | B w osobnym wcześniejszym commicie; START legalnie później. Start bez prior B, tego samego commitu, innego A/Attempt, extra events/facts odmówione |
| 13 | Real HTTPS qualified host, CA i pinned server DER, exact ZIP i release ID. Foreign endpoint/pin, niedozwolony caller sink, release przed START/po abort/result odmówione |
| 14 | Faktyczne dostarczenie pakietu i signed ACK audytora. HTTP 2xx bez ACK nie przyjmuje Delivery; wrong signer/package/release/start/scope odmówiony |
| 15 | Przerwać transport przed/po I/O i przed zapisem SENT. Retry zachowuje release ID/bytes, nie obiecuje exactly-once, nie dopisuje canonical Delivery bez ACK |
| 16 | Kwalifikator obserwuje real external audit przydzielonego task/view; retained actual report/outputs. Fixture/declaration/callback nie zastępuje wykonania |
| 17 | Oryginalny result ZIP retained przed canonical E; test raw/write/readback crash. Missing/repacked/substituted original nie może otrzymać E/R |
| 18 | Signed AUDIT_RETURN dokładnych bytes/RawRef/A/B/Delivery/cert/slot/source/campaign. Wrong/revoked signer, scope lub declaration odmówione |
| 19 | Strict result manifest/UTF-8 report/output MIME/member digests/source paths/findings/notes/quota. Unknown/extra/duplicate/unsafe/over-limit payload odmówiony |
| 20 | E dopiero po prior B/START/Delivery, R dopiero po prior E. One-commit, future, copied raw/alias, generic events lub extra objects odmówione |
| 21 | Dla każdego material target zmienić campaign/attempt/source/A/B/delivery/slot/schema/version/logical/revision/cut; użyć material mutation list. Odmowa nawet przy prawidłowym podpisie innego kontekstu |
| 22 | Każdy historical cut względem własnego input head, nowy cut względem current head. Old/future/post-head/wrong governing context odmówiony |
| 23 | Każda próba przyjęcia kolejnego E/R tego samego slotu, operation retry z nowym command ID, retry po terminal Result: odmowa; exact command retry jest osobnym przypadkiem 29 |
| 24 | Odwołać/wyczerpać prawa Co i audytora tuż przed COMMIT oraz delivery; brak accepted mutation/nielegalnego handoff. Production auditor musi odpowiadać qualified RQ certificate |
| 25 | Snapshot history dla każdej odmowy, również direct Store/Coordinator/E1/CLI/SCM/generator/raw loader. Brak faktu, receipt, raw row lub zmiany plików |
| 26 | Concurrent equal command, competing bind/E/R, same ID different bytes, stale expected head. Jeden legalny winner/receipt albo dokładny retry; przegrany bez mutation |
| 27 | Rzeczywisty new-process termination i power-loss-equivalent storage tests na raw staging/readback, object, command/trace/commit, receipt, head/flush/COMMIT boundaries. All-or-none |
| 28 | Nowy proces odtwarza cały accepted chain i ponownie sprawdza schema/raw/CMS/historical grant/trace/cuts/events/receipt/normalization. Corruption/missing bytes fail-closed, current expiry nie zmienia przeszłości |
| 29 | Ten sam exact signed command zwraca pierwotny receipt bez append; changed bytes/ID reuse/context lub current missing rights odmówione |
| 30 | Generic Store, old/new inbox, typed events, generators, both CLI surfaces, installed standalone i SCM próbują każdego applicable bypass. Ten sam finite Store gate; żaden fallback |
| 31 | Historyczne readers/profiles/model/namespace nie interpretują P0 jako starej wersji. R5.4.2/frozen evidence byte-equal; brak migration/backfill |
| 32 | Real Windows/service/runtime/dependencies/code/ACL/clock/transport/auditor boundary i pierwsze przyjęcie związane retained evidence z signed RQ. Różnice prod/qualification wymagają jawnie bound qualifier evidence |

Wyniki lokalnego pytest, 8100 schema vectors i natywny SCM host kod **nie są RQ**. Brakuje realnego service deployment, OS access probes/races/power-loss-equivalent qualification i actual external audit. First real result należy uzyskać najpierw w prawidłowo autoryzowanym QUALIFICATION_ONLY namespace; nie trzeba i nie wolno aktywować produkcji przed RQ.

## 5. Konkretna konfiguracja i podpisy — rzeczywisty punkt działania właściciela

1. Właściciel wskazuje realnego kwalifikatora, audytora i administratora oraz dwa oddzielne hosty: protected Windows Coordinator/service i external auditor. Ustala out of band tożsamości, certyfikaty DER SHA-256, kontrolę private keys i source/task scope. Odpowiedź w rozmowie powtórzyła pytanie; nie podała tych osób/hostów. Implementator nie może ich wybrać fikcyjnie ani wystawić własnej niezależności.
2. Autor kończy pełny Q1/final audit powyższego exact zakresu; rzeczywisty owner podpisuje OWNER_MODEL_DECISION i AUTHOR_QUALIFICATION (`independent_assurance=false`). Qualifier kończy Q2, retained independent review i podpisuje INDEPENDENT_FREEZE. Wszystkie JSON transport bytes: exact CJSON + LF; oba bindings i graph z tabeli §1. Nie zmieniać frozen `PROPOSED` labels w zatwierdzonych plikach.
3. Administrator przygotowuje dedykowany chroniony runtime z zainstalowaną aplikacją, Python/dependencies i Git. Owner/qualifier sprawdzają actual implementation files i OS/runtime dependency inventory. Uruchamianie service przez `python.exe -I -B -m bdb_audit.p0_service`; wyłączone caller environment/import paths, bez writable app/runtime files. `ENVIRONMENT.json` wiąże rzeczywiste ścieżki, OS build, interpreter oraz wszystkie pliki runtime/Git. Snapshot musi mieścić się w M06 i pozostać identyczny; instalacja z niechronionego roboczego checkoutu jest odmówiona.
4. Owner i qualifier podpisują **te same** bytes czasowego QUALIFICATION_MANDATE dla exact model/code/freeze i nowego qualification namespace. Nie ustanawia go CLI flag. Q2 poprzedza mandate, a RQ jeszcze nie istnieje.
5. Przygotować assets directory z oryginalnymi 58 candidate files, OWNER_MODEL_DECISION + `.p7s`, AUTHOR_QUALIFICATION + `.p7s`, retained final audit, INDEPENDENT_FREEZE + `.p7s`, retained independent review, mandate + `.p7s` i `.qualifier.p7s`, SOURCE_REPOSITORIES.json i AUDITOR_TRANSPORT.json. Żadnych private keys w assets/repo/ZIP/rozmowie. Nazwy qualification files podaje configuration. JSON operacyjny source: `{"repositories":[{"repository_id":"<approved id>","path":"<actual approved Git path>"}]}`; transport: `{"auditors":[{"auditor_certificate_sha256":"<real DER SHA256>","url":"https://<qualified endpoint>/<path>","server_certificate_sha256":"<real TLS DER SHA256>"}]}`. To placeholderowa składnia, nie gotowa authority.
6. Uruchomić `tools/nf02_p0_installation_packet.py --assets <dir> --configuration <file> --output <new-dir>` w finalnym runtime aplikacji. Configuration ma dokładnie: owner_certificate_sha256, qualifier_certificate_sha256, namespace_id, coordinator_service_sid, mode=QUALIFICATION_ONLY, freeze_file, qualification_file. Narzędzie przygotowuje unsigned bytes i sześć root objects; **nie podpisuje, nie instaluje, nie kwalifikuje i nie wydaje grants**. Owner sprawdza cały packet i podpisuje exact `installation.json` jako `installation.p7s`. Nie uruchamiać generatora ponownie po podpisaniu: zmienia root ID/namespace authority digest.
7. Administrator niezależnie instaluje wynik w OS CommonAppData `BDB Audit/NF02-P0-Limited`. Root/code/runtime oraz parent `BDB Audit`/`P0-Campaigns` są Admin/SYSTEM-owned i zapisywalne wyłącznie przez nich. Service ma read/execute, bez modyfikacji tych plików. Namespace storage: `BDB Audit/P0-Campaigns/<namespace_authority_digest>/<campaign>.sqlite`; service SID ma tam niezbędny zapis do DB/raw/outbox, a audytor/caller go nie ma. Usunąć nieodpowiednie inherited write/delete/change-owner ACL w instalacji, sprawdzić właścicieli i brak reparse points. Loader sprawdza to ponownie, trzymając file/directory handles. Przygotowanie ACL/SCM jest czynnością rzeczywistego OS administratora, nie producenta wyniku.
8. Zainstalować Windows service `BDBAuditNF02P0` pod realnym **NON_ADMIN_SERVICE_ACCOUNT**, bez członkostwa w Administrators/SYSTEM. Nadać Log on as a service i kontrolowany service-start access; zarejestrować Application Event Log source. `ServiceController.Start(string[])` przekazuje finite argv `status|prepare|accept|prepare-release|release`; standardowe `Start-Service` nie przekazuje tych argumentów. Event ID 1001 zawiera outcome; accepted receipt jest trwały w Store. Stop kończy rozpoczętą serializowaną operację; wymuszone zakończenie przechodzi przez crash recovery.
9. Owner podpisuje osobne PRINCIPAL_GRANT bytes dla Co i audytora, exact installation digest, campaign/source_scope/view_task/assignment_scope i czasu. Instalacja w `grants/<sha256>.json` oraz `.json.p7s`, wyłącznie przez uprawnionego administratora/owner. INITIALIZE grant ma assignment_scope=null. Draft nowego A/Attempt i scope należy przedstawić owner przed CREATE; kolejne granty wiążą ten exact assignment i audytora, nie wildcard. `LimitedProtocol.auth_scope` podaje dokładny preimage trzech domen SOURCE-SCOPE/VIEW-TASK/ASSIGNMENT-SCOPE. Odwołanie bieżącego grantu w protected root blokuje nowe writes/retry/release; historical proof pozostaje retained.
10. W uprawnionej usłudze użyć `LimitedIntake.initialize → draft_assignment/prepare CREATE → bind → start → release_job/release_p0 → delivery → E1ResultInbox.accept_p0_evidence → accept_p0_result`. Każda canonical operacja otrzymuje oddzielny CMS Coordinatora nad exact signing bytes i osobny receipt. ACK oraz AUDIT_RETURN podpisuje rzeczywisty audytor. ZIP nie jest wykonywany przez Coordinator. CLI `product p0 prepare/accept` przyjmuje odpowiadające exact packets; raw directory ma pliki nazwane pełnym SHA-256. Przygotowane bytes bez podpisu nie mogą zmienić historii.
11. Kwalifikator wykonuje wszystkie RQ cases na tym samym kodzie/Store, zachowuje real report/ZIP/ACK/return/traces oraz test/environment/boundary evidence i wystawia signed RUNTIME_QUALIFICATION. Pole qualified_auditor_certificate_sha256 wskazuje rzeczywiście kwalifikowanego audytora; produkcyjny grant innego certyfikatu jest odmówiony. Zmiana audytora poza ten dowód wymaga odpowiednio kwalifikowanego nowego RQ, nie tylko owner grantu.
12. Dopiero po prawdziwym RQ owner może przygotować osobny signed PRODUCTION installation record: nowe root ID/namespace, pustą campaign DB, current grants, actual readback i retained complete Q1/Q2/RQ chain. Zachować qualification namespace/evidence; nie kopiować jego facts/receipts jako produkcyjnych. Każdy nowy write ponownie weryfikuje wszystkie bramki. Nie wykonano tej aktywacji, service installation, push, merge ani release.

CMS musi być detached, single-signer, SHA-256, z certyfikatem rzeczywistego uprawnionego podmiotu. Pin to SHA-256 pełnych DER bytes, nie SHA-1 thumbprint. Governance/grants/ACK/return podpisują exact CJSON+LF transport bytes; komendy podpisują `ASCII BDB_NF02_P0_COMMAND/1 + NUL + CJSON(CommandEnvelope/3)` bez LF. Release podpisuje exact CJSON `LimitedProtocol.release_statement(job)` bez LF. Authority loader weryfikuje realne CMS, certificate interval, pin, current scoped grants i independently installed bytes. Nie używa własnego HMAC, caller manifest/cert/root, actor_ref ani local PASS jako źródła uprawnienia.

**Najmniejszy zewnętrzny krok:** wskazać kwalifikatora/audytora/hosty i ustanowić rzeczywiste tożsamości/piny oraz kontrolę kluczy. Pozwoli to wykonać owner-signed Q1 i niezależne Q2, następnie dual-signed qualification mandate i pierwszy legalny real run. Sama akceptacja tego pakietu ani wygenerowanie JSON nie aktywuje importu.

Zakres mypy repozytorium to konfiguracja pyproject.toml (56 files) plus dziewięć dodanych/zmienionych modułów history/authority/CLI/service. Oba przebiegi PASS. Dodatkowy diagnostyczny `mypy src` obejmujący całą szerszą aplikację zwrócił 131 błędów w 39 niezmienionych plikach; żaden ze zmienionych plików produkcyjnych P0 nie występuje na tej liście. Nie ogłoszono całego repozytorium wolnym od błędów typowania ani nie rozszerzono P0 o ich refaktoryzację.

Lokalna macierz M05/M15: `tests/product/test_limited_p0_state_matrix.py` — 1 pytest case, 72 operation/state pairs, 13 accepted i 59 denied bez byte mutation, 223.60 s. Niedozwolony initializer/parent może zostać odrzucony przez closed Command schema przed SQL; nie użyto słabszego konstruktora. Poprawione początkowe błędy harnessu (tuple unpacking, runtime rebinding i negative constructor boundary) nie są blockerami ani wynikami produkcyjnych predicates. Żaden FAIL nie pozostał w tym przebiegu.

Końcowe sprawdzenie po commicie `a2c1a4b`: **18 PASS / 63 deselected, 84.08 s**, w tym pełny E/R/E1/restart, qualification chain, RQ auditor identity, CMS quota i CLI bez authority. Szersze 333 PASS dotyczą baseline `39b2309`; późniejsze guardy mają osobne celowane wyniki, bez przypisywania temu starszemu przebiegowi blanket PASS finalnego kodu.
