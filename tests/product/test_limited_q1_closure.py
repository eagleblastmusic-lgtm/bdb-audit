"""Q1 reference/provisioning regressions; no actual owner or key is created."""
import json
import hashlib
from itertools import product
import subprocess
import base64
from copy import deepcopy

import pytest

from bdb_audit.core.errors import ValidationError
from tools.nf02_p0_q1_contexts import corpus
from tools.nf02_p0_q1_external_inputs import prepare, verify
from tools.nf02_p0_reference import valid, sha, fixed_zip
from tools.nf02_p0_q1 import reference_a, reference_b
from bdb_audit.workflow.limited_transport import LimitedTransport, approved_git_view
from tests.product import test_limited_p0 as f

setup_p0 = f.setup_p0


@pytest.fixture(name="corpus")
def p0_corpus():
    return corpus()


@pytest.mark.parametrize("schema_index", range(18))
def test_each_initial_schema_binding_rejects_other_actual_schema_bytes(setup_p0, schema_index, record_property):
    runtime = setup_p0[1].runtime
    original = runtime.roots["schema_registry"]
    body = deepcopy(original.body)
    body["bindings"][schema_index]["schema_raw_ref"] = body["bindings"][(schema_index + 1) % 18]["schema_raw_ref"]
    changed = runtime.object(original.kind, body, original.version)
    runtime.roots = {**runtime.roots, original.kind: changed}
    record_property("input_exact_cjson_sha256", sha(reference_a(body)))
    record_property("input_cjson_base64", base64.b64encode(reference_b(body)).decode())
    record_property("expected", "P0_SCHEMA_REGISTRY_EXACT_BINDINGS")
    with pytest.raises(ValidationError, match="P0_SCHEMA_REGISTRY_EXACT_BINDINGS"):
        runtime.validate_roots()
    record_property("actual", "P0_SCHEMA_REGISTRY_EXACT_BINDINGS")


@pytest.mark.parametrize("kind,field,expected", [
    ("artifact_contract_registry", "contracts", "P0_REGISTRY_EXACT_MEMBERSHIP"),
    ("schema_registry", "bindings", "P0_SCHEMA_REGISTRY_EXACT_BINDINGS"),
])
def test_initial_root_order_is_semantic_not_only_schema(setup_p0, kind, field, expected, record_property):
    runtime = setup_p0[1].runtime
    obj = runtime.roots[kind]
    body = {**obj.body, field: list(reversed(obj.body[field]))}
    changed = runtime.object(kind, body, obj.version)
    runtime.roots = {**runtime.roots, kind: changed}
    record_property("input_exact_cjson_sha256", sha(reference_a(body)))
    record_property("input_cjson_base64", base64.b64encode(reference_b(body)).decode())
    record_property("expected", expected)
    with pytest.raises(ValidationError, match=expected):
        runtime.validate_roots()
    record_property("actual", expected)


@pytest.mark.parametrize("profile", sorted(corpus().descriptor["profiles"]))
def test_every_profile_requires_exact_frozen_raw_pin(setup_p0, profile, record_property):
    runtime = setup_p0[1].runtime
    pin = runtime.corpus.pin(profile)
    runtime.check_profiles({"nested": [pin]})
    wrong = {**pin, "revision_digest": "0" * 64}
    record_property("input_exact_cjson_sha256", sha(reference_a(wrong)))
    record_property("expected", "P0_PROFILE_PIN_MISMATCH")
    with pytest.raises(ValidationError, match="P0_PROFILE_PIN_MISMATCH"):
        runtime.check_profiles({"nested": [wrong]})
    record_property("actual", "P0_PROFILE_PIN_MISMATCH")


@pytest.mark.parametrize("field,expected", [
    ("task_raw_ref", "P0_ASSIGNMENT_CONTEXT_JOIN"),
    ("input_members", "P0_APPROVED_VIEW_MEMBERS_MISMATCH"),
    ("auditor_certificate_sha256", "P0_ASSIGNMENT_CONTEXT_JOIN"),
    ("package_profile_ref", "P0_PROFILE_PIN_MISMATCH"),
    ("result_profile_ref", "P0_PROFILE_PIN_MISMATCH"),
    ("isolation_profile_ref", "P0_PROFILE_PIN_MISMATCH"),
])
def test_assignment_context_with_correctly_scoped_signed_test_grant(setup_p0, field, expected, record_property):
    store, intake, _, init, grant, source, genesis = setup_p0
    f.accept(intake, init)
    attempt, assignment = intake.draft_assignment(auditor_certificate_sha256=f.AUDITOR)
    body = deepcopy(assignment.body)
    extra_raw = {}
    if field == "task_raw_ref":
        raw = b"TEST ONLY other task bytes\n"
        body[field] = intake.runtime.corpus.raw_ref(raw, "P0_PACKAGE_TRANSPORT_V1", "text/markdown")
        extra_raw[sha(raw)] = raw
    elif field == "input_members":
        body[field] = body[field][:-1]
    elif field == "auditor_certificate_sha256":
        body[field] = "0" * 64
    else:
        body[field]["revision_digest"] = "0" * 64
    changed = intake.runtime.object(assignment.kind, body, assignment.version)
    scope = intake.runtime.auth_scope(genesis.body, source.body, changed.ref.as_dict(), body["auditor_certificate_sha256"])
    request = intake.prepare("CREATE_ASSIGNMENT", [attempt, changed], actor_ref="TEST_ONLY_COORDINATOR", grant_digest=grant(scope), raw=extra_raw)
    before = f.snapshot(store)
    record_property("input_command_signing_sha256", sha(request.signing_bytes()))
    record_property("input_assignment_cjson_sha256", sha(reference_a(body)))
    record_property("input_assignment_cjson_base64", base64.b64encode(reference_b(body)).decode())
    record_property("authority", "SIMULATED_OS_CMS_TEST_ONLY; grant matches altered Assignment exactly")
    record_property("expected", expected)
    with pytest.raises(ValidationError, match=expected):
        f.accept(intake, request)
    assert f.snapshot(store) == before
    record_property("actual", expected)


def test_assignment_requires_attempt_from_same_create_with_exact_scoped_grant(setup_p0, record_property):
    store, intake, _, assignment, _, grant = f.assigned(setup_p0)
    source, genesis = setup_p0[5:]
    scope = intake.runtime.auth_scope(genesis.body, source.body, assignment.ref.as_dict(), f.AUDITOR)
    abort = intake.abort(actor_ref="TEST_ONLY_OWNER_RECOVERY", grant_digest=grant(scope, "OWNER_RECOVERY"),
                         assignment_ref=assignment.ref.as_dict(), reason="OWNER_CANCELLED")
    f.accept(intake, abort, f.OWNER)
    attempt2, assignment2 = intake.draft_assignment(auditor_certificate_sha256=f.AUDITOR)
    altered = intake.runtime.object(assignment2.kind, {**assignment2.body, "attempt_ref": assignment.body["attempt_ref"]}, assignment2.version)
    exact_scope = intake.runtime.auth_scope(genesis.body, source.body, altered.ref.as_dict(), f.AUDITOR)
    gd = grant(exact_scope)
    request = intake.prepare("CREATE_ASSIGNMENT", [attempt2, altered], actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd)
    before = f.snapshot(store)
    record_property("input_command_signing_sha256", sha(request.signing_bytes()))
    record_property("authority", "SIMULATED_OS_CMS_TEST_ONLY; grant exactly matches altered Assignment")
    record_property("expected", "P0_ASSIGNMENT_ATTEMPT_CONTENT_MISMATCH; no mutation")
    with pytest.raises(ValidationError, match="P0_ASSIGNMENT_ATTEMPT_CONTENT_MISMATCH"):
        f.accept(intake, request)
    assert f.snapshot(store) == before
    record_property("actual", "P0_ASSIGNMENT_ATTEMPT_CONTENT_MISMATCH; no mutation")


@pytest.mark.parametrize("values,expected", [
    ([True, 1], True),
    ([False, 0], True),
    ([{"a": 1, "b": [True, None]}, {"b": [True, None], "a": 1}], False),
    ([[1, 2], [2, 1]], True),
    (["é", "e\u0301"], True),
    (["é", "é"], False),
    ([[], []], False),
])
def test_independent_unique_reference_preserves_strict_cjson_identity(values, expected):
    assert valid({"type": "array", "uniqueItems": True}, values, {}) is expected


def test_unsigned_decision_is_create_new_and_cannot_pass_real_cms(tmp_path, capsys):
    path = tmp_path / "TEST_ONLY_UNSIGNED_DECISION.json"
    prepare("TEST_ONLY_NOT_AN_ESTABLISHED_OWNER", path)
    metadata = json.loads(capsys.readouterr().out)
    raw = path.read_bytes()
    assert metadata["status"] == "PREPARED_UNSIGNED_NOT_AUTHORITY"
    assert sha(raw) == metadata["sha256"]
    assert corpus().external("OWNER_MODEL_DECISION", raw)["decision"] == "APPROVE_LIMITED_P0_MODEL"
    with pytest.raises(FileExistsError):
        prepare("TEST_ONLY_REPLACEMENT_DENIED", path)
    assert path.read_bytes() == raw
    cert, signature = tmp_path / "NOT_A_CERTIFICATE.cer", tmp_path / "NOT_A_SIGNATURE.p7s"
    cert.write_bytes(b"TEST_ONLY_INVALID_DER_NOT_A_CERTIFICATE")
    signature.write_bytes(b"TEST_ONLY_INVALID_CMS_NOT_A_SIGNATURE")
    with pytest.raises(ValidationError):
        verify(path, signature, cert, sha(cert.read_bytes()), sha(raw))


@pytest.fixture(scope="module", params=list(product(("sha1", "sha256"), ("100644", "100755"))))
def git_context(request, tmp_path_factory):
    algorithm, mode = request.param
    repo = tmp_path_factory.mktemp("q1-real-git-" + algorithm + "-" + mode)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
    git("init", "--object-format=" + algorithm)
    git("config", "user.name", "TEST ONLY Q1")
    git("config", "user.email", "q1-test-only@example.invalid")
    blob = b"TEST ONLY exact source bytes\n"
    (repo / "input.txt").write_bytes(blob)
    git("add", "input.txt")
    git("update-index", "--chmod=" + ("+x" if mode == "100755" else "-x"), "input.txt")
    git("commit", "-m", "TEST ONLY Q1 source context")
    commit, tree = (git("rev-parse", name).strip().decode("ascii") for name in ("HEAD", "HEAD^{tree}"))
    # Independently reconstruct typed Git object hashes from actual raw objects.
    raw_objects = {}
    for kind, oid in (("commit", commit), ("tree", tree)):
        raw = git("cat-file", kind, oid)
        assert hashlib.new(algorithm, kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid
        raw_objects[kind] = {"git_oid": oid, "raw_sha256": sha(raw), "raw_base64": base64.b64encode(raw).decode()}
    blob_oid = hashlib.new(algorithm, b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
    expected = {"repository_id": "TEST_ONLY_Q1_GIT_CONTEXT", "git_object_algorithm": algorithm, "commit_oid": commit, "tree_oid": tree,
                "entries": [{"source_path": "input.txt", "transport_path": "source/00000001.bin", "mode": mode, "git_blob_oid": blob_oid,
                             "sha256": sha(blob), "bytes": len(blob)}]}
    _, manifest, archive = approved_git_view(repo, commit, expected["repository_id"], ["input.txt"])
    assert manifest == reference_a(expected) + b"\n" == reference_b(expected) + b"\n"
    assert archive == fixed_zip({"MANIFEST.json": manifest, "source/00000001.bin": blob})
    return expected, blob, raw_objects


@pytest.mark.parametrize("commit_length,tree_length,blob_length", list(product((40, 64), repeat=3)))
def test_m07_full_algorithm_oid_lengths_and_mode_product(git_context, commit_length, tree_length, blob_length, record_property):
    from copy import deepcopy
    original, blob, raw_objects = git_context
    manifest = deepcopy(original)
    def sized(oid, length):
        return (oid + "0" * length)[:length]
    manifest["commit_oid"] = sized(manifest["commit_oid"], commit_length)
    manifest["tree_oid"] = sized(manifest["tree_oid"], tree_length)
    manifest["entries"][0]["git_blob_oid"] = sized(manifest["entries"][0]["git_blob_oid"], blob_length)
    raw = reference_a(manifest) + b"\n"
    assert raw == reference_b(manifest) + b"\n"
    archive = fixed_zip({"MANIFEST.json": raw, "source/00000001.bin": blob})
    snapshot = {"repository_id": manifest["repository_id"], "git_object_algorithm": manifest["git_object_algorithm"],
                "git_commit_object_id": manifest["commit_oid"], "git_tree_object_id": manifest["tree_oid"], "approved_view_digest": sha(raw)}
    width = 40 if original["git_object_algorithm"] == "sha1" else 64
    expected = (commit_length, tree_length, blob_length) == (width, width, width)
    try:
        LimitedTransport(corpus()).source(raw, archive, snapshot)
        actual = True
    except ValidationError:
        actual = False
    for name, value in {"authority": "TRANSPORT_ONLY_NO_REAL_AUTHORITY", "expected": str(expected), "actual": str(actual),
                        "manifest_exact_sha256": sha(raw), "archive_exact_sha256": sha(archive), "snapshot_cjson_sha256": sha(reference_a(snapshot)),
                        "manifest_base64": base64.b64encode(raw).decode(), "archive_base64": base64.b64encode(archive).decode(),
                        "snapshot": reference_a(snapshot).decode(), "actual_git_object_inputs": reference_a(raw_objects).decode()}.items():
        record_property(name, value)
    assert expected == actual
