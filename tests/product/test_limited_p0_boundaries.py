"""Local probes. These do not qualify real CMS, OS ACLs or an external audit."""

import base64
from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history import limited_environment as environment
from bdb_audit.history.limited_model import sha, strict_json
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.product_cli import run_product
from bdb_audit.product_p0_cli import packet, load_raw
from tests.product.test_limited_p0 import (
    corpus as p0_corpus,
    setup_p0 as p0_setup,
    started,
    assigned,
    accept,
    snapshot,
    OWNER,
    AUDITOR,
)

corpus = p0_corpus
setup_p0 = p0_setup


def test_cli_without_os_authority_cannot_create_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "bdb_audit.history.limited_authority.machine_root", lambda: tmp_path / "missing"
    )
    path = tmp_path / "must-not-create.sqlite"
    assert run_product(["p0", "status", "--store", str(path)]) == 2
    assert (
        json.loads(capsys.readouterr().err)["error"]
        == "P0_INSTALLATION_AUTHORITY_NOT_ESTABLISHED"
    )
    assert not path.exists()


@pytest.mark.parametrize("digest", ["../outside", "f" * 63, "F" * 64, "a" * 64])
def test_cli_raw_snapshot_cannot_traverse_or_substitute(tmp_path, digest):
    (tmp_path / ("a" * 64)).write_bytes(b"wrong bytes")
    with pytest.raises(ValidationError):
        load_raw(tmp_path, [digest])


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":-0}',
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":9007199254740992}',
        b'{"x":"\\ud800"}',
        b"[" * 33 + b"]" * 33,
    ],
)
def test_strict_json_untrusted_resource_and_number_forms(raw):
    with pytest.raises(ValidationError):
        strict_json(raw)


def test_environment_readback_detects_dependency_change_and_new_module(
    tmp_path, monkeypatch
):
    dependency = tmp_path / "module.py"
    dependency.write_bytes(b"approved code")
    monkeypatch.setattr(
        environment, "dependency_roots", lambda: {"PYTHON_ENV": tmp_path}
    )
    monkeypatch.setattr(environment, "_protected", lambda paths: None)
    expected = environment.snapshot()

    @contextmanager
    def locked(path, *, directory=False, check_acl=True, digest_only=False):
        yield (
            b""
            if directory
            else {"sha256": sha(path.read_bytes()), "bytes": path.stat().st_size}
        )

    monkeypatch.setattr(environment, "_locked_file", locked)
    fake_sys = SimpleNamespace(
        flags=SimpleNamespace(isolated=1, ignore_environment=1),
        dont_write_bytecode=True,
        version=sys.version,
        executable=sys.executable,
    )
    monkeypatch.setattr(environment, "sys", fake_sys)
    with ExitStack() as stack:
        environment.verify_environment(expected, stack)
    dependency.write_bytes(b"substituted")
    with (
        ExitStack() as stack,
        pytest.raises(ValidationError, match="ENVIRONMENT_DRIFT"),
    ):
        environment.verify_environment(expected, stack)
    dependency.write_bytes(b"approved code")
    (tmp_path / "extra.py").write_bytes(b"unqualified import")
    with (
        ExitStack() as stack,
        pytest.raises(ValidationError, match="ENVIRONMENT_DRIFT"),
    ):
        environment.verify_environment(expected, stack)
    fake_sys.flags.isolated = 0
    with (
        ExitStack() as stack,
        pytest.raises(ValidationError, match="INTERPRETER_REQUIRED"),
    ):
        environment.verify_environment(expected, stack)


def test_current_rights_lost_at_final_commit_roll_back(setup_p0):
    store, intake, authority, request, _, _, _ = setup_p0
    before = snapshot(store)

    def revoke(name):
        if name == "after_receipt_before_head":
            authority.leased["grants"] = []

    store.crash_hook = revoke
    with pytest.raises(ValidationError, match="GRANT_REQUIRED"):
        accept(intake, request)
    assert snapshot(store) == before


def test_abort_retry_and_terminal_release_denial(setup_p0):
    store, intake, authority, assignment, gd, grant, binding, _ = started(setup_p0)
    job = intake.release_job(binding_ref=binding.ref.as_dict(), grant_digest=gd)
    scope = next(g["body"] for g in authority.leased["grants"] if g["digest"] == gd)
    recovery = grant(
        {
            k: scope[k]
            for k in (
                "campaign_id",
                "source_scope_digest",
                "view_task_digest",
                "assignment_scope_digest",
            )
        },
        "OWNER_RECOVERY",
    )
    request = intake.abort(
        actor_ref="TEST_ONLY_OWNER_RECOVERY",
        grant_digest=recovery,
        assignment_ref=assignment.ref.as_dict(),
        reason="OWNER_CANCELLED",
    )
    accept(intake, request, OWNER)
    before = snapshot(store)
    with pytest.raises(ValidationError):
        store.release_p0(job, authentication=b"no longer legal")
    assert snapshot(store) == before
    attempt, replacement = intake.draft_assignment(auditor_certificate_sha256=AUDITOR)
    assert attempt.body["retry_of_attempt_ref"] == assignment.body["attempt_ref"]
    assert attempt.body["abort_basis_ref"] == request.objects[0].ref.as_dict()
    genesis = setup_p0[-1]
    source = setup_p0[-2]
    new_scope = intake.runtime.auth_scope(
        genesis.body, source.body, replacement.ref.as_dict(), AUDITOR
    )
    new_grant = grant(new_scope)
    grant(new_scope, "AUDITOR")
    new_request = intake.prepare(
        "CREATE_ASSIGNMENT",
        [attempt, replacement],
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=new_grant,
    )
    assert accept(intake, new_request).head.commit_seq == 6
    assert store.rebuild_projection()["state"] == "ASSIGNED"


@pytest.mark.parametrize(
    "boundary", ["after_object_durability", "after_commit_durability_before_ack"]
)
def test_real_process_exit_and_new_process_replay(setup_p0, boundary):
    store, _, authority, request, _, _, _ = setup_p0
    leased = {k: v for k, v in authority.leased.items() if k != "corpus"}
    leased = {
        **leased,
        "files": {k: base64.b64encode(v).decode() for k, v in leased["files"].items()},
        "grants": [
            {
                **g,
                "raw": base64.b64encode(g["raw"]).decode(),
                "signature": base64.b64encode(g["signature"]).decode(),
            }
            for g in leased["grants"]
        ],
    }
    for key in ("root_raw", "installation_raw", "installation_signature"):
        leased[key] = base64.b64encode(leased[key]).decode()
    state = {
        "leased": leased,
        "packet": packet(request),
        "raw": {k: base64.b64encode(v).decode() for k, v in request.raw.items()},
    }
    state_path = Path(store.path).parent / "TEST_ONLY_PROCESS_STATE.json"
    state_path.write_text(json.dumps(state), encoding="utf8")
    worker = Path(__file__).with_name("limited_process_worker.py")
    completed = subprocess.run(
        [sys.executable, str(worker), str(state_path), store.path, boundary],
        capture_output=True,
        timeout=120,
    )
    assert completed.returncode == 91, completed.stderr.decode("utf8", "replace")
    verified = subprocess.run(
        [sys.executable, str(worker), str(state_path), store.path, "VERIFY"],
        capture_output=True,
        timeout=120,
    )
    assert verified.returncode == 0, verified.stderr.decode("utf8", "replace")
    head = json.loads(verified.stdout)["head"]
    restarted = TransactionalHistoryStore.open_p0(store.path)
    if boundary == "after_object_durability":
        assert head is None and restarted.head() is None
        with restarted._connect() as con:
            for table in (
                "immutable_objects",
                "commits",
                "receipts",
                "immutable_raw_artifacts",
            ):
                assert con.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
    else:
        assert head["commit_seq"] == 1 and restarted.head().commit_seq == 1
