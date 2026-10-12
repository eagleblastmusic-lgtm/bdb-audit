"""Explicit P0 versions with the existing ObjectDigest primitive."""
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..core.hashing import object_digest
from .objects import CanonicalObject, ObjectRef, CommandEnvelope, AcceptedHead
from .limited_model import MODEL_ID


def copy(value):
    return parse(canonical_bytes(value))


def identifier(kind):
    return kind + "_" + str(uuid4())


def refs_in(value):
    if isinstance(value, dict):
        if {"kind", "version", "revision_digest", "schema_revision_ref", "digest_profile", "logical_id"} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from refs_in(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from refs_in(child)


def sorted_refs(refs):
    unique = {canonical_bytes(r): r for r in refs}
    return sorted(unique.values(), key=lambda r: (r["kind"], r["logical_id"], r["revision_digest"]))


@dataclass(frozen=True)
class LimitedRef(ObjectRef):
    schema_revision_ref: Any = ""
    version: str = "1"

    def __post_init__(self):
        # Full grammar/version/schema hash is verified by the installed corpus.
        if not self.logical_id or self.digest_profile != "BDB-OBJECT-DIGEST-1":
            raise ValidationError("P0_EXACT_TYPED_REF_REQUIRED")

    def as_dict(self, *, ref_class=None):
        return {"kind": self.kind, "version": self.version, "revision_digest": self.revision_digest,
                "digest_profile": self.digest_profile, "schema_revision_ref": copy(self.schema_revision_ref),
                "logical_id": self.logical_id}


@dataclass(frozen=True)
class LimitedObject(CanonicalObject):
    schema_revision_ref: Any = ""
    runtime: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        expected = self.runtime.schema_ref(self.kind, self.version)
        if self.schema_revision_ref and self.schema_revision_ref != expected:
            raise ValidationError("P0_SCHEMA_IDENTITY_MISMATCH")
        body = copy(self.body)
        if self.logical_id != body.get("object_id"):
            raise ValidationError("P0_LOGICAL_ID_MISMATCH")
        object.__setattr__(self, "schema_revision_ref", expected)
        object.__setattr__(self, "body", body)
        self.runtime.schemas.validate_schema(self.kind, canonical_bytes(body), self.version)

    @property
    def digest(self):
        return object_digest(self.kind, self.version, self.body, registry_kind=self.kind,
                             post_acceptance_sidecar=self.kind == "command_receipt", registry=self.runtime.registry).value

    def as_ref(self, *, ref_class=None):
        return LimitedRef(self.kind, self.digest, "BDB-OBJECT-DIGEST-1", self.schema_revision_ref,
                          self.logical_id, ref_class or "CONTENT_OR_PRIOR", self.version)

    @property
    def content_refs(self):
        return tuple(self.runtime.ref(r) for r in refs_in(self.body))


class LimitedCommand(CommandEnvelope):
    runtime: Any
    _value: dict[str, Any]
    def __init__(self, body, runtime):
        b = copy(body)
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "_value", b)
        self.as_object()  # Closed schema before reading caller-controlled fields.
        values = {"command_id": b["command_id"], "command_kind": b["operation"], "actor_ref": b["actor_ref"],
                  "expected_parent_head": b["expected_parent"], "governing_policy_ref": b["policy_ref"],
                  "governing_spec_refs": (b["spec_ref"],), "campaign_ref": b["campaign_id"],
                  "proposed_campaign_id": b["campaign_id"], "idempotency_scope": b["campaign_id"]}
        for k, v in values.items():
            object.__setattr__(self, k, v)
        if b["command_id"] != b["object_id"]:
            raise ValidationError("P0_COMMAND_ID_MISMATCH")

    def body(self):
        return copy(self._value)

    def as_object(self):
        return self.runtime.object("command_envelope", self.body())

    def signing_bytes(self):
        return b"BDB_NF02_P0_COMMAND/1\0" + canonical_bytes(self.body())


class LimitedCommit:
    def __init__(self, body, runtime):
        self.obj = runtime.object("commit_body", body)
        b = self.obj.body
        self.immutable_object_refs = tuple(runtime.ref(r) for r in b["immutable_object_refs"])
        self.digest = self.obj.digest

    def body(self):
        return copy(self.obj.body)


class LimitedReceipt:
    def __init__(self, body, runtime):
        self.obj = runtime.object("command_receipt", body)
        b = self.obj.body
        self.command_ref = runtime.ref(b["command_ref"])
        self.command_id = self.command_ref.logical_id
        self.result_object_refs = tuple(runtime.ref(r) for r in b["result_object_refs"])
        self.accepted_head = AcceptedHead(**b["accepted_head"])
        self.digest = self.obj.digest

    def body(self):
        return copy(self.obj.body)


def value_body(kind, fields, object_id=None):
    return {"object_id": object_id or identifier(kind), "model_id": MODEL_ID, **copy(fields)}
