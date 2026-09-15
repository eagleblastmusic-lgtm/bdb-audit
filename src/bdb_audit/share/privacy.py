from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ExportPrivacyPolicy:
    denied_fields: tuple[str, ...] = ("secret", "token", "password", "raw_private_path")
    allowed_sensitivity: tuple[str, ...] = ("PUBLIC", "INTERNAL")

    def __post_init__(self) -> None:
        if not self.denied_fields:
            raise ValueError("at least one denied field is required")
        if any(not value.strip() for value in self.denied_fields):
            raise ValueError("denied field names must be non-empty")
        if len({value.lower() for value in self.denied_fields}) != len(self.denied_fields):
            raise ValueError("denied field names must be unique case-insensitively")
        if not self.allowed_sensitivity:
            raise ValueError("at least one allowed sensitivity is required")
        normalized = [value.strip().upper() for value in self.allowed_sensitivity]
        if any(not value for value in normalized):
            raise ValueError("allowed sensitivity values must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("allowed sensitivity values must be unique")


def sanitize_document(
    document: Mapping[str, object],
    policy: ExportPrivacyPolicy,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Return a recipient-safe document and local-only redaction paths.

    Denied field matching and the ``sensitivity`` classification key are
    case-insensitive. Any mapping carrying a sensitivity outside the allowlist,
    a malformed classification, or multiple conflicting classification keys is
    redacted as a whole.
    """

    removed: list[str] = []
    denied = {item.lower() for item in policy.denied_fields}
    allowed_sensitivity = {item.strip().upper() for item in policy.allowed_sensitivity}

    def clean(value: object, path: str) -> object:
        if isinstance(value, Mapping):
            sensitivity_entries = [
                child for key, child in value.items() if str(key).lower() == "sensitivity"
            ]
            if len(sensitivity_entries) > 1:
                removed.append(path or "<root>")
                return {"redacted": True}
            if sensitivity_entries:
                sensitivity = sensitivity_entries[0]
                if not isinstance(sensitivity, str) or sensitivity.strip().upper() not in allowed_sensitivity:
                    removed.append(path or "<root>")
                    return {"redacted": True}

            out: dict[str, object] = {}
            for key, child in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                if key_text.lower() in denied:
                    removed.append(child_path)
                    continue
                out[key_text] = clean(child, child_path)
            return out
        if isinstance(value, (list, tuple)):
            return [clean(item, f"{path}[]") for item in value]
        return value

    cleaned = clean(dict(document), "")
    assert isinstance(cleaned, dict)
    return cleaned, tuple(sorted(set(removed)))


__all__ = ["ExportPrivacyPolicy", "sanitize_document"]
