# LOCAL PRODUCT MODE — wynik wykonania

Gałąź: `work/local-product-mode`. Punkt wyjściowy: `6af9870dac12500e10af78af2750b4a10e77f406`.

## Rzeczywiście dostępne

- Lokalna kampania z Git/GitHub, preflight i dokładny commit/tree, immutable source snapshot.
- Paczki/prompty i wymagane odpowiedzi dla 19 zadań użytkowego E1–E6.
- ZIP/JSON: import nieufny, walidacja struktury/contextu/załączników, decyzja lokalna,
  odrzucenie, idempotentny duplikat oraz jawna nowa rewizja.
- Osobny format SQLite LOCAL, trwały tryb, hash chain i CAS; brak transferu historii do NF02.
- Runner rzeczywistych, jawnych komend użytkownika: exact source, exit code, stdout/stderr,
  timeout, limit wyjścia, receipt; wznowienie publikacji paczek i recovery/abandon kontroli.
- E5-B po przyjęciu E5-A, zamrożenie wejść challenge; blokada poprawiania zakończonych etapów.
- Raporty Markdown/JSON z dowodami, zaleceniami, sporami i jawnymi ograniczeniami zaufania.
- CLI, osobne menu LOCAL oraz wejście 8 w istniejącym TUI; launcher bez instalacji usługi.
- Samodzielny build Windows x64 / CPython 3.14 sprawdzony z `-I -S`, bez projektowego site-packages.

## Rzeczywista demonstracja

Kampania: `local-fe51911405094e6c938e93fa3727e394`, katalog
`.product-smoke/local-product-final/campaign`.
Source commit: `b79959dd154c2be23bbbc5273dcfc97bad8eae9f`;
tree: `3f9e49e6bd9a35d8dc6d3dbce8cb076ae4a023a5`.

94 rzeczywiste wywołania produkcyjnego entry point CLI: start, preflight, kontrole,
inspect/import/validate/accept, przejścia E1–E6 i raport. 19 zaimportowanych ZIP-ów
z deklaracją `LOCAL_CONTROL`; **0 odpowiedzi EXTERNAL_AI, 0 importowanych TEST_FIXTURE**.
Odpowiedzi demonstracyjne to jawne automatyczne przeglądy rzeczywistych obserwacji
kontroli, nie pięciu niezależnych ekspertów. Akceptację wykonał jawny operator
automatyczny w zakresie zleconej demonstracji. Wznowienie sprawdzono także w nowym
procesie Python, następnie w samodzielnym artefakcie.

Rzeczywiste testy aplikacji demonstracyjnej: **3 PASS / 3 FAIL / 0 ERROR**.
Wykryte celowe błędy: SQL injection, brak dolnej granicy clamp, utrata aktualizacji
dwóch prawdziwych wątków. Te trzy FAIL nie są błędami BDB. Skan AST: rzeczywisty SUCCESS.
Source bundle, oryginalne ZIP-y, transcript CLI, SQLite i vault pozostają na dysku;
manifest odwołuje się do nich przez dokładne ścieżki i SHA-256 bez wielkich kopii.

Raport: `.product-smoke/local-product-final/final-report/REPORT.md` oraz `REPORT.json`.
Powtórny eksport przez standalone znajduje się w `standalone-report` obok.
Publiczny GitHub został faktycznie pobrany przez produkcyjny CLI: repo `octocat/Hello-World`,
commit `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`. Powstała osobna kampania
`.product-smoke/github-local-first`, która uczciwie oczekuje na odpowiedzi E1.

## Weryfikacja i naprawione problemy

Terminalne uruchomienia obejmują **236 różnych przypadków PASS / 0 FAIL / 0 ERROR**,
po usunięciu duplikatów pomiędzy zestawami. Pełna lista node IDs pozostaje w JUnit XML.
Wśród nich: 125 kontroli P0/Store/transportu/ZIP/UI/raportu, 100 LOCAL i granic,
35 końcowych LOCAL/vault, 30 źródła oraz 5 natywnego runnera; przypadki powtarzane
nie zwiększają liczby różnych testów. Końcowe LOCAL sprawdzono też po dopięciu opisu formatu.

Naprawiono podczas pracy:

- pominięcie limitu stdout/stderr przez proces kończący się między odczytami limitu;
- kolizję współbieżnych zapisów `.json.tmp` metadanych vault; publikacja create-only
  i exact readback zachowują wcześniejszy format bajtów;
- odczyt tymczasowego cache Git przez ograniczony token Windows/Python 3.13+;
  własny disposable cache dziedziczy ACL katalogu temp, bez zmiany ACL zasobów właściciela;
- odzyskanie opublikowanych paczek po przerwaniu pomiędzy zapisem historii a plikiem ZIP.

`mypy` nowego i zmienionego zakresu: 21 plików PASS; wymagany zakres projektu:
56 plików PASS. Harnessy demonstracji i readback także przechodzą kontrolę typów.
Ruff całego `src` i nowych harnessów/testów: PASS. Nie rozszerzano napraw na legacy mypy.
Build powtórzony niezależnie daje identyczne bajty. Hash i mapowanie wszystkich
420 embedded files weryfikuje zapisany manifest oraz source/artifact readback.

Pierwsze uruchomienia Windows w sandboxie nie dowiodły fetch przez lokalny Git ani
zabicia procesu potomnego: token sandboxa odmówił utworzenia signal pipe / kontroli
procesów. Te same kontrole przeszły w zwykłym, niesandboxowanym środowisku użytkownika.
Wczesny `p4-targeted.xml` zachowuje ten historyczny FAIL; nie jest terminalnym wynikiem.
Pierwotne błędy nazw fixture i sygnatury testowego crash hook poprawiono. Późniejsze
terminalne XML zawierają poprawione wykonania; żadnego błędu nie przemianowano na PASS.

## Granica zapewnienia

Frozen model `BDB_NF02_P0_LIMITED_1` i zakres **18/7/43** pozostały nienaruszone.
Manifest: `278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9`.
Oba set digests i wszystkie zadeklarowane bajty odczytano ponownie.
HIGH ASSURANCE nadal odrzuca import produkcyjny i magazyny LOCAL.
Nie zmieniono Q1/Q2/RQ, nie wystawiono podpisu ani kwalifikacji. Dawne dowody
kwalifikacyjne zachowują historyczne związanie ze swoim kodem; nie przypisano ich
bieżącemu rozszerzonemu buildowi jako niezależnej kwalifikacji.

Nie ma znanego nieusuniętego błędu z wykonanego zakresu LOCAL. Brak automatycznych
integracji modeli, niezależnej weryfikacji tożsamości/treści, izolacji sieci i całego
filesystemu runnera, obsługi submodułów/symlinków/LFS oraz dowodu prywatnego GitHub
pozostaje jawnym ograniczeniem. Dane z modeli AI dostarczasz ręcznie. Żaden lokalny
status ukończenia nie oznacza, że aplikacja jest wolna od usterek.

Wszystkie istniejące WIP i historyczne materiały zachowano. Bez push, merge i release.
Instrukcje uruchomienia: `README.md`. Exact readback: `tools/local_product_verify.py`.
