"""Exact approved 18/7/43 corpus. Definitions never establish authority."""
from copy import deepcopy
import hashlib

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..core.registry import ContractRegistry
from ..schemas.binding import SchemaBindings

MODEL_ID = "BDB_NF02_P0_LIMITED_1"
BASE = "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/"
MANIFEST_SHA = "278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9"
GRAPH_SHA = "7ad1c90ee72634b633e2a9c260e5d7b93d69fc9a1bcca76632291a047f15f27e"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def domain_hash(domain, body):
    return sha(domain.encode("ascii") + b"\0" + canonical_bytes(body))


def strict_json(raw, *, limit=2 * 1024 * 1024):
    """Bound bytes and nesting before allocating the parsed JSON structure."""
    if type(raw) is not bytes or len(raw) > limit:
        raise ValidationError("P0_JSON_RESOURCE_LIMIT")
    depth, quoted, escaped = 0, False, False
    for c in raw:
        if quoted:
            if escaped:
                escaped = False
            elif c == 92:
                escaped = True
            elif c == 34:
                quoted = False
        elif c == 34:
            quoted = True
        elif c in (91, 123):
            depth += 1
            if depth > 32:
                raise ValidationError("P0_JSON_RESOURCE_LIMIT")
        elif c in (93, 125):
            depth -= 1
    return parse(raw)


class LimitedRegistry(ContractRegistry):
    def __init__(self, descriptor, raw):
        self._raw = raw
        self._doc = {"contracts": list(descriptor["canonical_contracts"].values())}
        self._contracts = {(r["kind"], r["version"]): r for r in self._doc["contracts"]}
        self._extension_contracts = {}

    def contract(self, kind, version="1"):
        try:
            return deepcopy(self._contracts[(kind, version)])
        except KeyError as exc:
            raise ValidationError("P0_UNREGISTERED_CONTRACT", kind + "/" + version) from exc

    def register_extension_contract(self, contract_entry):
        raise ValidationError("P0_CLOSED_REGISTRY")


class LimitedSchemas(SchemaBindings):
    def __init__(self, documents):
        self.documents = documents
        self.resources = Registry().with_resources(
            (doc["$id"], Resource.from_contents(doc)) for doc in documents.values())
        for doc in documents.values():
            Draft202012Validator.check_schema(doc)

    def validate(self, name, value):
        try:
            doc = self.documents[name]
            Draft202012Validator(doc, registry=self.resources).validate(value)
        except Exception as exc:
            raise ValidationError("P0_SCHEMA_INVALID", name) from exc

    def validate_schema(self, kind, raw, wire_version="1"):
        self.validate("canonical/" + kind + "__" + wire_version, strict_json(raw))

    def validate_ref(self, value):
        try:
            Draft202012Validator({"$ref": "urn:bdb:p0:wire:COMMON/1#/$defs/TypedRef"}, registry=self.resources).validate(value)
        except Exception as exc:
            raise ValidationError("P0_EXACT_TYPED_REF_REQUIRED") from exc


class LimitedCorpus:
    def __init__(self, files):
        self.files = {name: bytes(raw) for name, raw in files.items()}
        manifest_raw = self.files[BASE + "CANDIDATE_MANIFEST.json"]
        if sha(manifest_raw) != MANIFEST_SHA or sha(self.files[BASE + "DEPENDENCY_GRAPH.json"]) != GRAPH_SHA:
            raise ValidationError("P0_APPROVED_CANDIDATE_MISMATCH")
        manifest = strict_json(manifest_raw)
        for group in ("normative", "machine"):
            entries = manifest[group + "_files"]
            if entries != sorted(entries, key=lambda x: x["file"]) or len({e["file"] for e in entries}) != len(entries):
                raise ValidationError("P0_CANDIDATE_SET_MEMBERSHIP")
            digest = domain_hash("BDB-NF02-P0-" + group.upper() + "-SET/1", entries)
            if manifest[group + "_set_sha256"] != digest:
                raise ValidationError("P0_CANDIDATE_SET_DIGEST")
            for entry in entries:
                raw = self.files[entry["file"]]
                if entry != {"file": entry["file"], "sha256": sha(raw), "bytes": len(raw)}:
                    raise ValidationError("P0_CANDIDATE_CONTENT_DRIFT", entry["file"])
        self.manifest = manifest
        self.descriptor = strict_json(self.files[BASE + "MODEL.json"])
        documents = {name[len(BASE + "schemas/"):-len(".schema.json")]: strict_json(raw)
                     for name, raw in self.files.items() if name.startswith(BASE + "schemas/") and name.endswith(".schema.json")}
        if len(documents) != 43 or len(self.descriptor["canonical_contracts"]) != 18:
            raise ValidationError("P0_CLOSURE_MISMATCH")
        self.schemas = LimitedSchemas(documents)
        self.schemas.validate("external/CANDIDATE_MANIFEST__1", manifest)
        self.registry = LimitedRegistry(self.descriptor, self.files[BASE + "MODEL.json"])
        self.versions = {v["kind"]: v["version"] for v in self.descriptor["canonical_contracts"].values()}
        self.operations = {v["name"]: v for v in self.descriptor["operations"]}

    def pin(self, profile):
        return {"profile_id": profile, "revision_digest": sha(self.files[BASE + "profiles/" + profile + ".json"])}

    def schema_ref(self, kind, version=None):
        version = version or self.versions[kind]
        row = self.registry.contract(kind, version)
        raw = self.files[BASE + "schemas/canonical/" + kind + "__" + version + ".schema.json"]
        return {"schema_id": row["schema_id"], "raw_digest": sha(raw)}

    def raw_ref(self, raw, profile, media_type):
        return {"raw_digest": sha(raw), "byte_length": len(raw), "media_type": media_type,
                "artifact_contract_ref": self.pin(profile)}

    def bindings(self):
        return {"candidate_manifest_sha256": MANIFEST_SHA,
                "normative_set_sha256": self.manifest["normative_set_sha256"],
                "machine_set_sha256": self.manifest["machine_set_sha256"]}

    def external(self, name, raw):
        value = strict_json(raw)
        if name != "CANDIDATE_MANIFEST" and raw != canonical_bytes(value) + b"\n":
            raise ValidationError("P0_CJSON_TRANSPORT_REQUIRED", name)
        self.schemas.validate("external/" + name + "__1", value)
        if name not in {"ROOT", "PRINCIPAL_GRANT", "CANDIDATE_MANIFEST"}:
            if any(value[k] != v for k, v in self.bindings().items()):
                raise ValidationError("P0_GOVERNANCE_CANDIDATE_MISMATCH", name)
        return value
