"""Exact §192 wire adapter. Historical R5.3 values keep their original codec.

No registrations or trust grants are made by these value classes. Every schema
identity is supplied by the independently installed, immutable SchemaRegistry.
"""
from dataclasses import dataclass, field
import re
from typing import Any

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..core.hashing import object_digest
from .objects import CanonicalObject, ObjectRef, CommandEnvelope, CommitBody, CommandReceipt


def copy(value):
    return parse(canonical_bytes(value))


def eq_ref(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


@dataclass(frozen=True)
class SuccessorRef(ObjectRef):
    schema_revision_ref: Any = ""
    def __post_init__(self):
        if (not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.kind)
                or not re.fullmatch(r"[0-9a-f]{64}", self.revision_digest)
                or self.digest_profile != "BDB-OBJECT-DIGEST-1"
                or type(self.schema_revision_ref) is not dict
                or set(self.schema_revision_ref) != {"kind", "revision_digest"}
                or self.schema_revision_ref["kind"] != "schema"
                or not re.fullmatch(r"[0-9a-f]{64}", self.schema_revision_ref["revision_digest"])):
            raise ValidationError("NF02_EXACT_TYPED_REF_REQUIRED")
        if self.logical_id is not None and not re.fullmatch(
                re.escape(self.kind) + r"_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", self.logical_id):
            raise ValidationError("INVALID_TYPED_ID")

    @classmethod
    def from_dict(cls, value, *, ref_class="CONTENT_OR_PRIOR"):
        required = {"kind", "revision_digest", "digest_profile", "schema_revision_ref"}
        if type(value) is not dict or not required <= set(value) or set(value) - required - {"logical_id"}:
            raise ValidationError("NF02_EXACT_TYPED_REF_REQUIRED")
        return cls(value["kind"], value["revision_digest"], value["digest_profile"],
                   copy(value["schema_revision_ref"]), value.get("logical_id"), ref_class)

    def as_dict(self, *, ref_class=None):
        out = {"kind": self.kind, "revision_digest": self.revision_digest,
               "digest_profile": self.digest_profile, "schema_revision_ref": copy(self.schema_revision_ref)}
        if self.logical_id is not None:
            out["logical_id"] = self.logical_id
        return out


@dataclass(frozen=True)
class SuccessorObject(CanonicalObject):
    schema_revision_ref: Any = ""
    runtime: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        expected = self.runtime.schema_ref(self.kind, self.version)
        if self.schema_revision_ref and self.schema_revision_ref != expected:
            raise ValidationError("NF02_SCHEMA_IDENTITY_MISMATCH")
        object.__setattr__(self, "schema_revision_ref", expected)
        object.__setattr__(self, "body", copy(self.body))
        self.runtime.schemas.validate_schema(self.kind, canonical_bytes(self.body), self.version)
        self.as_ref()  # Check the exact logical-ID grammar, when present.

    @property
    def digest(self):
        return object_digest(self.kind, self.version, self.body, registry_kind=self.kind,
                             registry=self.runtime.registry,
                             post_acceptance_sidecar=self.kind == "command_receipt").value

    def as_ref(self, *, ref_class=None):
        return SuccessorRef(self.kind, self.digest, "BDB-OBJECT-DIGEST-1", self.schema_revision_ref,
                            self.logical_id, ref_class or "CONTENT_OR_PRIOR")

    @property
    def content_refs(self):
        return tuple(self.runtime.object_refs(self, {"CONTENT_OR_PRIOR", "CONTENT_OBJECT"}))

    @property
    def prior_content_refs(self):
        return tuple(self.runtime.object_refs(self, {"PRIOR_ACCEPTED_ONLY"}))


@dataclass(frozen=True)
class SuccessorCommand(CommandEnvelope):
    expected_parent_head: Any
    runtime: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if not re.fullmatch(r"command_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", self.command_id):
            raise ValidationError("INVALID_COMMAND_ID")
        object.__setattr__(self, "expected_parent_head", copy(self.expected_parent_head))
        object.__setattr__(self, "governing_policy_ref", copy(self.governing_policy_ref))
        object.__setattr__(self, "governing_spec_refs", tuple(copy(list(self.governing_spec_refs))))
        if self.command_payload is not None:
            object.__setattr__(self, "command_payload", copy(self.command_payload))
        self.as_object()

    def as_object(self):
        return self.runtime.object("command_envelope", self.body())


@dataclass(frozen=True)
class SuccessorCommit(CommitBody):
    runtime: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if (self.command_digest != self.command_ref.revision_digest
                or self.prev_history_ref != self.expected_parent_head
                or (self.commit_seq == 1) != (self.prev_history_ref == "EMPTY_HISTORY")
                or self.command_digest not in [ref.revision_digest for ref in self.immutable_object_refs]
                or len({ref.revision_digest for ref in self.immutable_object_refs}) != len(self.immutable_object_refs)):
            raise ValidationError("NF02_COMMIT_BINDING_CONFLICT")
        # Ordinal is the sequence position, outside the closed event body.
        if any("ordinal" in event for event in self.ordered_event_bodies):
            raise ValidationError("EVENT_ORDINAL_IN_BODY")
        self.as_object()

    def as_object(self):
        return self.runtime.object("commit_body", self.body())


@dataclass(frozen=True)
class SuccessorReceipt(CommandReceipt):
    runtime: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.accepted_commit_ref["revision_digest"] != self.accepted_head.commit_hash:
            raise ValidationError("RECEIPT_HEAD_TARGET_MISMATCH")
        self.as_object()

    def body(self):
        return {"command_id": self.command_id, "command_digest": self.command_ref.revision_digest,
                "command_ref": self.command_ref.as_dict(), "accepted_commit_ref": copy(self.accepted_commit_ref),
                "accepted_head": self.accepted_head.as_dict(),
                "result_object_refs": [ref.as_dict() for ref in self.result_object_refs]}

    def as_object(self):
        return self.runtime.object("command_receipt", self.body())
