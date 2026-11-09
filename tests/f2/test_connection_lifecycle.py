"""SQLite read guards release files independently of garbage collection."""
import sqlite3

import pytest

from bdb_audit.coordinator.operations import AuditOperationApi
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore


@pytest.mark.parametrize("foreign_schema", [False, True])
def test_existing_history_readers_close_on_success_and_refusal(tmp_path, monkeypatch, foreign_schema):
    path = tmp_path / "campaign.sqlite"
    if foreign_schema:
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE immutable_objects(schema_ref BLOB)")
            connection.execute("INSERT INTO immutable_objects VALUES (?)", (b"installed-schema",))
            connection.commit()
        finally:
            connection.close()
    else:
        AuditOperationApi().create_campaign(path, seed="connection-lifecycle")
    before = path.read_bytes()
    connect = sqlite3.connect
    connections = []  # Keep strong references: GC must not make the test pass.

    def track(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track)
    try:
        if foreign_schema:
            with pytest.raises(ValidationError, match="NF02_INSTALLED_READER_REQUIRED"):
                TransactionalHistoryStore(path)
        else:
            store = TransactionalHistoryStore(path)
            assert store.head().commit_seq == 1
            assert len(store.commits()) == 1
        assert connections
        for connection in connections:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                connection.execute("SELECT 1")
        assert path.read_bytes() == before
        path.unlink()  # Windows refuses this while a reader still owns the file.
    finally:
        for connection in connections:
            connection.close()
