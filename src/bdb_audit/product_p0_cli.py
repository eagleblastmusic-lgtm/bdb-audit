"""Installed P0 command surface; authority is never selected by arguments."""
import argparse
import base64
from pathlib import Path
import re
import sys

from .core.canonical_json import canonical_bytes
from .core.errors import ValidationError
from .history.limited_model import strict_json, sha, MODEL_ID
from .history.limited_wire import LimitedCommand
from .history.store import TransactionalHistoryStore
from .workflow.limited_intake import LimitedIntake, LimitedRequest


def read_bounded(path, limit):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValidationError("P0_INPUT_RESOURCE_LIMIT")
    return raw


def packet(request):
    return {"command": request.command.body(), "objects": [{"kind": o.kind, "version": o.version, "body": o.body} for o in request.objects],
            "raw_digests": sorted(request.raw)}


def load_objects(runtime, objects):
    if not isinstance(objects, list) or len(objects) > 15:
        raise ValidationError("P0_INPUT_OBJECT_SET")
    out = []
    for row in objects:
        if set(row) != {"kind", "version", "body"}:
            raise ValidationError("P0_INPUT_OBJECT_SET")
        out.append(runtime.object(row["kind"], row["body"], row["version"]))
    return tuple(out)


def load_raw(directory, digests):
    if not isinstance(digests, list) or len(digests) > 64 or len(digests) != len(set(digests)):
        raise ValidationError("P0_RAW_INPUT_SET")
    raw, total = {}, 0
    for digest in digests:
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValidationError("P0_RAW_INPUT_SET")
        data = read_bounded(Path(directory) / digest, 64 * 1024 * 1024)
        total += len(data)
        if sha(data) != digest or total > 128 * 1024 * 1024:
            raise ValidationError("P0_RAW_INPUT_IDENTITY")
        raw[digest] = data
    return raw


def write_prepared(store, path, raw):
    """Service output stays in the leased campaign directory; never overwrites."""
    target = Path(path).absolute()
    parent = Path(store.path).absolute().parent
    if target.parent != parent or target.resolve().parent != parent.resolve():
        raise ValidationError("P0_PROTECTED_OUTPUT_LOCATION_REQUIRED")
    with store._nf02.lease(store.path):
        with target.open("xb") as stream:
            stream.write(raw)


def run_p0(argv):
    parser = argparse.ArgumentParser(prog="bdb-audit product p0")
    subs = parser.add_subparsers(dest="action", required=True)
    for action in ("status", "prepare", "accept", "prepare-release", "release"):
        sub = subs.add_parser(action)
        sub.add_argument("--store", required=True)
        if action in {"prepare", "accept", "release"}:
            sub.add_argument("--input", required=True)
        if action in {"prepare", "accept"}:
            sub.add_argument("--raw-dir", required=True)
        if action in {"accept", "release"}:
            sub.add_argument("--signature", required=True)
        if action == "prepare-release":
            sub.add_argument("--binding-ref", required=True)
            sub.add_argument("--grant-digest", required=True)
        if action in {"prepare", "prepare-release"}:
            sub.add_argument("--output", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        store = TransactionalHistoryStore.open_p0(args.store)
        intake, runtime = LimitedIntake(store), store._nf02
        if args.action == "status":
            model = store.rebuild_projection()
            data = {"status": "VERIFIED", "mode": runtime.installation["mode"], "accepted_head": store.head().as_dict() if store.head() else None,
                    "state": model["state"], "assurance": "ACCEPTED_AUDITOR_SUBMISSION_ONLY"}
        elif args.action == "prepare-release":
            ref = strict_json(read_bounded(args.binding_ref, 2 * 1024 * 1024))
            job = intake.release_job(binding_ref=ref, grant_digest=args.grant_digest)
            raw = canonical_bytes(runtime.release_statement(job))
            write_prepared(store, args.output, raw)
            data = {"status": "PREPARED_UNSIGNED", "output": str(Path(args.output).resolve()), "sign_exact_bytes_sha256": sha(raw)}
        elif args.action == "release":
            statement = strict_json(read_bounded(args.input, 2 * 1024 * 1024))
            job = statement["job"]
            if statement != runtime.release_statement(job):
                raise ValidationError("P0_SIGNED_RELEASE_CONTEXT_MISMATCH")
            data = store.release_p0(job, authentication=read_bounded(args.signature, 2 * 1024 * 1024))
        else:
            value = strict_json(read_bounded(args.input, 2 * 1024 * 1024))
            allowed = ({"operation", "objects", "raw_digests", "actor_ref", "grant_digest", "events", "command_id"}
                       if args.action == "prepare" else {"command", "objects", "raw_digests"})
            required = allowed - {"events", "command_id"}
            if not isinstance(value, dict) or not required <= value.keys() <= allowed:
                raise ValidationError("P0_INPUT_PACKET_FIELDS")
            objects = load_objects(runtime, value["objects"])
            raw = load_raw(args.raw_dir, value["raw_digests"])
            if args.action == "prepare":
                request = intake.prepare(value["operation"], objects, actor_ref=value["actor_ref"], grant_digest=value["grant_digest"],
                    raw=raw, events=value.get("events"), command_id=value.get("command_id"))
                write_prepared(store, args.output, canonical_bytes(packet(request)) + b"\n")
                data = {"status": "PREPARED_UNSIGNED", "output": str(Path(args.output).resolve()),
                        "signing_preimage_base64": base64.b64encode(request.signing_bytes()).decode("ascii")}
            else:
                command = LimitedCommand(value["command"], runtime)
                request = LimitedRequest(command, objects, tuple(command.body()["events"]), raw)
                result = intake.accept(request, read_bounded(args.signature, 2 * 1024 * 1024))
                data = {"status": "ACCEPTED", "mode": runtime.installation["mode"], "accepted_head": result.head.as_dict(),
                        "receipt": result.receipt.body(), "already_accepted": result.already_accepted}
        data["model_id"] = MODEL_ID
        code = 0
    except (ValidationError, OSError, KeyError, TypeError, ValueError) as exc:
        data = {"status": "BLOCKED", "model_id": MODEL_ID, "error": getattr(exc, "code", "P0_INPUT_OR_INSTALLATION_INVALID"), "detail": str(exc)}
        code = 2
    stream = sys.stderr if code else sys.stdout
    stream.write(canonical_bytes(data).decode("utf8") + "\n")
    return code
