from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ExportPrivacyPolicy:
    denied_fields: tuple[str, ...] = ("secret", "token", "password", "raw_private_path")
    allowed_sensitivity: tuple[str, ...] = ("PUBLIC", "INTERNAL")


def sanitize_document(document: Mapping[str, object], policy: ExportPrivacyPolicy) -> tuple[dict, tuple[str, ...]]:
    removed: list[str] = []

    def clean(value: object, path: str) -> object:
        if isinstance(value, dict):
            out: dict[str, object] = {}
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if str(key).lower() in {item.lower() for item in policy.denied_fields}:
                    removed.append(child_path)
                    continue
                out[str(key)] = clean(child, child_path)
            return out
        if isinstance(value, (list, tuple)):
            return [clean(item, f"{path}[]") for item in value]
        return value

    cleaned = clean(dict(document), "")
    assert isinstance(cleaned, dict)
    return cleaned, tuple(sorted(removed))
