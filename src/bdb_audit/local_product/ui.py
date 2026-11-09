"""Guided local audit TUI over the existing production workflow."""
from __future__ import annotations

from datetime import datetime
import getpass
import json
from pathlib import Path
import shlex
import sqlite3
import sys
import shutil
from typing import Any, Callable, Sequence
import unicodedata

from ..core.errors import ValidationError
from .artifacts import WindowsActions
from .guided import CampaignController
from .profile import NOTICE, STAGES
from .recent import RecentCampaigns
from .workflow import LocalWorkflow


def parse_manual_paths(value: str) -> list[str]:
    # | cannot occur in a Windows filename; spaces and Unicode remain intact.
    return [part.strip().strip('"') for part in value.split("|") if part.strip().strip('"')]


def prompt_pages(text: str, lines: int = 24) -> list[str]:
    content = text.splitlines(keepends=True)
    return ["".join(content[i:i + lines]) for i in range(0, len(content), lines)] or [""]


def one_line(value: object) -> str:
    return "".join(f"\\u{ord(ch):04x}" if unicodedata.category(ch).startswith("C") or ch in "\u2028\u2029"
                   else ch for ch in str(value))


def render_import_summary(batch: dict[str, Any], *, details: bool = False) -> str:
    labels = {"ACCEPTED": "OK — przyjęty lokalnie przez politykę AUTO",
              "VALIDATED": "OK — VALIDATED_STRUCTURE; czeka na decyzję",
              "INCOMPLETE": "NIEKOMPLETNY — zachowano obserwacje; zadanie nieukończone",
              "DUPLICATE": "DUPLIKAT — bez zastąpienia wyniku",
              "REJECTED": "BŁĄD — odrzucony", "CONFLICT": "KONFLIKT — zachowano poprzedni wynik"}
    lines = ["", "IMPORT WYNIKÓW — " + batch.get("stage_id", "LOCAL") + " | " + batch["status"]]
    for number, row in enumerate(batch["items"], 1):
        task = str(row.get("task_id") or "?")
        if len(task) > 120:
            task = task[:120] + "…"
        lines.append(f"{number}. {one_line(Path(row['file']).name)} | {one_line(task)} | {labels[row['outcome']]}")
        if row["issues"]:
            lines.append("  " + "; ".join(one_line(d["message"] + (": " + d["field"] if d.get("field") else ""))
                                           for d in row["diagnostics"]))
        if details:
            for diagnostic in row["diagnostics"]:
                lines.append("  " + one_line(diagnostic["code"] + ": " + diagnostic["message"]))
                for finding in diagnostic.get("findings", []):
                    lines.append(f"  Ustalenie {one_line(finding['id'])} — wykryto: {one_line(finding['detected'])}")
                if diagnostic.get("allowed"):
                    lines.append("  Dozwolone wartości: " + ", ".join(map(one_line, diagnostic["allowed"])))
                if diagnostic.get("finding_ids"):
                    lines.append("  Ustalenia: " + ", ".join(map(one_line, diagnostic["finding_ids"])))
                if diagnostic.get("additional_findings_in_raw"):
                    lines.append(f"  Dalsze ustalenia: {diagnostic['additional_findings_in_raw']} — pełna odpowiedź w podglądzie W.")
    lines.extend([f"Zaimportowano: {batch['imported']} | Przyjęto AUTO: {batch['accepted']} | "
                  f"Odrzucono: {batch['rejected']} | Duplikaty: {batch['duplicates']}",
                  "LOCAL: sprawdzono formalny kontrakt; prawdziwość ustaleń i tożsamość modelu pozostają niezweryfikowane."])
    if batch.get("remaining_files"):
        lines.append("Przerwany import — nieprzetworzone pliki: " + ", ".join(map(one_line, batch["remaining_files"])))
    return "\n".join(lines)


def render_campaign(view: dict[str, Any]) -> str:
    status = view["status"]
    source = status["source"]
    next_step = view["next"]
    progress = " ── ".join((" [● " if p["state"] == "BIEŻĄCY" else "[✓ " if p["state"] == "UKOŃCZONY" else "[○ ")
                           + p["stage"] + "]" for p in view["progress"])
    lines = ["", "═" * 76, f"BDB Audit / Moje audyty / {one_line(view['name'])}                 LOCAL",
             "═" * 76, "Repozytorium: " + one_line(source["location"]), "Ref: " + one_line(source["requested_ref"]),
             "Exact commit: " + source["commit"], f"Audyt: {view['stage']} z E6 | {status['status']}", progress,
             "Autoakceptacja LOCAL: " + ("WŁĄCZONA dla tej kampanii" if status["acceptance_policy"]["enabled"] else "WYŁĄCZONA — ręczna decyzja"),
             "", "PACZKI BIEŻĄCEGO ETAPU — " + view["stage"]]
    for number, row in enumerate(view["packages"], 1):
        lines.extend([f"  {number}. {row['task_id']} | {row['title']}",
                      f"     [{row['state']}] [WYNIK: {row['result_state']}]",
                      "     ZIP SHA-256: " + row.get("expected_sha256", "brak utrwalonej paczki")
                      + (" | raw OK" if row["raw_verified"] else " | brak potwierdzenia raw"),
                      f"     Prompt {row['task_id']}: [P {row['task_id']}] Pokaż  [K {row['task_id']}] Kopiuj"
                      if row["prompt_available"] else "     Prompt będzie dostępny po przygotowaniu paczki",
                      f"     Zwróć: {row['suggested_result_json']} lub {row['suggested_result_zip']}"])
        if row.get("error"):
            lines.append("     Problem: " + one_line(row["error"]))
        if row.get("last_import_error"):
            lines.append("     Ostatni import: " + one_line(row["last_import_error"]))
    if status["batch_imports"]:
        batch = status["batch_imports"][-1]
        lines.append(f"Ostatni import {batch['stage_id']}: {batch['processed']}/{batch['selected']} plików | "
                     f"przyjęto AUTO {batch['accepted']} | odrzucono {batch['rejected']} | {batch['status']} [I Szczegóły]")
    if status["missing_results"]:
        lines.append("Brakujące obowiązkowe wyniki: " + ", ".join(status["missing_results"]))
    if view["workflow_stage"] == "COMPLETE":
        ready = any(r.get("verified") and r.get("history_head") == status["history_head"] for r in view["reports"])
        lines.extend(["", "Raport gotowy" if ready else "E1–E6 ukończone lokalnie. Raport czeka na eksport.",
                      "Zaakceptowane lokalnie: " + str(view["accepted_count"]) + "; źródła: " + str(view["producer_counts"]),
                      "Zakres: " + source["scope"] + "; plików: " + str(len(source["paths"])),
                      "Ograniczenia: deklaracje AI i tożsamości niezweryfikowane; LOCAL_CONTROL oznacza lokalne kontrole."])
    lines.extend(["", "NASTĘPNY KROK: " + next_step["label"], next_step["message"],
                  "[Enter] " + next_step["label"], "", "1 Otwórz folder paczek   2 Wybierz paczkę / szczegóły / Eksplorator",
                  "3 Dodaj wynik AI         4 Wyniki i decyzje",
                  "5 Raporty                6 Stan i narzędzia   0 Menu główne",
                  "7 Polityka LOCAL         I Podsumowanie importu   M Wklej ścieżki wyników",
                  "LOCAL: USER_ACCEPTED_LOCAL jest decyzją użytkową; NF02/Q1/Q2/RQ pozostają zablokowane."])
    return "\n".join(lines)


def run_local_ui(input_func: Callable[[str], str] = input,
                 output_func: Callable[[str], None] = print, *,
                 index_path: str | Path | None = None, actions: WindowsActions | None = None,
                 actor: str | None = None, no_gui: bool = False) -> int:
    recent = RecentCampaigns(index_path)
    controller: CampaignController | None = None
    actor = actor if actor is not None else getpass.getuser()

    def output(value: str) -> None:
        # Untrusted claims and source names must not control the terminal.
        output_func("".join(ch if ch in "\n\t" or not unicodedata.category(ch).startswith("C")
                            and ch not in "\u2028\u2029" else f"\\u{ord(ch):04x}" for ch in value))

    def show(value: object) -> None:
        output(json.dumps(value, ensure_ascii=False, indent=2))

    def answer(prompt: str) -> str:
        value = input_func(prompt).strip()
        return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value

    def remember(selected: CampaignController) -> None:
        try:
            recent.remember(selected.workflow())
        except (OSError, ValueError) as exc:
            output("Nie zapisano skrótu ostatnich audytów: " + str(exc) + ". Kampania pozostaje dostępna z dysku.")

    def choose_campaign() -> CampaignController | None:
        try:
            entries = recent.entries()
        except (OSError, ValueError, sqlite3.Error) as exc:
            output("Indeks skrótów niedostępny: " + str(exc))
            entries = []
        output("\nMOJE AUDYTY — stores są źródłem prawdy; indeks zawiera jedynie skróty.")
        for number, entry in enumerate(entries, 1):
            output(f"{number}. {one_line(entry['name'])} | {entry.get('stage', '?')} | {entry['state']}")
            if "source" in entry:
                source = entry["source"]
                active = datetime.fromtimestamp(entry["last_activity"]).astimezone().isoformat(timespec="seconds")
                output(f"   {one_line(source['location'])} | ref {one_line(source['requested_ref'])} | commit {source['commit']}")
                output(f"   Aktywność store: {active} | zdarzenia: {entry['history_events']}")
            else:
                output("   " + entry.get("error", "Brak store"))
            output("   " + entry["path"])
        output("O Otwórz istniejącą kampanię z dysku   0 Wstecz")
        choice = answer("Audyt (numer / O): ")
        if choice == "0":
            return None
        if choice.lower() == "o":
            location = answer("Katalog kampanii: ")
        elif choice.isdigit() and 1 <= int(choice) <= len(entries):
            location = entries[int(choice) - 1]["path"]
        else:
            raise ValidationError("LOCAL_CAMPAIGN_SELECTION_INVALID")
        selected = CampaignController(location, actions=actions, recent=recent)
        remember(selected)
        return selected

    def choose_task(selected: CampaignController) -> str | None:
        rows = selected.view()["packages"]
        for number, row in enumerate(rows, 1):
            output(f"{number}. {row['task_id']} [{row['state']}] — {row['title']}")
        value = answer("Numer paczki lub task_id (0 Wstecz): ")
        if value == "0":
            return None
        if value.isdigit() and 1 <= int(value) <= len(rows):
            return rows[int(value) - 1]["task_id"]
        if value in {row["task_id"] for row in rows}:
            return value
        raise ValidationError("LOCAL_PACKAGE_SELECTION_INVALID")

    def display_prompt(selected: CampaignController, task: str) -> None:
        prompt = selected.prompt(task)
        pages = prompt_pages(prompt["text"], max(6, min(32, shutil.get_terminal_size((80, 32)).lines - 8)))
        page = 0
        while True:
            output(f"\nPROMPT {task} — strona {page + 1}/{len(pages)} | SHA-256 {prompt['prompt_sha256']}")
            output(pages[page])
            choice = answer("N następna / P poprzednia / A całość / K kopiuj pełny prompt / 0 Wstecz: ").lower()
            if choice == "0":
                return
            if choice in {"n", ""}:
                page = min(page + 1, len(pages) - 1)
            elif choice == "p":
                page = max(0, page - 1)
            elif choice == "a":
                output(prompt["text"])
            elif choice == "k":
                copy_prompt(selected, task)

    def copy_prompt(selected: CampaignController, task: str) -> None:
        prompt = selected.copy_prompt(task)
        if prompt["copied"]:
            output(f"Skopiowano pełny prompt {task} ({len(prompt['text'])} znaków).")
        else:
            output("Schowek niedostępny. Pełny prompt do skopiowania:")
            output(prompt["text"])

    def packages(selected: CampaignController) -> None:
        task = choose_task(selected)
        if task is None:
            return
        while True:
            row = next(r for r in selected.view()["packages"] if r["task_id"] == task)
            show(row)
            output("1 Pokaż w Eksploratorze   2 Otwórz folder   3 Kopiuj ścieżkę   4 Eksportuj kopię")
            output("5 Pokaż prompt           6 Kopiuj pełny prompt   0 Wstecz")
            choice = answer("Paczka: ")
            if choice == "0":
                return
            try:
                if choice == "1":
                    output("Przekazano Eksploratorowi zaznaczenie pliku: " + str(selected.select_package(task)))
                elif choice == "2":
                    output("Przekazano Eksploratorowi folder: " + str(selected.open_package_folder(task)))
                elif choice == "3":
                    data = selected.copy_package_path(task)
                    output(("Skopiowano ścieżkę: " if data["copied"] else "Schowek niedostępny. Ścieżka do skopiowania: ") + data["path"])
                elif choice == "4":
                    output("Kopia zweryfikowana SHA-256: " + str(selected.export_package(task, answer("Istniejący katalog docelowy: "))))
                elif choice == "5":
                    display_prompt(selected, task)
                elif choice == "6":
                    copy_prompt(selected, task)
                else:
                    output("Nieznany wybór.")
            except (ValidationError, OSError, ValueError) as exc:
                output("ODMOWA: " + str(exc))
                output("Rzeczywista ścieżka paczki: " + str(row["path"]) + ". Możesz ponowić działanie w tym menu.")

    def review(selected: CampaignController, result_id: str | None = None) -> None:
        workflow = selected.workflow()
        if result_id is None:
            results = [rid for rid, r in workflow.results.items() if r["response"].get("stage_id") == workflow.stage]
            if not results:
                output("Brak wyników bieżącego etapu. Dodaj plik ZIP/JSON.")
                return
            for number, rid in enumerate(results, 1):
                info = workflow.result_info(rid)
                output(f"{number}. {one_line(info['response'].get('task_id'))} | {info['status']} | {rid}")
            value = answer("Numer wyniku / result_id (0 Wstecz): ")
            if value == "0":
                return
            result_id = results[int(value) - 1] if value.isdigit() and 1 <= int(value) <= len(results) else value
        info = selected.preview(result_id)
        output("\nPODGLĄD — deklarowany producent/model, zakres, findings, dowody i ograniczenia")
        show(info)
        if info["status"] == "IMPORTED_UNTRUSTED":
            if answer("Wpisz SPRAWDZ, aby zapisać walidację struktury; Enter bez zmiany: ") != "SPRAWDZ":
                return
            selected.workflow(info["history_head"]).validate(result_id)
            info = selected.preview(result_id)
            show(info)
        if info["status"] != "VALIDATED_STRUCTURE":
            output("Ten wynik nie oczekuje na akceptację. Błędy/odrzucenie wymagają nowego, poprawionego pliku.")
            return
        if info["response"]["completion"] != "COMPLETE":
            output("Wynik niekompletny — zachowano obserwacje. Popraw odpowiedź i dodaj nowy plik; etap pozostaje otwarty.")
            return
        output("Zatwierdź lokalnie: pozwalasz użyć treści, bez potwierdzenia prawdziwości i tożsamości audytora.")
        decision = answer("Wpisz AKCEPTUJ LOCAL, ODRZUC albo Enter (decyzja później): ")
        if decision == "AKCEPTUJ LOCAL":
            previous = selected.workflow(info["history_head"]).accepted.get(info["response"]["task_id"])
            replacement = None
            if previous and previous != result_id:
                output("Poprzednia przyjęta rewizja: " + previous)
                replacement = answer("Aby świadomie zastąpić, wklej jej pełny result_id: ")
            show(selected.decide(result_id, decision, actor=actor, expected_head=info["history_head"], replaces=replacement))
        elif decision == "ODRZUC":
            show(selected.decide(result_id, decision, actor=actor, expected_head=info["history_head"], reason=answer("Powód odrzucenia: ")))
        elif decision:
            output("Brak decyzji: wymagane dokładne AKCEPTUJ LOCAL lub ODRZUC.")

    def add_result(selected: CampaignController, *, manual: bool = False) -> None:
        output("Wybierz JSON i ZIP razem — Ctrl/Shift lub Ctrl+A. Każdy plik przechodzi pełną walidację LOCAL.")
        files: Sequence[str | Path] | None = None
        try:
            if not manual:
                files = selected.actions.choose_results(interactive=not no_gui and input_func is input and sys.stdin.isatty())
        except OSError as exc:
            output(str(exc) + ". Dostępne ręczne wskazanie plików.")
        if files is None:
            value = input_func("Ścieżki JSON/ZIP (oddziel |; można wkleić cudzysłowy; Enter Wstecz): ").strip()
            files = parse_manual_paths(value)
        if not files:
            output("Anulowano wybór. Stan kampanii bez zmian.")
            return
        output(f"Importowanie {len(files)} plików; po zakończeniu zobaczysz zbiorczy wynik.")
        batch = selected.import_results(list(files))
        output(render_import_summary(batch))
        output("I — szczegóły błędów / pełny JSON / ponów; 4 — Wyniki i decyzje. Widok audytu odświeżony.")
        if len(files) == len(batch["items"]) == 1 and batch["items"][0]["outcome"] == "VALIDATED":
            review(selected, batch["items"][0]["result_id"])

    def import_summary(selected: CampaignController) -> None:
        batches = selected.workflow().batch_summaries()
        if not batches:
            output("Brak zapisanych importów zbiorczych.")
            return
        batch = batches[-1]
        while True:
            output(render_import_summary(batch, details=True))
            choice = answer("J JSON / W pełna odpowiedź / R ponów / S rozpatrz konflikt / H historia partii / 0 Audyt: ").lower()
            if choice in {"0", ""}:
                return
            if choice == "h":
                history = list(reversed(selected.workflow().batch_summaries()))
                for position, row in enumerate(history, 1):
                    output(f"{position}. {row['stage_id']} | {row['status']} | {row['processed']}/{row['selected']} | {row['batch_id']}")
                number_text = answer("Numer partii (0 Wstecz): ")
                if number_text.isdigit() and 1 <= int(number_text) <= len(history):
                    batch = history[int(number_text) - 1]
            elif choice == "j":
                show(batch)
            elif choice == "w":
                number = answer("Numer pliku z podsumowania (od 1): ")
                if number.isdigit():
                    show(selected.workflow().batch_item_info(batch["batch_id"], int(number) - 1))
            elif choice == "s":
                number = answer("Numer konfliktującego pliku (od 1; Enter Wstecz): ")
                if number.isdigit():
                    output("Oddzielny ręczny podgląd zachowanych bajtów. Poprzedni wynik pozostaje przyjęty; polityka AUTO nie rozstrzyga konfliktu.")
                    if answer("Wpisz ROZPATRZ REWIZJE, aby przygotować ten wynik do ręcznej decyzji: ") == "ROZPATRZ REWIZJE":
                        staged = selected.workflow().review_batch_conflict(batch["batch_id"], int(number) - 1)
                        review(selected, staged["result_id"])
            elif choice == "r":
                retry = [r["file"] for r in batch["items"] if r["outcome"] in {"REJECTED", "CONFLICT"}] + batch["remaining_files"]
                if retry:
                    batch = selected.import_results(retry)
                else:
                    output("Brak plików wymagających ponowienia.")

    def policy(selected: CampaignController) -> None:
        workflow = selected.workflow()
        output("Autoakceptacja przyjmuje wyłącznie poprawne COMPLETE do użytku LOCAL. Nie potwierdza prawdziwości ani HIGH ASSURANCE.")
        output("Polityka jest zapamiętana dla kampanii; nie kończy etapów i nie zastępuje konfliktujących wyników.")
        token = "WYLACZ AUTO LOCAL" if workflow.acceptance_policy["enabled"] else "WLACZ AUTO LOCAL"
        if answer("Wpisz " + token + ", aby zmienić politykę; Enter bez zmiany: ") == token:
            selected.set_acceptance_policy(not workflow.acceptance_policy["enabled"], actor, workflow.head)
            output("Zapisano politykę kampanii w historii LOCAL.")

    def reports(selected: CampaignController) -> None:
        while True:
            view = selected.view()
            rows = view["reports"]
            output("\nRAPORTY — " + ("E1–E6 ukończone lokalnie" if view["workflow_stage"] == "COMPLETE" else "audyt częściowy"))
            for number, row in enumerate(rows, 1):
                output(f"{number}. {row['path']} | " + (row["status"] if row["verified"] else "NIESPÓJNY: " + row["error"]))
            output("N Utwórz kolejny eksport (nowy katalog)   O Otwórz istniejący eksport z dysku   0 Wstecz")
            value = answer("Raport: ")
            if value == "0":
                return
            if value.lower() == "n":
                location = answer("Nowy katalog eksportu [Enter: automatyczna nowa nazwa]: ")
                exported = selected.export_report(location or None)
                show(exported)
                root = exported["output"]
            elif value.lower() == "o":
                root = answer("Katalog istniejącego eksportu: ")
                show(selected.verify_report(root))
                try:
                    recent.remember(selected.workflow(), root)
                except (OSError, ValueError) as exc:
                    output("Eksport zweryfikowany; skrót niedostępny: " + str(exc))
            elif value.isdigit() and 1 <= int(value) <= len(rows):
                root = rows[int(value) - 1]["path"]
            else:
                output("Nieznany wybór.")
                continue
            while True:
                output("Eksport: " + root)
                output("1 Otwórz raport Markdown   2 Pokaż raport JSON   3 Pokaż folder eksportu   0 Wstecz")
                action = answer("Działanie raportu: ")
                if action == "0":
                    break
                mapping = {"1": "markdown", "2": "json", "3": "folder"}
                if action not in mapping:
                    continue
                try:
                    result = selected.open_report(root, mapping[action])
                    output(result if action == "2" else "Przekazano do otwarcia: " + result)
                except (ValidationError, OSError, ValueError) as exc:
                    output("ODMOWA: " + str(exc) + ". Eksport: " + root + ". Możesz ponowić lub pokazać JSON.")

    def tools(selected: CampaignController) -> None:
        while True:
            workflow = selected.workflow()
            output("\nSTAN I NARZĘDZIA — " + str(selected.root))
            output("1 Szczegółowy stan / integralność   2 Przygotuj / przywróć paczki")
            output("3 Jawna lokalna kontrola           4 Receipts i logi kontroli")
            output("5 Inspekcja raw dowodu             6 Eksport raportu i manifestu   0 Wstecz")
            if workflow.pending_runs:
                show(list(workflow.pending_runs.values()))
                output("R Odzyskaj receipt utrwalony w historii   A Porzuć nieukończoną kontrolę (z powodem)")
            choice = answer("Narzędzie: ").lower()
            if choice == "0":
                return
            if choice == "1":
                show(workflow.status())
            elif choice == "2":
                show(selected.prepare())
            elif choice == "3":
                task = choose_task(selected)
                if task is None:
                    continue
                command = input_func("Jawna komenda kontroli: ").strip()
                argv = [item.strip('"\'') for item in shlex.split(command, posix=False)]
                output("Ta komenda wykona kod zamrożonego repozytorium. Runner nie izoluje całego hosta ani sieci.")
                if answer("Wpisz URUCHOM, aby wykonać: ") == "URUCHOM":
                    show(workflow.run_check(task, argv))
            elif choice == "4":
                show({"receipts": workflow.runs, "pending": list(workflow.pending_runs.values()), "abandoned": workflow.abandoned_runs})
            elif choice == "5":
                digest = answer("Utrwalony raw SHA-256 z paczki, wyniku lub receipt: ")
                raw = workflow.store.vault.read_bytes(digest)
                show({"raw_sha256": digest, "byte_length": len(raw), "preview_utf8": raw[:4096].decode("utf-8", errors="replace")})
            elif choice == "6":
                show(selected.export_report(answer("Nowy katalog eksportu [Enter: automatyczny]: ") or None))
            elif choice in {"r", "a"} and workflow.pending_runs:
                run_id = answer("run_id z listy oczekujących kontroli: ")
                if run_id not in workflow.pending_runs:
                    raise ValidationError("LOCAL_PENDING_CHECK_NOT_FOUND")
                show(workflow.pending_runs[run_id])
                if choice == "r" and answer("Wpisz ODZYSKAJ, aby odczytać dowód zapisany w historii: ") == "ODZYSKAJ":
                    show(workflow.recover_check(run_id))
                elif choice == "a":
                    reason = answer("Powód porzucenia (nie ustanawia PASS): ")
                    if answer("Wpisz PORZUC, aby zapisać decyzję i powód w historii: ") == "PORZUC":
                        show(workflow.abandon_check(run_id, reason))
            else:
                output("Nieznany wybór lub brak rzeczywistego pending run.")

    output("LOCAL PRODUCT MODE — bez certyfikatów; lokalne przyjęcie nie weryfikuje prawdziwości ustaleń.")
    output(NOTICE)
    while True:
        try:
            if controller is None:
                output("\nBDB Audit                         LOCAL PRODUCT MODE")
                output("1 Nowy audyt\n2 Moje audyty\n3 Raporty\n4 Ustawienia i narzędzia\n0 Wyjście")
                choice = answer("Wybór: ").lower()
                if choice in {"0", "q", "exit"}:
                    return 0
                if choice == "1":
                    source = answer("Repozytorium (katalog główny lokalnego Git lub URL GitHub): ")
                    target = "github" if source.startswith(("https://", "http://", "git@", "ssh://")) else "local"
                    ref = answer("Ref/commit [main dla GitHub, HEAD lokalnie]: ") or ("main" if target == "github" else "HEAD")
                    scope = parse_manual_paths(input_func("Wybrane pliki względne (oddziel |; Enter: wszystkie regularne): "))
                    campaign = answer("Nowy katalog kampanii (nie może istnieć): ")
                    workflow = LocalWorkflow.start(campaign, source, ref, target, scope or None)
                    controller = CampaignController(workflow.store.root, actions=actions, recent=recent)
                    remember(controller)
                    show(controller.prepare())
                elif choice == "2":
                    controller = choose_campaign()
                elif choice == "3":
                    selected = choose_campaign()
                    if selected:
                        reports(selected)
                elif choice == "4":
                    output("Indeks skrótów LOCAL: " + str(recent.path))
                    output("HIGH ASSURANCE: osobny formalny tryb. Import zewnętrzny BLOCKED; NF02/Q1/Q2/RQ nie są odblokowane.")
                    output("1 Stan i narzędzia wybranego audytu   0 Wstecz")
                    if answer("Ustawienia: ") == "1":
                        selected = choose_campaign()
                        if selected:
                            tools(selected)
                else:
                    output("Nieznany wybór.")
                continue
            try:
                view = controller.view()
            except (ValidationError, OSError, sqlite3.Error):
                output("Nie można zweryfikować kampanii " + str(controller.root) + ". Powrót do listy audytów.")
                controller = None
                raise
            output(render_campaign(view))
            choice = answer("Działanie [Enter: następny krok]: ").lower()
            if choice.startswith(("p ", "k ")):
                task = choice[2:].strip().upper()
                if choice.startswith("p "):
                    display_prompt(controller, task)
                else:
                    copy_prompt(controller, task)
                continue
            if choice == "0":
                controller = None
                continue
            action = view["next"]["action"] if not choice else {"1": "folder", "2": "packages", "3": "import", "4": "review", "5": "report", "6": "tools",
                                                               "7": "policy", "i": "import_summary", "m": "manual_import"}.get(choice)
            if action == "folder":
                output("Przekazano Eksploratorowi folder: " + str(controller.open_package_folder()))
            elif action == "packages":
                packages(controller)
            elif action == "import":
                add_result(controller)
            elif action == "manual_import":
                add_result(controller, manual=True)
            elif action == "policy":
                policy(controller)
            elif action == "import_summary":
                import_summary(controller)
            elif action == "review":
                review(controller, view["next"].get("result_id") if not choice else None)
            elif action == "prepare":
                show(controller.prepare())
            elif action == "advance":
                stage = view["workflow_stage"]
                stages = list(STAGES)
                following = stages[stages.index(stage) + 1:] or ["COMPLETE"]
                token = "ZAKONCZ LOCAL" if following[0] == "COMPLETE" else "PRZEJDZ " + following[0]
                output(view["next"]["message"])
                if answer("Wpisz " + token + ", aby potwierdzić przejście; Enter bez zmiany: ") == token:
                    status = controller.advance(view["status"]["history_head"])
                    show(status)
                    if status["stage"] == "COMPLETE":
                        show(controller.export_report())
            elif action == "report":
                if not choice and view["workflow_stage"] == "COMPLETE":
                    ready = [r for r in view["reports"] if r.get("verified") and r.get("history_head") == view["status"]["history_head"]]
                    if ready:
                        root = ready[0]["path"]
                    else:
                        exported = controller.export_report()
                        show(exported)
                        root = exported["output"]
                    output("Raport: " + str(Path(root) / "REPORT.md"))
                    output("Przekazano do otwarcia: " + controller.open_report(root, "markdown"))
                else:
                    reports(controller)
            elif action == "tools":
                tools(controller)
            else:
                output("Nieznany wybór.")
        except (EOFError, KeyboardInterrupt):
            output("Kampania zachowana. Wznów przez Moje audyty.")
            return 0
        except (ValidationError, OSError, sqlite3.Error, ValueError) as exc:
            output("ODMOWA: " + str(exc))
            if controller:
                output("Kampania: " + str(controller.root) + ". Stan zostanie odczytany ponownie. Zakończone transakcje zachowano; sprawdź I — podsumowanie importu.")
            else:
                output("Sprawdź Git/ref, zakres i uprawnienia, a następnie ponów wybór.")
