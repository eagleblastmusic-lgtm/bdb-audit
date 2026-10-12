# Rzeczywiste wejścia owner — PENDING_OWNER_PROVISIONING

Owner potwierdził, że `owner_actor_ref` i publiczny pin certyfikatu nie zostały formalnie ustanowione. Nie wpisano ich do rekordu kanonicznego. Nie utworzono klucza, certyfikatu, podpisu ani kwalifikacji. Ten dokument jest żądaniem wejść, nie decyzją owner.

## Ustanowienie tożsamości i publicznego pinu

1. Rzeczywisty właściciel wskazuje osobę/podmiot odpowiedzialny za decyzję oraz stabilny `owner_actor_ref`. Zamrożony `OWNER_MODEL_DECISION/1` wymaga niepustego stringu długości 1–4096; nie narzuca UUID, adresu e-mail ani formatu identyfikatora. Właściciel zatwierdza powiązanie identyfikatora z rzeczywistym podmiotem w osobnym, zachowanym protokole. Sam string nie ustanawia uprawnienia.
2. Owner/administrator PKI provisionuje rzeczywisty certyfikat podpisujący w kontrolowanej przez owner infrastrukturze. Klucz prywatny pozostaje pod jego wyłączną kontrolą (np. CNG/HSM). Nie trafia do repozytorium, pakietu ani logów. Certyfikat musi mieć ważny, zaufany łańcuch i dostępne bieżące informacje o unieważnieniu. Samopodpisany certyfikat testowy nie stanowi wymaganego dowodu.
3. Na hoście owner eksportuje się wyłącznie publiczny DER. Dla wcześniej zidentyfikowanego rzeczywistego certyfikatu PowerShell: `Export-Certificate -Cert $ownerCertificate -FilePath $publicDerPath -Type CERT`. Zmienne oznaczają wybrane przez owner rzeczywiste obiekty i ścieżki; nie należy wklejać fikcyjnego thumbprintu. Thumbprint magazynu certyfikatów nie zastępuje SHA-256 DER.
4. Obliczyć `(Get-FileHash -LiteralPath $publicDerPath -Algorithm SHA256).Hash.ToLowerInvariant()`. Drugi uprawniony operator, na niezależnie kontrolowanym hoście, odczytuje ten sam publiczny DER i liczy SHA-256, np. `certutil -hashfile <rzeczywisty-plik-DER> SHA256`. Obaj potwierdzają dokładny hash i rzeczywistą tożsamość certyfikatu oddzielnym, uwierzytelnionym kanałem. Zachować kto, kiedy, jakim kanałem oraz jakie dokładne bajty potwierdził. Dwa różne programy na jednym kontrolowanym przez producenta hoście nie dowodzą niezależnej kontroli klucza.
5. Dostarczyć `owner_actor_ref`, publiczny DER, potwierdzony SHA-256 DER oraz protokół ustanowienia/potwierdzenia. Nie dostarczać klucza prywatnego, PFX ani hasła.

## Przygotowanie i podpisanie decyzji

Po ustanowieniu rzeczywistych danych uruchomić z katalogu repozytorium:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_q1_external_inputs prepare-owner-decision --owner-actor-ref $actualOwnerActorRef --output $newUnsignedDecisionPath
```

Narzędzie tworzy nowy plik, odmawia nadpisania, sprawdza zamrożony schemat, dwa niezależne kodery CJSON i wiąże exact candidate/graph/set digests. Wynik to **niepodpisany wniosek**, nie authority. Owner odczytuje cały plik, wszystkie zaakceptowane ograniczenia i SHA-256 jego dokładnych bajtów. Każda zmiana treści wymaga nowego odczytu i hasha.

Podpis na hoście kontrolowanym przez owner, z istniejącym rzeczywistym certyfikatem:

```powershell
.\tools\nf02_p0_windows.ps1 -Mode SignDetached -Apply -CertificateSha256 $confirmedOwnerDerSha256 -InputPath $reviewedDecisionPath -OutputPath $newDetachedCmsPath
```

To podpis detached CMS/SHA-256 dokładnego pliku, z LF transportowym. Polecenie nie ustanawia Q1, Q2, RQ ani instalacji. Nie uruchomiono go w tym zadaniu. Weryfikacja dostarczonego kompletu:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_q1_external_inputs verify-owner-decision --decision $decisionPath --signature $cmsPath --certificate-der $publicDerPath --owner-pin $confirmedOwnerDerSha256 --expected-sha256 $confirmedDecisionSha256
```

Wymagane: exact SHA-256 payload/DER, zamrożony schemat, właściwy graph/model/sets, podpis dokładnych bajtów, zgodny signer DER, SHA-256, ważny łańcuch i bieżący revocation readback. Brak/expiry/unknown revocation/zmiana bajtów = odmowa. Weryfikator niczego nie instaluje i nie tworzy grantów.

## Co pozostaje zewnętrzne

| Wymaganie | Brakujące rzeczywiste wejście | Wpływ |
|---|---|---|
| M18, Q1-11 | rzeczywista tożsamość owner i podpisana exact `OWNER_MODEL_DECISION/1` z publicznym DER/pinem i potwierdzeniem | nie można wydać prawdziwego author record `READY` wskazującego `owner_decision_sha256` |
| Q1-08, M01/M02/M07 | rzeczywiście zatwierdzony namespace/root/source/view/task; osiem initial pins po ustanowieniu authority | lokalne próby bootstrap pozostają jawnie testowe; brak dowodu legalnego bootstrap rzeczywistej instalacji |
| Q1-09, M01/M02 | poprawne rzeczywiste podpisane wejścia i role; pozytywna weryfikacja CMS z kontrolowanymi kluczami i bieżącą PKI | symulowany podpis sprawdza przepływ/predykaty, nie dowodzi realnej authority |

Nie żądamy fikcyjnego Q2 freeze, RQ ani qualification mandate przed Q1. Q2 następuje po author qualification, a realny mandate/installation/grants i zewnętrzny audyt należą do późniejszego RQ. Ich przyszła zależność jest zapisana w istniejącym runbooku; nie wykonujemy tych etapów za kwalifikatora. Oddzielne kontrole owner/qualifier/Coordinator/auditor i ich rzeczywiste certyfikaty muszą zostać ustanowione przez uprawnione podmioty. Ten pakiet nie potwierdza ich niezależności.

Po dostarczeniu owner inputs wymagany jest ponowny exact readback, weryfikacja native CMS, zamknięcie właściwych wierszy macierzy i finalny audyt Q1. Sam odbiór plików nie zmienia statusu na PASS. Import produkcyjny pozostaje BLOCKED.
