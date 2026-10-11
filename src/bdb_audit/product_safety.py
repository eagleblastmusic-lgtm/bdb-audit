"""PRODUCT-V1 activation boundary; no caller setting grants NF02 authority."""
from .core.errors import ValidationError

NF02_BLOCK_CODE = "PRODUCT_V1_EXTERNAL_INGESTION_BLOCKED"
NF02_BLOCK_DETAIL = (
    "NF02 OPEN: brak niezależnie autoryzowanego producenta i kwalifikowanej "
    "aktywacji. Zachowaj ZIP poza historią. Przygotowanie paczek, lokalne "
    "kontrole i raport częściowy są dostępne; E1-E6 nie jest ukończone."
)
EXTERNAL_RESULT_KINDS = frozenset({"lane_result_admission_evidence", "bdb_audit_lane_result"})
NF02_ACTIVATION_BLOCKERS = (
    "INDEPENDENT_INSTALLATION_AND_PRODUCER_AUTHORITY_NOT_ESTABLISHED",
    "QUALIFIED_SUCCESSOR_SCHEMA_PROTOCOL_AND_Q1_Q2_NOT_ESTABLISHED",
    "NEW_CAMPAIGN_PRIOR_PACKAGE_BINDING_AND_STARTED_CHRONOLOGY_NOT_IMPLEMENTED",
)

# These lifecycle claims require the unavailable qualified execution protocol,
# even when the caller omits external-result objects from a generic command.
# AttemptStarted itself needs a prior package binding in the successor (§192 E.4).
_QUALIFIED_TRANSITION_TARGETS = {
    "attempt": frozenset({"STARTED", "RESULT_RECEIVED", "RESULT_ACCEPTED"}),
    "lane": frozenset({"COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED"}),
    "stage": frozenset({"COMPLETION_CANDIDATE", "COMPLETION_ACCEPTED"}),
    "campaign": frozenset({"E6_REQUIRED", "E6_RUNNING", "CAMPAIGN_CONCLUDED", "CLOSED"}),
}
_QUALIFIED_EXECUTION_EVENTS = frozenset({
    "AttemptStarted", "LaneCompletionAccepted", "StageCompletionAccepted", "CampaignConclusionAccepted",
})


def require_external_ingestion_authority() -> None:
    """Fail before raw retention, tickets, transactions, or completion writes."""
    raise ValidationError(NF02_BLOCK_CODE, NF02_BLOCK_DETAIL)


def require_qualified_transition_authority(events) -> None:
    """Prevent ordered events from bypassing PRODUCT-V1's activation boundary.

    This is an activation guard, not a substitute for successor transition
    predicates, independent producer authorization, or completion evidence.
    """
    for event in events:
        if not isinstance(event, dict):
            continue  # The commit schema validates all event bodies.
        event_type = event.get("event_type")
        if isinstance(event_type, str) and event_type in _QUALIFIED_EXECUTION_EVENTS:
            require_external_ingestion_authority()
        aggregate = str(event.get("aggregate", "")).lower()
        target = event.get("to_state")
        if isinstance(target, str) and target in _QUALIFIED_TRANSITION_TARGETS.get(aggregate, ()):
            require_external_ingestion_authority()
