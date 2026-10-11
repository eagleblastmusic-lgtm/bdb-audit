"""Local checks of a proposed model, never authority or Q1/Q2/runtime qualification."""
from __future__ import annotations

import copy
import json
import unittest
from typing import Any, ClassVar

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools import nf02_p0_limited_model as model

ZERO = "0" * 64  # Shape-only placeholder, never a credential or qualification.
UUID = "00000000-0000-4000-8000-000000000000"


def reference(kind):
    version = model.KINDS[kind]
    return {"kind": kind, "version": version, "revision_digest": ZERO,
            "schema_revision_ref": {"schema_id": "urn:bdb:p0:canonical:" + kind + "/" + version, "raw_digest": ZERO},
            "digest_profile": "BDB-OBJECT-DIGEST-1", "logical_id": kind + "_" + UUID}


def raw(profile, media):
    return {"raw_digest": ZERO, "byte_length": 1, "media_type": media,
            "artifact_contract_ref": {"profile_id": profile, "revision_digest": ZERO}}


class ProposedModelChecks(unittest.TestCase):
    artifacts: ClassVar[dict[str, bytes]]
    nodes: ClassVar[dict[str, Any]]
    registry: ClassVar[Registry]
    @classmethod
    def setUpClass(cls):
        cls.artifacts = model.artifacts()
        cls.nodes = copy.deepcopy(model.SCHEMA_NODES)
        cls.registry = Registry().with_resources((key, Resource.from_contents(node["schema"])) for key, node in cls.nodes.items())

    def validate(self, schema, value):
        return Draft202012Validator(schema, registry=self.registry).is_valid(value)

    def schema(self, key):
        return self.nodes[key]["schema"]

    def test_all_43_schemas_have_valid_draft_2020_12_grammar(self):
        self.assertEqual(len(self.nodes), 43)
        for key, node in self.nodes.items():
            with self.subTest(key=key):
                Draft202012Validator.check_schema(node["schema"])

    def test_all_external_refs_and_fragments_resolve_offline(self):
        def visit(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    self.registry.resolver().lookup(value["$ref"])
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        for node in self.nodes.values():
            visit(node["schema"])

    def test_closure_has_all_categories_no_unknowns_and_three_qualifications(self):
        graph = json.loads(self.artifacts["DEPENDENCY_GRAPH.json"])
        self.assertEqual(graph["counts"]["schema_categories"], {"wire": 9, "profile": 7, "canonical": 18, "external": 9})
        self.assertEqual(graph["counts"]["qualification_stages"], 3)
        seen = set(graph["roots"])
        while True:
            expanded = seen | {edge["to"] for edge in graph["edges"] if edge["from"] in seen}
            if expanded == seen:
                break
            seen = expanded
        self.assertEqual(seen, set(graph["nodes"]))
        self.assertEqual(seen, set(self.nodes))
        self.assertFalse(graph["semantic_qualification"])
        self.assertEqual(graph["import"], "BLOCKED")

    def test_all_typed_kinds_accept_only_their_exact_version_schema_and_id(self):
        schema = model.typ("TypedRef")
        for kind in model.KINDS:
            with self.subTest(kind=kind):
                valid = reference(kind)
                self.assertTrue(self.validate(schema, valid))
                for field, value in (("version", "999"), ("digest_profile", "RAW-SHA256"), ("logical_id", "alias_" + UUID)):
                    bad = copy.deepcopy(valid)
                    bad[field] = value
                    self.assertFalse(self.validate(schema, bad))
                bad = copy.deepcopy(valid)
                bad["schema_revision_ref"]["schema_id"] = "urn:bdb:p0:canonical:" + kind + "/999"
                self.assertFalse(self.validate(schema, bad))

    def test_old_unknown_and_generic_ref_classes_are_denied(self):
        valid = reference("assignment_package_binding")
        for addition in ({"kind": "checkpoint"}, {"version": "1"}, {"ref_class": "CONTENT_OR_PRIOR"}, {"actor_ref": "self"}):
            with self.subTest(addition=addition):
                self.assertFalse(self.validate(model.typ("TypedRef"), valid | addition))

    def test_field_specific_refs_and_raw_profile_media_are_closed(self):
        self.assertFalse(self.validate(model.ref("assignment_manifest"), reference("attempt")))
        schema = model.raw("P0_RESULT_TRANSPORT_V1", "application/zip")
        value = raw("P0_RESULT_TRANSPORT_V1", "application/zip")
        self.assertTrue(self.validate(schema, value))
        for value in (value | {"media_type": "application/json"}, raw("P0_PACKAGE_TRANSPORT_V1", "application/zip"),
                      value | {"raw_digest": "SHA256:" + ZERO}, value | {"byte_length": True}):
            self.assertFalse(self.validate(schema, value))

    def command(self, op):
        data = json.loads(self.artifacts["MODEL.json"])
        operation = data["operations"][op]
        objects = [reference(key.split("/")[0]) for key in operation["objects"]]
        events = [{"event_type": "P0FactAccepted", "artifact_ref": ref} for ref in objects]
        if op == 3:
            events = [{"event_type": "P0AttemptStarted", "attempt_ref": reference("attempt"),
                       "assignment_ref": reference("assignment_manifest"), "binding_ref": reference("assignment_package_binding")}]
        return {"object_id": "command_envelope_" + UUID, "model_id": model.MODEL_ID,
                "command_id": "command_envelope_" + UUID, "operation": operation["name"], "actor_ref": "shape_only",
                "installation_digest": ZERO, "grant_digest": ZERO, "namespace_authority_digest": ZERO, "mode": "QUALIFICATION_ONLY",
                "campaign_id": "campaign_genesis_" + UUID,
                "expected_parent": "EMPTY_HISTORY" if op == 0 else
                {"campaign_id": "campaign_genesis_" + UUID, "commit_seq": 1, "commit_hash": ZERO},
                "policy_ref": reference("policy_revision"), "spec_ref": reference("spec_revision"),
                "schema_registry_ref": reference("schema_registry"), "proposed_object_refs": objects, "events": events, "basis_refs": []}

    def test_each_of_eight_command_branches_and_fact_domains(self):
        schema = self.schema("urn:bdb:p0:canonical:command_envelope/3")
        for index in range(8):
            with self.subTest(operation=index):
                value = self.command(index)
                self.assertTrue(self.validate(schema, value))
                self.assertFalse(self.validate(schema, value | {"operation": "GENERIC_IMPORT"}))
                self.assertFalse(self.validate(schema, value | {"command_payload": {"issuer": "self"}}))
                self.assertFalse(self.validate(schema, value | {"proposed_object_refs": value["proposed_object_refs"] + [reference("nf02_p0_abort")]}))
                if index != 0:
                    self.assertFalse(self.validate(schema, value | {"expected_parent": "EMPTY_HISTORY"}))

    def test_start_requires_one_specific_event_and_no_new_binding(self):
        schema = self.schema("urn:bdb:p0:canonical:command_envelope/3")
        value = self.command(3)
        self.assertFalse(self.validate(schema, value | {"events": []}))
        self.assertFalse(self.validate(schema, value | {"events": [{"event_type": "AttemptStarted"}]}))
        self.assertFalse(self.validate(schema, value | {"proposed_object_refs": [reference("assignment_package_binding")]}))

    def test_no_signature_trace_cycle_in_command_and_installation_grants(self):
        command = self.schema("urn:bdb:p0:canonical:command_envelope/3")
        commit = self.schema("urn:bdb:p0:canonical:commit_body/3")
        installation = self.schema("urn:bdb:p0:external:INSTALLATION_RECORD/1")
        self.assertNotIn("authorization_trace_raw_ref", command["properties"])
        self.assertIn("authorization_trace_raw_ref", commit["required"])
        self.assertNotIn("principal_grant_digests", installation["properties"])

    def test_every_profile_is_exact_and_rejects_changed_or_extra_rules(self):
        for profile, value in json.loads(self.artifacts["MODEL.json"])["profiles"].items():
            with self.subTest(profile=profile):
                schema = self.schema("urn:bdb:p0:profile:" + profile)
                self.assertTrue(self.validate(schema, value))
                self.assertFalse(self.validate(schema, value | {"authority": "self"}))
                self.assertFalse(self.validate(schema, value | {"rules": value["rules"] + ["BYPASS"]}))

    def test_source_manifest_explicitly_preserves_git_types_and_original_names(self):
        value: dict[str, Any] = {"repository_id": "shape_only", "git_object_algorithm": "sha1", "commit_oid": "a" * 40, "tree_oid": "b" * 40,
                 "entries": [{"source_path": "src/zażółć gęślą.py", "transport_path": "source/00000001.bin",
                              "git_blob_oid": "c" * 40, "mode": "100644", "sha256": ZERO, "bytes": 1}]}
        schema = self.schema("urn:bdb:p0:wire:SOURCE_MANIFEST/1")
        self.assertTrue(self.validate(schema, value))
        for field, invalid in (("mode", "120000"), ("transport_path", "../x"), ("git_blob_oid", "current")):
            bad = copy.deepcopy(value)
            bad["entries"][0][field] = invalid
            self.assertFalse(self.validate(schema, bad))

    def test_result_schema_has_no_truth_or_completion_authority(self):
        value: dict[str, Any] = {"findings": [], "report_paths": ["reports/audit.md"], "evidence_paths": [], "log_paths": [], "notes": []}
        schema = self.schema("urn:bdb:p0:wire:NORMALIZED_RESULT/1")
        self.assertTrue(self.validate(schema, value))
        additions: list[dict[str, Any]] = [{"status": "PASS"}, {"authority": "self"}, {"report_paths": []}, {"report_paths": ["../report.md"]}]
        for addition in additions:
            self.assertFalse(self.validate(schema, value | addition))

    def test_abort_body_schema_excludes_terminal_states(self):
        states = self.schema("urn:bdb:p0:canonical:nf02_p0_abort/1")["properties"]["from_state"]["enum"]
        self.assertNotIn("RESULT_ACCEPTED", states)
        self.assertNotIn("ABORTED", states)
        self.assertEqual(len(states), 5)

    def test_shared_definitions_are_not_public_payload_dispatch(self):
        common = self.schema(model.COMMON)
        values: list[Any] = [{}, {"kind": "attempt"}, [], "any"]
        for value in values:
            self.assertFalse(self.validate(common, value))

    def test_installation_modes_require_real_runtime_or_independent_mandate(self):
        modes = self.schema("urn:bdb:p0:external:INSTALLATION_RECORD/1")["allOf"][0]
        self.assertTrue(self.validate(modes, {"mode": "PRODUCTION", "runtime_qualification_sha256": ZERO, "qualification_mandate_sha256": None}))
        self.assertFalse(self.validate(modes, {"mode": "PRODUCTION", "runtime_qualification_sha256": None, "qualification_mandate_sha256": ZERO}))
        self.assertTrue(self.validate(modes, {"mode": "QUALIFICATION_ONLY", "runtime_qualification_sha256": None, "qualification_mandate_sha256": ZERO}))
        self.assertFalse(self.validate(modes, {"mode": "QUALIFICATION_ONLY", "runtime_qualification_sha256": ZERO, "qualification_mandate_sha256": None}))

    def test_qualification_matrix_preserves_full_declared_case_sets(self):
        matrix = json.loads(self.artifacts["QUALIFICATION_MATRIX.json"])
        self.assertEqual(matrix["counts"], {"Q1": 11, "Q2": 6, "RQ": 32})
        runtime = self.schema("urn:bdb:p0:external:RUNTIME_QUALIFICATION/1")
        cases = runtime["properties"]["mandatory_case_ids"]["const"]
        self.assertEqual(cases, sorted(matrix["cases"]["RQ"]))
        self.assertFalse(self.validate(runtime["properties"]["mandatory_case_ids"], cases[:-1]))

    def test_generation_is_deterministic_and_schema_membership_is_exact(self):
        self.assertEqual(self.artifacts, model.artifacts())
        schema_paths = [name for name in self.artifacts if name.endswith(".schema.json")]
        self.assertEqual(len(schema_paths), 43)
        self.assertEqual(len(set(schema_paths)), 43)

    def test_candidate_manifest_has_two_complete_sets_without_self_preimages(self):
        value = json.loads(model.manifest(self.artifacts))
        schema = self.schema("urn:bdb:p0:external:CANDIDATE_MANIFEST/1")
        self.assertTrue(self.validate(schema, value))
        for field in ("normative_files", "machine_files"):
            paths = [entry["file"] for entry in value[field]]
            self.assertEqual(paths, sorted(set(paths)))
            self.assertEqual(len(paths), 55)
            self.assertFalse(any(name.endswith(("CANDIDATE_MANIFEST.json", "LOCAL_VALIDATION.json")) for name in paths))
            self.assertEqual(sum(name.endswith(".schema.json") for name in paths), 43)


if __name__ == "__main__":
    unittest.main(verbosity=2)
