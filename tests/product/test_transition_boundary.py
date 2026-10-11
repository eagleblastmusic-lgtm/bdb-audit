"""Production Store events cannot substitute for qualified result authority."""
from uuid import uuid4

import pytest

from bdb_audit.coordinator import Coordinator
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.objects import CommandEnvelope
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.product_safety import NF02_BLOCK_CODE
from tests.product.test_product_v1 import campaign as product_campaign, _bytes

campaign = product_campaign


def _command(store):
    prior = store.commits()[-1]
    head = store.head()
    return CommandEnvelope(
        command_id=f"command_{uuid4()}", command_kind="RECORD_FOUNDATION_FACT",
        actor_ref=prior["actor_ref"],
        expected_parent_head={"tag": "ACCEPTED_HEAD_REF", **head.as_dict()},
        governing_policy_ref=prior["governing_policy_ref"],
        governing_spec_refs=tuple(prior["governing_spec_refs"]),
        idempotency_scope="transition-boundary-test", campaign_ref=head.campaign_id,
    )


def _events(aggregate, aggregate_id, states):
    return [{"aggregate": aggregate, "aggregate_id": aggregate_id,
             "from_state": before, "to_state": after}
            for before, after in zip(states, states[1:])]


@pytest.mark.parametrize("aggregate,states", [
    ("attempt", ["CREATED", "STARTED", "RESULT_RECEIVED", "RESULT_ACCEPTED"]),
    ("lane", ["PLANNED", "READY", "RUNNING", "COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED"]),
    ("Stage", ["PLANNED", "READY", "RUNNING", "COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED"]),
    ("Campaign", ["CREATED", "GENESIS_ACCEPTED", "E0_READY", "AUDIT_RUNNING", "CAMPAIGN_CONCLUDED", "CLOSED"]),
])
@pytest.mark.parametrize("entrypoint", ["store", "coordinator-generator"])
def test_events_cannot_launder_external_result_or_completion(campaign, aggregate, states, entrypoint):
    path, _, created = campaign
    store = TransactionalHistoryStore(path)
    attempt = store.object_record(created["packages"][0]["attempt_ref"]["revision_digest"])
    lane = store.object_record(attempt["body"]["lane_run_ref"]["revision_digest"])
    stage = store.object_record(lane["body"]["stage_run_ref"]["revision_digest"])
    aggregate_id = {
        "attempt": attempt["body"]["attempt_id"],
        "lane": lane["body"]["lane_run_id"],
        "stage": stage["body"]["stage_run_id"],
        "campaign": created["campaign_id"],
    }[aggregate.lower()]
    events = _events(aggregate, aggregate_id, states)
    if entrypoint == "coordinator-generator":
        # The alias accepted by the pure projector must have the same boundary.
        for event in events:
            event["id"] = event.pop("aggregate_id")
        writer = Coordinator(store)
        supplied = (event for event in events)
    else:
        writer = store
        supplied = events
    command = _command(store)
    before = _bytes(path.parent)
    with pytest.raises(ValidationError, match=NF02_BLOCK_CODE):
        writer.accept(command, expected_head=store.head(), ordered_events=supplied)
    assert store.receipt(command.command_id) is None
    assert _bytes(path.parent) == before


def test_generator_events_are_validated_and_persisted_from_one_snapshot(campaign):
    path, _, _ = campaign
    store = TransactionalHistoryStore(path)
    command = _command(store)
    event = {"event_type": "ProductDiagnostic", "detail": "No execution or acceptance claim"}
    result = store.accept(command, expected_head=store.head(), ordered_events=(e for e in [event]))
    assert result.commit.ordered_event_bodies == (event,)
    assert store.commits()[-1]["ordered_event_bodies"] == [event]
    retry = store.accept(command, expected_head=store.head(), ordered_events=(e for e in [event]))
    assert retry.already_accepted and retry.receipt.digest == result.receipt.digest


@pytest.mark.parametrize("aggregate,before,after", [
    ("attempt", "STARTED", "RESULT_RECEIVED"),
    ("ATTEMPT", "RESULT_RECEIVED", "RESULT_ACCEPTED"),
    ("lane", "COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED"),
    ("STAGE", "COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED"),
    ("Campaign", "AUDIT_RUNNING", "E6_REQUIRED"),
    ("campaign", "E6_REQUIRED", "E6_RUNNING"),
    ("campaign", "CAMPAIGN_CONCLUDED", "CLOSED"),
])
def test_separate_success_event_has_same_activation_boundary(campaign, aggregate, before, after):
    # This also covers a late event submitted against an already-started legacy
    # history. Neither an invented id nor a prior FSM state can grant authority.
    path, _, _ = campaign
    store = TransactionalHistoryStore(path)
    command = _command(store)
    snapshot = _bytes(path.parent)
    with pytest.raises(ValidationError, match=NF02_BLOCK_CODE):
        store.accept(command, expected_head=store.head(), ordered_events=[{
            "aggregate": aggregate, "id": "caller-selected-subject",
            "from_state": before, "to_state": after,
        }])
    assert store.receipt(command.command_id) is None
    assert _bytes(path.parent) == snapshot


def test_caller_cannot_change_events_after_transition_validation(campaign):
    path, _, _ = campaign
    original = {"event_type": "ProductDiagnostic", "detail": {"message": "checked"}}
    event = {"event_type": "ProductDiagnostic", "detail": {"message": "checked"}}

    def mutate_caller_payload(boundary):
        if boundary == "before_object_durability":
            event["detail"]["message"] = "substituted"
            event.update({"aggregate": "attempt", "aggregate_id": "forged-attempt",
                          "from_state": "CREATED", "to_state": "STARTED"})

    store = TransactionalHistoryStore(path, crash_hook=mutate_caller_payload)
    result = store.accept(_command(store), expected_head=store.head(), ordered_events=[event])
    assert event != original
    assert result.commit.ordered_event_bodies == (original,)
    assert TransactionalHistoryStore(path).commits()[-1]["ordered_event_bodies"] == [original]


@pytest.mark.parametrize("event_type", [
    "AttemptStarted", "LaneCompletionAccepted", "StageCompletionAccepted", "CampaignConclusionAccepted",
])
def test_typed_execution_event_cannot_substitute_for_qualified_fact(campaign, event_type):
    path, _, _ = campaign
    store = TransactionalHistoryStore(path)
    command = _command(store)
    snapshot = _bytes(path.parent)
    with pytest.raises(ValidationError, match=NF02_BLOCK_CODE):
        store.accept(command, expected_head=store.head(), ordered_events=[{
            "event_type": event_type, "campaign_id": store.head().campaign_id,
        }])
    assert store.receipt(command.command_id) is None
    assert _bytes(path.parent) == snapshot
