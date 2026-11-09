"""Bounded, non-executing parsing of explicitly untrusted local responses."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from ..assurance.zip_safety import Limits, read_bytes, snapshot, canonical_path, ArchiveInput
from ..core.canonical_json import parse
from ..core.errors import ValidationError
from .contract import (MODE, RESPONSE, RESULT_LIMITS, JSON_LIMIT, SEVERITIES, DISPOSITIONS, COMPLETIONS,
                       PRODUCERS, FINDING_FIELDS, FINDING_TEXT_FIELDS, TEXT_LISTS, RESPONSE_FIELDS)
from .store import sha

def decode(raw: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    members: dict[str, bytes] = {}
    if raw.startswith(b"PK"):
        members = read_bytes(raw, limits=RESULT_LIMITS)
        if "LOCAL_RESULT.json" not in members:
            raise ValidationError("LOCAL_RESULT_MANIFEST_MISSING", "Expected root LOCAL_RESULT.json")
        body = parse(members["LOCAL_RESULT.json"], max_bytes=JSON_LIMIT)
    else:
        body = parse(raw, max_bytes=JSON_LIMIT)
    if not isinstance(body, dict):
        raise ValidationError("LOCAL_RESPONSE_OBJECT_REQUIRED")
    return body, members


def read_file(path: str | Path | ArchiveInput) -> bytes:
    raw = snapshot(path, limits=RESULT_LIMITS).raw
    decode(raw)  # Unsafe or malformed bytes are refused before journal/vault mutation.
    return raw


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 100_000


def issues(body: dict[str, Any], members: dict[str, bytes], context: dict[str, Any],
           required_outputs: list[str], source_paths: set[str], *,
           line_counts: dict[str, int] | None = None) -> list[str]:
    errors: list[str] = []
    if body.get("format") != RESPONSE or body.get("mode") != MODE:
        errors.append("LOCAL_RESPONSE_FORMAT_OR_MODE_MISMATCH")
    for key, expected in context.items():
        if body.get(key) != expected:
            errors.append("LOCAL_CONTEXT_MISMATCH:" + key)
    producer = body.get("producer")
    if (not isinstance(producer, dict) or producer.get("kind") not in PRODUCERS
            or not _text(producer.get("declared_name"))):
        errors.append("LOCAL_DECLARED_PRODUCER_REQUIRED")
    if body.get("completion") not in COMPLETIONS:
        errors.append("LOCAL_COMPLETION_INVALID")
    outputs = body.get("outputs")
    if not isinstance(outputs, dict):
        errors.append("LOCAL_OUTPUTS_REQUIRED")
    elif body.get("completion") == "COMPLETE":
        for key in required_outputs:
            if not _text(outputs.get(key)):
                errors.append("LOCAL_REQUIRED_OUTPUT_MISSING:" + key)
    if line_counts is not None and isinstance(outputs, dict):
        if set(outputs) - set(required_outputs) or any(not isinstance(v, str) or len(v) > 100_000 for v in outputs.values()):
            errors.append("LOCAL_OUTPUT_FIELDS_INVALID")
    if line_counts is not None and isinstance(producer, dict) and set(producer) != {"kind", "declared_name"}:
        errors.append("LOCAL_PRODUCER_FIELDS_INVALID")
    for field in TEXT_LISTS:
        value = body.get(field)
        if not isinstance(value, list) or len(value) > 2000 or any(not _text(v) for v in value):
            errors.append("LOCAL_TEXT_LIST_REQUIRED:" + field)
    findings = body.get("findings")
    if not isinstance(findings, list) or len(findings) > 2000:
        errors.append("LOCAL_FINDINGS_REQUIRED")
    else:
        ids: set[str] = set()
        for finding in findings:
            if not isinstance(finding, dict):
                errors.append("LOCAL_FINDING_OBJECT_REQUIRED")
                continue
            identifier = finding.get("id")
            if not isinstance(identifier, str) or not _text(identifier) or identifier in ids:
                errors.append("LOCAL_FINDING_ID_INVALID_OR_DUPLICATE")
            else:
                ids.add(identifier)
            for key in FINDING_TEXT_FIELDS[1:]:
                if not _text(finding.get(key)):
                    errors.append("LOCAL_FINDING_FIELD_REQUIRED:" + key)
            if finding.get("severity") not in SEVERITIES:
                errors.append("LOCAL_FINDING_SEVERITY_INVALID")
            if finding.get("disposition") not in DISPOSITIONS:
                errors.append("LOCAL_FINDING_DISPOSITION_INVALID")
            refs = finding.get("source_refs")
            if not isinstance(refs, list):
                errors.append("LOCAL_FINDING_SOURCE_REFS_REQUIRED")
            else:
                for ref in refs:
                    if (not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or ref["path"] not in source_paths
                            or type(ref.get("line")) is not int or ref["line"] < 1):
                        errors.append("LOCAL_FINDING_SOURCE_REF_INVALID")
                    elif line_counts is not None and (set(ref) != {"path", "line"}
                                                      or ref["line"] > line_counts[ref["path"]]):
                        errors.append("LOCAL_FINDING_SOURCE_REF_INVALID")
            if line_counts is not None and set(finding) - set(FINDING_FIELDS):
                errors.append("LOCAL_FINDING_UNKNOWN_FIELDS")
    evidence = body.get("evidence_files")
    declared: set[str] = set()
    if not isinstance(evidence, list):
        errors.append("LOCAL_EVIDENCE_LIST_REQUIRED")
    else:
        for item in evidence:
            if not isinstance(item, dict):
                errors.append("LOCAL_EVIDENCE_OBJECT_REQUIRED")
                continue
            name = item.get("path")
            try:
                if canonical_path(name) != name or name == "LOCAL_RESULT.json" or name in declared:
                    raise ValidationError("LOCAL_EVIDENCE_PATH_INVALID")
            except ValidationError:
                errors.append("LOCAL_EVIDENCE_PATH_INVALID")
                continue
            declared.add(name)
            member = members.get(name)
            if member is None or sha(member) != item.get("sha256") or len(member) != item.get("byte_length"):
                errors.append("LOCAL_EVIDENCE_EXACT_BYTES_MISMATCH:" + name)
            if line_counts is not None and (set(item) != {"path", "sha256", "byte_length"}
                                            or type(item.get("byte_length")) is not int):
                errors.append("LOCAL_EVIDENCE_FIELDS_INVALID")
    if set(members) - {"LOCAL_RESULT.json"} != declared:
        errors.append("LOCAL_UNDECLARED_OR_MISSING_MEMBERS")
    # Qualified record envelopes cannot be smuggled in as an alternate root.
    allowed = set(RESPONSE_FIELDS)
    if set(body) - allowed:
        errors.append("LOCAL_UNKNOWN_RESPONSE_FIELDS:" + ",".join(sorted(set(body) - allowed)))
    return sorted(set(errors))


def diagnostics(body: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    """Polish presentation of stable machine codes, without repairing AI data."""
    def display(value: Any) -> str:
        # Invalid AI values may themselves be objects resembling vault refs.
        # Diagnostic fragments are text, never journal-owned reference objects.
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        return text if len(text) <= 500 else text[:500] + "… [podgląd skrócony; pełna wartość w zachowanej odpowiedzi]"

    messages = {
        "LOCAL_CONTEXT_MISMATCH": "Niezgodne powiązanie wyniku z kampanią, źródłem lub zamrożoną paczką",
        "LOCAL_TASK_PACKAGE_NOT_FOUND": "Nie znaleziono zamrożonej paczki tego zadania",
        "LOCAL_CURRENT_STAGE_REQUIRED": "Wynik nie należy do dostępnego zadania bieżącego etapu",
        "LOCAL_BATCH_RESULT_CONFLICT": "Konflikt z innym wynikiem zadania; poprzedni wynik zachowano. Rozpatrz rewizję w Wynikach",
        "LOCAL_FINDING_FIELD_REQUIRED": "Wymagane niepuste pole tekstowe ustalenia",
        "LOCAL_FINDING_ID_INVALID_OR_DUPLICATE": "Identyfikator ustalenia jest pusty, nieprawidłowy lub powtórzony",
        "LOCAL_FINDING_SEVERITY_INVALID": "Nieprawidłowa wartość pola severity",
        "LOCAL_FINDING_DISPOSITION_INVALID": "Nieprawidłowa wartość pola disposition",
        "LOCAL_FINDING_SOURCE_REFS_REQUIRED": "source_refs musi być tablicą obiektów path/line",
        "LOCAL_FINDING_SOURCE_REF_INVALID": "Nieprawidłowa referencja: użyj oryginalnej ścieżki i istniejącego numeru linii od 1",
        "LOCAL_TEXT_LIST_REQUIRED": "Pole musi być listą niepustych tekstów, a nie obiektem",
        "LOCAL_UNKNOWN_RESPONSE_FIELDS": "Niedozwolone dodatkowe pola odpowiedzi; popraw odpowiedź według szablonu",
        "LOCAL_REQUIRED_OUTPUT_MISSING": "Brak wymaganego, merytorycznego opisu wyniku zadania",
        "LOCAL_OUTPUT_FIELDS_INVALID": "outputs zawiera niedozwolone klucze lub wartości inne niż tekst",
        "LOCAL_PRODUCER_FIELDS_INVALID": "producer może zawierać wyłącznie kind i declared_name",
        "LOCAL_FINDING_UNKNOWN_FIELDS": "Ustalenie zawiera dodatkowe pola nieobecne w kontrakcie finding",
        "LOCAL_EVIDENCE_FIELDS_INVALID": "Załącznik wymaga wyłącznie path, sha256 i całkowitego byte_length",
        "LOCAL_COMPLETION_INVALID": "Nieprawidłowa wartość completion",
        "LOCAL_EVIDENCE_EXACT_BYTES_MISMATCH": "Załącznik nie odpowiada zadeklarowanemu SHA-256 lub długości",
        "LOCAL_UNDECLARED_OR_MISSING_MEMBERS": "ZIP zawiera niezgłoszone załączniki lub brakuje zgłoszonego pliku",
        "LOCAL_RESULT_MANIFEST_MISSING": "ZIP wymaga wewnętrznego pliku LOCAL_RESULT.json w katalogu głównym",
        "LOCAL_RESPONSE_FORMAT_OR_MODE_MISMATCH": "Oczekiwano BDB_LOCAL_RESPONSE_1 w trybie LOCAL_PRODUCT",
        "LOCAL_BATCH_FILE_READ_FAILED": "Nie można odczytać pliku; sprawdź ścieżkę i uprawnienia",
        "LOCAL_DECLARED_PRODUCER_REQUIRED": "Podaj dozwolony kind oraz rzeczywistą deklarowaną nazwę producenta",
    }
    enum_fields = {"LOCAL_FINDING_SEVERITY_INVALID": ("severity", SEVERITIES),
                   "LOCAL_FINDING_DISPOSITION_INVALID": ("disposition", DISPOSITIONS),
                   "LOCAL_COMPLETION_INVALID": ("completion", COMPLETIONS)}
    result = []
    for error in errors:
        code, _, field = error.partition(":")
        item: dict[str, Any] = {"code": error, "message": messages.get(code, "Błąd formatu lub bezpieczeństwa; wymagana korekta odpowiedzi"),
                                "task_id": body.get("task_id") if isinstance(body.get("task_id"), str) else None,
                                "field": field or None}
        if code in enum_fields:
            key, allowed = enum_fields[code]
            item.update(field=key, allowed=list(allowed))
            findings = body.get("findings")
            if key == "completion":
                item["detected"] = display(body.get(key))
            elif isinstance(findings, list):
                invalid = [f for f in findings if isinstance(f, dict) and f.get(key) not in allowed]
                item["findings"] = [{"id": display(f.get("id")), "detected": display(f.get(key))} for f in invalid[:20]]
                item["additional_findings_in_raw"] = max(0, len(invalid) - 20)
        elif code.startswith("LOCAL_FINDING") and isinstance(body.get("findings"), list):
            objects = [f for f in body["findings"] if isinstance(f, dict)]
            item["finding_ids"] = [display(f.get("id")) for f in objects[:20]]
            item["additional_findings_in_raw"] = max(0, len(objects) - 20)
        result.append(item)
    return result
