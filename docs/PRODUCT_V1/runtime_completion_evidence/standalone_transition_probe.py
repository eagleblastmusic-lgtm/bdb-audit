"""Negative probe of the actual standalone Store, using no source imports."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
from uuid import uuid4

artifact, database, output = map(Path, sys.argv[1:])
embedded = runpy.run_path(str(artifact.resolve()))
runtime_root = embedded["bootstrap_environment"]()
from bdb_audit.core.errors import ValidationError  # noqa: E402
from bdb_audit.history.objects import CommandEnvelope  # noqa: E402
from bdb_audit.history.store import TransactionalHistoryStore  # noqa: E402
from bdb_audit.product_safety import NF02_BLOCK_CODE  # noqa: E402

def snapshot():
    return {str(p.relative_to(database.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in database.parent.rglob("*") if p.is_file()}

before = snapshot()
store = TransactionalHistoryStore(database)
head = store.head()
prior = store.commits()[-1]
rejected = []
for event in [
    {"aggregate": "Attempt", "id": "negative-probe", "from_state": "CREATED", "to_state": "STARTED"},
    {"aggregate": "Lane", "id": "negative-probe", "from_state": "COMPLETION_CANDIDATE", "to_state": "COMPLETION_ACCEPTED"},
    {"event_type": "AttemptStarted"},
    {"event_type": "StageCompletionAccepted"},
]:
    command = CommandEnvelope(
        command_id=f"command_{uuid4()}", command_kind="RECORD_FOUNDATION_FACT",
        actor_ref=prior["actor_ref"], expected_parent_head={"tag": "ACCEPTED_HEAD_REF", **head.as_dict()},
        governing_policy_ref=prior["governing_policy_ref"], governing_spec_refs=tuple(prior["governing_spec_refs"]),
        idempotency_scope="standalone-negative-probe", campaign_ref=head.campaign_id,
    )
    try:
        store.accept(command, expected_head=head, ordered_events=(e for e in [event]))
    except ValidationError as error:
        assert error.code == NF02_BLOCK_CODE, str(error)
        rejected.append(event)
    else:
        raise AssertionError("Unqualified event was accepted")
    assert store.receipt(command.command_id) is None
    assert snapshot() == before
assert store.head() == head
result = {
    "status": "PASS_NEGATIVE_RUNTIME_ONLY", "distribution": "standalone -I",
    "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    "runtime_root": str(runtime_root), "store": str(database), "rejected_events": rejected,
    "all_campaign_file_hashes_unchanged": True, "receipt_created": False,
    "producer_authority": "NOT_ESTABLISHED", "full_audit": "NOT_COMPLETED", "formal_Q1_Q2": "NO_NEW_PASS",
}
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": result["status"], "rejected": len(rejected)}))
