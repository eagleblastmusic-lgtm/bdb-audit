"""Finite service dispatch only. Real SCM/account/ACL remain RQ obligations."""
import json

import pytest

from bdb_audit.p0_service import execute


@pytest.mark.parametrize("arguments", [[], ["GENERIC_IMPORT"], ["status", "x" * 4097], ["status"] * 25])
def test_service_has_only_finite_p0_commands(arguments):
    code, output = execute(arguments)
    assert code == 2
    assert json.loads(output)["error"] == "P0_SERVICE_FINITE_COMMAND_REQUIRED"


def test_service_dispatch_uses_actual_closed_authority_gate(tmp_path, monkeypatch):
    monkeypatch.setattr("bdb_audit.history.limited_authority.machine_root", lambda: tmp_path / "missing")
    path = tmp_path / "not-created.sqlite"
    code, output = execute(["status", "--store", str(path)])
    assert code == 2
    assert json.loads(output)["error"] == "P0_INSTALLATION_AUTHORITY_NOT_ESTABLISHED"
    assert not path.exists()
