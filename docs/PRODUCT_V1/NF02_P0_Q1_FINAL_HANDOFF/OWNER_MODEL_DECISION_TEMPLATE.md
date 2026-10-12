# Niekompletny szablon decyzji owner

**PENDING_OWNER_PROVISIONING — NIE JEST REKORDEM KANONICZNYM, WAŻNYM ANI PODPISANYM.**

Brakuje formalnie ustanowionego `owner_actor_ref` oraz niezależnie potwierdzonego publicznego SHA-256 DER certyfikatu owner. Poniższy fragment celowo pomija obowiązkowe `owner_actor_ref` i `accepted_limits`, więc nie przechodzi `OWNER_MODEL_DECISION/1`. Nie zapisywać go jako decyzji `.json` i nie podpisywać. Certyfikat/pin są wejściami weryfikacji podpisu, a nie dodatkowymi polami tego zamkniętego schematu.

```json
{
  "candidate_manifest_sha256": "278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9",
  "decision": "APPROVE_LIMITED_P0_MODEL",
  "machine_set_sha256": "7449d5eb45ca2aa49b065318d1287ac473fed54dc0e8359bcc32033215f5709d",
  "normative_set_sha256": "f4aeeadd96314ef7854f61747fdf3f72caf5dfb599c4977a78170aa3620165df",
  "scope_graph_sha256": "7ad1c90ee72634b633e2a9c260e5d7b93d69fc9a1bcca76632291a047f15f27e"
}
```

Owner musi jawnie zaakceptować: odrębny scope 18/7/43 i M01–M18/Q1/Q2/RQ; approved-Git-only bootstrap nowej pustej kampanii; ustalone source/view/task i jeden slot; brak migracji lub transferu assurance z R5.4.2; audyt nonblind z możliwą wcześniejszą wiedzą; wynik jako submission audytora bez finding truth/Completion/STOP/release; at-least-once delivery tych samych bajtów; brak gwarancji pełnego rollback hosta; brak aktywacji importu przez tę decyzję; zachowanie historycznego R5.4.2.

Pełne proponowane teksty `accepted_limits` i generator niepodpisanych bajtów znajdują się w `tools/nf02_p0_q1_external_inputs.py`. Procedura ustanowienia tożsamości, potwierdzenia DER i podpisania jest w `10_EXTERNAL_INPUT_REQUEST.md`. Dopiero rzeczywisty owner uzupełnia i zatwierdza ten komplet.
