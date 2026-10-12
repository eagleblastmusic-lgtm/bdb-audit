# BDB Audit — LOCAL PRODUCT MODE

Osobny workflow użytkowy bez certyfikatów i Q1/Q2/RQ. Jego historia nie jest
kwalifikowaną historią NF02. Deklaracje modeli i tożsamości producentów pozostają
niezweryfikowane nawet po ręcznej akceptacji. HIGH ASSURANCE zachowuje swoje blokady.

Pierwszy checkpoint: P0 import, walidacja struktury, ręczna akceptacja, nowa rewizja,
exact Git commit/tree, paczki E1, oddzielny magazyn i wznowienie.

Uruchamiaj w repozytorium BDB Audit:

```powershell
$env:PYTHONPATH = 'src'
$python = '.\.venv-f2\Scripts\python.exe'
& $python -m bdb_audit product local start --source 'C:\repo\aplikacja' --campaign 'C:\audyty\moj-local'
& $python -m bdb_audit product local status --campaign 'C:\audyty\moj-local'
& $python -m bdb_audit product local inspect --campaign 'C:\audyty\moj-local' --file 'C:\wyniki\odpowiedz.zip'
& $python -m bdb_audit product local import --campaign 'C:\audyty\moj-local' --file 'C:\wyniki\odpowiedz.zip'
& $python -m bdb_audit product local validate --campaign 'C:\audyty\moj-local' --result 'local-result-<sha256>'
& $python -m bdb_audit product local accept --campaign 'C:\audyty\moj-local' --result 'local-result-<sha256>' --confirm-local
```

Źródło GitHub: `--target github --source https://github.com/OWNER/REPO.git --ref main`.
Repozytorium prywatne korzysta z istniejącego dostępu Git; nie umieszczaj tokenu w URL.
Audyt obejmuje commit, nie niezapisane pliki worktree. Domyślnie wybiera wszystkie
pliki regularne; większe repozytorium wymaga jawnego zakresu `--path` (powtarzanego).
Brak obsługi symlinków, submodułów i niepobranych obiektów LFS jest jawną odmową.

Paczki znajdują się w `CAMPAIGN\packages`. Zawierają prompt, mapę źródeł i
`RESPONSE_TEMPLATE.json`. Wypełnioną odpowiedź zwróć jako JSON albo ZIP z głównym
`LOCAL_RESULT.json`. Załączniki wymagają dokładnego SHA-256 i długości. Sam zgodny
schemat/hash nie dowodzi prawdziwości treści. `NEEDS_WORK` można zachować, lecz nie
zalicza zadania. Poprawka to nowy plik i jawne `accept --replace <poprzedni-id>`.

Historia jest sprawdzana przy każdym wznowieniu. SHA-256 i łańcuch historii chronią
przed przypadkową utratą integralności, nie przed przepisaniem całego magazynu przez
administratora hosta. Przerwanie przed zapisem zdarzenia może pozostawić nieprzyjęty
blob w vault; nie staje się on wynikiem audytu. Nie przenoś danych LOCAL do NF02.
