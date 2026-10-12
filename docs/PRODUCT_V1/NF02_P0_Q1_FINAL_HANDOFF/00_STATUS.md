# BDB NF02 P0 — końcowy pakiet Q1

**Q1 OPEN. QG-01 i QG-02 CLOSED_LOCAL_Q1; QG-03 OPEN_EXTERNAL_INPUT; QG-04 OPEN_DEPENDS_ON_QG_03.** Nie wydano AUTHOR_QUALIFICATION. Q2/RQ NOT_RUN, produkcyjny import BLOCKED.

Kontynuacja checkpointu `4132c5d81599042ccaef21e9a92f7bb84ac88645`, gałąź `work/nf02-runtime-completion`. Zamrożony model BDB_NF02_P0_LIMITED_1 pozostaje 18/7/43. Manifest `278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9`; oba set digests i graph ponownie zweryfikowano względem zatwierdzonych bajtów. Finalny commit jest wskazany w końcowym raporcie i terminalnym POST_COMMIT_READBACK_CURRENT.json; nie wpisujemy samoodnoszącego SHA do jego własnego preimage.

Końcowa regresja: **568 PASS / 0 FAIL / 0 ERROR / 0 SKIP**. Oddzielnie 72 pary operacja–stan: 13 dozwolonych i 59 odmów. Nowe dowody: 78539 full-document schema cases / 43 schemas; 1539 material/context/entry/retry cases; 456 joint role/prepare/release/retry cases; 74 alternate entry cases; 380 replay corruption cases. Te strumienie nie są sumowane jako liczba pytest. Każdy ma expected/actual i dokładne hashe wejść albo odtwarzalne recepty. 8100 wcześniejszych wektorów i 72 primitive checks zostały ponownie sprawdzone dwoma koderami/reference interpreterem.

Naprawiono rzeczywisty błąd: Assignment mógł wskazać wcześniejszy Attempt mimo nowego Attempt w CREATE_ASSIGNMENT. Dodano dokładne powiązanie z obiektem tej komendy; te same bajty są teraz DENY bez mutacji, a wadliwa historia jest odrzucana przy replay. Pozostałe predykaty runtime, Store, Coordinator, E1, CLI, source Git i parsers wykonują prawdziwy kod. OS/CMS/HTTPS w dodatnich testach są jawnie lokalną symulacją.

Pełny rzeczywisty import closure P0 przechodzi mypy; Ruff/configured mypy i rebuild/readback PASS. Nie rozszerzano prac na legacy: historyczna klasyfikacja 131 pozostaje w 04; 83 pozostałe błędy legacy nie należą do admitted closure. Nowe narzędzia Q1 sprawdzono osobno wraz z closure.

Windows: artefakty instalatora/usługi i bezpieczne lokalne kontrole przygotowane; **rzeczywista instalacja, ACL, niezależna PKI i audyt zewnętrzny UNQUALIFIED**. Nie wykonano instalacji ani zmiany ACL. Nowy standalone/wheel mają dokładny source readback i zamkniętą bramkę bez authority.

Od owner potrzebne są rzeczywisty identyfikator, publiczny DER i niezależnie potwierdzony SHA-256 oraz podpisana exact decyzja. Procedura: 10_EXTERNAL_INPUT_REQUEST.md; jawny rejestr: EXTERNAL_DEPENDENCIES.json. Template pozostaje niekompletnym Markdownem, nie rekordem authority. Pozostałe rzeczywiste role/hosty/mandate należą do późniejszych Q2/RQ.

WIP zachowano. Nie wykonano push, merge, release, migracji ani aktywacji produkcyjnego importu.

Dodatkowe finalne dowody: **38** przypadków rzeczywiście innego commitu Git, view i task; **72** osobno zachowane pary operacja–stan (13 accept / 59 deny) z dokładnym SHA-256 bazy i pełnego packetu; **56** faktycznych odmów dla siedmiu schema-allowed, lecz operation-inapplicable basis targets we wszystkich ośmiu komendach. Każda alternatywa target 37 material fields ma teraz osobny wynik albo normatywnie uzasadnioną, wykonaną odmowę. Są to przypadki kwalifikacyjne, nie dodatkowe liczniki pytest.
