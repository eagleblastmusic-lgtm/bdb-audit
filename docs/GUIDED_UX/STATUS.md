# Guided Audit UX — raport dostawy

Zakres: LOCAL PRODUCT MODE, prowadzony TUI i natywne operacje Windows.
Baza: 3c129a2856f29742b406076927ab4a75e921a856.
Gałąź: work/guided-audit-ux. Bez push, PR, merge, tag i release.
Zastany WIP pozostawiono; staging obejmuje wyłącznie pliki tej dostawy.

Instrukcja i komenda uruchomienia: README.md. Specyfikację i prompt paczki zapisano
bez zmiany treści obok. EVIDENCE_MANIFEST.json zawiera dokładne SHA-256 i długości
źródeł, artefaktu, testów i dowodów wykonania. Końcowy commit podaje odpowiedź dostawy;
post-commit readback jest zapisywany osobno.

## Zmiana

- ui.py: cztery działania główne, lista audytów, ekran kampanii i kontekstowa nawigacja.
- guided.py: odczyt zweryfikowanego store, dynamiczne paczki E1–E6, jedno główne działanie,
  bezpośredni podgląd oczekującego wyniku/raportu, cienka orkiestracja istniejących funkcji.
- artifacts.py: sprawdzanie ścieżki i bajtów przed akcjami Windows, symlink/reparse denial,
  clipboard fallback, kopia z exclusive creation i SHA-256, natywny fallback Shell.
- recent.py: skróty do stores/eksportów, ostatnie użycie i rzeczywista aktywność store;
  indeks nie podejmuje decyzji o stanie audytu.
- cli.py: ten sam entry point product local ui, opcjonalny --index.
- tests/product/test_guided_local_ui.py: regresje AC i kontekstowych zabezpieczeń.
  Istniejący test starego menu LOCAL dostosowano do nowej nawigacji.
- tools/local_product_smoke.py --guided: rzeczywiste kontrole i workflow przez nowy TUI.
- tools/guided_ux_verify.py: exact readback źródło/standalone, historia, raporty,
  protokoły transcriptów, JUnit i zamrożony model HIGH ASSURANCE.
- pyproject.toml: włączenie całego LOCAL do wymaganej kontroli mypy.
- dist/BDB_AUDIT_LOCAL_PRODUCT.py: zaktualizowany deterministyczny artefakt.

Silnik LOCAL, profile/stores/walidatory/runner/renderer i formalny HIGH ASSURANCE
nie były modyfikowane. Nie wprowadzono nowej zależności produkcyjnej.

## Kryteria odbioru

| Kryterium | Wykonany dowód |
|---|---|
| AC-01 | Dokładnie 4 działania + wyjście; test_main_menu_has_four_product_actions_and_no_startup_open; menu w transcriptach produkcyjnego TUI i standalone |
| AC-02 | Wybór istniejącej kampanii otwiera etap/paczki/CTA; screen/read-only/restart tests; TUI_SESSIONS.json, FINAL_SCREEN.txt |
| AC-03 | Realne SHA/statusy E1; test_stage_lists_use_engine_and_e5_gate sprawdza wszystkie listy, tytuły i faktyczne publikacje E2–E6, w tym E5-A/B |
| AC-04 | Natywne folder/select/clipboard/copy przez TUI na ścieżce ze spacjami i żółć; brakujący ZIP; Windows argument-vector i error-reporting tests |
| AC-05 | Podmiana ZIP odmawia każdej akcji bez mutacji; rzeczywisty junction; import z unsafe ZIP i artifact_path odmawiany; brak uruchamiania zawartości |
| AC-06 | Inspect przed importem, walidacja, pełny podgląd, odłożenie, osobna akceptacja/odrzucenie; rzeczywisty restart bez akceptacji; stale-preview denial |
| AC-07 | Guards silnika dla braków/pending, osobny token przejścia, rzeczywiste E1–E6; żadna nawigacja nie zatwierdza wyników |
| AC-08 | Deterministyczny view po restarcie, brakująca publikacja z vault bez nowej historii, REAL_TUI_PROCESS_RESTART.txt i REAL_PROCESS_RESTART.json |
| AC-09 | LOCAL_COMPLETED, 19 zaakceptowanych LOCAL_CONTROL; realne Markdown/JSON/folder z ekranu i bezpośrednie Enter; także eksport standalone |
| AC-10 | Realny HIGH ASSURANCE import BLOCKED, exit 2, bajty LOCAL DB bez zmian; oddzielne stores; model 18/7/43 exact bytes unchanged |
| AC-11 | 41 sesji produkcyjnego TUI, realne źródło/kontrole/importy/decyzje/E1–E6/restart/raport; podmieniony i brakujący ZIP nie mutują historii |
| AC-12 | Niniejszy raport, README z instrukcją/komendami/przed-po/ograniczeniami, źródła, testy, standalone i exact manifest |

Status kryteriów: AC-01–AC-12 spełnione w zakresie LOCAL; znany SKIP i ograniczenia obserwacji Windows podano poniżej.

## Rzeczywisty smoke

Katalog: .product-smoke/guided-ux-20261012-v4.
Kampania: local-8d3d7ceb8a3d4cc285935413e399e28a.
Exact source commit: 2df70942b30e927fe85bcf06a056fe54bf030f18.
Exact tree: 3f9e49e6bd9a35d8dc6d3dbce8cb076ae4a023a5.
Final LOCAL head: 8a577a2eca2b6c8b17fe9d20fdc63bcd5d5b2ad67e3306c919ed495f47c3b1cc.

41 sesji używa rzeczywistej funkcji produkcyjnego TUI, ze świadomymi tokenami podanymi
przez jawnego operatora automatycznego, oraz rzeczywistego restartu procesu CLI/TUI.
Nie jest to twierdzenie, że właściciel osobiście przeczytał 19 wyników.

20 zaimportowanych LOCAL_CONTROL, 19 zaakceptowanych, 1 świadomie odrzucony draft.
0 EXTERNAL_AI, 0 TEST_FIXTURE w rzeczywistym demo. Testy regresji mają osobne,
jawnie zadeklarowane fixtures. Nie wywołano zewnętrznych modeli.

Dwie rzeczywiste kontrole: unittest na zamrożonej kopii source i odczyt AST.
Sześć testów demo: 3 PASS, 3 FAIL na celowo wprowadzonych błędach — SQL injection,
brak dolnej granicy clamp i utrata aktualizacji dwóch prawdziwych wątków.
To obserwacje niepoprawnej aplikacji demonstracyjnej, nie regresje BDB.
Źródło nie było naprawiane; raport zachowuje ograniczenia i propozycje działań.

Raport: .product-smoke/guided-ux-20261012-v4/final-report/REPORT.md oraz REPORT.json.
Oryginalne ZIP-y, SQLite/vault, source bundle, protokoły TUI/CLI i checksumy są zachowane.
TUI_SESSIONS.json wiąże każdą sesję z dokładnym fragmentem TUI_TRANSCRIPT.txt.

## Weryfikacja

Wszystkie polecenia z repo, z PYTHONPATH wskazującym jego src i PYTHONUTF8=1.
Windows tests są wykonywane w zwykłym środowisku użytkownika poza sandboxem.
Użyto istniejącego -p no:tmpdir -p tools.product_test_tmp; nie zmieniano ACL ani
przywilejów użytkownika. Każda fixture ma odrębny katalog.

~~~powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTHONUTF8 = '1'
$taskPython = '.\.venv-f2\Scripts\python.exe'
& $taskPython -m pytest -q -p no:tmpdir -p tools.product_test_tmp tests/product/test_guided_local_ui.py tests/product/test_local_product.py --junitxml=docs/GUIDED_UX/evidence/final-guided-ui.xml
& $taskPython -m ruff check src build tools/local_product_smoke.py tools/guided_ux_verify.py tests/product/test_guided_local_ui.py
& $taskPython -m mypy
& $taskPython -m mypy tools/local_product_smoke.py tools/guided_ux_verify.py
& $taskPython tools/local_product_smoke.py --guided --output '.product-smoke\<nowy-katalog>'
& $taskPython -c 'from build.build_single_file import build_standalone; from pathlib import Path; print(build_standalone(Path("dist/BDB_AUDIT_LOCAL_PRODUCT.py")))'
& $taskPython -I -S dist/BDB_AUDIT_LOCAL_PRODUCT.py --verify-payload
& $taskPython -m tools.guided_ux_verify --standalone-checks --capture
& $taskPython -m tools.guided_ux_verify
~~~

Pełną listę 4 grup regresji i dokładne argv zapisuje evidence/TEST_COMMANDS.json.
Terminalne wyniki:

| Dowód | Wynik |
|---|---|
| final-guided-ui.xml: finalny TUI + LOCAL | 58 PASS, 1 SKIP |
| final-report-and-ui.xml: finalne odmowy uszkodzonych raportów i TUI | 30 PASS, 1 ten sam SKIP |
| local-interface.xml: LOCAL/product/protocol/authority/inspection/transition/Git | 126 PASS, 1 ten sam SKIP |
| source-runtime.xml: stage2/source, vault, ZIP, runner, istniejący UI i build | 141 PASS |
| qualification-boundaries.xml: niezmienione granice Q1/qualification/service/Windows | 105 PASS |
| formal-regression.xml: dokładna tożsamość, P0, transport, stan i crash/replay | 74 PASS |
| Ruff / mypy / mypy harnessów | PASS; 67 plików wymaganego mypy |
| Determinizm standalone i payload | PASS; 423 embedded files |
| Standalone -I -S: wznowienie, render TUI/JSON i eksport | PASS |
| Exact source/artifact readback | 281 źródeł i zasobów plus całkowity payload |
| HIGH ASSURANCE boundary/frozen readback | BLOCKED_AS_REQUIRED / EXACT_BYTES_UNCHANGED |

451 unikalnych PASS, 1 SKIP, 0 failures i 0 errors; duplikaty uruchomień nie są sumowane.
Dokładna tożsamość standalone: SHA-256
9ece4c70d75d5c2ae721d20809f4cc814d7f7c02b495cad666c95671ea77a458,
1 637 616 bajtów. Pełny readback jest w EVIDENCE_MANIFEST.json.
Warnings JUnit record_property i duplicate ZIP są z istniejących testów; nie zmieniano
assertions ani kryteriów, aby uzyskać wynik.

Wczesny fetch w sandboxie miał Win32 error 5 w sh.exe; ten sam test przeszedł poza
sandboxem. Pierwsza szeroka komenda nie ustawiła PYTHONPATH dla workerów crash/replay.
Oba przypadki przeszły po naprawie środowiska; finalne grupy dziedziczą prawidłowy path.
Historyczna pusta XML z błędnej komendy pozostaje w evidence/historical i nie jest
terminalnym dowodem ani częścią zestawu PASS.

## Ograniczenia

- Jeden rzeczywisty test symlinku plikowego jest SKIP z powodu WinError 1314.
  Nie zmieniano systemowych uprawnień. Rzeczywisty junction Windows został wykonany
  i zablokowany; sprawdzono również inne negatywne ścieżki i exact byte refusal.
- Computer Use odczytał rzeczywisty folder paczek ze spacjami/Unicode i rozpoznał
  otwarty REPORT.md w Notatniku. Przechwycenie obrazu dwukrotnie zakończyło się timeoutem.
  Przypadkowy Escape zatrzymał helper; mimo pozwolenia użytkownika i reinitializacji
  narzędzie zachowało stop state. Nie obchodzono tego stanu. Natywne akcje produkcyjnego
  TUI mają niezależne wykonane dowody; nie deklarujemy screenshot/visual premium PASS.
- Brak automatycznego wywoływania AI i uwierzytelniania producentów jest granicą produktu.
  LOCAL_CONTROL i lokalna akceptacja nie oznaczają NF02, Q1/Q2/RQ ani normatywnego STOP.
- Pozostałe ograniczenia unsigned LOCAL journal i runnera zostały zachowane i opisane
  w instrukcji/raporcie. Nie ma otwartego blockera wymagającego sekretu lub uprawnienia.
