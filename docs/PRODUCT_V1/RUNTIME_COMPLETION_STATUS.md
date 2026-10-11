# PRODUCT-V1 — aktualny stan NF02 runtime

## Decyzja o odrębnym successor P0 — 2026-10-11

Właściciel wybrał przygotowanie strategii 2, z obowiązkiem powrotu po decyzję, jeśli transitive closure nadal obejmie 131 kontraktów. [Konkretny pakiet zakresu](NF02_P0_SUCCESSOR_SCOPE_PROPOSAL.md) i [exact dependency inventory](NF02_P0_SUCCESSOR_DEPENDENCIES.json) są gotowe. **Wynik: 131 kontraktów, 127 profili i 277 schematów; brak mniejszego Q1 przy zachowaniu obecnych target domains.** Zarówno zatwierdzony graf, jak i aktualny niezakwalifikowany Registry zostały prześledzone od rzeczywistych korzeni P0. Wskazano command/commit/receipt oraz retry/checkpoint jako konkretne zależności rozszerzające zakres.

Nie rozpoczęto pełnego semantic review 131, nie zmieniono R5.4.2/owner approval i nie aktywowano importu. Potrzebna jest decyzja właściciela: kontynuacja pełnego Q1 obecnego modelu z pierwszym wynikiem jako milestone albo dodatkowe upoważnienie do opracowania rzeczywiście ograniczonego normatywnego modelu, wymagającego nowego closure i osobnego zatwierdzenia. Strategiczna zgoda na przygotowanie nie jest approval nowych normative bytes. Checkpoint implementacji: `7508d4fd5d0dc3e2f3cfa3fe5e07834c9e3b8298`.

## Checkpoint P0 — implementacja 2026-10-11

**NF02 OPEN; P0 NOT_DELIVERED; produkcyjny import BLOCKED; E1–E6 NOT_COMPLETED; brak nowego Q1/Q2 PASS.** Powstał dodatni protokół przez istniejący Store/Coordinator i E1 inbox. Testy symulują authority na granicy OS; nie są niezależną kwalifikacją. Nie uzyskano rzeczywistego wyniku uprawnionego zewnętrznego audytora.

| Część P0 | Aktualny rezultat |
| --- | --- |
| Authority | Read-only MachineAuthority: administrator-owned OS CommonAppData root, niezależny owner/qualifier, CMS, pełne pins plików/kodu, ograniczone czasowo granty producenta i exact command/scope signature. Bez publicznego issuera, własnego HMAC, tworzenia kluczy/certyfikatów i wyboru root przez caller/env. Chronione code/history locations, file/directory leases, ACL/reparse verification. **Rzeczywista authority nieustanowiona.** |
| Nowa kampania | `open_nf02`, przygotowanie independently approved bootstrap/context packets, external raw schema root przed SchemaRegistry/2, exact initial pins. Brak upgrade/backfill; stare codecs pozostają oddzielne. Dodatni test tworzy nową historię na predecessor schemas jako jawnych danych testowych, bez promowania ich kwalifikacji. |
| Binding/1 | Prior full Assignment, exact context/HistoryCut, source/run/executor/delivery/knowledge/grants/views join; bezpieczny ZIP i semantic rederivation. Exact raw ZIP zapisany przed obiektami/commitem w istniejącej transakcji Store. Jeden binding; operation retry zwraca pierwotny fact/receipt. |
| STARTED/delivery | Osobna późniejsza komenda i exact event. Writer lock serializuje actual byte handoff z innymi zmianami historii. Bieżąca authority/cut/state i retained bytes sprawdzane przed callbackiem. Testowy synchroniczny odbiorca otrzymał exact package bytes; rzeczywisty transport audytora nie został wykonany. |
| Evidence/2 | Oddzielne przyjęcie po STARTED, exact slot/profile/binding/campaign/source/attempt/HistoryCut, trwały oryginalny ZIP. Podpis wiąże dokładny fakt. E1 inbox przyjmuje evidence, a nie automatycznie wynik. |
| Result/2 | Kolejna komenda z wcześniejszym accepted evidence, ponowna normalizacja retained bytes i byte-equal finite payload. Jeden produkcyjny writer; brak słabszego fallback importu. |
| CAS/crash/restart | Testy obu rodzajów retry, concurrent one-winner binding, konfliktu różnych wyników jednego slotu, 7 crash hooks, restartu, ACK loss, brakującego raw, caller mutation i odwołania praw przed COMMIT. Odmowy porównują bajty wszystkich plików historii. |
| Rzeczywisty audyt / assurance | Niewykonany. Wynik jest fixture, principal i protected storage są symulowane na granicy testu. Brak nowego ENFORCED, Lane/StageCompletion, STOP, NF02 closure lub full lifecycle PASS. |

Dokładny pakiet decyzji/configuration: [NF02_P0_QUALIFICATION_REQUEST.md](NF02_P0_QUALIFICATION_REQUEST.md). Komendy, zakresy weryfikacji, source hashes i unqualified build: [NF02_P0_IMPLEMENTATION_EVIDENCE.json](NF02_P0_IMPLEMENTATION_EVIDENCE.json). Poprzedni evidence JSON pozostał bez zmian.

Rzeczywisty source bug był w `AuditOperationApi.create_campaign`, gdzie kopiowano commit do tree. API używa teraz istniejącego verified resolvera przed tworzeniem DB. Test sprawdza oba polecenia Git i zaakceptowany SourceIdentity. Checkpoint poprawki `4e4554dd6ea955f8669e63ea8b6b982200691396` ma tree `f19d4f895377ccf5218af867d0cc87c77871c273`; historyczne raporty nie zostały zmienione.

Zatwierdzenie `OWNER_R5_4_2_SEMANTIC_CLOSURE_APPROVAL.json` wymaga fresh Q1 exact R5.4.2 i graph 131. Aktualny autonomous checkpoint nadal nie ma materializowanego candidate, Q1/Q2 ani zakończonej semantic parity. Minimalny żądany wire protocol /1 → /2 → /2 nie jest aliasem późniejszych wersji w pełnym draft R5.4.2. Finalne compatible pins/codecs wymagają wskazanej w pakiecie decyzji o zakresie; nie należy ich zgadywać ani aktywować predecessor Q1. N4 oraz N5–N9 są częścią wymaganej aktywacji/guard proof. N10 zamyka NF02, N11 kwalifikuje całą aplikację; nie dodano N11 jako warunku pierwszego wyniku.

Właściciel wybrał strategię 2: przygotowanie konkretnej formalnej propozycji osobnego minimalnego successor P0 z pełnym dependency closure, wersjami, wpływem i porównaniem nakładu. Ta decyzja strategiczna nie zatwierdza nowej normy. Pełny R5.4.2/131 pozostaje bez zmian. Najmniejszy następny krok to przedstawić ten zakres do zatwierdzenia; potem potrzebne są finalne compatible candidate/pins, dopasowanie codeców, fresh Q1/Q2, niezależny kwalifikator/producent i chroniona podpisana instalacja. Samo utworzenie root.json lub podpisanie request nie włącza importu.

Szersza affected regresja istniejącego produktu: **274 PASS**, w tym Store/F1/F2, runner, product, E1 freeze/isolation i standalone clean environment. Dodatnia ścieżka ma własne targeted evidence, oddzielone od tych wyników. Zamrożone legacy self-testy potrzebowały normalnego kontekstu Windows po potwierdzonym WinError 5 w sandboxie; kodu i kryteriów nie zmieniano. Nie wykonano merge, push, release ani zmian frozen materiałów.

## Historyczny checkpoint 00ef7b0 — zachowany opis poprzedniego stanu

Poniższy zapis dotyczy stanu sprzed implementacji dodatniego adaptera. Bieżący stan i ograniczenia są w sekcji powyżej; historyczne dowody nie otrzymują nowego zakresu PASS.

2026-10-11. Repo: `C:\Projekty\Audyty\BDB Audit`. Gałąź robocza: `work/nf02-runtime-completion`, utworzona od `e75f14ed443d6d6c7f60359687938c1fb6b062c0`. Zastane pliki untracked i historyczne materiały zachowano. Nie wykonano push, merge, release ani zmian frozen źródeł.

Pierwszy lokalny checkpoint napraw: `b01eb89`. Dalsza delta zamyka obejście przez zdarzenia Store, potwierdzone testem regresji przed poprawką.

**P0 nie jest dostarczone. NF02 OPEN; import BLOCKED; E1–E6 NOT_COMPLETED; brak nowego Q1/Q2 PASS.** To checkpoint napraw i działającej kontroli manualnej, nie aktywacja zaufanego przyjmowania wyników.

## Działający rezultat

Użytkownik może przygotować kampanię i pięć paczek E1, uruchomić istniejący lokalny runner, wznowić kampanię, sprawdzić otrzymany ZIP E1 oraz wyeksportować raport częściowy z lokalnymi dowodami i jawnie nieprzyjętymi deklaracjami. `product inspect-result --store ... --zip ... --json` zwraca `INSPECTED_UNTRUSTED`, `accepted=false`, dokładne hashe i powiązania. `product report ... --result-zip ...` dodaje tę kontrolę do raportu. Oba inboxy używają tej samej transformacji raw-to-proposal. CLI obsługuje paczki E1, API Stage sprawdza transport istniejącej fazy; outputy specyficzne dla E2–E6 nadal wymagają osobnych predykatów.

Nie można przyjąć żadnego nowego wyniku zewnętrznego ani ukończyć E1 na tym produkcie. Zgodność ZIP/kontekstu nie ustanawia producenta, prawdziwości ustaleń, wykonania AI, ENFORCED ani completion.

## Zmiany i granice dowodu

| Luka / właściwość | Wykonana zmiana i wynik |
| --- | --- |
| Lokalny issuer jako samodzielna authority | Usunięto implementacje wystawiania ticketów i HMAC capability. Publiczne metody odrzucają przed otwarciem transakcji. Przygotowanie/wznowienie E1 i Stage nie wywołują issuera. Nowa kampania nie wytwarza klucza. Brak niezależnego uprawnionego producenta pozostaje nierozwiązany. |
| Mutacja przy szukaniu klucza | Historyczny helper wyłącznie czyta istniejący klucz; brak klucza odrzuca bez INSERT. Zachowano stare tabelę/bajty i historyczny validator. Klucz nie aktywuje produktowego Store. |
| Nadpisywanie sprzecznych deklaracji | Wspólna transformacja odrzuca sprzeczne pełne tożsamości Assignment/Attempt przed normalizacją. |
| Rzeczywiste bajty i kontekst | Read-only kontrola używa bounded snapshot, istniejących safe ZIP/strict JSON i raw derivation. Sprawdza hashe/length/members, faktycznie odczytaną paczkę, source commit, slot, executor/model, fazę, assignment i cut. Lokalny receipt paczki nie jest zaakceptowanym bindingiem z chwili przypisania. |
| Odrzucenie bez mutacji | Testy porównują pełne bajty plików kampanii oraz brak accepted raw/admission/result/completion. Inspekcja nie używa staging vault ani writera. |
| Bezpośredni Store / obejścia | Centralna blokada pozostaje dla obu kinds i komendy importu, także przez Coordinator i generic command. Same-commit i dwustopniowa próba laundering odrzucone atomowo. |
| Obejście przez `ordered_events` | Test przed poprawką potwierdził przyjęcie generic command z CREATED → STARTED → RESULT_RECEIVED → RESULT_ACCEPTED bez wyników. Wspólna bramka Store odrzuca teraz STARTED, RESULT_RECEIVED/ACCEPTED, lane/stage completion candidate/accepted oraz E6/conclusion/closed campaign transitions wymagające nieaktywowanego protokołu. Obejmuje Coordinator, różną wielkość liter aggregate, alias `id`, pojedynczy event i generator. Osobny test przed poprawką potwierdził też przyjęcie `event_type=AttemptStarted` bez pól FSM; bramka obejmuje teraz nazwane AttemptStarted/LaneCompletionAccepted/StageCompletionAccepted/CampaignConclusionAccepted. Odrzucenie nie zmienia żadnego pliku kampanii ani receipt. To bramka aktywacji, nie dowód pozytywnych guardów binding/STARTED/evidence. |
| Rozbieżność walidowanych i zapisanych zdarzeń | Store tworzy jedną głęboką kopię CJSON przed walidacją. Generator nie znika podczas wcześniejszego odczytu, a mutacja zachowanego przez wywołującego słownika po walidacji nie zmienia zapisanego commitu. Testuje się również dokładny receipt retry i restart. |
| Izolacja | Raport jawnie podaje NOT_ESTABLISHED. Nie dodano żadnego ENFORCED. Zachowany hook dla ENFORCED odrzuca nierozwiązywalne material channels. |
| CAS, crash, idempotencja, chronology | Weryfikacja istniejącego Store pozostaje oddzielna od NF02. Nie dowiedziono tych właściwości dla nowej pozytywnej ścieżki, bo jej nie aktywowano. |

## Dokładny blocker pozytywnego przyjęcia

Istniejący writer używa rozszerzeń `/1`, lokalnych schemas i starszego formatu paczek. Nie implementuje legalnej nowej kampanii z zainstalowanymi successor pins, przyjętym `assignment_package_binding`, osobnym późniejszym `STARTED` i evidence/result w kolejnych commitach. Retroaktywne przypięcie obecnych paczek nie jest dozwoloną migracją.

Wymagania nie wynikają z nowego lokalnego planu:

- `docs/R5_4_1/candidate/BDB_AUDIT_V2_DATA_AND_ARTIFACT_CONTRACTS_R5_4.md`, §15.1: „actor_ref ... nie ustanawia sam sobie authority”; authority wynika z prior accepted kontekstu lub niezależnego bootstrap root.
- `F1_QUALIFICATION/inputs/BDB_AUDIT_V2_DATA_AND_ARTIFACT_CONTRACTS.md`, §14.2–14.4 oraz §16: każda zmiana state wymaga accepted transition fact z exact prior state/ref, governing transition policy i input HistoryCut; sama legalna krawędź FSM ani nazwa typed event nie dowodzi przyjęcia wyniku. Lokalny czysty projector FSM pozostaje validator/projector, a bramka działa w produkcyjnym Store przed transakcją.
- Ten sam dokument, §192 D.2/D.3: closed binding/1, evidence/2, result/2, exact raw-backed SchemaRegistry/2 i niezależny zewnętrzny schema root. §192 E.1/E.4: unique prior binding, osobny późniejszy STARTED, serialized delivery, prior evidence i exact raw normalization. §192 H: nowa niezależna kampania, bez backfill ani in-place upgrade.
- §187.2 i §192.2: kwalifikacja author-only jest poza historią i nie jest runtime capability; design approval nie zastępuje kwalifikacji exact candidate ani niezależnej instalacji.
- `docs/R5_4_2/R5_4_2_Q1_QUALIFICATION_REPORT.md`: brak świeżego Q1 i brak runtime activation. Nie przypisano staremu raportowi statusu kwalifikacji nowego kodu.
- `docs/R5_4_2/autonomous_2026_10_07/design/SOURCE_TRUST_BUILD_PARAMETERS.json`: scope `UNQUALIFIED_CANDIDATE_INPUTS`, `guarantees=[]`, wymagany executor-write boundary i brak uwierzytelnienia/instalacji. Nie jest dostępnym trust root.
- `docs/R5_4_2/autonomous_2026_10_07/design/HISTORY_BOOTSTRAP_NF02_PARAGRAPH_REVIEW.md` oraz `tools/transition_contract.py`: istniejąca mapa wymaganych guardów; nie są produkcyjną authority ani dowodem guardów.

Zatem sama implementacja podpisu, klucza, flagi lub nowego testowego principal nie może zapewnić legalnego P0. Brakuje niezależnie uwierzytelnionej instalacji/producenta i kwalifikowanej aktywacji exact successor. Nie wystawiono fikcyjnego root, certyfikatu, ticketu ani Q1/Q2. Pozostały także lokalne elementy runtime binding/STARTED/migration, wymagające tych dokładnych zatwierdzonych pins i kontraktów; nie ogłoszono ich naprawionymi.

Najmniejszy następny krok do P0: ustanowić rzeczywistą niezależną authority instalacji/producenta dla exact kwalifikowanego NF02 successor, następnie podłączyć jego binding → STARTED → evidence/2 → result/2 do istniejącego Store w **nowej** kampanii. Wykorzystać przygotowane normalizer/predykaty i wymagane zależności bootstrap/schema/trust; nie uruchamiać ponownie całej kolejki 131 kontraktów bez konkretnej zależności. Wymagane Q1/Q2 i odpowiednie N5–N11 pozostają bramkami przed aktywacją. P1–P3 zależą od P0.

## Weryfikacja

Ruff, mypy i deterministyczny standalone build przeszły. Świeże wyniki, komendy i source/build hashes zapisane są w `RUNTIME_COMPLETION_EVIDENCE.json`. PASS isolated successor normalizer, PASS integration/product i PASS dostępnego rzeczywistego przepływu są rozdzielone; żaden nie jest Q1/Q2 lub kwalifikacją wydania.

Końcowa regresja objęła F1/F2, runner, produkt, freeze/isolation E1 i standalone build/clean environment: **274 PASS**. Osobno **6 PASS** wybranych negative NF02, bez przypisywania PASS 22 pozostałym historycznym przypadkom. Mypy: 51 source files. Build preview: SHA-256 `7f80032369513a885cd09621aa6926e02ce5d8ec0db2e0bfd57dc34e17f3e4ad`, 1504429 bajtów. Poprzednie materiały checkpointu zachowano; evidence wiąże nowe wyniki z dokładnymi hashami źródeł.

Nowa regresja `tests/product/test_transition_boundary.py` wiąże test z rzeczywistymi Attempt/LaneRun/StageRun kampanii. Obejście wykonano przed zmianą i uzyskano FAIL (Store nie odrzucił); po zmianie wymagany jest dokładny kod centralnej blokady oraz równość wszystkich bajtów kampanii. Nie oznaczono tego jako pozytywnego przyjęcia ani naprawy jeszcze niezaimplementowanego protokołu successor. Produkt nadal umożliwia operacje przygotowania, lokalny runner, odtworzenie i raport częściowy.

Osobna próba `standalone_transition_probe.py`, uruchomiona z `-I`, importuje Store wyłącznie z weryfikowanego embedded payload. Cztery próby generic command przez eventy FSM i typed events odrzucono bez receipt i bez zmiany hashy wszystkich plików rzeczywistej kampanii smoke. Skrypt i jego wynik są w `runtime_completion_evidence/`; nie tworzą authority ani Q1/Q2.

W testach użyto istniejącego `tools.product_test_tmp` zamiast Windows mkdir(mode=0700), który w sandboxie odmawia dostępu. Zamrożone self-testy legacy i sprawdzenie taskkill wymagają normalnego kontekstu hosta; ich udane przebiegi nie zmieniają źródeł ani kryteriów. Dwa negative tests oczekujące starego głębszego błędu zaktualizowano do dokładnego obecnego `PRODUCT_V1_EXTERNAL_INGESTION_BLOCKED`, zachowując atomowość i bez przypisania PASS głębszym guardom. Historyczne positive-control suites NF02 `/1` nie stanowią testów aktywnego produktu i nie otrzymują nowego PASS.

Rzeczywisty test standalone `-I` utworzył repo z błędnym clamp. Kontrola sumy wykonała się poprawnie; test midpoint wykrył błąd. ZIP z tymi faktycznymi lokalnymi dowodami został odrzucony jako inny executor, bez podszywania się pod AI. Po odrzuceniu nowy proces wznowił kampanię z identycznymi plikami historii/paczek; raport pozostał częściowy. Ostatni legalny etap: **E1_PREPARED + LOCAL_CHECKS + RESUME + PARTIAL_REPORT**.

## Definition of Done

1. Uprawnione przyjęcie rzeczywistego wyniku: **NIE**.
2. Pełne NF02 dla pozytywnej produkcyjnej ścieżki: **NIE**; wykonane konkretne naprawy i negatywne zabezpieczenia powyżej.
3. Wymagane kwalifikacje i autoryzacja aktywacji: **NIE**.
4. Rzeczywisty audyt E1–E6: **NIE**.
5. Raport końcowy zaakceptowanych ustaleń: **NIE**; raport częściowy rzeczywistych kontroli dostępny.
6. Wznowienie/integralność/nielegalne wejścia: **TAK w zdefiniowanym zakresie produktu**, bez rozszerzenia na nieaktywowany import.
7. Instrukcja uruchomienia i weryfikacji: **TAK** w `QUICKSTART_PL.md` i tym dokumencie.
