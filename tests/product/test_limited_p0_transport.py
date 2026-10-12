"""Missing P0 transport and finite-entry-point regressions, without authority."""
from dataclasses import replace
import io
import json
import subprocess
import zipfile

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.workflow.limited_transport import LimitedTransport, fixed_zip, approved_git_view
from tests.product.test_limited_p0 import corpus as p0_corpus, setup_p0 as p0_setup, accept, snapshot, ROOT

corpus = p0_corpus
setup_p0 = p0_setup


@pytest.mark.parametrize("members", [
    {"../outside.txt": b"x"}, {"C:/escape.txt": b"x"}, {"CON.txt": b"x"},
    {"A.txt": b"a", "a.txt": b"b"}, {"report.txt": b"a", "extra.json": b'{"x":1,"x":2}'},
])
def test_fixed_zip_still_rejects_unsafe_member_identity(corpus, members):
    with pytest.raises(ValidationError):
        LimitedTransport(corpus).archive(fixed_zip(members), "P0_RESULT_TRANSPORT_V1")


@pytest.mark.parametrize("mutation", ["comment", "extra", "compressed", "trailing", "duplicate"])
def test_semantically_equal_repacked_zip_is_not_exact_transport(corpus, mutation):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        info = zipfile.ZipInfo("REPORT.md", (1980, 1, 1, 0, 0, 0))
        info.create_system = 3
        info.create_version = info.extract_version = 20
        info.external_attr = 0o100644 << 16
        if mutation == "extra":
            info.extra = b"\x01\x00\x00\x00"
        if mutation == "compressed":
            info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, b"actual report")
        if mutation == "comment":
            archive.comment = b"changed metadata"
        if mutation == "duplicate":
            archive.writestr(info, b"actual report")
    raw = stream.getvalue() + (b"trailing" if mutation == "trailing" else b"")
    with pytest.raises(ValidationError):
        LimitedTransport(corpus).archive(raw, "P0_RESULT_TRANSPORT_V1")


def test_source_snapshot_uses_actual_distinct_git_object_types(corpus):
    identity, manifest, archive = approved_git_view(ROOT, "HEAD", "ACTUAL_LOCAL_REPOSITORY_NO_AUTHORITY", ["pyproject.toml"])
    assert identity.commit_object_id != identity.tree_object_id
    value = json.loads(manifest)
    assert (value["commit_oid"], value["tree_oid"]) == (identity.commit_object_id, identity.tree_object_id)
    assert LimitedTransport(corpus).archive(archive, "P0_BOOTSTRAP_SOURCE_V1")["MANIFEST.json"] == manifest


def test_m07_source_transport_index_starts_at_one_and_follows_utf8_order(corpus):
    # Literal expectations from MODEL.md M07, independent of the builder/parser.
    _, manifest, _ = approved_git_view(ROOT, "HEAD", "TEST_ONLY_INDEX", ["pyproject.toml", "AGENTS.md"])
    entries = json.loads(manifest)["entries"]
    assert [(e["source_path"], e["transport_path"]) for e in entries] == [
        ("AGENTS.md", "source/00000001.bin"), ("pyproject.toml", "source/00000002.bin")]


def test_m07_zero_based_source_cannot_be_accepted(setup_p0):
    from bdb_audit.core.canonical_json import canonical_bytes
    from bdb_audit.history.limited_model import sha
    from bdb_audit.history.limited_wire import copy
    store, intake, _, request, _, source, genesis = setup_p0
    before = snapshot(store)
    raw_manifest = request.raw[source.body["source_manifest_raw_ref"]["raw_digest"]]
    archive = request.raw[source.body["source_archive_raw_ref"]["raw_digest"]]
    manifest = json.loads(raw_manifest)
    members = intake.runtime.transport.archive(archive, "P0_BOOTSTRAP_SOURCE_V1")
    original = manifest["entries"][0]["transport_path"]
    manifest["entries"][0]["transport_path"] = "source/00000000.bin"
    raw_manifest = canonical_bytes(manifest) + b"\n"
    archive = fixed_zip({"MANIFEST.json": raw_manifest, "source/00000000.bin": members[original]})
    body = copy(source.body)
    body.update(approved_view_digest=sha(raw_manifest),
        source_manifest_raw_ref=intake.runtime.corpus.raw_ref(raw_manifest, "P0_BOOTSTRAP_SOURCE_V1", "application/json"),
        source_archive_raw_ref=intake.runtime.corpus.raw_ref(archive, "P0_BOOTSTRAP_SOURCE_V1", "application/zip"))
    wrong_source = intake.runtime.object("nf02_p0_source_snapshot", body)
    wrong_genesis = intake.runtime.object("campaign_genesis", {**genesis.body, "source_ref": wrong_source.ref.as_dict()})
    raw = {**request.raw, sha(raw_manifest): raw_manifest, sha(archive): archive}
    altered = intake.initialize(source=wrong_source, genesis=wrong_genesis,
        actor_ref=request.command.actor_ref, grant_digest=request.command.body()["grant_digest"], raw=raw)
    with pytest.raises(ValidationError, match="P0_GIT_BLOB_IDENTITY_MISMATCH"):
        accept(intake, altered)
    assert snapshot(store) == before


@pytest.mark.parametrize("algorithm", ["sha1", "sha256"])
def test_m07_both_git_algorithms_and_regular_file_modes(corpus, tmp_path, algorithm):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], stderr=subprocess.DEVNULL).strip().decode("ascii")
    git("init", "--object-format=" + algorithm)
    git("config", "user.name", "TEST ONLY")
    git("config", "user.email", "test-only@example.invalid")
    (tmp_path / "plain.txt").write_bytes(b"plain\n")
    (tmp_path / "script.sh").write_bytes(b"#!/bin/sh\nexit 0\n")
    git("add", "plain.txt", "script.sh")
    git("update-index", "--chmod=+x", "script.sh")
    git("commit", "-m", "TEST ONLY supported source variants")
    identity, raw, archive = approved_git_view(tmp_path, "HEAD", "TEST_ONLY_VARIANTS", ["script.sh", "plain.txt"])
    value = json.loads(raw)
    assert identity.object_format == algorithm
    assert [(e["mode"], e["transport_path"]) for e in value["entries"]] == [
        ("100644", "source/00000001.bin"), ("100755", "source/00000002.bin")]
    source = {"repository_id": value["repository_id"], "git_object_algorithm": algorithm,
        "git_commit_object_id": value["commit_oid"], "git_tree_object_id": value["tree_oid"], "approved_view_digest": __import__("hashlib").sha256(raw).hexdigest()}
    assert LimitedTransport(corpus).source(raw, archive, source)[0] == value


def test_git_replace_cannot_change_the_tree_of_an_approved_commit(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], stderr=subprocess.DEVNULL).strip().decode("ascii")

    git("init")
    git("config", "user.name", "TEST ONLY")
    git("config", "user.email", "test-only@example.invalid")
    (tmp_path / "view.txt").write_bytes(b"original")
    git("add", "view.txt")
    git("commit", "-m", "original")
    original = git("rev-parse", "HEAD")
    (tmp_path / "view.txt").write_bytes(b"replacement")
    git("commit", "-am", "replacement")
    replacement = git("rev-parse", "HEAD")
    git("replace", original, replacement)
    with pytest.raises(ValidationError, match="ACTUAL_COMMIT_TREE_MISMATCH"):
        approved_git_view(tmp_path, original, "TEST_ONLY_REPLACE_REPOSITORY", ["view.txt"])


@pytest.mark.parametrize("mutation", ["generic_operation", "legacy_typed_event", "same_commit_start"])
def test_no_generic_or_same_commit_transition_bypass(setup_p0, mutation):
    store, intake, _, request, _, _, _ = setup_p0
    before = snapshot(store)
    body = request.command.body()
    if mutation == "generic_operation":
        body["operation"] = "GENERIC_IMPORT"
    elif mutation == "legacy_typed_event":
        body["events"] = [{"event_type": "AttemptStarted"}]
    else:
        body["events"].append({"event_type": "P0AttemptStarted", "attempt_ref": body["proposed_object_refs"][0],
                               "assignment_ref": body["proposed_object_refs"][0], "binding_ref": body["proposed_object_refs"][0]})
    with pytest.raises(ValidationError):
        accept(intake, replace(request, command=LimitedCommand(body, intake.runtime)))
    assert snapshot(store) == before


def test_generator_events_are_snapshotted_once_by_same_store(setup_p0):
    store, intake, _, request, _, _, _ = setup_p0
    generated = replace(request, events=(event for event in request.events))
    assert accept(intake, generated).head.commit_seq == 1
    assert len(store.commits()[0]["events"]) == 8
