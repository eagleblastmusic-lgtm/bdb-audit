# Rzeczywista authority i certyfikaty

Nie wydano certyfikatów, grantów, mandate, podpisów owner/qualifier ani kwalifikacji. W local history występują wyłącznie oznaczone `TEST_ONLY_SIMULATED_CMS` bez kluczy prywatnych; nie są instalowalne jako prawdziwa authority.

## Kontrola tożsamości i kluczy

| Signer | Podpisuje | Kontrola |
|---|---|---|
| Owner | OWNER_MODEL_DECISION, AUTHOR_QUALIFICATION po Q1, installation, principal grants, owner część mandate | Real owner identity/upoważnienie; key poza service account i audytorem; token/HSM albo zabezpieczony keystore |
| Qualifier | INDEPENDENT_FREEZE, qualifier część mandate, RUNTIME_QUALIFICATION | Rzeczywiście niezależny podmiot, własna kontrola key i akceptacji exact bytes; nie używa cert owner/Coordinator/audytora |
| Coordinator | CommandEnvelope signing preimage, release request | Oddzielny actual cert i scoped grant; brak governance keys i uprawnień administratora w runtime |
| Auditor | DELIVERY_ACK oraz AUDIT_RETURN | Oddzielny actual cert, owner-approved exact assignment/slot/source/task grant; host zewnętrzny |

Cztery DER SHA-256 muszą być różne. Dodatkowo dokumentuje się ludzi, podmioty, powiązania administracyjne, możliwość eksportu kluczy, administratorów keystore, approval signer i kanał out-of-band. Same cztery hashe nie dowodzą niezależności. OS installer jest zaufanym administratorem provisioningu, a nie issuerem podpisów kwalifikatora.

Wariant minimalny: istniejąca zarządzana PKI z indywidualnymi certyfikatami signing i działającym CRL/OCSP; dla kwalifikatora własny token/keystore. Nie jest wymagany komercyjny podpis kwalifikowany jako nowa norma. Wymagana jest faktyczna tożsamość/kontrola kluczy i akceptowana przez qualifier PKI. Nie dostarczono publicznych DER/pins ani sekretów.

## CMS, ważność i revocation

Detached CMS podpisuje dokładne bytes, z jednym signerem i SHA-256 OID `2.16.840.1.101.3.4.2.1`. DER SHA-256 jest pinem; SHA-1 thumbprint Windows Store służy najwyżej do nawigacji, nie do runtime authority. Cryptographic CheckSignature, actual certificate interval i exact pin są obowiązkowe.

Dla nowych operacji P0 włączono native X509Chain Online/ExcludeRoot/NoFlag, timeout retrieval 10 s, minimum dwa chain elements i fail-closed przy błędzie, unknown/offline revocation lub nieprawidłowym chain. Leaf self-signed nie daje pozytywnej ścieżki. Konieczne są odpowiednie CA stores i dostęp do revocation infrastruktury na service host. [X509RevocationFlag](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.x509certificates.x509revocationflag) i [ChainStatus flags](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.x509certificates.x509chainstatusflags) opisują zakres i odmowy; exact pins pozostają niezależnym warunkiem.

Historyczny replay weryfikuje zachowane podpisy, grant context i certificate validity w zapisanym acceptance time; nie używa dzisiejszego expiry do przepisywania historii. Nowe write/retry/release wymagają bieżących praw i current PKI. Usunięcie/revocation signed grant jest sprawdzane pod leases i ponownie tuż przed COMMIT/delivery. Host clock i history context muszą być rzeczywiście zakwalifikowane; trace nie jest niezależnym timestamping ani anti-host-rollback anchor.

`tools/nf02_p0_windows.ps1 -Mode SignDetached -Apply -CertificateSha256 ... -InputPath ... -OutputPath ...` korzysta z jednoznacznego real CurrentUser/My certificate, wymaga private key w kontrolowanym providerze, ważnego chain/revocation i create-new output. Nie tworzy certyfikatów, kluczy ani signature fixtures. Wykonuje je wyłącznie rzeczywisty uprawniony signer po review; autor tego polecenia nie wykonywał. Podpisanie pliku o verdict PASS jest decyzją signer, nie wynikiem skryptu.

## Dokładne dane i sekwencja

1. Owner decision wiąże actual candidate manifest SHA, oba set digests, dependency graph SHA i wszystkie jawne limity M18. Używa frozen `schemas/external/OWNER_MODEL_DECISION__1.schema.json`. Zgoda w rozmowie nie zastępuje CMS w runtime.
2. Q1 record powstaje tylko po domknięciu wszystkich mandatory cases, z pełnym exact 57-file readback, retained final audit hash, `mismatch_count=0`, `independent_assurance=false`, `P0_AUTHOR_BASELINE_READY`; owner podpisuje record. Schema nie dopuszcza OPEN. Ponieważ Q1 jest OPEN, nie wygenerowano udającego gotową kwalifikację record.
3. Qualifier podpisuje exact INDEPENDENT_FREEZE wraz z independent review hash i tym samym author/owner decision/candidate; Q2 nie kwalifikuje kodu runtime.
4. Po Q1/Q2 owner i qualifier podpisują **te same** QUALIFICATION_MANDATE bytes, dla final implementation_files, osobnego qualification_namespace, `[not_before,not_after)` UTC i QUALIFICATION_ONLY. Nazwy plików owner `.p7s`, qualifier `.qualifier.p7s`. Mandate nie zawiera installation digest i nie tworzy cyklu.
5. Owner podpisuje installation record dla rzeczywistych assets, ENVIRONMENT, code, service SID, sześciu roots, external schema root oraz mandate. Protected ROOT wiąże raw installation digest, owner/qualifier pins i namespace. Namespace hash nie zawiera installation digest.
6. Grants są oddzielnymi signed external records, poza installed manifest, o nazwie actual raw SHA. Wiążą installation, campaign, source_scope_digest, view_task_digest, assignment_scope_digest, role, cert, operations i czas. Initial bootstrap ma null assignment scope; CREATE i dalsze operacje exact nonnull future assignment scope. Nowy retry wymaga nowych exact grants. OWNER_RECOVERY jest osobną uprawnioną rolą; revoked audytor nie zyskuje abort.
7. Po prawdziwym RQ qualifier podpisuje RUNTIME_QUALIFICATION z rzeczywistymi środowiskami, external run/ZIP/ACK/return oraz boundary/test evidence. Owner przygotowuje **nową** PRODUCTION installation i pustą produkcyjną campaign/namespace. Nie przenosi qualified result/history ani mandate do produkcji.

Wartości namespace/repository/source/view-task/assignment/release hash wylicza się z exact domain + NUL + CJSON preimage podanych M02/M11. UUID, actor_ref, certificate pin, własny digest lub schema-valid record sam nie nadaje praw. Pakiet wskazuje frozen schemas i produkcyjne `LimitedMachineAuthority`/`LimitedProtocol`; nie dodaje governance kind ani profilu.

## Obowiązkowe odmowy do real RQ

Wrong signer/bytes/domain/algorithm/pin, two signers, missing cert, expiry, revoked/unknown status, brak grant, niezgodne role/scope/namespace/model/code/environment, mandate expiry, mode transfer i substituted root/install/grants muszą odmówić. Wszystkie role przechodzą controls final authority recheck. Dla denied acceptance obowiązuje byte-for-byte zero mutation DB/raw/receipt/head; unknown network outcome zachowuje PREPARED i identyczny release ID/ZIP. Każde rzeczywiste sprawdzenie podpisu i expiry/revocation zostaje utrwalone jako wynik RQ, bez wywołania symulowanej MachineAuthority.
