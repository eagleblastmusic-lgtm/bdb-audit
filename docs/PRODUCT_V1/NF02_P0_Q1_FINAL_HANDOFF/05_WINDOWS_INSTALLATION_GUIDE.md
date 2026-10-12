# Przygotowanie instalacji Windows

Pakiet implementacyjny, bez wykonanej instalacji uprzywilejowanej i bez RQ PASS. Nie uruchomiono Install, SignDetached, StartJob, migracji ani zmian ACL na komputerze właściciela. Domyślny tryb `tools/nf02_p0_windows.ps1` jest tylko do odczytu.

## Wariant infrastruktury

Najmniejszy praktyczny wariant wykorzystuje dwa istniejące, oddzielnie administrowane hosty wykonawcze oraz istniejące stanowiska osób zarządzających. Liczba ról nie jest liczbą nowych maszyn. Nie jest konieczny zakup serwera, klastra ani publicznego hostingu aplikacji.

| Rola | Minimalne zasoby planistyczne | System i dostęp | Granica |
|---|---|---|---|
| Host usługi | 2 rdzenie/vCPU, 8 GiB RAM, 40 GiB wolnego SSD; dodatkowe miejsce na retained raw i testowe kampanie | Wspierany Windows x64, dokładny Python/Git/backend związany manifestem; lokalny SCM; egress tylko do audytora, DNS, czasu i PKI | Dedykowane konto wirtualne `NT SERVICE\BDBAuditNF02P0`, bez Administrators; DB/vault/outbox lokalne, bez SMB/NFS |
| Host audytora | 2 rdzenie, 4–8 GiB RAM, 20 GiB wolnego miejsca dla ograniczonego widoku | Może być Windows lub Linux; HTTPS odbiorczy z CA i exact DER pin; narzędzia rzeczywistego audytu zatwierdzonego zadania | Oddzielny host i administrator; brak dostępu do service host/root/code/DB/vault, governance keys i kont instalatora |
| Owner/installer | Istniejące stanowisko administratora; bez nowej maszyny przy zachowaniu kontroli klucza owner | Uprawnienia OS instalatora wyłącznie do provisioningu; signer owner poza kontem usługi | Administrator OS jest jawnie zaufany, ale nie staje się niezależnym kwalifikatorem. Kontrola SCM i kont nie nadaje podpisu audytora |
| Niezależny kwalifikator | Istniejące własne stanowisko, dostęp do repo/pakietu i obserwacji obu hostów | Własny token/keystore, kontrola review/attestation, możliwość readback i prowadzenia negatywnych prób | Owner/Coordinator/audytor nie mogą korzystać z klucza qualifier. Ujawniona zależność organizacyjna, upoważnienie i kontrola administratorów |

VM jest dopuszczalnym sposobem provisioningu dopiero po ocenie administracyjnej. Wspólny hypervisor administrator, snapshot/restore, shared folders, clipboard, sieć zarządzająca i kopie kluczy wprowadzają wspólne zaufanie. Dwie VM pod kontrolą producenta nie dowodzą niezależności audytora ani qualifier. Kwalifikator zapisuje ocenę tych granic. Nie deklaruje się ochrony przed pełnym rollback całego hosta.

Lokalne read-only probes wykazały Windows build 19045 i brak zainstalowanej usługi/root. To środowisko autorskie. Wybierz wspierany build Windows 11 Pro/Enterprise albo Windows Server; przy Windows 10 udokumentuj konkretny program obsługi/ESU i akceptację kwalifikatora. Standardowe wsparcie Home/Pro zakończyło się w 2025 r. ([Microsoft Lifecycle](https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro)); aktualny build wybiera się według [cyklu Windows 11](https://learn.microsoft.com/en-us/lifecycle/products/windows-11-home-and-pro). Podane zasoby są budżetem tego wdrożenia, bez przeprowadzonego benchmarku RQ.

## Provisioning i kolejność

1. Owner wyznacza ludzi/podmioty i hosty; qualifier zatwierdza granice administracyjne. Host audytora nie otrzymuje poświadczeń service host.
2. Installer tworzy świeży, minimalny runtime w przeznaczonej do tego lokalizacji, np. `C:\BDB-P0-Runtime`. Instaluje finalny wheel i dokładne zależności z `requirements-f2.lock`, zgodne ABI Python/rpds i Git. Nie wykorzystuje użytkownikowego środowiska deweloperskiego z pluginami i narzędziami testowymi. Nie dopisuje pakietów po pinning.
3. Zapisuje rzeczywisty `sc.exe showsid BDBAuditNF02P0` jako przyszły virtual service SID. Rozdziela konto administracyjne instalatora, signer owner i konto usługi. Konto usługi nie otrzymuje interaktywnego logowania ani governance keys.
4. Osobno provisionuje PKI/clock/network zgodnie z 06. Rzeczywiste Q1 i Q2 poprzedzają podpisany przez owner oraz qualifier `QUALIFICATION_MANDATE/1`. Ten pakiet nie zawiera gotowego mandate ani podpisów.
5. Na finalnym runtime przygotowuje assets: wszystkie manifest-pinned norm/machine files wraz z CANDIDATE_MANIFEST, rzeczywiste governance records/signatures/final audit/review oraz dwa operacyjne JSON: `SOURCE_REPOSITORIES.json` i `AUDITOR_TRANSPORT.json`. Każdy jest ścisłym CJSON + LF. Endpoint nie ma userinfo/query/fragment i odpowiada rzeczywistemu zewnętrznemu audytorowi.
6. Przygotowuje configuration o dokładnych polach: `owner_certificate_sha256`, `qualifier_certificate_sha256`, `namespace_id`, `coordinator_service_sid`, `mode`, `freeze_file`, `qualification_file`. Używa `QUALIFICATION_ONLY`; `qualification_file` wskazuje rzeczywisty mandate. Uruchamia `tools/nf02_p0_installation_packet.py --assets ... --configuration ... --output ...` finalnym interpreterem `-I -B`. Output musi być nowy. Narzędzie tworzy sześć roots/osiem pins, ENVIRONMENT i **unsigned** installation/root. Nie tworzy praw. Inventory środowiska musi mieścić się w 2 MiB; w przeciwnym razie przygotowanie odmawia i trzeba zmniejszyć runtime, bez zmiany normy.
7. Owner przegląda exact installation bytes i podpisuje `installation.json`; signature zapisuje jako `installation.p7s`. Pins root owner/qualifier są sprawdzane niezależnym kanałem. Nie przenosi prywatnych kluczy do assets.
8. Installer chroni świeże runtime/stdlib/Git/code trees i ich rodziców: owner SYSTEM/Administrators, write/delete/change-ACL tylko zaufanego instalatora, konto usługi ReadAndExecute. Kontroluje reparse points i odziedziczone reguły. Używa rzeczywistych SID. Nie wykonuje recursive takeover istniejącego Python/Git ani dysków użytkownika. Po wszystkich zmianach wykonuje ponowny exact environment readback; kwalifikator wiąże te same bytes/paths/OS.
9. Uruchamia na **upoważnionym hoście kwalifikacyjnym**, jako installer:

```powershell
# Te polecenia są procedurą do późniejszego wykonania, nie zostały wykonane przez autora.
powershell.exe -NoProfile -File tools/nf02_p0_windows.ps1 -Mode Inspect
powershell.exe -NoProfile -File tools/nf02_p0_windows.ps1 -Mode Install -Apply `
  -PythonExe 'C:\BDB-P0-Runtime\env\Scripts\python.exe' -Packet '<signed-packet>' `
  -OwnerPin '<actual SHA256 DER>' -QualifierPin '<actual SHA256 DER>'
```

Skrypt weryfikuje signed packet produkcyjnymi loader/predicate, actual code/environment i osiem pins przed instalacją. Odrzuca overwrite istniejącej usługi/root/namespace. Tworzy demand-start SCM host, read-only authority/grants i odrębny writable namespace campaign. Nie naprawia automatycznie starego niechronionego parent. Przy takim stanie installer osobno ustala bezpieczną deltę ACL. Istniejący parent musi także pozwalać kontu usługi na odczyt atrybutów/traversal potrzebny leases.

10. Installer zapewnia niepubliczny odczyt campaign DB/vault/outbox: tylko SYSTEM/Administrators i exact service SID, bez Everyone/Users/audytora. Namespace directory daje service Modify, parent jest read-only. Instaluje actual owner-signed grants w `grants/<sha256(raw)>.json` oraz `.json.p7s`; grants pozostają owner-managed, konto usługi ma tylko read. Po kopii weryfikuje ACL wszystkich plików.
11. Przeprowadza real service/ACL/PKI/transport RQ. Sam wynik `INSTALLED_NOT_RQ_PASS` nie jest kwalifikacją. Częściowy błąd instalacji pozostaje do inspekcji; skrypt nie usuwa danych i nie próbuje upgrade/migracji.

## Uruchamianie, zatrzymanie i recovery

Service ImagePath to finalny chroniony Python z `-I -B -m bdb_audit.p0_service`; brak env-root override, logowania i zapisu pyc. Host wykonuje **jedno** serializowane żądanie SCM i wraca do STOPPED. Obsługuje status/prepare/accept/prepare-release/release, a authority/state/rights weryfikuje rzeczywisty Store.

`-Mode StartJob -Apply -JobArguments ...` wywołuje StartService z argumentami. Przykład statusu używa `--store` we właściwym `C:\ProgramData\BDB Audit\P0-Campaigns\<actual-namespace-authority-digest>\campaign.sqlite`. Pliki unsigned output z prepare/prepare-release muszą znajdować się w tym samym leased campaign directory; zapis jest create-new. Signing preimage z prepare należy odczytać i podpisać exact, poza logiem usługi.

STOP/SHUTDOWN przechodzą przez STOP_PENDING i drain rozpoczętej atomowej operacji, z checkpointami co sekundę i wait hint. Forced termination jest awarią: po nowym procesie wymagany replay i exact retry. Usługa nie deklaruje PAUSE/CONTINUE; „wznowienie” oznacza ponowne uruchomienie exact signed job. SCM nie zachowuje transient StartService arguments podczas auto-restart, dlatego instalacja jest demand-start; nie konfiguruje fikcyjnego automatycznego recovery z pustymi argumentami. Operator przechowuje original packet/signature i po readback ponawia ten sam command ID/bytes. Release retry zachowuje release ID i original ZIP, z uczciwym at-least-once I/O.

Event Application/1001 zawiera stały service ID, exit code i bezpieczny error token. Nie zawiera signed bodies, signing preimage, paths, prywatnych danych ani exception detail. Brak provider, root, mandate, grant, drift, invalid ACL i nieznany transport są fail-closed. [SCM state transitions](https://learn.microsoft.com/en-us/windows/win32/services/service-status-transitions) wyjaśniają wymagane statusy i controls; w pakiecie są native negative/lease probes oraz jawna symulacja callbacków, a nie dowód działania rzeczywistej zainstalowanej usługi.

## Odbiór instalacji

Kwalifikator potwierdza actual service SID/token bez Administrators, real start/stop/drain/new-process restart, deny-write code/root, allowed DB/vault/outbox, deny-read/write audytora, leases/rename/reparse i końcowy readback. Sprawdza original source commit/tree/blob, PKI current revocation, zegar i osobny namespace. Żaden z tych wyników nie jest zastępowany lokalnym pytest z monkeypatch OS/CMS.

Aktualny rebuild po poprawce same-create: `evidence/q1-closure-4132c5d/build-current-v2/BUILD_READBACK.json`, `bdb_p0_unqualified.py` i wheel w tym samym katalogu. Starszy `evidence/build/` jest historycznym niekwalifikowanym buildem; nie stanowi dowodu naprawionego runtime. Źródła i payload LF normalization mają oddzielne exact SHA-256. Nadal nie wolno instalować ani aktywować bez właściwego upoważnienia i qualified authority.
