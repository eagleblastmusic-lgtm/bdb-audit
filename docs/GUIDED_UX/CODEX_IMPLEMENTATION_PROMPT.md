# PROMPT DO CODEXA — BDB Audit: Guided Audit UX

Wykonaj projekt UX według załączonego `BDB_AUDIT_GUIDED_UX_SPEC_v1.md`.

**Cel:** „Aplikacja prowadzi użytkownika przez audyt”. Użytkownik nie ma ręcznie wybierać kilkunastu operacji ani odnajdywać paczek ZIP na dysku. Na ekranie konkretnego audytu ma widzieć E1–E6, aktualny etap, paczki z rzeczywistymi nazwami, statusy i jedno oczywiste następne działanie.

**Repo:** `C:\Projekty\Audyty\BDB Audit`, aktualna lokalna gałąź `work/local-product-mode` i jej rzeczywisty HEAD. Użytkownik podał wcześniejszy checkpoint `3c129a2856f29742b406076927ab4a75e921a856`, ale HEAD i stan worktree trzeba zweryfikować zamiast zakładać. Nie tracisz WIP. Pracuj na osobnej gałęzi od aktualnej zweryfikowanej lokalnej wersji użytkowej.

**Zakres:**

1. Skróć menu główne do „Nowy audyt”, „Moje audyty”, „Raporty”, „Ustawienia i narzędzia” oraz „Wyjście”. Zachowaj funkcje zaawansowane kontekstowo, nie usuwaj ich z silnika.
2. Po otwarciu kampanii bezpośrednio pokazuj etap E1–E6, listę paczek **bieżącego etapu** i jeden główny krok zależny od istniejącego utrwalonego stanu.
3. Dla każdej paczki pokaż realny tytuł, slot, stan wyniku i operacje „Pokaż w Eksploratorze”, „Otwórz folder”, „Kopiuj ścieżkę”. Wymagaj rzeczywistej weryfikacji ścieżki/hash przed otwarciem. Uwzględnij Windows paths z Unicode, symlinks/reparse i błędy uprawnień. Nie uruchamiaj archiwum lub zawartości bez wyraźnej decyzji.
4. Przenieś „Import i walidacja” → „Przeczytaj i zdecyduj” → „Następny etap” do prowadzonego workflow. Zachowaj rozdzielenie importu, walidacji, podglądu i **świadomego `USER_ACCEPTED_LOCAL`**. Nie autoakceptuj niezaufanych wyników.
5. Zadbaj o odtwarzanie widoku po wznowieniu, otwieranie gotowego raportu i dostęp do receipts / porzucania kontroli wyłącznie w odpowiednim kontekście/zaawansowanych narzędziach.
6. Zachowaj separację LOCAL od HIGH ASSURANCE, pełną blokadę kwalifikowanego importu i wszystkie istniejące zabezpieczenia. Nie zmieniaj zatwierdzonego modelu 18/7/43.
7. Testuj rzeczywiste operacje w nowym TUI i Explorer; przeprowadź smoke lokalnego E1–E6 (oddziel fixtures od rzeczywistych kontroli), odtwórz po restarcie, przetestuj podmieniony/brakujący ZIP, a następnie Ruff/mypy/standalone build i regresję.

**Sposób pracy:** implementuj zamiast tworzyć kolejny dokument planistyczny. Wykorzystaj istniejące komendy i stores jako źródło prawdy. Najpierw działający TUI, nie projekt nowego frameworka ani GUI premium. Bez push, merge, force-push i release.

**Odbiór:** wszystkie AC-01–AC-12 z załączonej specyfikacji albo jawny blocker z dowodami. Dostarcz pliki źródłowe, testy, działające menu, komendę uruchomienia Windows, krótką instrukcję, dowody smoke i commit SHA. Nie deklaruj gotowości, jeśli nie możesz z poziomu audytu otworzyć prawdziwej paczki bieżącego etapu w Eksploratorze.
