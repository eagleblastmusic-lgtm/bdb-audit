"""Windows launcher + real mixed file import/resume; disclosed TEST_FIXTURE only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from bdb_audit.assurance.zip_safety import read_bytes
from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.local_product.contract import result_filename
from bdb_audit.local_product.guided import CampaignController
from bdb_audit.local_product.store import sha
from bdb_audit.local_product.workflow import LocalWorkflow
from bdb_audit.workflow.packaging import _deterministic_zip

ROOT = Path(__file__).resolve().parents[1]


def run(output: Path, standalone: Path | None = None) -> dict[str, Any]:
    if output.exists():
        raise ValueError("Use a new smoke directory; previous evidence is preserved")
    output.mkdir(parents=True)
    repository = output / "source żółć"
    repository.mkdir()
    (repository / "app.py").write_text("def clamp(n):\n    return min(n, 10)\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "app.py"),
                 ("-c", "user.name=Batch smoke", "-c", "user.email=smoke@example.invalid", "commit", "-qm", "Explicit workflow fixture")):
        subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True)
    workflow = LocalWorkflow.start(output / "campaign żółć", str(repository), "HEAD")
    workflow.prepare()
    results = output / "wyniki ze spacją żółć"
    results.mkdir()
    files = []
    for index, task in enumerate(workflow._available_tasks()):
        package = workflow.packages[task]
        members = read_bytes(workflow.store.vault.read_bytes(package["raw"]["raw_digest"]))
        body = parse(members["RESPONSE_TEMPLATE.json"])
        body.update(producer={"kind": "TEST_FIXTURE", "declared_name": "Disclosed workflow smoke; no external AI run"},
                    completion="COMPLETE", limitations=["Workflow protocol exercise; no real audit or executed target tests"])
        body["outputs"] = {key: "TEST_FIXTURE workflow output for " + key + "; no qualification or true AI assessment claimed"
                           for key in package["required_outputs"]}
        raw = canonical_bytes(body)
        zipped = index % 2 == 0
        if zipped:
            raw = _deterministic_zip({"LOCAL_RESULT.json": raw})
        file = results / result_filename(task, "zip" if zipped else "json")
        file.write_bytes(raw)
        files.append(file)

    env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=str(ROOT / "src"))
    transcripts: list[dict[str, Any]] = []
    def command(name: str, argv: list[str], answers: str | None = None) -> bytes:
        proc = subprocess.run(argv, input=None if answers is None else answers.encode("utf-8"),
                              capture_output=True, env=env, cwd=ROOT, timeout=120)
        raw = proc.stdout + proc.stderr
        (output / name).write_bytes(raw)
        transcripts.append({"argv": argv, "transcript": name, "exit_code": proc.returncode,
                            "sha256": sha(raw), "bytes": len(raw)})
        if proc.returncode:
            raise RuntimeError(raw.decode("utf-8", errors="replace"))
        return proc.stdout

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if os.name != "nt" or not powershell:
        raise RuntimeError("This smoke explicitly requires the Windows PowerShell launcher")
    selection = " | ".join('"' + str(p) + '"' for p in files)
    answers = "\n".join(["2", "O", str(workflow.store.root), "p E1-A", "a", "0", "7", "WLACZ AUTO LOCAL",
                         "m", selection, "i", "j", "0", "", "PRZEJDZ E2", "0", "0", ""])
    text = command("LAUNCHER_TUI.txt", [powershell, "-NoProfile", "-File", str(ROOT / "Run-Local-Audit.ps1"),
                                       "-NoGui", "-Index", str(output / "recent.json")], answers).decode("utf-8")
    assert "ODMOWA:" not in text and "Przyjęto AUTO: 5" in text and "PROMPT E1-A" in text
    current = LocalWorkflow(workflow.store.root)
    assert current.stage == "E2" and len(current.accepted) == 5
    batch = current.batch_summaries()[-1]
    assert (batch["accepted"], batch["rejected"], batch["duplicates"]) == (5, 0, 0)
    assert all(r["acceptance_mechanism"] == "AUTO_POLICY" for r in current.results.values())
    assert current.head == CampaignController(current.store.root).view()["status"]["history_head"]
    standalone_status = "NOT_RUN"
    if standalone:
        payload = parse(command("STANDALONE_PAYLOAD.json", [sys.executable, "-I", "-S", str(standalone), "--verify-payload"]))
        assert payload["status"] == "PASS"
        state = parse(command("STANDALONE_STATUS.json", [sys.executable, "-I", "-S", str(standalone),
                            "product", "local", "status", "--campaign", str(current.store.root)]))
        assert state["stage"] == "E2" and state["history_head"] == current.head
        before = current.head
        duplicate = parse(command("STANDALONE_DUPLICATES.json", [sys.executable, "-I", "-S", str(standalone),
            "product", "local", "import-batch", "--campaign", str(current.store.root),
            *[arg for file in files for arg in ("--file", str(file))]]))
        assert duplicate["duplicates"] == 5 and duplicate["accepted"] == 0
        current = LocalWorkflow(current.store.root)
        assert len(current.results) == len(current.accepted) == 5 and current.head != before
        standalone_status = "PASS_ISOLATED_PAYLOAD_RESUME_IDEMPOTENCE"
    record = {"status": "PASS", "provenance": "TEST_FIXTURE; real files/import/Windows launcher, no external AI responses",
              "source_commit": current.source["commit"], "source_tree": current.source["tree"],
              "campaign": str(current.store.root), "history_head": current.head, "stage": current.stage,
              "accepted_results": len(current.accepted), "batch": batch, "commands": transcripts,
              "standalone": standalone_status,
              "physical_native_dialog": "NOT_RUN; native multi-selection is covered by adapter tests"}
    (output / "SMOKE_RESULT.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--standalone", type=Path)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.standalone.resolve() if args.standalone else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
