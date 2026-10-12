"""Public CLI for the separate local product, with no certificate prerequisites."""
from __future__ import annotations

import argparse
import getpass
import json
import sqlite3
import sys
from typing import Any, Sequence

from ..core.errors import ValidationError
from .profile import MODE, NOTICE
from .workflow import LocalWorkflow, preflight


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="bdb-audit product local", description=NOTICE)
    sub = root.add_subparsers(dest="action", required=True)
    for name in ("preflight", "start"):
        command = sub.add_parser(name)
        command.add_argument("--source", required=True)
        command.add_argument("--target", choices=("local", "github"), default="local")
        command.add_argument("--ref")
        command.add_argument("--path", action="append", help="Explicit source file scope; repeat per file")
        if name == "start":
            command.add_argument("--campaign", required=True, help="New campaign directory (must not exist)")
    for name in ("status", "resume", "prepare", "inspect", "import", "validate", "accept", "reject", "advance", "run-check", "recover-check"):
        command = sub.add_parser(name)
        command.add_argument("--campaign", required=True)
        if name in {"inspect", "import"}:
            command.add_argument("--file", required=True)
        if name in {"validate", "accept", "reject"}:
            command.add_argument("--result", required=True)
        if name == "accept":
            command.add_argument("--confirm-local", action="store_true", help="I reviewed this unverified result and accept local use")
            command.add_argument("--actor", default=getpass.getuser(), help="Local decision label, not certified identity")
            command.add_argument("--replace", help="Exact previous accepted result ID for this task")
        if name == "reject":
            command.add_argument("--reason", required=True)
        if name == "run-check":
            command.add_argument("--task", required=True)
            command.add_argument("--timeout", type=int, default=60)
            command.add_argument("--max-output", type=int, default=4 * 1024 * 1024)
            command.add_argument("argv", nargs=argparse.REMAINDER, help="Explicit command after --; never read from an AI result")
        if name == "recover-check":
            command.add_argument("--run-id", required=True)
    return root


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.action in {"preflight", "start"}:
        ref = args.ref or ("main" if args.target == "github" else "HEAD")
        if args.action == "preflight":
            return preflight(args.source, ref, args.target, args.path)
        return LocalWorkflow.start(args.campaign, args.source, ref, args.target, args.path).prepare()
    workflow = LocalWorkflow(args.campaign)
    if args.action in {"status", "resume"}:
        return workflow.status()
    if args.action == "prepare":
        return workflow.prepare()
    if args.action == "inspect":
        return workflow.inspect(args.file)
    if args.action == "import":
        return workflow.import_result(args.file)
    if args.action == "validate":
        return workflow.validate(args.result)
    if args.action == "accept":
        return workflow.accept(args.result, args.actor, confirm=args.confirm_local, replaces=args.replace)
    if args.action == "reject":
        return workflow.reject(args.result, args.reason)
    if args.action == "advance":
        return workflow.advance()
    if args.action == "run-check":
        argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        return workflow.run_check(args.task, argv, args.timeout, args.max_output)
    if args.action == "recover-check":
        return workflow.recover_check(args.run_id)
    raise ValidationError("LOCAL_ACTION_NOT_IMPLEMENTED")


def run_local(argv: Sequence[str]) -> int:
    try:
        args = parser().parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        data = execute(args)
        code = 2 if data.get("status") == "REJECTED" else 0
    except (ValidationError, OSError, sqlite3.Error) as exc:
        data = {"mode": MODE, "status": "REFUSED", "error": getattr(exc, "code", "LOCAL_IO_ERROR"),
                "detail": str(exc), "notice": NOTICE}
        code = 2
    print(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2), file=sys.stderr if code else sys.stdout)
    return code
