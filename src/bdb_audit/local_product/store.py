"""Separate local journal with CAS, exact raw readback and immutable mode.

Hash chains detect accidental corruption. A person controlling the whole host
can rewrite an entire unsigned journal; this is not independent attestation.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError
from ..vault.raw_store import RawArtifactVault
from .profile import MODE, PROFILE, PROFILE_SHA256

APPLICATION_ID = 0x42444C31
EMPTY_HEAD = "0" * 64


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash(previous: str, raw: bytes) -> str:
    return sha(b"BDB-LOCAL-JOURNAL/1\x00" + bytes.fromhex(previous) + raw)


class LocalStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.path = self.root / "local.sqlite3"
        if not self.path.is_file():
            raise ValidationError("LOCAL_CAMPAIGN_NOT_FOUND", str(self.root))
        with self.connect() as con:
            self._check_mode(con)
        # Opening a wrong-format database must not create any vault directories.
        self.vault = RawArtifactVault(self.root / "vault")
        self.events()

    @classmethod
    def create(cls, root: str | Path, genesis: dict[str, Any], source_raw: bytes) -> LocalStore:
        location = Path(root).resolve()
        if location.exists():
            raise ValidationError("LOCAL_CAMPAIGN_PATH_EXISTS", str(location))
        location.mkdir(parents=True)
        vault = RawArtifactVault(location / "vault")
        ref = vault.put_bytes(source_raw).as_dict()
        genesis = {**genesis, "source_snapshot": ref}
        con = sqlite3.connect(location / "local.sqlite3", isolation_level=None)
        try:
            con.execute("PRAGMA synchronous=FULL")
            con.execute(f"PRAGMA application_id={APPLICATION_ID}")
            con.executescript("""
                CREATE TABLE local_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE local_events(seq INTEGER PRIMARY KEY, event_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL, body BLOB NOT NULL);
                CREATE TRIGGER local_no_update BEFORE UPDATE ON local_events
                    BEGIN SELECT RAISE(ABORT, 'LOCAL_IMMUTABLE_HISTORY'); END;
                CREATE TRIGGER local_no_delete BEFORE DELETE ON local_events
                    BEGIN SELECT RAISE(ABORT, 'LOCAL_IMMUTABLE_HISTORY'); END;
            """)
            con.execute("BEGIN IMMEDIATE")
            con.executemany("INSERT INTO local_meta VALUES (?,?)", [
                ("mode", MODE), ("profile", PROFILE), ("profile_sha256", PROFILE_SHA256)])
            body = canonical_bytes({"mode": MODE, "profile": PROFILE, "seq": 1,
                                    "kind": "CAMPAIGN_CREATED", "payload": genesis})
            con.execute("INSERT INTO local_events VALUES (1,?,?,?)", (_hash(EMPTY_HEAD, body), EMPTY_HEAD, body))
            con.commit()
        finally:
            con.close()
        return cls(location)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(f"{self.path.as_uri()}?mode=rw", uri=True, isolation_level=None, timeout=30)
        try:
            con.execute("PRAGMA synchronous=FULL")
            yield con
        finally:
            con.close()

    @staticmethod
    def _check_mode(con: sqlite3.Connection) -> None:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if (con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or tables != {"local_meta", "local_events"}):
            raise ValidationError("LOCAL_STORE_FORMAT_REQUIRED")
        meta = dict(con.execute("SELECT key,value FROM local_meta"))
        if meta != {"mode": MODE, "profile": PROFILE, "profile_sha256": PROFILE_SHA256}:
            raise ValidationError("LOCAL_PERMANENT_MODE_MISMATCH")

    def _events(self, con: sqlite3.Connection) -> list[dict[str, Any]]:
        self._check_mode(con)
        previous = EMPTY_HEAD
        events: list[dict[str, Any]] = []
        for seq, digest, prev, raw in con.execute("SELECT seq,event_hash,previous_hash,body FROM local_events ORDER BY seq"):
            if seq != len(events) + 1 or prev != previous or digest != _hash(prev, raw):
                raise ValidationError("LOCAL_HISTORY_INTEGRITY_FAILED")
            body = parse(raw)
            if (canonical_bytes(body) != raw or body.get("seq") != seq
                    or body.get("mode") != MODE or body.get("profile") != PROFILE):
                raise ValidationError("LOCAL_HISTORY_MODE_OR_BYTES_MISMATCH")
            self._read_refs(body)
            events.append({**body, "event_hash": digest})
            previous = digest
        if not events or events[0]["kind"] != "CAMPAIGN_CREATED":
            raise ValidationError("LOCAL_GENESIS_MISSING")
        return events

    def _read_refs(self, value: Any) -> None:
        if isinstance(value, dict):
            if "raw_digest" in value and "byte_length" in value:
                raw = self.vault.read_bytes(value["raw_digest"])
                if len(raw) != value["byte_length"]:
                    raise ValidationError("LOCAL_RAW_LENGTH_MISMATCH")
            for child in value.values():
                self._read_refs(child)
        elif isinstance(value, list):
            for child in value:
                self._read_refs(child)

    def events(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            return self._events(con)

    def append(self, kind: str, payload: dict[str, Any], expected_head: str) -> str:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            events = self._events(con)
            actual = events[-1]["event_hash"]
            if actual != expected_head:
                raise ValidationError("LOCAL_CAS_CONFLICT", "Reload status and retry the action")
            body = canonical_bytes({"seq": len(events) + 1, "mode": MODE, "profile": PROFILE,
                                    "kind": kind, "payload": payload})
            self._read_refs(payload)
            digest = _hash(actual, body)
            con.execute("INSERT INTO local_events VALUES (?,?,?,?)", (len(events) + 1, digest, actual, body))
            con.commit()
            return digest

    def put(self, raw: bytes) -> dict[str, Any]:
        # A single media type prevents conflicting metadata for identical bytes
        # used as both a source transport and an attached evidence file.
        return self.vault.put_bytes(raw).as_dict()
