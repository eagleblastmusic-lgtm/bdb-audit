"""M04 content refs must bind all target fields, including logical ID."""
from copy import deepcopy
from pathlib import Path

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_wire import LimitedCommand
from tests.product.test_limited_p0 import corpus as p0_corpus, setup_p0 as p0_setup, accept, snapshot

corpus = p0_corpus
setup_p0 = p0_setup


@pytest.mark.parametrize("field", ["installation_ref", "source_ref"])
def test_same_content_digest_cannot_alias_target_logical_id(setup_p0, field):
    store, intake, _, request, _, source, genesis = setup_p0
    before = snapshot(store)
    before_bytes = open(store.path, "rb").read()
    body = deepcopy(genesis.body)
    ref = body[field]
    ref["logical_id"] = ref["kind"] + "_00000000-0000-4000-8000-000000000000"
    changed = intake.runtime.object("campaign_genesis", body)
    altered = intake.initialize(source=source, genesis=changed, actor_ref=request.command.actor_ref,
        grant_digest=request.command.body()["grant_digest"], raw=request.raw)
    with pytest.raises(ValidationError, match="P0_CONTENT_REFERENCE_IDENTITY_MISMATCH"):
        accept(intake, altered)
    assert snapshot(store) == before
    assert open(store.path, "rb").read() == before_bytes


@pytest.mark.parametrize("field", ["command_id", "operation", "policy_ref", "basis_refs"])
def test_missing_command_field_is_schema_denial_before_field_access(setup_p0, field):
    store, intake, _, request, _, _, _ = setup_p0
    before = snapshot(store)
    body = deepcopy(request.command.body())
    del body[field]
    with pytest.raises(ValidationError, match="P0_SCHEMA_INVALID"):
        LimitedCommand(body, intake.runtime)
    assert snapshot(store) == before


def test_service_prepared_output_is_scoped_and_never_overwrites(setup_p0, tmp_path):
    from bdb_audit.product_p0_cli import write_prepared
    store, _, _, _, _, _, _ = setup_p0
    before = snapshot(store)
    database_before = Path(store.path).read_bytes()
    outside = Path(store.path).parent.parent / "must-not-be-written.json"
    with pytest.raises(ValidationError, match="P0_PROTECTED_OUTPUT_LOCATION_REQUIRED"):
        write_prepared(store, outside, b"packet")
    assert not outside.exists()
    assert snapshot(store) == before
    target = Path(store.path).parent / "unsigned-packet.json"
    write_prepared(store, target, b"packet")
    prepared_snapshot = snapshot(store)
    with pytest.raises(FileExistsError):
        write_prepared(store, target, b"replacement")
    assert target.read_bytes() == b"packet"
    assert snapshot(store) == prepared_snapshot
    assert Path(store.path).read_bytes() == database_before


def test_history_namespace_cannot_be_escaped_by_parent_segments(tmp_path, monkeypatch):
    from bdb_audit.history import limited_authority
    root = tmp_path / "BDB Audit" / "NF02-P0-Limited"
    monkeypatch.setattr(limited_authority, "machine_root", lambda: root)
    namespace = "a" * 64
    requested = root.parent / "P0-Campaigns" / namespace / ".." / "another-namespace" / "campaign.sqlite"
    with pytest.raises(ValidationError, match="P0_PROTECTED_HISTORY_LOCATION_REQUIRED"):
        with limited_authority.LimitedMachineAuthority().storage_lease(requested, {"root": {"namespace_authority_digest": namespace}}):
            pytest.fail("Parent traversal admitted as protected namespace storage")
    assert not requested.exists()
