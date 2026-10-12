# Przekazanie do niezależnego Q2

**NOT_RUN. Freeze pozostaje niedopuszczony przy Q1 OPEN.** Pakiet jest materiałem do rzeczywistego review, z ujawnionymi brakami; nie wystawia decyzji w imieniu kwalifikatora. Wszystkie ścieżki są względem repozytorium. `EVIDENCE_MANIFEST.json` wiąże actual bytes; nie wystarcza nazwa gałęzi ani podany checkpoint.

Kontynuację checkpointu 4132 opisują 01/02 i `evidence/q1-closure-4132c5d/`. Nowe materiały obejmują pełne enclosing contexts, material-target/chronology/wrapper/entry-point cases oraz naprawę F11 SAME_CREATE_ASSIGNMENT_CONTENT. Końcowy status każdego QG znajduje się w 02; brak realnych owner inputs jest oddzielony w `EXTERNAL_DEPENDENCIES.json` i 10. `11_Q1_REPRODUCTION.md` podaje aktualną procedurę. Nie traktować zachowanych przebiegów sprzed F11 jako dowodu końcowego kodu; ich inputs są użyte ponownie przez rzeczywisty końcowy runtime.

## Wejście recenzenta

Recenzent otrzymuje repo/commit podany w 00_STATUS, ten katalog, frozen `NF02_P0_LIMITED_MODEL` i istniejące `nf02_p0_runtime_qualification` bez kopiowania dużych shardów. Odczytuje manifest obu zbiorów, MODEL.md §§M01–M18, całe MODEL.json/Registry, siedem profili, 43 schemas, graph i qualification matrix. Informacyjne statusy PROPOSED w zamrożonych plikach pozostają oryginalnymi bajtami; późniejsze owner approval jest odrębnym record, nie edycją normy.

Najpierw weryfikuje wszystkie file entries i oba domain-separated set hashes. Oczekiwana tożsamość: manifest `278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9`, graph `7ad1c90ee72634b633e2a9c260e5d7b93d69fc9a1bcca76632291a047f15f27e`, normative `f4aeeadd96314ef7854f61747fdf3f72caf5dfb599c4977a78170aa3620165df`, machine `7449d5eb45ca2aa49b065318d1287ac473fed54dc0e8359bcc32033215f5709d`. Liczniki 18/7/43 i Q1/Q2/RQ 11/6/32 są konieczne, ale nie wystarczają do PASS.

## Wszystkie rodziny Q2

| Rodzina | Wykonanie i wynik wymagany od niezależnego recenzenta |
|---|---|
| Q2-01 | Ustalić własną tożsamość/upoważnienie i niezależność, zweryfikować actual owner decision, candidate, obie pełne listy i graph. Rozbieżność bytes lub membership = brak freeze |
| Q2-02 | Ocenić każdy kontrakt/field/target/class/predicate, siedem profile rules/quotas, 43 schemas, inline/wire/external oraz każde M01–M18. Sprawdzić body/schema parity i znaczenie predykatów; schema-only vectors nie dowodzą authority/history |
| Q2-03 | Przeprowadzić adversarial review bootstrap/schema precedence, finite dispatch, same-content identity, prior cuts, source commit/tree, CMS role separation, storage/leases, service output i transport. Przejrzeć każdą publiczną/direct drogę, także standalone/alternate CLI/inbox/generator |
| Q2-04 | Sprawdzić findings z 01/02 i dowody fixów. Zamknąć każde mandatory finding/gap lub otrzymać konkretną dopuszczoną decyzję owner; nie tworzyć lokalnego safety waiver ani nowej normy. Mandatory safety issue blokuje freeze |
| Q2-05 | Powiązać Q1 final audit, właściwy AUTHOR_QUALIFICATION i wszystkie retained vector/reference inputs/outputs przez exact hashes, także kod harnessu/backendu. Zweryfikować owner risk/compatibility decision dla tych samych bytes i limitów |
| Q2-06 | Dopiero po pełnym closure podpisać prawidłowy zewnętrzny INDEPENDENT_FREEZE/1; code/install/RQ nadal unqualified. Nie zmieniać production gate i nie przenosić author PASS na runtime |

## Odtworzenie krytycznych dowodów

W świeżym author/review checkout użyć zgodnych wersji z environment evidence i osobnych katalogów wyniku. Nie nadpisywać zachowanych dowodów. To lokalne sprawdzenia autora, nie RQ.

```powershell
$env:PYTHONPATH='src;.'
$env:PYTHONUTF8='1'
.venv-f2/Scripts/python.exe tools/nf02_p0_limited_model.py --check
.venv-f2/Scripts/python.exe tools/nf02_p0_final_audit.py identity
.venv-f2/Scripts/python.exe tools/nf02_p0_q1.py --output-dir '<new-reference-directory>'
.venv-f2/Scripts/python.exe tools/nf02_p0_q1_semantics.py --output '<new-local-simulation-directory>'
.venv-f2/Scripts/python.exe -m pytest tests/product/test_limited_content_identity.py tests/product/test_limited_p0_transport.py tests/product/test_limited_qualification.py -q -p no:tmpdir -p tools.product_test_tmp
```

Recenzent porównuje regenerated reference files byte-for-byte z materiałami przez `03_GOLDEN_VECTOR_REGISTER.json`, a expected primitive/node decisions dodatkowo niezależną procedurą `tools/nf02_p0_reference.py`. Powtarza literal M07 one-based indexing, wrong-content-logical-ID denial, mode chain/current rights i najistotniejsze crash/CAS/replay. Reference history czyta zachowany SQLite read-only, liczy CJSON dwoma encoderami, własny digest/domain/Kahn/receipts; nie weryfikuje udawanych CMS jako prawdziwych.

Wektory danych zachowują exact bytes. Metadane `LOCAL_Q1_INPUT_CHECKS.json` mają historyczny hash procedury; aktualny `REFERENCE_INPUT_CHECKS_CURRENT.json` i `VECTOR_EXECUTION.json` jawnie pokazują zmianę wyłącznie `reference_procedures` po poprawkach typowania harnessu. Wszystkie pozostałe pola tego rekordu i wszystkie vector shards muszą być byte-equivalent; nie dopuszcza się dowolnej zmiany expected. Niezależny history readback obejmuje także klasy material refs, exact basis/index oraz odrzucenie pre-F11 kontrprzykładu.

Własny reviewer może użyć dodatkowej procedury/implementacji oracle; nie może wyprowadzić expected wyłącznie z writer response. Każda niezgodność ma exact input, expected, observed, normative clause, source binding i retest. Do zamknięcia Q1 pozostaje lista konkretnych OPEN obligations z 02, w tym enclosing/cross-field combinations oraz pełne temporal/material-target/mode/signed-input proof. Nie wolno podpisać freeze na podstawie liczby 8100/322/72.

## Wynik i podpisy

Independent review zachowuje pełną listę sprawdzonych cases/predicates, findings oraz readback i własną decyzję. `INDEPENDENT_FREEZE/1` musi przejść frozen schema, wiązać actual author/owner review/candidate digests i rzeczywisty signer qualifier. `OWNER_MODEL_DECISION/1` podpisuje owner. CMS jest detached nad exact CJSON+LF, bez sekretów w repo. Nie wygenerowano fikcyjnego review/freeze ani certyfikatu niezależności.

Pakiet obejmuje zmiany implementation/typing/SCM/quotas i świeże evidence. Historyczne R5.4.2 i jego approval/goldens nie są modyfikowane i nie dają nowej kwalifikacji. Jeżeli zostanie wykazana materialna sprzeczność frozen normy, review zapisuje SPEC_CONFLICT i przekazuje exact konflikt owner; implementacja nie zmienia normy samodzielnie.
