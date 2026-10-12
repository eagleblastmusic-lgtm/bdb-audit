# Rzeczywiste RQ — procedura kwalifikatora

**NOT_RUN; żadnego RQ PASS, prawdziwego external run ani independent attestation w tym pakiecie.** Wszystkie 32 rodziny są wymagane. Local tests/TEST_ONLY CMS/callback delivery nie mogą wypełnić ich rzeczywistych kryteriów. Wynik RQ powstaje w osobnym qualification namespace, po Q1/Q2 i dual-signed mandate.

## Wejście i przygotowanie

Kwalifikator ustala identity/upoważnienie/niezależność, real owner/installer/auditor, cztery kontrolowane signer certs, TLS server CA/pin, final host/OS/Python/Git/backend i approved repository/commit/tree/view/task. Wymaga signed owner decision, AUTHOR_QUALIFICATION, INDEPENDENT_FREEZE/review, mandat `[not_before,not_after)` i exact implementation_files. Bez któregokolwiek warunku zatrzymuje real run jako niespełniony; nie tworzy jego zastępnika.

Installer wykonuje 05/06 na wyznaczonym hoście, bez istniejącej kampanii/migracji. Rzeczywiste namespace/mode/SID/pins pochodzą z installation, nie z flag kwalifikatora. Kwalifikator wykonuje readback root/install/assets/code/environment, service token i ACL, sprawdza permissions również z konta audytora na external host. Zamraża exact environment inventory, PKI/time/transport i narzędzia kwalifikacyjne. Testowe masowe kopie starego repo ani host rollback nie są częścią activation.

## Pierwsza legalna ścieżka

1. Przygotować przydzielony Git-only source za pomocą rzeczywistego `approved_git_view` i production `LimitedObject`/`root_objects` definitions. OIDs commit/tree/blob i source manifest oraz archive są osobne. Wybrać fixed task, nowe campaign ID i exact sześć installed roots/osiem pins. Owner przegląda source/view/task i podpisuje initial grant o null assignment scope **przed genesis**. Nie używać shape-only przykładowych ID z wektorów jako authority.
2. Wykonać unsigned INITIALIZE packet przez service `prepare`, z exact objects, raw digests, actor/grant i EMPTY_HISTORY. `product_p0_cli.packet` dokumentuje transport input: prepare ma `operation,objects,raw_digests,actor_ref,grant_digest` oraz opcjonalne `events,command_id`; accept ma `command,objects,raw_digests`. Raw directory zawiera pliki nazwane SHA-256 bez rozszerzeń. Owner kontroluje root/grants; Coordinator podpisuje **domain command preimage** z prepare, nie całe opakowanie packet.
3. Wywołać SCM `accept` z zachowanym packet/raw-dir/signature; potwierdzić seq=1 i osiem facts. Zachować signing preimage, raw task/source, command/CMS, trace/commit/receipt/head i niezależny expected readback.
4. Przygotować nowe Attempt/Assignment production `LimitedIntake.draft_assignment` albo te same closed bodies z current verified cut i retained source/task. To przygotowanie unsigned proposal, bez priors przez samą obecność w DB. Owner zatwierdza exact future assignment/auditor i instaluje nowe COORDINATOR/AUDITOR grants z nonnull assignment scope. Podpisać CREATE, przyjąć seq=2; potwierdzić jeden active attempt/assignment/slot.
5. Przygotować fixed package z exact accepted assignment i source/task. Zachować original ZIP. BIND podpisuje Coordinator, seq=3, atomic raw retention. Oddzielne START bez nowych facts/Binding daje seq=4. Używać current exact input cut i wszystkich prior refs, bez ręcznego poprawiania accepted records.
6. Service `prepare-release` wytwarza unsigned release statement w campaign directory. Coordinator podpisuje **dokładne zapisane preimage bytes** `BDB_P0_RELEASE_REQUEST/1...`; service `release` wysyła przez installed HTTPS adapter do external host. Endpoint zapisuje release ID, ZIP SHA/length/body i request context, oddaje 2xx dopiero po właściwym odbiorze. At-least-once retry deduplikuje ten sam release ID/bytes; nie uznaje response za ACK.
7. Audytor sprawdza package/source/task scope i podpisuje exact CJSON+LF DELIVERY_ACK/1 własnym CMS. Coordinator przygotowuje/przyjmuje CONFIRM_DELIVERY, seq=5. Kwalifikator porównuje observer/network/host evidence, outbox SENT i ACK; brak callbacka oznaczającego SENT.
8. Audytor **rzeczywiście wykonuje** zadanie na fixed view na odrębnym hoście. Kwalifikator niezależnie obserwuje wykonanie i utrwala tool versions/inputs/outputs/trace/report. Audytor przygotowuje fixed ZIP `MANIFEST.json` + declared reports/evidence/logs, payload NORMALIZED_RESULT, wszystkie paths/member hashes i original ZIP bytes, a osobno CMS nad AUDIT_RETURN/1 z exact ZIP RawRef i scope. Nie podpisuje losowego JSON lub samego ZIP, gdy norma wymaga return record.
9. Coordinator przygotowuje/przyjmuje INGEST_EVIDENCE, seq=6, przez ten sam Store/inbox i signed command; raw ZIP/return/CMS muszą być durable przed acceptance. Następnie nowy signed ACCEPT_RESULT w seq=7 rereads original ZIP i rederives payload; potwierdzić accepted submission, bez promotion findings/Completion/STOP/release.
10. Zatrzymać/startować usługę i wykonać full replay w nowym procesie. Powtórzyć exact signed commands: original receipt i brak append. Oddzielne negative/crash/concurrency campaigns w tym namespace mają własne authority/cuts i komplet retained evidence. Nie wykonywać niszczących prób na owner WIP lub kampanii produkcyjnej.

SDK i builders wskazane powyżej są actual production code. Kwalifikacyjny driver działa pod rzeczywistym service SID i tymi samymi installed predicates; można zautomatyzować operator recipes dopiero jako narzędzie kwalifikacyjne z exact code binding. Nie importować `SimulatedOsAuthority`, `simulated_verify`, test grant factory ani monkeypatch produkcyjnych predykatów. Raw preparation/proposal sam nie przyjmuje historii. Klucze pozostają w real providers; nie dodaje się ich do drivera ani JSON.

## Macierz wszystkich rodzin

Każdy wiersz jest rodziną: qualifier rozwija operacje/entry points, role, gałęzie, kontekst oraz dodatnie i ujemne kombinacje. Szczegółowa inventory fields/predicates/variants jest w 02 i existing QUALIFICATION_WORKLIST. Positive result bez wszystkich obowiązkowych siblings nie zamyka rodziny.

| RQ | Kontrola rzeczywista; wymagany rezultat |
|---|---|
| 01 | Identity/upoważnienia owner/qualifier/auditor, key custody i cztery różne DER pins; niezależność potwierdzona, brak governance key w service/audytorze |
| 02 | Native service token non-admin; deny modification root/code, allowed campaign writes, auditor deny read/write DB/vault/outbox/root/code; raw ACL/token export i actual access trials |
| 03 | Wszystkie signer/body/domain/install/namespace/scope/algorithm/expiry/revocation/missing-rights mutations dla właściwych CMS/grants; każde DENY bez accepted mutation |
| 04 | Root/grant/code/storage replacement, reparse/junction/symlink, rename i revocation races przed/przy COMMIT/release; leases/readback fail-closed |
| 05 | Exact model/schema/code/assets/dependencies readback przy install i restart, drift/incomplete records odrzucone; hashes actual deployed files |
| 06 | Real dual-signed mandate, czas/mode/namespace/code exact; expiry/cross-mode transfer i production przed RQ odrzucone |
| 07 | Actual authorized Git sha1/sha256 i commit/tree/blob types/bytes, approved complete assigned view i source grant; bez hash-only deklaracji |
| 08 | Unsupported path/mode/symlink/submodule/LFS/non-UTF8, omitted/substituted/extra source/task i quotas; DENY bez historii |
| 09 | Real EMPTY_HISTORY initializer, exact eight pins/external-schema precedence/Kahn; replay fresh ID i root revision po genesis odrzucone |
| 10 | Initial i retry po owner abort, każdy nonterminal branch, permitted auditor change z nowymi grants; one active, no retry po result |
| 11 | Original bound ZIP SHA/length/members/metadata; repack/substitution/extra/missing/alias denied i zero mutation |
| 12 | BIND prior i distinct later START, wszystkie wrong/missing/context/order/duplicate/same-commit variants denied |
| 13 | Real installed external-host HTTPS: exact retained bytes, TLS CA/DER pin, current rights/state, server observation; release nie kieruje caller |
| 14 | Fake ACK/SENT/callback, wrong auditor/source/slot/assignment/package/release/start denied; actual signed ACK joined |
| 15 | Crash przed/po I/O, response/ACK loss, PREPARED/SENT/ACKNOWLEDGED oraz retry; ten sam release ID i bytes, jawny at-least-once |
| 16 | Genuine external audit z independent observation, actual report/evidence/logs i original signed return ZIP; fixture nie jest wykonaniem |
| 17 | Raw ZIP/CMS/return/auth trace durable przed acceptance; missing/corrupt raw/index/length/digest na replay/write/retry denied |
| 18 | Strict fixed ZIP traversal/case/NFC/Win32/duplicate/metadata/encryption/compression/bomb/quotas; strict JSON duplicate/float/surrogate/depth/bounds denied |
| 19 | Delivery → later Evidence → later Result, exact own historical cuts, same-commit/post-cut laundering denied |
| 20 | Każdy full campaign/attempt/assignment/source/view/task/slot/binding/start/delivery/raw/profile/cut substitution, exact kind/version/schema/logical ID; zero accepted mutation |
| 21 | Reread original retained ZIP i deterministic normalization, findings/report paths/content/claims/payload modification denied |
| 22 | One E/R per slot/attempt i terminal semantics; no truth/PASS/Completion/STOP/release/full-NF02 promotion |
| 23 | Owner recovery abort w pięciu states, raw/facts preserved, revoked/wrong-role auditor abort denied, old attempt nie daje new result |
| 24 | Actual rights/revocation/root/code recheck immediately przed COMMIT/delivery; control race denied bez accepted append |
| 25 | Wszystkie denied commands/events/raw i public/direct entry points mają byte-exact DB/raw/vault/receipt/head before/after; rejection diagnostics osobne |
| 26 | Rzeczywiste konkurencyjne procesy: equal exact retry, competing B/E/R, same ID different bytes/CAS expected head; jeden poprawny winner |
| 27 | Terminate process / power-loss-equivalent na raw/object/command/trace/commit/receipt/head/flush boundaries; all-or-none durable transaction; scope storage/VM/device zapisany |
| 28 | Actual new-process/service restart/full replay: raw, signature/valid-at-acceptance grants/root/install/context/cuts/receipts reverified; corruption denied |
| 29 | Exact command retry current rights i original context/raw; original receipt bez append; missing rights/conflicting bytes denied |
| 30 | Generic Store/Coordinator/inbox/direct APIs/events/generators/installed standalone/alternate CLI używają tych samych predicates albo deny; żadnego bypass |
| 31 | Historical materials/readers zachowane; model/profile/schema/namespace mismatch nie fallbackuje do legacy; bytes/readback evidence |
| 32 | Same actual production-equivalent OS/code/dependencies/service/account/network/PKI/auditor boundary objęte evidence i qualifier signature; różnice mają jawne bound approval, bez deklaracji równoważności |

## Format i zachowanie evidence

Utrzymywać jeden nowy katalog namespace run: `inputs/` (public signed records/pins/approved source/task/actual code+environment inventories), `cases/` (case JSON + original logs), `raw/` (exact archive/ACK/return/CMS), `observations/` (OS/account/ACL/network/auditor/crash), `readback/` i manifest. Duże raw pozostają raz; dalsze records używają path/SHA256/length. Nie generować kopii wielogigabajtowych repo. Private keys, credentials i bearer tokens nie trafiają do evidence.

Każdy case JSON zawiera: `case_id`, `family`, `normative_clauses`, `predicate`, `contract/schema/profile refs`, `entry_point`, `operation/state/role/variant`, exact input identities, independent expected i jego procedurę/source, actual command/exit/status, before/after file hashes/head/receipts, observer identity/time, implementation/environment identities, logs/raw refs i wynik PASS/FAIL/INCOMPLETE. Authority flags podają **REAL**; użyta symulacja lub brak obowiązkowego dowodu oznacza brak RQ PASS. Case evidence samo nie wydaje prawa.

Final readback obejmuje wszystkie frozen/governance/code/environment/test/observer/raw files. Qualifier zamyka każdy finding i wszystkie obowiązkowe cases wszystkich rodzin, potwierdza actual external execution i signer custody, a dopiero potem tworzy zgodny frozen schema RUNTIME_QUALIFICATION/1 i detached qualifier CMS. Owner podpisuje późniejszą PRODUCTION installation dla nowego namespace. Until then production import pozostaje BLOCKED.
