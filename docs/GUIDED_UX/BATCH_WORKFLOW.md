# Guided LOCAL — import zbiorczy i kontrakty, 2026-10-13

Gałąź zadania: `work/guided-audit-ux`; baza: `a2013241ce21c32be6936f3dca56cfc45b7ddc98`.
Rozszerzenie LOCAL nie stanowi nowej kwalifikacji NF02. Wcześniejsze manifesty dowodów
pozostają historycznymi zapisami swoich wersji; nie przenosimy ich PASS na nowy kod.

## Uruchomienie i przebieg

```powershell
& 'C:\Projekty\Audyty\BDB Audit\Run-Local-Audit.ps1'
```

Wariant bez okien: `Run-Local-Audit.ps1 -NoGui`. Opcjonalne `-Index <ścieżka>` wybiera
inny indeks skrótów; nie zmienia źródła prawdy kampanii. Launcher czyta aktualne `src`
i korzysta z `.venv-f2\Scripts\python.exe`, z fallbackiem do `python`.

1. **Nowy audyt → Moje audyty → E1–E6 → Wyniki → Raporty** zachowuje obecny model.
   Techniczny JSON utworzonej kampanii, pliki, identyfikatory i hashe nadal są widoczne.
2. Przy każdym zadaniu **P <task_id>** pokazuje zamrożony prompt; N/P zmienia stronę,
   A pokazuje całość, K kopiuje pełną treść. **K <task_id>** z ekranu audytu kopiuje ją
   jednym działaniem. Przy braku schowka TUI pokazuje całą treść do skopiowania.
3. Przekaż modelowi odpowiednią paczkę i prompt. Nowe prompty zawierają pełny kontrakt:
   wymagane pola, enum, manifest źródła, oryginalne ścieżki/linie, deklaracje wykonania
   testów, ograniczenia i nazwę wyniku. Osobny plik promptu nie jest potrzebny.
4. Zapisz wynik np. `E1-A_RESULT.json` albo `E1-A_RESULT.zip`. Dla późniejszych etapów
   nazwa pochodzi z rzeczywistego zadania, np. `E2-CONVERGENCE_RESULT.json`,
   `E5-A-INTERACTION_RESULT.zip`, `E6-FOLLOWUP_RESULT.json`. W ZIP plik główny nadal
   nazywa się `LOCAL_RESULT.json`. Starsze nazwy są przyjmowane; przypisanie zawsze
   wynika z kanonicznych pól odpowiedzi, nie z nazwy.
5. Opcjonalnie **7 — Polityka LOCAL → WLACZ AUTO LOCAL**. Zgoda jest zapamiętana
   wyłącznie dla tej kampanii i może zostać wyłączona przez WYLACZ AUTO LOCAL.
   Zmiana polityki nie przyjmuje wstecz istniejących wyników ani nie kończy etapu.
6. **3 — Dodaj wynik AI** otwiera jedno okno Windows, z filtrem JSON/ZIP razem,
   wielokrotnym wyborem Ctrl/Shift i Ctrl+A. Anulowanie nie zapisuje zdarzeń.
   **M** pozwala wkleić ścieżki rozdzielone |, ze spacjami, Unicode i cudzysłowami.
   Headless, SSH, inne systemy i `--no-gui` korzystają z wariantu tekstowego.
7. Podsumowanie pokazuje przyjęte, czekające na decyzję, niekompletne, odrzucone
   i duplikaty. Widok kampanii odświeża się od razu. **I** otwiera trwałe szczegóły,
   H — wybiera wcześniejszą partię, J — pokazuje JSON, W — pełną zachowaną
   odpowiedź, R — ponawia błędne lub nieprzetworzone pliki. S kieruje konflikt do osobnego ręcznego rozpatrzenia,
   wymagającego ROZPATRZ REWIZJE oraz późniejszej jawnej decyzji i ID poprzedniej rewizji.
   Bez autoakceptacji decyzja nadal jest w **4 — Wyniki**.
8. Przejście etapu nadal wymaga kompletu przyjętych COMPLETE, rozstrzygniętych pending
   checks i osobnego potwierdzenia PRZEJDZ E2 itd. E5-B wymaga przyjętych E5-A.

Sprawdzenie odpowiedzi przed dostarczeniem/importem używa tego samego walidatora
i nie zmienia kampanii:

```powershell
$env:PYTHONPATH = 'C:\Projekty\Audyty\BDB Audit\src'
$taskPython = 'C:\Projekty\Audyty\BDB Audit\.venv-f2\Scripts\python.exe'
& $taskPython -m bdb_audit product local inspect --campaign 'C:\audyty\kampania' --file 'C:\wyniki\E1-A_RESULT.json'
& $taskPython -m bdb_audit product local policy --campaign 'C:\audyty\kampania' --auto-accept on
& $taskPython -m bdb_audit product local import-batch --campaign 'C:\audyty\kampania' --file 'C:\wyniki\E1-A_RESULT.json' --file 'C:\wyniki\E1-B_RESULT.zip'
```

Dotychczasowy niski poziom CLI `import → validate → accept` pozostaje zgodny.
Nowy `import-batch` wykonuje walidację i stosuje politykę kampanii także dla jednego pliku.
`prompt --campaign ... --task E1-A` zwraca pełny zamrożony tekst i jego tożsamość.

## Własność danych i zgodność

- `contract.py` jest wspólnym źródłem pól, enum, limitów, szablonu, nazw i instrukcji.
  Nie należy do kwalifikowanego Registry. Format odpowiedzi pozostaje `BDB_LOCAL_RESPONSE_1`.
- Nowe paczki zapisują `generator_version: 3` w historii i manifeście.
  Przy przekroczeniu budżetu załączników manifest wskazuje `RETAINED_IN_VAULT`.
  Paczka zawiera wtedy pełne odpowiedzi i tożsamości załączników, a oryginalne
  wyniki pozostają w vault. Generatory 1 i 2 zachowują dokładne bajty zapisanych paczek.
- Podgląd promptu czyta PROMPT.md z utrwalonego vault i sprawdza hash, manifest,
  input_package_digest oraz powiązanie z szablonem. Akcje TUI sprawdzają także
  opublikowany ZIP i jego ścieżkę. Brakujący plik odtwarza dotychczasowe prepare/resume.
- Nowe zdarzenia RESULT_IMPORTED jawnie zapisują `validation_version: 2` także
  dla odpowiedzi do dawnych paczek. Walidator odmawia nieznanych pól zagnieżdżonych,
  niewłaściwych kluczy outputs i numerów linii poza zamrożonym plikiem. Dawne zdarzenia
  bez wersji odtwarzają pierwotną walidację; zaakceptowane wyniki i ich dokładne duplikaty
  nie są reinterpretowane. Generator i walidator mają osobno wersjonowane znaczenie.
  Odczyt starych kampanii jest zgodny; nowe typy zdarzeń wymagają tego wydania lub nowszego.
- Każdy plik ma istniejące limity bezpiecznego ZIP/JSON; partia obejmuje do 128 plików
  przetwarzanych sekwencyjnie. Nie ma ekstrakcji ani wykonania treści odpowiedzi.
- Oryginalne ograniczone bajty są zapisywane w vault także przy odmowie strukturalnej.
  Przekroczenie limitu wejścia i brak dostępu do pliku są jawnymi odmowami bez pełnego
  raw. Nie ma adaptera, który dopisuje dowody, uzasadnienia lub usuwa dodatkowe dane.
- Polska diagnostyka podaje pole, ID ustalenia, dozwolone wartości i wykrytą wartość.
  Podgląd bardzo długiej błędnej wartości jest jawnie skracany do 500 znaków, a próbka
  do 20 ustaleń na błąd; liczba pozostałych jest widoczna. W udostępnia pełną oryginalną
  odpowiedź. Fragmenty niezaufanych wartości są tekstem diagnostycznym, nie obiektami
  mogącymi udawać referencje raw w dzienniku.
- `BATCH_STARTED`, `BATCH_ITEM_RECORDED`, `BATCH_FINISHED` opisują operację w tym samym
  dzienniku LOCAL. Dla pojedynczego pliku import, walidacja, ewentualna akceptacja
  i pozycja podsumowania są jednym SQLite CAS/COMMIT. Vault jest zapisany wcześniej.
  Awaria może zostawić nieprzyjęty blob; nie tworzy częściowo zaakceptowanego wyniku.
- Restart odtwarza podsumowanie i przyjęte fakty z historii. Ponowienie rozpoznaje
  dokładne duplikaty po raw SHA-256, bez powielania przyjęcia. `already_present` jest
  opisem próby zapisu, nie częścią tożsamości raw.
- Konflikty z przyjętym albo oczekującym kompletnym wynikiem nie zastępują go.
  Świadoma rewizja w I → S używa zachowanych bajtów z vault, nawet jeśli plik na dysku
  później się zmieni. Pozostaje w dotychczasowym ręcznym workflow; blokady wcześniejszych
  etapów i zamrożonych E5-A pozostają aktywne.
- `LOCAL_ACCEPTANCE_POLICY_SET` zapisuje rzeczywiste upoważnienie. `RESULT_ACCEPTED`
  zachowuje `USER_ACCEPTED_LOCAL`, dodając `mechanism: AUTO_POLICY` i hash zdarzenia
  upoważnienia, albo `MANUAL`. Stare akceptacje bez tego pola odtwarzają się jako MANUAL.
  Raport rozróżnia `local_policy_acceptance` i `local_manual_acceptance`.
- NEEDS_WORK/BLOCKED pozostają niekompletnymi obserwacjami; nie są przyjmowane jako
  COMPLETE. Autoakceptacja nie potwierdza prawdy, tożsamości, niezależnych dowodów
  ani HIGH ASSURANCE. NF02/Q1/Q2/RQ nie są zmienione.

Natywny adapter używa standardowego [GetOpenFileNameW / OPENFILENAMEW](https://learn.microsoft.com/en-us/windows/win32/api/commdlg/ns-commdlg-openfilenamew)
z flagami Explorer i ALLOWMULTISELECT oraz filtrem `*.json;*.zip`. Nie dodaje zależności
GUI do środowisk bez pulpitu. Błąd API otwiera wariant ręczny, anulowanie go nie uruchamia.

## Zmienione pliki

`src/bdb_audit/local_product/`: nowe `contract.py`, `file_dialog.py`; zmienione
`artifacts.py`, `cli.py`, `guided.py`, `profile.py`, `report.py`, `responses.py`,
`store.py`, `ui.py`, `workflow.py`. Ponadto `Run-Local-Audit.ps1`,
`tests/product/test_local_batch_workflow.py`, `tools/local_batch_smoke.py`,
`dist/BDB_AUDIT_LOCAL_PRODUCT.py`, ta dokumentacja oraz odnośniki README.

## Weryfikacja wersji

Regresja LOCAL zakończyła się wynikiem 160 PASS i 1 SKIP (uprawnienie Windows do
symlinku). F8 zakończyło się wynikiem 86 PASS, w tym próbą czterech równoległych
startów standalone. Przeszły też Ruff, mypy, demonstracja CLI E1–E6, sprawdzenie
integralności 425 plików payload, głęboki self-test oraz lokalny walidator artefaktu.

## Weryfikacja pierwotnej implementacji z 2026-10-13

Zapisane dowody dotyczą stanu z daty weryfikacji: `evidence/batch-verification.json`,
`evidence/batch-smoke.json`, `evidence/batch-launcher-tui.txt`.
Nie utworzono commitu. HEAD nadal wskazuje bazę `a2013241ce21c32be6936f3dca56cfc45b7ddc98`;
zmiany znajdują się w working tree gałęzi `work/guided-audit-ux`.

| Sprawdzenie | Wynik | Dowód |
| --- | --- | --- |
| Cały `tests/product` | 372 PASS, 1 SKIP, 0 FAIL/ERROR | `evidence/batch-product-regression.xml` |
| Końcowy zestaw LOCAL po wszystkich poprawkach: nowy batch, istniejący LOCAL i guided UI | 137 PASS, 1 SKIP, 0 FAIL/ERROR | `evidence/batch-final-local.xml` |
| Źródła, ZIP, runner, workflow UI i build/runtime closure | 141 PASS, 0 SKIP/FAIL/ERROR | `evidence/batch-source-runtime.xml` |
| Natywny adapter Windows i przekazanie całej treści do `clip.exe` | 4 PASS | `evidence/batch-windows-adapters.xml` |
| Ruff: `src build tools/local_batch_smoke.py tests/product/test_local_batch_workflow.py` | PASS | wynik polecenia |
| Mypy: skonfigurowany zakres 69 plików i osobno smoke | PASS | wynik polecenia |
| `git diff --check` | PASS | wynik polecenia |

Łącznie po odjęciu powtórzonych identyfikatorów testów: **526 PASS, 1 SKIP, 0 FAIL/ERROR**.
Pełny zestaw produktu zakończył się przed ostatnimi poprawkami wyłącznie w LOCAL;
końcowy zestaw LOCAL ponownie sprawdził wszystkie dotknięte ścieżki. Dowody niezmienionych
komponentów formalnych pozostają aktualne. Jedyny SKIP dotyczy istniejącego testu symlinku
pliku: host nie ma uprawnienia Windows, WinError 1314. Osobny rzeczywisty test junction PASS.
Pełny przebieg produktu zgłosił 68 ostrzeżeń, m.in. dla celowo powielonych wpisów ZIP;
nie było błędów testów.

Uruchomienia używały `.venv-f2\Scripts\python.exe`, `PYTHONPATH=<repo>\src` i
`PYTHONUTF8=1`. Dla fixture katalogów tymczasowych użyto istniejącego adaptera repo
`-p no:tmpdir -p tools.product_test_tmp`, ponieważ domyślny katalog pytest na tym hoście
ma błąd ACL WinError 5. Nie zmieniano ACL ani kryteriów odbioru.

```powershell
& $taskPython -m pytest -q -p no:tmpdir -p tools.product_test_tmp tests/product --junitxml=docs/GUIDED_UX/evidence/batch-product-regression.xml
& $taskPython -m pytest -q -p no:tmpdir -p tools.product_test_tmp tests/product/test_local_batch_workflow.py tests/product/test_local_product.py tests/product/test_guided_local_ui.py --junitxml=docs/GUIDED_UX/evidence/batch-final-local.xml
& $taskPython -m pytest -q -p no:tmpdir -p tools.product_test_tmp tests/stage2 tests/stage3/test_ru03_assignment_vault.py tests/f1/test_zip.py tests/runner tests/workflow/test_ui_v2_0_3.py tests/f8/test_m46_build.py tests/f8/test_runtime_build_input_closure.py --junitxml=docs/GUIDED_UX/evidence/batch-source-runtime.xml
```

Nowy zestaw zawiera 75 testów korzystających z rzeczywistego generatora, walidatora,
Git, vault i SQLite. Obejmuje wszystkie 19 zadań E1–E6 i pełny nowy przebieg etapów,
gating E5-A/B, bajtową zgodność promptu, nazwy, pięć mieszanych wyników, częściową odmowę,
duplikaty i konflikty, błędne kampanie/źródła/paczki, wszystkie zgłoszone błędy kontraktu,
referencje do linii, NEEDS_WORK/BLOCKED, zmianę polityki, ręczne rewizje, crash/rollback,
restart/resume i zgodność dawnych pakietów. Mockowane są granice OS oraz punkty awarii,
nie generator, importer lub akceptacja.

W smoke uruchomiono rzeczywisty `Run-Local-Audit.ps1 -NoGui -Index <indeks testowy>`
w PowerShell 7. Pięć plików ze spacjami i Unicode (3 ZIP + 2 JSON) zostało przyjętych
przez AUTO_POLICY. E1 zakończono osobnym potwierdzeniem i pokazano gotowe paczki E2.
Test korzystał z jawnych `TEST_FIXTURE`; nie jest nową kampanią zewnętrznego modelu AI
ani weryfikacją merytoryczną odpowiedzi Bechmark-2.

Ponowne odczyty istniejących kampanii LOCAL potwierdziły ich pełną historię E1–E6,
19 zaakceptowanych wyników, raporty i niezmienione bajty baz SQLite. Formalny import
LOCAL nadal zwraca wymagane BLOCKED, bez zmiany bazy. Normatywne i maszynowe pliki
`BDB_NF02_P0_LIMITED_1` pozostały identyczne; manifest SHA-256:
`278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9`.

Standalone przebudowano dwukrotnie do identycznych bajtów. Artefakt ma 1 654 660 bajtów,
SHA-256 `73e7691c5ce1d61d2b9330fba9d1ee563160a050458d9916c76b7bad44df791a`.
Odczyt potwierdził zgodność 283 plików źródłowych i integralność 425 plików payload.
Uruchomienie `python -I -S` sprawdziło payload, resume oraz ponowny import tych pięciu
plików już na E2: pięć duplikatów, bez dodatkowych faktów akceptacji.

Pierwszy nowy test wykrył błąd rozpoznawania duplikatów przez porównanie zmiennego
`already_present`; poprawiono tożsamość raw i ponowiono właściwe regresje. Pierwszy
`evidence/historical/batch-workflow-first-fail.xml` oraz wcześniejszy
`evidence/historical/batch-final-local-first-pass.xml` zachowano historycznie.
Końcowe dowody nie zawierają FAIL/ERROR. Dodatkowe testy zabezpieczyły diagnostykę przed
niezaufanymi obiektami przypominającymi referencje vault i nadmiernym rozmiarem podglądu.

**NOT_RUN:** fizyczny wybór Ctrl/Shift/Ctrl+A w oknie Windows, zawartość rzeczywistego
schowka po wykonaniu `clip.exe`, screenshot/pikselowa ocena TUI i czytnik ekranu.
Środowisko nie udostępnia natywnego sterowania pulpitem. ABI, flagi, filtr, pojedynczy
i zbiorczy wybór, anulowanie, Unicode, fallback i pełne bajty do procesu schowka są
sprawdzone automatycznie. Rzeczywisty tekst TUI z PowerShell został przejrzany;
nie deklarujemy akceptacji wizualnej na podstawie screenshotu. Nie wykonano ponownego
audytu zewnętrznymi modelami ani importu nieudostępnionych oryginalnych odpowiedzi AI.

## Aktualizacja lokalnej instalacji po późniejszym scaleniu

Po zatwierdzeniu i scaleniu zmian przełącz checkout na faktyczną gałąź docelową,
zachowując własne zmiany, i wykonaj `git pull --ff-only` w repo BDB Audit. Następnie
uruchom ten sam Run-Local-Audit.ps1. Nie trzeba odtwarzać kampanii ani zmieniać PKI.
Wariant standalone aktualizuje się przez zastąpienie samego programu nowym
zweryfikowanym `dist/BDB_AUDIT_LOCAL_PRODUCT.py`; katalogi kampanii pozostają osobno.
Źródła wymagają Python 3.12+ i istniejących zależności z lockfile, standalone
zawiera obecny runtime Windows x64 / CPython 3.14. Nie dodano zależności produkcyjnej.
Nie wykonano push, merge ani release.
