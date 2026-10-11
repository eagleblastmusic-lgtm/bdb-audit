"""All M05 operation/state branches in the real writer, with simulated OS/CMS.

Histories are copies of real accepted test transactions. No state predicate,
history verifier, transport parser or writer is replaced. This is not RQ.
"""

from dataclasses import replace
from pathlib import Path
import shutil

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_wire import LimitedCommand, identifier, sorted_refs
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake
from tests.product import test_limited_p0 as fixtures
from tests.product.test_limited_p0 import corpus as p0_corpus, setup_p0 as p0_setup

corpus = p0_corpus
setup_p0 = p0_setup


def test_all_72_operation_state_pairs_in_central_store(setup_p0, monkeypatch):
    store, intake, _, _, grant, source, genesis = setup_p0
    folder = Path(store.path).parent
    original_accept = fixtures.accept
    templates, states, contexts = {}, {}, {}

    def save(state):
        target = folder / ("TEST_ONLY_STATE_" + state + ".sqlite")
        # Store uses synchronous DELETE journals and has no open transaction here.
        assert not Path(store.path + "-wal").exists()
        assert not Path(store.path + "-journal").exists()
        shutil.copyfile(store.path, target)
        head, records, _ = intake.snapshot()
        states[state] = target
        contexts[state] = (
            head,
            intake.runtime.cut_for(head, records) if head else None,
        )

    effects = {
        "INITIALIZE_P0_FROM_APPROVED_GIT": "GENESIS",
        "CREATE_ASSIGNMENT": "ASSIGNED",
        "BIND_PACKAGE": "BOUND",
        "START_ATTEMPT": "STARTED",
        "CONFIRM_DELIVERY": "DELIVERED",
        "INGEST_EVIDENCE": "EVIDENCE_ACCEPTED",
        "ACCEPT_RESULT": "RESULT_ACCEPTED",
    }

    def capture(current_intake, request, cert=fixtures.COORDINATOR):
        templates[request.command.command_kind] = request
        # This STARTED snapshot includes the real protected outbox SENT record.
        if request.command.command_kind == "CONFIRM_DELIVERY":
            save("STARTED")
        outcome = original_accept(current_intake, request, cert)
        save(effects[request.command.command_kind])
        return outcome

    save("EMPTY_HISTORY")
    monkeypatch.setattr(fixtures, "accept", capture)
    delivery_context = fixtures.delivered(setup_p0, monkeypatch)
    assignment = delivery_context[3]
    evidence, _ = fixtures.evidence_request(delivery_context)
    fixtures.accept(intake, evidence)
    scope = intake.runtime.auth_scope(
        genesis.body, source.body, assignment.ref.as_dict(), fixtures.AUDITOR
    )
    recovery = grant(scope, "OWNER_RECOVERY")
    abort = intake.abort(
        actor_ref="TEST_ONLY_OWNER_RECOVERY",
        grant_digest=recovery,
        assignment_ref=assignment.ref.as_dict(),
        reason="OWNER_CANCELLED",
    )
    templates["ABORT_ATTEMPT"] = abort
    result = intake.result(
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=delivery_context[4],
        admission_ref=evidence.objects[0].ref.as_dict(),
    )
    fixtures.accept(intake, result)
    monkeypatch.setattr(fixtures, "accept", original_accept)

    probe_path = folder / "TEST_ONLY_BRANCH_PROBE.sqlite"
    shutil.copyfile(states["EVIDENCE_ACCEPTED"], probe_path)
    probe = TransactionalHistoryStore.open_p0(probe_path)
    probe_intake = LimitedIntake(probe)
    rebound_abort = replace(
        abort,
        command=LimitedCommand(abort.command.body(), probe_intake.runtime),
        objects=tuple(
            probe_intake.runtime.object(o.kind, o.body) for o in abort.objects
        ),
    )
    original_accept(probe_intake, rebound_abort, fixtures.OWNER)
    states["ABORTED"] = folder / "TEST_ONLY_STATE_ABORTED.sqlite"
    shutil.copyfile(probe.path, states["ABORTED"])
    head, records, _ = probe_intake.snapshot()
    contexts["ABORTED"] = (head, probe_intake.runtime.cut_for(head, records))
    next_attempt, next_assignment = probe_intake.draft_assignment(
        auditor_certificate_sha256=fixtures.AUDITOR
    )
    next_scope = probe_intake.runtime.auth_scope(
        genesis.body, source.body, next_assignment.ref.as_dict(), fixtures.AUDITOR
    )
    retry_grant = grant(next_scope)
    grant(next_scope, "AUDITOR")
    retry = probe_intake.prepare(
        "CREATE_ASSIGNMENT",
        [next_attempt, next_assignment],
        actor_ref="TEST_ONLY_COORDINATOR",
        grant_digest=retry_grant,
    )

    # Independent expectations transcribed from approved M05/M15, not runtime dispatch.
    legal = {
        "INITIALIZE_P0_FROM_APPROVED_GIT": {"EMPTY_HISTORY"},
        "CREATE_ASSIGNMENT": {"GENESIS", "ABORTED"},
        "BIND_PACKAGE": {"ASSIGNED"},
        "START_ATTEMPT": {"BOUND"},
        "CONFIRM_DELIVERY": {"STARTED"},
        "INGEST_EVIDENCE": {"DELIVERED"},
        "ACCEPT_RESULT": {"EVIDENCE_ACCEPTED"},
        "ABORT_ATTEMPT": {
            "ASSIGNED",
            "BOUND",
            "STARTED",
            "DELIVERED",
            "EVIDENCE_ACCEPTED",
        },
    }
    assert len(states) == 9 and set(templates) == set(legal)
    allowed, denied = 0, 0

    def candidate(prototype, operation, state, head, cut):
        objects = []
        for obj in prototype.objects:
            body = obj.body.copy()
            for field in body:
                if field.endswith("_cut") and cut is not None:
                    body[field] = cut
            if operation == "ABORT_ATTEMPT" and state in legal[operation]:
                body["from_state"] = state
            objects.append(probe_intake.runtime.object(obj.kind, body))
        command = prototype.command.body()
        command_id = identifier("command_envelope")
        command.update(
            command_id=command_id,
            object_id=command_id,
            expected_parent=head.as_dict() if head else "EMPTY_HISTORY",
            proposed_object_refs=sorted_refs(o.ref.as_dict() for o in objects),
        )
        if operation != "START_ATTEMPT":
            command["events"] = [
                {"event_type": "P0FactAccepted", "artifact_ref": o.ref.as_dict()}
                for o in probe_intake.runtime.order(objects)
            ]
        command["basis_refs"] = probe_intake.runtime.basis(objects, command["events"])
        return replace(
            prototype,
            command=LimitedCommand(command, probe_intake.runtime),
            objects=tuple(objects),
            events=tuple(command["events"]),
        )

    for operation, allowed_states in legal.items():
        for state, template_path in states.items():
            shutil.copyfile(template_path, probe_path)
            prototype = (
                retry
                if operation == "CREATE_ASSIGNMENT" and state == "ABORTED"
                else templates[operation]
            )
            head, cut = contexts[state]
            before = fixtures.snapshot(probe)
            cert = (
                fixtures.OWNER if operation == "ABORT_ATTEMPT" else fixtures.COORDINATOR
            )
            if state in allowed_states:
                request = candidate(prototype, operation, state, head, cut)
                accepted = original_accept(probe_intake, request, cert)
                assert (
                    accepted.head.commit_seq == (head.commit_seq if head else 0) + 1
                ), (operation, state)
                assert not accepted.already_accepted
                allowed += 1
            else:
                # Closed Command grammar can deny an illegal branch before SQL;
                # no weaker constructor is used to force it into the writer.
                with pytest.raises(ValidationError):
                    request = candidate(prototype, operation, state, head, cut)
                    original_accept(probe_intake, request, cert)
                assert fixtures.snapshot(probe) == before, (operation, state)
                denied += 1
    assert (allowed, denied) == (13, 59)
