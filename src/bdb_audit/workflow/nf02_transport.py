"""Production form of the prepared R5.4.2 raw normalizer.

All profiles/schema bytes are selected by the installed successor context.
The pure transform neither grants authority nor stages/accepts raw artifacts.
"""
from __future__ import annotations

import hashlib
import io
import struct
import zipfile

from jsonschema import Draft202012Validator

from ..assurance.zip_safety import Limits, read_bytes
from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError

ASSIGNMENT_CLAIMS = frozenset(("assignment_ref", "attempt_ref", "source_generation_ref", "assignment_input_history_cut",
                              "stage_spec_ref", "lane_spec_ref", "executor_profile_ref", "delivery_profile_ref"))


class NF02Transport:
    def __init__(self, profiles, schemas):
        self.profiles = {name: bytes(raw) for name, raw in profiles.items()}
        self.schemas = {name: bytes(raw) for name, raw in schemas.items()}

    def pin(self, name):
        return {"profile_id": name, "revision_digest": hashlib.sha256(self.profiles[name]).hexdigest()}

    def profile(self, name):
        return parse(self.profiles[name])

    def _transport(self, raw, profile_id):
        profile = self.profile(profile_id)
        q = profile["quotas"]
        members = read_bytes(raw, limits=Limits(input_bytes=q["max_archive_bytes"], members=q["max_members"],
                            member_bytes=q["max_member_bytes"], expanded_bytes=q["max_total_expanded_bytes"]))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if (archive.comment or not infos or infos[0].header_offset != 0
                    or names != sorted(names, key=lambda name: name.encode("utf-8"))
                    or [item.header_offset for item in infos] != sorted(item.header_offset for item in infos)):
                raise ValidationError("NF02_TRANSPORT_METADATA")
            if len({name.casefold() for name in names}) != len(names):
                raise ValidationError("NF02_CASEFOLD_PATH_COLLISION")
            for item in infos:
                method, local_time, local_date = struct.unpack_from("<HHH", raw, item.header_offset + 8)
                if (method, local_time, local_date) != (zipfile.ZIP_STORED, 0, 33):
                    raise ValidationError("NF02_LOCAL_TRANSPORT_METADATA", item.filename)
                if (not item.filename.isascii() or len(item.filename) > q["max_path_bytes"]
                        or any(part in ("", ".", "..") for part in item.filename.split("/"))
                        or item.compress_type != zipfile.ZIP_STORED or item.date_time != (1980, 1, 1, 0, 0, 0)
                        or item.comment or item.flag_bits & 1 or (item.external_attr >> 16) != 0o100644):
                    raise ValidationError("NF02_TRANSPORT_METADATA", item.filename)
        if "MANIFEST.json" not in members:
            raise ValidationError("MISSING_MANIFEST")
        manifest = parse(members["MANIFEST.json"])
        schema = parse(self.schemas[profile_id])
        if not Draft202012Validator(schema).is_valid(manifest):
            raise ValidationError("NF02_TRANSPORT_SCHEMA")
        if manifest["transport_profile_ref"] != self.pin(profile_id):
            raise ValidationError("NF02_NORMALIZER_PIN_MISMATCH")
        records = []
        mime = profile["mime_mapping"]
        for name in sorted(set(members) - {"MANIFEST.json"}, key=lambda name: name.encode("utf-8")):
            data = members[name]
            extension = "." + name.rsplit(".", 1)[-1] if "." in name else ""
            records.append({"path": name, "raw_digest": hashlib.sha256(data).hexdigest(),
                            "byte_length": len(data), "media_type": mime.get(extension, mime["default"])})
        if manifest["members"] != records:
            raise ValidationError("NF02_RESULT_MEMBER_MISMATCH")
        return manifest, members, records

    @staticmethod
    def claims(manifest, expected, required):
        if type(expected) is not dict or set(expected) != required:
            raise ValidationError("NF02_COMPLETE_EXPECTED_CONTEXT_REQUIRED")
        if any(manifest[key] != expected[key] for key in required):
            raise ValidationError("NF02_ACCEPTED_CONTEXT_CLAIM_MISMATCH")

    def package(self, raw, expected):
        manifest, members, records = self._transport(raw, "NF02_INPUT_PACKAGE_TRANSPORT_V2")
        self.claims(manifest, expected, ASSIGNMENT_CLAIMS | {"result_slot_contract_refs"})
        pin = self.pin("NF02_PACKAGE_SEMANTIC_PROFILE_V1")
        descriptor = {"profile_ref": pin,
                      "manifest": {k: v for k, v in manifest.items() if k != "package_semantic_digest"}, "members": records}
        semantic = {"profile_ref": pin, "digest": hashlib.sha256(canonical_bytes(descriptor)).hexdigest()}
        if manifest["package_semantic_digest"] != semantic:
            raise ValidationError("NF02_PACKAGE_SEMANTIC_MISMATCH")
        return semantic, members

    def result(self, raw, expected):
        manifest, members, _ = self._transport(raw, "NF02_RESULT_TRANSPORT_V2")
        self.claims(manifest, expected, ASSIGNMENT_CLAIMS | {"package_binding_ref", "result_slot_contract_ref", "input_package_digest"})
        payload = manifest["result_payload"]
        ids = [finding["finding_id"] for finding in payload["findings"]]
        if len(ids) != len(set(ids)):
            raise ValidationError("NF02_DUPLICATE_FINDING_ID")
        sequences = [finding["evidence_member_paths"] for finding in payload["findings"]]
        sequences.extend(output["member_paths"] for output in payload["outputs"].values())
        for paths in sequences:
            if paths != sorted(set(paths), key=lambda name: name.encode("utf-8")):
                raise ValidationError("NF02_MEMBER_PATH_ORDER")
            if any(name not in members or name == "MANIFEST.json" for name in paths):
                raise ValidationError("NF02_MISSING_PAYLOAD_MEMBER")
        return canonical_bytes(payload)
