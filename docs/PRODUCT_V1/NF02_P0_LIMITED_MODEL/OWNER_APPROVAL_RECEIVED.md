# Otrzymana decyzja właściciela — 2026-10-11

Właściciel w tej rozmowie wydał decyzję: **„ZATWIERDZAM model BDB_NF02_P0_LIMITED_1 i przejście do implementacji oraz kwalifikacji Q1/Q2/RQ”**. Zatwierdzenie obejmuje 18 kontraktów canonical, 7 profili, 43 schematy, M01–M18 oraz ograniczenia MODEL.md §9. Pełny R5.4.2 pozostaje nienaruszony. Zezwolenie obejmuje implementację i przygotowanie kwalifikacji; nie ustanawia authority, kwalifikacji PASS ani aktywacji importu. Push, merge i release nie są zatwierdzone.

Przed zapisaniem tego dokumentu sprawdzono rzeczywiste bajty wszystkich wpisów obu zbiorów oraz ich zgodność z obiektami Git checkpointu `63256bf2d8092332bc54f357fbff8e135f738e5f`. Wynik: **0 rozbieżności**, 55 wpisów w każdym zbiorze, 57 różnych plików.

| Tożsamość zatwierdzonego, niezmienionego kandydata | Zweryfikowana wartość |
| --- | --- |
| CANDIDATE_MANIFEST.json — raw SHA-256 | `278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9` |
| DEPENDENCY_GRAPH.json — raw SHA-256 | `7ad1c90ee72634b633e2a9c260e5d7b93d69fc9a1bcca76632291a047f15f27e` |
| normative_set_sha256 | `f4aeeadd96314ef7854f61747fdf3f72caf5dfb599c4977a78170aa3620165df` |
| machine_set_sha256 | `7449d5eb45ca2aa49b065318d1287ac473fed54dc0e8359bcc32033215f5709d` |

Oba set digests obliczono ponownie według zatwierdzonego preimage, z posortowanych wpisów `(file, sha256, bytes)` i odpowiedniej domeny, separatora NUL oraz CJSON. Manifest i graf sprawdzono niezależnie jako RawDigest. Commit i tree mają różne, prawidłowo rozpoznane tożsamości: commit wskazany powyżej, tree `5ae64ddbae0ec3de1c7cdbacfa3077e5bce6f999`.

Ten dokument jest **niepodpisanym zapisem faktycznie otrzymanego polecenia**, sporządzonym przez implementatora. Nie jest wystawionym za właściciela podpisanym `OWNER_MODEL_DECISION/1`, nie podaje fikcyjnego actor/certyfikatu i nie może stanowić runtime authority. Do instalacji potrzebne będą rzeczywiste podpisane wejścia właściciela i niezależnego kwalifikatora, opisane w M18. Zatwierdzone pliki kandydata zachowują swoje oryginalne bajty, także historyczne oznaczenie PROPOSED.
