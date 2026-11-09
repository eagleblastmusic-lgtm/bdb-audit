"""One LOCAL response vocabulary for templates, prompts and validation.

This is outside the qualified Registry. Package generators retain their frozen
format, and generators from version 2 record their version in history.
"""
from __future__ import annotations

import re
from typing import Any

from ..assurance.zip_safety import Limits
from ..core.errors import ValidationError

MODE = "LOCAL_PRODUCT"
RESPONSE = "BDB_LOCAL_RESPONSE_1"
GENERATOR_VERSION = 3
VALIDATION_VERSION = 2
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
DISPOSITIONS = ("CLAIM", "SUPPORTED", "DISPUTED", "WITHDRAWN")
COMPLETIONS = ("COMPLETE", "NEEDS_WORK", "BLOCKED")
PRODUCERS = ("EXTERNAL_AI", "HUMAN", "LOCAL_CONTROL", "TEST_FIXTURE")
CONTEXT_FIELDS = ("campaign_id", "stage_id", "task_id", "source_commit", "source_tree", "input_package_digest")
FINDING_TEXT_FIELDS = ("id", "title", "statement", "rationale")
FINDING_FIELDS = (*FINDING_TEXT_FIELDS, "severity", "disposition", "source_refs")
TEXT_LISTS = ("limitations", "recommendations", "contradictions")
RESPONSE_FIELDS = ("format", "mode", *CONTEXT_FIELDS, "producer", "completion", "outputs", "findings",
                   "evidence_files", *TEXT_LISTS)
JSON_LIMIT = 2 * 1024 * 1024
RESULT_LIMITS = Limits(input_bytes=64 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                      members=512, member_bytes=32 * 1024 * 1024, expanded_bytes=50 * 1024 * 1024, ratio=500)


def result_filename(task: str, extension: str = "json") -> str:
    if not re.fullmatch(r"E[1-6]-[A-Z0-9]+(?:-[A-Z0-9]+)*", task) or extension not in {"json", "zip"}:
        raise ValidationError("LOCAL_RESULT_FILENAME_INVALID")
    return f"{task}_RESULT.{extension}"


def response_template(context: dict[str, Any], outputs: list[str]) -> dict[str, Any]:
    return {"format": RESPONSE, "mode": MODE, **{key: context[key] for key in CONTEXT_FIELDS},
            "producer": {"kind": "EXTERNAL_AI", "declared_name": ""}, "completion": "NEEDS_WORK",
            "outputs": {key: "" for key in outputs}, "findings": [], "evidence_files": [],
            **{key: [] for key in TEXT_LISTS}}


def response_guide() -> str:
    return f"""# LOCAL response contract — {RESPONSE}

Use exactly the attached RESPONSE_TEMPLATE.json. Return one UTF-8 JSON object;
do not add root or nested fields, Markdown fences, comments or duplicate keys.
Required root fields: {', '.join(RESPONSE_FIELDS)}.
Keep {', '.join(CONTEXT_FIELDS)}, format and mode unchanged. Never infer identity
from a filename. The template and MANIFEST.json identify this frozen task.

producer has exactly kind and declared_name (a nonempty actual declared name).
Allowed kinds: {', '.join(PRODUCERS)}. Names are unverified declarations.
Do not invent an AI run, producer identity, test, evidence or independent auditor.
completion: {', '.join(COMPLETIONS)}. COMPLETE requires substantive text for every
MANIFEST.json.required_outputs key in outputs; explain an absence where relevant.
outputs maps only those keys to text. NEEDS_WORK/BLOCKED preserve unfinished work
and never complete a task. Empty template fields are not a completed assessment.

findings is an array of objects (or [] when declaring none). Each has exactly:
{', '.join(FINDING_FIELDS)}.
{', '.join(FINDING_TEXT_FIELDS)}: nonempty text, at most 100000 characters each;
id is unique within this response (use a stable identifier such as E1A-004).
severity: {', '.join(SEVERITIES)}.
disposition: {', '.join(DISPOSITIONS)}. These are producer assessments, not qualification.
source_refs is an array of {{"path": "original/path.py", "line": 1}} objects.
Use original SOURCE_MANIFEST.json paths, not numeric source transport paths.
Line numbers are integers, 1-based, within the cited file; never invent references.
An empty source_refs array declares no source references; disclose that limitation.

{', '.join(TEXT_LISTS)} are arrays of nonempty text strings, never objects;
use [] when there are no declarations. Keep dissent, missing evidence and limits
explicit. Do not serialize extra JSON objects into rationale or these text lists.
Separate static inspection and predictions from tests actually executed. Attach
real run output for an execution claim and state its scope and limitations.
Do not promote an unverified claim to SUPPORTED just to satisfy this contract.

Direct JSON uses evidence_files: []. ZIP must contain root LOCAL_RESULT.json
(even when the outer ZIP uses a task-specific name), plus declared attachments.
Every other member is declared once in evidence_files as exactly
{{"path": "run.txt", "sha256": "64 lowercase hex digits", "byte_length": 123}}.
Use exact original attachment bytes, a nonnegative integer length and relative
paths without traversal, backslashes, colons or absolute paths. No self-hash for
LOCAL_RESULT.json. No nested ZIP as a replacement for the response manifest.
JSON limit: {JSON_LIMIT} bytes; ZIP input: {RESULT_LIMITS.input_bytes} bytes;
expanded: {RESULT_LIMITS.expanded_bytes} bytes; members: {RESULT_LIMITS.members};
one member: {RESULT_LIMITS.member_bytes} bytes; compression ratio: {RESULT_LIMITS.ratio}.
Text arrays and findings: at most 2000 items. Responses are not executed.

Validate before delivery with the same importer validator:
python -m bdb_audit product local inspect --campaign <campaign-directory> --file <result>
This checks structure and frozen context without accepting or changing history.
VALIDATED_STRUCTURE and USER_ACCEPTED_LOCAL permit local processing only.
They do not prove truth, identity, independent evidence or HIGH ASSURANCE.
"""


def auditor_prompt(context: dict[str, Any], instruction: str, outputs: list[str]) -> str:
    identity = "\n".join(f"{key}: {context[key]}" for key in CONTEXT_FIELDS if key != "input_package_digest")
    return (f"# {context['task_id']} — LOCAL audit\n\n{identity}\n\n{instruction}\n\n"
            "Inspect the exact attached source transport and PRIOR_RESULTS.json.\n"
            f"Required outputs: {', '.join(outputs)}.\n"
            "Use the attached template, preserving its input_package_digest; do not recalculate it.\n"
            f"Save direct JSON as {result_filename(context['task_id'])}.\n"
            f"For attachments, save {result_filename(context['task_id'], 'zip')} with root LOCAL_RESULT.json.\n"
            "Do not include credentials or private data.\n\n" + response_guide())
