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

    def _events(self, con: sqlite3.Connection, *, after: tuple[int, str] = (0, EMPTY_HEAD)) -> list[dict[str, Any]]:
        self._check_mode(con)
        offset, previous = after
        if offset:
            anchor = con.execute("SELECT event_hash FROM local_events WHERE seq=?", (offset,)).fetchone()
            if anchor != (previous,):
                raise ValidationError("LOCAL_HISTORY_INTEGRITY_FAILED")
        events: list[dict[str, Any]] = []
        for seq, digest, prev, raw in con.execute(
                "SELECT seq,event_hash,previous_hash,body FROM local_events WHERE seq>? ORDER BY seq", (offset,)):
            if (not isinstance(raw, bytes) or not isinstance(prev, str) or len(prev) != 64
                    or any(c not in "0123456789abcdef" for c in prev)):
                raise ValidationError("LOCAL_HISTORY_INTEGRITY_FAILED")
            if seq != offset + len(events) + 1 or prev != previous or digest != _hash(prev, raw):
                raise ValidationError("LOCAL_HISTORY_INTEGRITY_FAILED")
            body = parse(raw)
            if (not isinstance(body, dict) or set(body) != {"seq", "mode", "profile", "kind", "payload"}
                    or not isinstance(body["kind"], str) or not isinstance(body["payload"], dict)
                    or canonical_bytes(body) != raw or body.get("seq") != seq
                    or body.get("mode") != MODE or body.get("profile") != PROFILE):
                raise ValidationError("LOCAL_HISTORY_MODE_OR_BYTES_MISMATCH")
            self._read_refs(body)
            events.append({**body, "event_hash": digest})
            previous = digest
        if not offset and (not events or events[0]["kind"] != "CAMPAIGN_CREATED"):
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

    def events(self, *, after: tuple[int, str] = (0, EMPTY_HEAD)) -> list[dict[str, Any]]:
        with self.connect() as con:
            return self._events(con, after=after)

    def append(self, kind: str, payload: dict[str, Any], expected_head: str) -> str:
        return self.append_many([(kind, payload)], expected_head)

    def append_many(self, entries: list[tuple[str, dict[str, Any]]], expected_head: str, *,
                    verified_seq: int | None = None) -> str:
        """Commit one file's import/validation/decision/summary as a single CAS.

        Vault publication precedes this transaction. A rollback may leave an
        unreferenced raw blob, never a partially accepted history fact.
        """
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if verified_seq is None:
                events = self._events(con)
                last_seq, actual = events[-1]["seq"], events[-1]["event_hash"]
            else:
                # A batch already verified and replayed this prefix. Bind its
                # decisions to the immutable journal tip under the write lock.
                self._check_mode(con)
                tip = con.execute("SELECT seq,event_hash FROM local_events ORDER BY seq DESC LIMIT 1").fetchone()
                if tip is None:
                    raise ValidationError("LOCAL_GENESIS_MISSING")
                last_seq, actual = tip
            if actual != expected_head or (verified_seq is not None and last_seq != verified_seq):
                raise ValidationError("LOCAL_CAS_CONFLICT", "Reload status and retry the action")
            for seq, (kind, payload) in enumerate(entries, last_seq + 1):
                body = canonical_bytes({"seq": seq, "mode": MODE, "profile": PROFILE,
                                        "kind": kind, "payload": payload})
                self._read_refs(payload)
                digest = _hash(actual, body)
                con.execute("INSERT INTO local_events VALUES (?,?,?,?)", (seq, digest, actual, body))
                actual = digest
            con.commit()
            return actual

    def put(self, raw: bytes) -> dict[str, Any]:
        # A single media type prevents conflicting metadata for identical bytes
        # used as both a source transport and an attached evidence file.
        return self.vault.put_bytes(raw).as_dict()
