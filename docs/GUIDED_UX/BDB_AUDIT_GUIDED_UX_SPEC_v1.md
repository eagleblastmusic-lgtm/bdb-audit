# BDB Audit — Guided Audit UX v1.0

**Status:** projekt funkcjonalny do implementacji (nie deklaracja, że opisane ekrany już istnieją).  
**Produkt docelowy:** `LOCAL PRODUCT MODE`, istniejące CLI/TUI, Windows x64.  
**Cel:** „Aplikacja prowadzi użytkownika przez audyt”, pokazuje paczki bieżącego etapu i umożliwia ich otwarcie bez samodzielnego szukania plików.

## 1. Zasady produktu

1. **Jedno główne następne działanie (decision first).** Na ekranie kampanii widoczny jest stan audytu, blokada i wyraźne CTA wynikające ze stanu, np. „Otwórz paczki”, „Dodaj wyniki”, „Sprawdź i zatwierdź”, „Przejdź do E2”, „Otwórz raport”.
2. **Nie ukrywamy dowodów ani ograniczeń.** Status `LOCAL` jest jawny. `USER_ACCEPTED_LOCAL` nie oznacza uwierzytelnionego audytora, `NF02/Q1/Q2/RQ` nie są odblokowane w HIGH ASSURANCE.
3. **Paczki są częścią interfejsu**, a nie plikami, których użytkownik samodzielnie szuka w systemie plików.
4. **Akceptacja wyników AI jest decyzją użytkownika.** Import, walidacja, podgląd i świadoma akceptacja to oddzielne, sprawdzalne kroki; nie wolno autoprzyjmować niezaufanego materiału.
5. **Postęp etapu jest wyliczany z utrwalonego stanu**, nie z flagi GUI. Jeden proces lub restart nie powinien zmieniać statusów bez rzeczywistych operacji workflow.
6. **Nie rozbudowywać nowego silnika audytowego.** Zmiana skupia się na UX i cienkiej warstwie orkiestracji obecnych, testowanych komend `product local ...`.

## 2. Struktura menu

### Menu główne — tylko 4 pozycje

```text
┌───────────────────────────────────────────────────────────────┐
│ BDB Audit                              LOCAL PRODUCT MODE     │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  1  Nowy audyt                                                │
│  2  Moje audyty                                               │
│  3  Raporty                                                   │
│  4  Ustawienia i narzędzia                                    │
│                                                               │
│  0  Wyjście                                                   │
└───────────────────────────────────────────────────────────────┘
```

Opcje istniejącego menu (`Status`, `Wznów`, `Paczki`, `Import i walidacja`, `Przeczytaj i zdecyduj`, `Następny etap`, `Lokalna kontrola`, `Raport`, `Receipt`, `Porzuć kontrolę`) nie znikają z silnika. Przenosimy je do kontekstu konkretnej kampanii/etapu lub do narzędzi zaawansowanych.

### Ekran kampanii — jedno centrum pracy

```text
┌──────────────────────────────────────────────────────────────────────┐
│ BDB Audit  /  Moje audyty  /  Projekt X                       LOCAL  │
├──────────────────────────────────────────────────────────────────────┤
│ Repozytorium: Projekt X                 Commit: a13b8d2…             │
│ Audyt: E1 z E6                         Stan: oczekuje na wyniki AI   │
│ [● E1]──[○ E2]──[○ E3]──[○ E4]──[○ E5]──[○ E6]                       │
├──────────────────────────────────────────────────────────────────────┤
│ PACZKI BIEŻĄCEGO ETAPU — E1                                          │
│                                                                      │
│  A  General Systems & Architecture         [GOTOWA]   [WYNIK BRAK]   │
│  B  Security, Trust & Authority            [GOTOWA]   [WYNIK BRAK]   │
│  C  State, Persistence & Recovery          [GOTOWA]   [WYNIK BRAK]   │
│  D  Data, Catalog & Parsing                [GOTOWA]   [WYNIK BRAK]   │
│  E  Concurrency, Resources & Oracles       [GOTOWA]   [WYNIK BRAK]   │
│                                                                      │
│  [1] Otwórz folder paczek                                            │
│  [2] Wybierz paczkę i pokaż w Eksploratorze                          │
│  [3] Skopiuj ścieżkę lub wyeksportuj kopię paczki                    │
├──────────────────────────────────────────────────────────────────────┤
│ NASTĘPNY KROK                                                        │
│ Paczki są gotowe. Przekaż je audytorom AI i dodaj otrzymane wyniki.  │
│                                                                      │
│  [4] Dodaj wynik AI      [5] Stan szczegółowy      [0] Wstecz        │
└──────────────────────────────────────────────────────────────────────┘
```

Przykładowe tytuły A–E odnoszą się do znanych pięciu paczek E1. **Liczba zadań i nazwy w E2–E6 muszą być pobierane z rzeczywistych danych kampanii**, nie kopiowane na sztywno z E1.

## 3. Zasada inteligentnego „następnego kroku”

| Stan rzeczywisty | Ekran informuje | Główne działanie |
|---|---|---|
| Brak kampanii | Wybierz repo i ref | **Nowy audyt** |
| Source/preflight wymaga naprawy | Problem z Git/ref/uprawnieniami | **Napraw i sprawdź ponownie** |
| Etap utworzony, paczki brakują | Trwa przygotowanie / błąd przygotowania | **Przygotuj paczki** lub **Ponów bez utraty historii** |
| Paczki przygotowane | Lista wszystkich paczek etapu + status każdej | **Otwórz paczki** |
| Paczki gotowe; oczekiwanie na wyniki | Widoczna lista brakujących wyników | **Dodaj wynik AI** |
| Zaimportowany materiał, walidacja negatywna | Dokładny problem w pliku, źródle lub slocie | **Popraw / wybierz inny wynik** |
| Poprawny strukturalnie, niezaufany wynik | Podgląd findings, model deklarowany, dowody i ryzyka | **Sprawdź i zatwierdź lokalnie** |
| Etap ma brakujące obowiązkowe wyniki | Lista braków; blokada przejścia | **Dokończ etap** |
| Etap kompletny według zasad LOCAL | Jawne podsumowanie i zgoda użytkownika | **Przejdź do E(n+1)** |
| E6 zakończone | Raport i zakres/ograniczenia | **Otwórz raport** |
| Przerwany audyt | Obecny utrwalony stan | **Wznów od ostatniego bezpiecznego punktu** |

**Automatyzacja:** można bez pytania przygotować widok, odczytać status, odświeżyć listę paczek i zaproponować kolejny krok. Nie wolno automatycznie ufać wynikom AI, zatwierdzać findings, dopisywać historii bez właściwej operacji ani przełączać do High Assurance.

## 4. Paczki — odkrywanie i otwieranie bez szukania plików

### Prezentacja paczek

Każda paczka pokazuje:
- Slot/id oraz tytuł zadania i etap.
- Stan: `GOTOWA`, `BRAK PLIKU`, `NIESPÓJNA`, `ZASTĄPIONA / WYMAGA WERYFIKACJI` (wyłącznie jeśli dane rzeczywiście wspierają taki stan).
- Oczekiwany i rzeczywisty SHA-256 bajtów ZIP, długość i weryfikację raw (w szczegółach).
- Status wyniku: `BRAK`, `IMPORTOWANY_NIEZAUFANY`, `WYMAGA_DECYZJI`, `ZAAKCEPTOWANY_LOKALNIE`, `ODRZUCONY`.
- Trzy działania: **Pokaż w Eksploratorze**, **Otwórz folder**, **Kopiuj ścieżkę**; opcjonalnie **Otwórz archiwum ZIP** po świadomym wyborze użytkownika.

### Rzeczywista integracja z Windows

1. Źródło ścieżki: zapisany metadanymi kampanii artefakt paczki bieżącego etapu. Nie wolno generować ścieżki wyłącznie z tytułu/slotu ani ufać ścieżce z importowanego wyniku AI.
2. Przed akcją: potwierdzić istnienie, oczekiwaną lokalizację oraz SHA-256 względem utrwalonej tożsamości paczki. Odmówić przy niespójności lub niebezpiecznym przekierowaniu/reparse do lokalizacji poza dozwolonym katalogiem artefaktów.
3. **Pokaż paczkę**: otworzyć Eksplorator Windows z zaznaczeniem konkretnego ZIP (`explorer.exe /select,<absolute-path>`), bez `shell=True` i bez uruchamiania zawartości ZIP. Testować ścieżki ze spacjami i Unicode. Nie opierać zabezpieczeń na samym łączeniu łańcuchów.
4. **Otwórz folder**: otworzyć katalog rzeczywistych paczek aktualnego etapu z zaufanej lokalizacji kampanii. W przypadku kilku katalogów pokazać listę zamiast zgadywać.
5. **Kopiuj ścieżkę**: schowek tylko na wyraźne żądanie, a gdy nie jest dostępny — wyświetlenie pełnej ścieżki do skopiowania.
6. **Eksportuj kopię**: wybór katalogu docelowego, bez nadpisania istniejącego pliku, SHA-256 po skopiowaniu. Nie przenosić oryginału, nie zmieniać historii kampanii i nie oznaczać kopii jako nowego bindingu.
7. Brak Eksploratora / błąd uprawnień: czytelny komunikat z rzeczywistą pełną ścieżką i opcją ponowienia; nigdy „otwarto”, jeśli wywołanie się nie udało.
8. Nie otwierać paczek automatycznie w chwili startu aplikacji; jeden przycisk pozwala uniknąć wielu niechcianych okien.

### Import odpowiedzi audytora

Przycisk **Dodaj wynik AI** → wybór pliku ZIP/JSON → strukturalna walidacja → podgląd (deklarowany model, zakres, ustalenia, wymagane dowody, błędy) → osobna zgoda **Zatwierdź lokalnie** albo **Odrzuć**. Dane `USER_ACCEPTED_LOCAL` to akceptacja użytkowa, nie dowód pochodzenia/kwalifikacji. Brak autoprzyjmowania przy powrocie do menu lub kliknięciu Następny etap.

## 5. Moje audyty

- Lista znanych kampanii: nazwa, repo/ref, exact commit, ostatni etap E1–E6, ostatnia aktywność, stan; sortowanie ostatnio używane najpierw.
- Wybór kampanii: od razu otwiera ekran opisany w §2, nie tylko surowe submenu „wznów/status”.
- Indeks ostatnich kampanii stanowi jedynie skróty do rzeczywistych stores. Autorytatywny jest odczyt i weryfikacja store; usunięte/przeniesione pliki oznaczyć jako brakujące, bez tworzenia zastępczej historii.
- Osobne „Otwórz istniejącą kampanię z dysku” dla braku wpisu w indeksie.

## 6. Raporty

- Po E6 ekran prezentuje „Raport gotowy” wraz z dokładnym zakresem, liczbą zaakceptowanych lokalnie wyników i znanymi ograniczeniami.
- Akcje **Otwórz raport Markdown**, **Pokaż raport JSON**, **Pokaż folder eksportu**, **Utwórz kolejny eksport** (nowy plik, nie nadpisuj).
- Nie twierdzić, że model AI wykonał pracę, jeśli kampania ukończona na kontrolach `LOCAL_CONTROL`. Raport musi rozróżniać rzeczywiste typy źródeł i lokalne decyzje.

## 7. Ustawienia i narzędzia — funkcje drugoplanowe

- Szczegółowy stan i walidacja integralności kampanii.
- Bieżący raw hash, receipts, eksport logów i inspekcja dowodów.
- Lokalna kontrola: dostępna w etapie, jeśli właściwa dla zadania.
- **Odzyskaj receipt** i **Porzuć nieukończoną kontrolę**: tylko gdy dotyczy rzeczywistego, trwającego runa; szczegóły, wyraźne potwierdzenie, zachowanie powodu i zgodna z silnikiem operacja.
- Diagnostyka/tryb zaawansowany; HIGH ASSURANCE widoczny jako oddzielny, nadal zablokowany tryb, nigdy nie przełącza się przez edycję flagi.

## 8. Wymagania implementacyjne

1. Najpierw zinwentaryzować faktyczne obecne komendy `product local`, struktury paczek/statusów i CLI/TUI w bieżącym lokalnym HEAD (nie sugerować się jedynie starszymi snapshotami GitHub).
2. Dodać cienki **controller stanu ekranu** nad istniejącym workflow, a nie kopiować protokołu do menu.
3. Dla bieżącego etapu dynamicznie pobierać listę paczek i związane z nimi wyniki. Dane po restarcie identyczne jak przed nim.
4. Wszystkie działania plikowe i nawigacja wywołują realną, testowaną funkcję; żadnych atrap lub tylko wydrukowanych etykiet.
5. Przy obsłudze Windows Explorer nie budować polecenia shell i nie przekazywać dowolnej ścieżki z ZIP/JSON.
6. Nawigacja nie może dokonywać autonomicznej akceptacji, zmieniać accepted history ani wykonywać przejścia etapu bez istniejących guardów LOCAL.
7. Nie zmieniać `BDB_NF02_P0_LIMITED_1`, jej kontraktów ani formalnej centralnej blokady HIGH ASSURANCE.
8. Nie robić pełnego redesignu graficznego w tym etapie. Najpierw czytelne TUI i działający Windows Explorer; ewentualna przyszła GUI pozostaje odrębnym projektem.

## 9. Kryteria odbioru — obowiązkowe

- **AC-01:** menu główne ma maksymalnie 4 działania produktowe + wyjście.
- **AC-02:** po wybraniu istniejącego audytu program pokazuje etap, dynamiczną listę paczek i jedno najważniejsze następne działanie.
- **AC-03:** dla E1 pięć rzeczywistych paczek jest widocznych z poprawnymi SHA/statusami; E2–E6 korzystają z faktycznych list z silnika (bez hardcode liczby).
- **AC-04:** z poziomu pojedynczej paczki można otworzyć Eksplorator z zaznaczeniem pliku; oddzielnie można otworzyć folder i skopiować ścieżkę. Testy działają na path ze spacjami/Unicode i na brakujących plikach.
- **AC-05:** podmieniony ZIP jest blokowany przed otwarciem jako „prawidłowa paczka”. Nie można przez symlink/reparse/input ZIP skierować akcji otwierania poza zaufany obszar artefaktów.
- **AC-06:** wybór „Dodaj wynik” prowadzi przez walidację i podgląd, wymaga osobnego `Zatwierdź lokalnie`.
- **AC-07:** po kompletowaniu obowiązkowych zadań lokalnego etapu ekran pokazuje zgodne z silnikiem przejście do kolejnego etapu; nie omija bramek i nie zatwierdza samodzielnie wyników.
- **AC-08:** restart i wznowienie odtwarza bieżący etap, statusy paczek i wcześniej podjęte decyzje.
- **AC-09:** raport końcowy po rzeczywistym LOCAL E1–E6 otwiera się z ekranu, zachowuje rozróżnienie provenance/LOCAL_CONTROL/AI, Markdown i JSON.
- **AC-10:** REGRESJA — HIGH ASSURANCE import nadal BLOCKED; tryby mają odrębne trwałe dane i nie mogą się wzajemnie promować.
- **AC-11:** demo E1–E6 obejmuje nawigację nowym TUI, import, decyzję, wznowienie, raport; przypadki negatywne nie mutują kampanii.
- **AC-12:** końcowy raport dostawy zawiera instrukcję użytkownika, komendę uruchomienia, testy, zmianę interfejsu przed/po i znane ograniczenia.

## 10. Sugerowana kolejność prac

1. Inwentaryzacja istniejącego CLI/UI i minimalna mapa stanów.
2. Widok bieżącego etapu + lista paczek.
3. Windows Explorer / path / copy / export z bezpiecznym sprawdzaniem bajtów.
4. Kontekstowa akcja import → review → local accept.
5. Przejście E1–E6 i wznowienie.
6. Menu główne + raporty + narzędzia zaawansowane.
7. Rzeczywiste smoke na małym repo, regresja, standalone build, instrukcja, commit.

**Granice wdrożenia:** Bez automatycznego wywoływania modeli AI, bez nowych roszczeń o prawdziwość findings, bez zmian normy High Assurance. Nie robić push/merge/release bez dodatkowej zgody.
