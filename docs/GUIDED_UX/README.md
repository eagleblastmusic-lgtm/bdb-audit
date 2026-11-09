# BDB Audit — prowadzony audyt LOCAL

Aktualizacja 2026-10-13: [import zbiorczy, prompty i polityka LOCAL](BATCH_WORKFLOW.md).
STATUS.md i EVIDENCE_MANIFEST.json opisują wcześniejszy checkpoint.
[Weryfikacja tej wersji](BATCH_WORKFLOW.md#weryfikacja-wersji) obejmuje LOCAL i standalone.

Uruchom w PowerShell:

~~~powershell
& 'C:\Projekty\Audyty\BDB Audit\Run-Local-Audit.ps1'
~~~

Launcher wybiera istniejący Python z repo i ustawia PYTHONPATH. Alternatywa z katalogu repo:

~~~powershell
$env:PYTHONPATH = 'src'
& .\.venv-f2\Scripts\python.exe -m bdb_audit product local ui
~~~

Samodzielny wariant, bez projektowego site-packages:

~~~powershell
python .\dist\BDB_AUDIT_LOCAL_PRODUCT.py product local ui
~~~

Bieżący artefakt zawiera zamknięty runtime Windows x64 / CPython 3.14. Źródła nadal
korzystają z istniejących zależności projektu; nie dodano nowej zależności produkcyjnej.

## Jak pracować

1. **Nowy audyt**: podaj lokalne repo lub URL GitHub, ref/commit, opcjonalny zakres plików
   rozdzielonych znakiem | oraz nowy katalog kampanii. Aplikacja zamraża rzeczywisty
   commit/tree i przygotowuje paczki E1. Niezapisany WIP źródła nie należy do tego commitu.
2. **Moje audyty**: wybierz skrót albo **O — Otwórz istniejącą kampanię z dysku**.
   Od razu zobaczysz ekran kampanii, etap E1–E6, stan paczek, braki i jeden następny krok.
   Indeks w %LOCALAPPDATA%\BDBAudit\local-campaigns.json zawiera tylko skróty.
   Brak store nie tworzy zastępczej kampanii. Opcja CLI ui --index pozwala wskazać
   inny plik indeksu, np. dla odrębnej demonstracji.
3. Na ekranie kampanii **Enter** wykonuje pokazany następny krok.
   **1** otwiera folder paczek. **2** pozwala wybrać konkretną paczkę i następnie:
   zaznaczyć ZIP w Eksploratorze, otworzyć folder, skopiować ścieżkę lub wyeksportować
   kopię do istniejącego katalogu. Szczegóły podają oczekiwany/rzeczywisty SHA-256,
   długości, raw verification i status wyniku. Przy każdej paczce **P E1-A** pokazuje
   zamrożony prompt ze stronicowaniem, a **K E1-A** kopiuje całość jednym działaniem.
   Te same akcje są w szczegółach paczki. Działa to dla rzeczywistych ID zadań E1–E6.
4. **7 — Polityka LOCAL**: jednorazowe **WLACZ AUTO LOCAL** upoważnia automatyczne
   przyjmowanie poprawnych COMPLETE w tej kampanii. Domyślnie polityka jest wyłączona.
   Nie potwierdza prawdziwości ustaleń ani tożsamości modelu; nie kończy etapu.
5. **3 — Dodaj wynik AI** otwiera jedno natywne okno Windows: wybierz JSON i ZIP razem,
   Ctrl/Shift lub Ctrl+A. **M** pozwala wkleić wiele ścieżek rozdzielonych |.
   Przekazuj modelowi paczkę i skopiowany prompt. Szablon i pełny opis formatu są
   wewnątrz nowych paczek. Wynik zapisz np. jako E1-A_RESULT.json lub E1-A_RESULT.zip;
   ZIP nadal wymaga wewnętrznego LOCAL_RESULT.json. Starsze nazwy nadal działają.
   Poprawne wyniki są walidowane i przyjmowane zgodnie z polityką; pojedyncze błędy
   nie cofają pozostałych plików. **I** pokazuje trwałe podsumowanie, polskie błędy,
   pełną odpowiedź oraz ponowienie błędnych lub nieprzetworzonych plików.
   Bez autoakceptacji **4 — Wyniki i decyzje** nadal wymaga **AKCEPTUJ LOCAL** albo
   **ODRZUC** z powodem; Enter odkłada decyzję. Zastąpienie przyjętej rewizji wymaga
   jej dokładnego ID i świadomej decyzji. Import zbiorczy odrzuca takie konflikty.
6. Gdy silnik potwierdzi wszystkie obowiązkowe wyniki i brak pending run, Enter
   proponuje przejście. Potwierdź osobno PRZEJDZ E2, PRZEJDZ E3 itd.
   Po E5-A przygotowanie paczek E5-B pojawia się jako następny krok.
   Po E6 wpisz ZAKONCZ LOCAL: zostanie utworzony nowy eksport, a ekran pokaże
   **Raport gotowy**, rzeczywisty zakres i liczbę lokalnych decyzji.
7. **5 — Raporty** w kampanii lub **Raporty** w menu głównym: otwórz Markdown,
   pokaż JSON, pokaż folder albo utwórz kolejny eksport. Domyślne eksporty trafiają
   do CAMPAIGN\reports\<czas-uuid>; wcześniejsze katalogi i pliki nie są nadpisywane.
   Istniejący eksport spoza kampanii można zweryfikować i otworzyć przez **O**.
8. **6 — Stan i narzędzia**: szczegółowy status, przygotowanie/przywrócenie paczek,
   jawna kontrola, receipts/logi, raw evidence i raport. Odzyskanie lub porzucenie
   kontroli pojawia się wyłącznie dla rzeczywistego pending run, pokazuje szczegóły
   i wymaga ODZYSKAJ lub PORZUC. Porzucenie zachowuje powód i nie ustanawia PASS.

Po przerwaniu wybierz kampanię w **Moje audyty**. Czytanie i nawigacja nie przyjmują
wyników, nie kończą etapu i nie zmieniają accepted history. Przy brakującym ZIP
wybierz **Przygotuj / przywróć paczki**: silnik odtwarza dokładne bajty z vault.
Podmieniony plik pozostaje jawną niespójnością i nie jest nadpisywany.

## Co zmieniło się w interfejsie

| Przed | Teraz |
|---|---|
| Kilkanaście równorzędnych komend LOCAL w jednym menu | 4 działania produktowe + wyjście |
| Osobno status, paczki, import, decyzja i następny etap | Jeden ekran kampanii i CTA wyliczane z trwałego stanu |
| Użytkownik odnajduje ZIP-y na dysku | Rzeczywista lista bieżącego etapu, weryfikacja i natywne akcje Windows |
| Import i późniejsza decyzja przez oddzielne komendy | Import wielu plików → walidacja → podsumowanie; decyzja ręczna albo upoważniona polityka LOCAL |
| Wznowienie przez wpisywanie katalogu za każdym razem | Zweryfikowane skróty ostatnich kampanii i otwarcie store z dysku |
| Raport wymaga komendy i odnalezienia eksportu | Raporty w kampanii i menu głównym, Markdown/JSON/folder/nowy eksport |
| Receipt/abandon stale dostępne jako główne operacje | Narzędzia kontekstowe, tylko dla istniejącej nieukończonej kontroli |

Istniejące komendy product local i osobny formalny TUI pozostają dostępne. Wejście 8
w dotychczasowym formalnym menu uruchamia ten sam nowy LOCAL TUI.

## Granice zaufania i rzeczywiste ograniczenia

- LOCAL PRODUCT MODE pozostaje osobnym trwałym formatem. USER_ACCEPTED_LOCAL jest
  zgodą użytkową (MANUAL albo AUTO_POLICY), nie potwierdzeniem prawdziwości ustaleń ani uwierzytelnieniem audytora.
  HIGH ASSURANCE, NF02/Q1/Q2/RQ oraz model BDB_NF02_P0_LIMITED_1 (18/7/43) nie są zmienione.
- Nie ma automatycznych wywołań modeli. Wyniki EXTERNAL_AI dostarcza użytkownik;
  deklaracja modelu pozostaje niezweryfikowana. Demonstracja używa rzeczywistych
  LOCAL_CONTROL, a testy regresji oznaczają odpowiedzi TEST_FIXTURE.
- Paczka otwiera się dopiero po sprawdzeniu ścieżki z produkcyjnego statusu silnika,
  powiązanej utrwalonej tożsamości ZIP, SHA-256 i długości. Symlinki i reparse/junction
  są odmawiane. Żaden importowany JSON/ZIP nie dostarcza ścieżki do otwierania.
  Zawartość ZIP nie jest uruchamiana ani automatycznie otwierana.
- Eksplorator jest wywoływany wektorem argumentów bez powłoki. Na tym Windows
  proces potrafi zakończyć się kodem 1 po przekazaniu żądania; zaznaczenie jest wtedy
  potwierdzane przez HRESULT funkcji
  [SHOpenFolderAndSelectItems](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shopenfolderandselectitems).
  Odmowa Shell pozostaje błędem, z pełną ścieżką i możliwością ponowienia.
- Gdy brak skojarzenia Markdown, jawne otwarcie raportu korzysta z istniejącego
  Notatnika Windows. Brak schowka daje pełną ścieżkę do ręcznego skopiowania.
- Historia LOCAL jest niepodpisana. Zachowane ograniczenia runnera: brak izolacji
  całego hosta/sieci. Wykonuje wyłącznie jawnie wpisaną, potwierdzoną komendę.
- Na tym hoście brak przywileju tworzenia symlinku plikowego (WinError 1314).
  Ten jeden przypadek jest SKIP; rzeczywisty junction katalogu oraz negatywne
  przypadki przekierowania, podmiany ZIP i ścieżki w odpowiedzi mają wykonane dowody.

Dowody wykonania, kryteria AC-01–AC-12 i dokładne polecenia są w STATUS.md oraz
EVIDENCE_MANIFEST.json. Wcześniejsza dokumentacja LOCAL_PRODUCT_MODE opisuje poprzedni
checkpoint; jej zapisane dowody nie są deklaracją weryfikacji obecnego buildu.
