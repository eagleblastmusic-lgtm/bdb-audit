# PRODUCT-V1 — aktualny stan NF02 runtime

2026-10-11. Repo: `C:\Projekty\Audyty\BDB Audit`. Gałąź robocza: `work/nf02-runtime-completion`, utworzona od `e75f14ed443d6d6c7f60359687938c1fb6b062c0`. Zastane pliki untracked i historyczne materiały zachowano. Nie wykonano push, merge, release ani zmian frozen źródeł.

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
| Izolacja | Raport jawnie podaje NOT_ESTABLISHED. Nie dodano żadnego ENFORCED. Zachowany hook dla ENFORCED odrzuca nierozwiązywalne material channels. |
| CAS, crash, idempotencja, chronology | Weryfikacja istniejącego Store pozostaje oddzielna od NF02. Nie dowiedziono tych właściwości dla nowej pozytywnej ścieżki, bo jej nie aktywowano. |

## Dokładny blocker pozytywnego przyjęcia

Istniejący writer używa rozszerzeń `/1`, lokalnych schemas i starszego formatu paczek. Nie implementuje legalnej nowej kampanii z zainstalowanymi successor pins, przyjętym `assignment_package_binding`, osobnym późniejszym `STARTED` i evidence/result w kolejnych commitach. Retroaktywne przypięcie obecnych paczek nie jest dozwoloną migracją.

Wymagania nie wynikają z nowego lokalnego planu:

- `docs/R5_4_1/candidate/BDB_AUDIT_V2_DATA_AND_ARTIFACT_CONTRACTS_R5_4.md`, §15.1: „actor_ref ... nie ustanawia sam sobie authority”; authority wynika z prior accepted kontekstu lub niezależnego bootstrap root.
- Ten sam dokument, §192 D.2/D.3: closed binding/1, evidence/2, result/2, exact raw-backed SchemaRegistry/2 i niezależny zewnętrzny schema root. §192 E.1/E.4: unique prior binding, osobny późniejszy STARTED, serialized delivery, prior evidence i exact raw normalization. §192 H: nowa niezależna kampania, bez backfill ani in-place upgrade.
- §187.2 i §192.2: kwalifikacja author-only jest poza historią i nie jest runtime capability; design approval nie zastępuje kwalifikacji exact candidate ani niezależnej instalacji.
- `docs/R5_4_2/R5_4_2_Q1_QUALIFICATION_REPORT.md`: brak świeżego Q1 i brak runtime activation. Nie przypisano staremu raportowi statusu kwalifikacji nowego kodu.
- `docs/R5_4_2/autonomous_2026_10_07/design/SOURCE_TRUST_BUILD_PARAMETERS.json`: scope `UNQUALIFIED_CANDIDATE_INPUTS`, `guarantees=[]`, wymagany executor-write boundary i brak uwierzytelnienia/instalacji. Nie jest dostępnym trust root.
- `docs/R5_4_2/autonomous_2026_10_07/design/HISTORY_BOOTSTRAP_NF02_PARAGRAPH_REVIEW.md` oraz `tools/transition_contract.py`: istniejąca mapa wymaganych guardów; nie są produkcyjną authority ani dowodem guardów.

Zatem sama implementacja podpisu, klucza, flagi lub nowego testowego principal nie może zapewnić legalnego P0. Brakuje niezależnie uwierzytelnionej instalacji/producenta i kwalifikowanej aktywacji exact successor. Nie wystawiono fikcyjnego root, certyfikatu, ticketu ani Q1/Q2. Pozostały także lokalne elementy runtime binding/STARTED/migration, wymagające tych dokładnych zatwierdzonych pins i kontraktów; nie ogłoszono ich naprawionymi.

Najmniejszy następny krok do P0: ustanowić rzeczywistą niezależną authority instalacji/producenta dla exact kwalifikowanego NF02 successor, następnie podłączyć jego binding → STARTED → evidence/2 → result/2 do istniejącego Store w **nowej** kampanii. Wykorzystać przygotowane normalizer/predykaty i wymagane zależności bootstrap/schema/trust; nie uruchamiać ponownie całej kolejki 131 kontraktów bez konkretnej zależności. Wymagane Q1/Q2 i odpowiednie N5–N11 pozostają bramkami przed aktywacją. P1–P3 zależą od P0.

## Weryfikacja

Ruff, mypy i deterministyczny standalone build przeszły. Świeże wyniki, komendy i source/build hashes zapisane są w `RUNTIME_COMPLETION_EVIDENCE.json`. PASS isolated successor normalizer, PASS integration/product i PASS dostępnego rzeczywistego przepływu są rozdzielone; żaden nie jest Q1/Q2 lub kwalifikacją wydania.

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
