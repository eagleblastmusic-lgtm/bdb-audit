# Odtworzenie końcowego Q1

Start: dokładny checkout, Windows, zamrożone dependencies requirements-f2.lock, bez instalacji usługi/ACL. Manifest entries są względem repository_root. Najpierw SHA-256 wszystkich entries, następnie `tools/nf02_p0_limited_model.py --check`. Nie traktować historycznego wadliwego DB jako valid campaign.

```powershell
$env:PYTHONPATH = 'src'
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_q1_finalize checks
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_final_audit vectors
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_final_audit matrix
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_final_audit regression
.\.venv-f2\Scripts\python.exe -m tools.nf02_p0_q1_readback
```

Long-running harness CLI: `nf02_p0_q1_contexts --output NEW_DIRECTORY`; `nf02_p0_q1_adversarial --replay-templates RETAINED_TEMPLATES --output NEW_DIRECTORY`; `nf02_p0_q1_history --source RETAINED_SQLITE --output NEW_DIRECTORY`; `nf02_p0_q1_supplement` i `nf02_p0_q1_entrypoints` przyjmują `--source`, `--templates`, `--output`. Wszystkie moduły uruchamia się przez `python -m tools.<nazwa>`. Nowe katalogi są wymagane, aby zachować stare dowody. Nie używać opcji reuse-cases do twierdzenia, że runtime ponownie wykonał te przypadki.

Retained integration inputs wiążą rzeczywistą lokalizację approved Git repository wpisaną w testowym SOURCE_REPOSITORIES.json. Exact replay wymaga tego samego checkout path i retained Git bytes. Na nowym hoście `nf02_p0_q1_adversarial --output NEW_DIRECTORY` buduje od nowa rzeczywiste repozytoria, historie i testowe authority; nowe UUID i verified_at dają nowe exact hashes. Expected predicates nadal wynikają z zamrożonej normy. Local simulated OS/CMS/HTTPS nie stają się real authority przez regenerację.

Finalny readback odtwarza full schema inputs i replay recipes, ponawia independent expected checks oraz wiąże inputs/outputs. Material-field case index jest w FINAL_Q1_AUDIT.json, szczegóły 37 pól i wszystkich kontraktowych predykatów w 02. Exact input hashes są w każdym JSONL wierszu; duże ciągi/tablice są receptami bez redundantnych kopii. Regression JUnit zawiera raw Git object/manifest/archive properties.

Realne owner inputs: wyłącznie procedura 10, bez zastępowania braków testowym podpisem. Q1/Q2/RQ i authority pozostają odrębnymi bramkami. Narzędzia checks/build/readback/assemble nie tworzą kwalifikacyjnego podpisu ani produkcyjnej authority.

Pełny zakres kontekstów jest kompozycją `contexts-final/EXECUTED_PROCEDURE.py` oraz `EXECUTED_COMMON_ROOT_COMPLEMENT.py`: COMMON/1 jest celowo `not:{}` library root, ma siedem wykonanych odmów, a jego inline definitions mają enclosing contexts; State enum ma 14 node cases i pełną FSM. `EXECUTED_READBACK_PROCEDURE.py` przyspiesza jedynie konstrukcję inputów niezależnym interpreterem, zawsze sprawdzając ich pierwotne exact hashes; nie zastępuje runtime/SUT. Dodatkowe case scripts i FINALIZE_EXTRA_EVIDENCE.py zapisują końcowe source/state/target proofs. Każdy wymaga nowego output directory lub świeżego checkoutu evidence; nie nadpisywać zachowanych wyników.
