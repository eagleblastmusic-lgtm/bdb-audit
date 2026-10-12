"""Small local audit menu reusing the production workflow and CLI operations."""
from __future__ import annotations

import getpass
import json
import shlex
import sqlite3
from typing import Callable

from ..core.errors import ValidationError
from .profile import NOTICE
from .report import export_report
from .workflow import LocalWorkflow


def run_local_ui(input_func: Callable[[str], str] = input,
                 output_func: Callable[[str], None] = print) -> int:
    workflow: LocalWorkflow | None = None
    output_func("LOCAL PRODUCT MODE — bez certyfikatów; ręcznie przyjmowane, niezweryfikowane wyniki.")
    output_func(NOTICE)
    def show(value: object) -> None:
        output_func(json.dumps(value, ensure_ascii=False, indent=2))
    def answer(prompt: str) -> str:
        return input_func(prompt).strip().strip('"')
    while True:
        output_func("\n1 Nowy audyt  2 Wznów audyt  3 Status  4 Przygotuj/odnajdź paczki")
        output_func("5 Import i walidacja  6 Przeczytaj i zdecyduj  7 Następny etap")
        output_func("8 Lokalna kontrola  9 Raport Markdown/JSON  0 Powrót")
        output_func("R Odzyskaj receipt kontroli  A Porzuć nieukończoną kontrolę z powodem")
        try:
            choice = answer("Wybór: ").lower()
            if choice in {"0", "q", "exit"}:
                return 0
            if choice == "1":
                source = answer("Repozytorium (lokalna ścieżka lub URL GitHub): ")
                target = "github" if source.startswith(("https://", "http://", "git@", "ssh://")) else "local"
                ref = answer("Ref/commit [main dla GitHub, HEAD lokalnie]: ") or ("main" if target == "github" else "HEAD")
                campaign = answer("Nowy katalog kampanii (nie może istnieć): ")
                workflow = LocalWorkflow.start(campaign, source, ref, target)
                show(workflow.prepare())
                continue
            if choice == "2":
                workflow = LocalWorkflow(answer("Katalog kampanii: "))
                show(workflow.prepare())
                continue
            if workflow is None:
                output_func("Najpierw utwórz lub wznów kampanię (1/2).")
                continue
            workflow = LocalWorkflow(workflow.store.root)
            if choice == "3":
                show(workflow.status())
            elif choice == "4":
                show(workflow.prepare())
            elif choice == "5":
                result = workflow.import_result(answer("Plik odpowiedzi ZIP lub JSON: "))
                show(workflow.validate(result["result_id"]))
                output_func("Import nie oznacza akceptacji. Przeczytaj odpowiedź i użyj opcji 6.")
            elif choice == "6":
                results = list(workflow.results)
                for index, rid in enumerate(results, 1):
                    info = workflow.result_info(rid)
                    output_func(f"{index}. {info['response'].get('task_id')} — {info['status']} — {rid}")
                selected = answer("Numer wyniku lub pełny result_id: ")
                rid = results[int(selected) - 1] if selected.isdigit() and 1 <= int(selected) <= len(results) else selected
                show(workflow.result_info(rid))
                decision = answer("Wpisz AKCEPTUJ LOCAL, ODRZUC lub Enter (bez zmiany): ")
                if decision == "AKCEPTUJ LOCAL":
                    task = workflow.results[rid]["response"].get("task_id")
                    previous = workflow.accepted.get(task)
                    replacement = None
                    if previous and previous != rid:
                        output_func("Poprzednia przyjęta rewizja: " + previous)
                        replacement = answer("Aby zastąpić, wklej jej pełny result_id: ")
                    show(workflow.accept(rid, getpass.getuser(), confirm=True, replaces=replacement))
                elif decision == "ODRZUC":
                    show(workflow.reject(rid, answer("Powód odrzucenia: ")))
            elif choice == "7":
                show(workflow.advance())
            elif choice == "8":
                task = answer("Zadanie (np. E1-A): ")
                command = input_func("Jawna komenda kontroli (np. python -m unittest discover): ").strip()
                argv = [item.strip('"\'') for item in shlex.split(command, posix=False)]
                output_func("Ta komenda wykona kod repozytorium. Runner nie izoluje całego hosta ani sieci.")
                if answer("Wpisz URUCHOM, aby wykonać: ") == "URUCHOM":
                    show(workflow.run_check(task, argv))
            elif choice == "9":
                show(export_report(workflow, answer("Nowy katalog eksportu: ")))
            elif choice == "r":
                show(workflow.recover_check(answer("run_id oczekującej kontroli: ")))
            elif choice == "a":
                run_id = answer("run_id oczekującej kontroli: ")
                show(workflow.abandon_check(run_id, answer("Powód (nie ustanawia PASS): ")))
            else:
                output_func("Nieznany wybór.")
        except (EOFError, KeyboardInterrupt):
            output_func("Kampania zachowana. Możesz wznowić ją później.")
            return 0
        except (ValidationError, OSError, sqlite3.Error, ValueError) as exc:
            output_func("ODMOWA: " + str(exc))
