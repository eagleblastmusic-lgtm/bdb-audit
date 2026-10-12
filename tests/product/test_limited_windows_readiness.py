"""Safe native Windows negative/lease probes; never install or change ACLs.

These local tests do not qualify a service account, PKI or independent host.
"""
import ctypes
import json
import os
from pathlib import Path
import subprocess

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history import installation_authority as windows
from bdb_audit.history import limited_authority
from bdb_audit import p0_service


def test_service_diagnostics_cannot_log_payload_paths_or_secrets():
    secret = "PRIVATE-DATA c:\\secret\\packet.json"
    output = p0_service.diagnostic(2, json.dumps({"error": "P0_INPUT_OR_INSTALLATION_INVALID", "detail": secret}))
    assert secret not in output
    assert json.loads(output)["error"] == "P0_INPUT_OR_INSTALLATION_INVALID"
    assert secret not in p0_service.diagnostic(2, secret)


def test_p0_requires_current_revocation_and_preserves_historical_time(monkeypatch):
    calls = []

    def verified(script, data):
        calls.append((script, data))
        return "VERIFIED"

    monkeypatch.setattr(windows, "_powershell", verified)
    limited_authority.verify_cms(b"body", b"signature", "1" * 64)
    assert calls[-1][1]["require_current_revocation"] is True
    assert "RevocationMode]::Online" in calls[-1][0]
    assert "ChainElements.Count -lt 2" in calls[-1][0]
    assert "VerificationFlags]::NoFlag" in calls[-1][0]
    limited_authority.verify_cms(b"body", b"signature", "1" * 64, at_time="2026-10-12T00:00:00Z")
    assert calls[-1][1]["at_time"] == "2026-10-12T00:00:00Z"
    windows.verify_cms(b"body", b"signature", "1" * 64)
    assert calls[-1][1]["require_current_revocation"] is False


@pytest.mark.skipif(os.name != "nt", reason="Native Windows API")
def test_native_cms_malformed_signature_denies():
    with pytest.raises(ValidationError, match="NF02_AUTHORITY_VERIFICATION_FAILED"):
        limited_authority.verify_cms(b"NOT_AUTHORITY", b"NOT_A_CMS_SIGNATURE", "1" * 64)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows API")
def test_native_file_lease_denies_write_and_rename(tmp_path):
    path = tmp_path / "retained.bin"
    path.write_bytes(b"original")
    with windows._locked_file(path, check_acl=False) as raw:
        assert raw == b"original"
        with pytest.raises(OSError):
            path.write_bytes(b"substitution")
        with pytest.raises(OSError):
            path.rename(tmp_path / "moved.bin")
    assert path.read_bytes() == b"original"


@pytest.mark.skipif(os.name != "nt", reason="Native Windows API")
def test_native_leased_read_is_bounded_before_allocation(tmp_path):
    path = tmp_path / "bounded.bin"
    path.write_bytes(b"0123456789")
    with pytest.raises(ValidationError, match="NF02_INSTALLATION_RESOURCE_LIMIT"):
        with windows._locked_file(path, check_acl=False, byte_limit=4):
            pytest.fail("Oversized leased input was returned")
    with windows._locked_file(path, check_acl=False, byte_limit=10) as raw:
        assert raw == b"0123456789"


@pytest.mark.skipif(os.name != "nt", reason="Native Windows API")
def test_native_dispatcher_outside_scm_is_closed():
    # No CreateService, account, ACL or certificate mutation.
    with pytest.raises(OSError) as raised:
        p0_service.run_service()
    assert raised.value.winerror == 1063


@pytest.mark.skipif(os.name != "nt", reason="Native Windows API")
def test_installer_script_parses_without_execution():
    script = Path(__file__).resolve().parents[2] / "tools/nf02_p0_windows.ps1"
    checker = "$file='" + str(script).replace("'", "''") + "';" + r"""$tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors);if($errors.Count){$errors | ForEach-Object {$_.Message};exit 1}"""
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", checker], capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors="replace") + result.stdout.decode(errors="replace")


@pytest.mark.parametrize("mode", ["Install", "StartJob", "SignDetached"])
@pytest.mark.skipif(os.name != "nt", reason="Native Windows PowerShell")
def test_windows_script_refuses_mutation_without_explicit_apply(mode):
    script = Path(__file__).resolve().parents[2] / "tools/nf02_p0_windows.ps1"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script), "-Mode", mode], capture_output=True)
    assert result.returncode != 0
    assert b"explicit -Apply" in result.stderr


def test_scm_callbacks_drain_and_report_stopped_without_secret(monkeypatch):
    """SCM API simulation, actual service_main/worker/diagnostic code."""
    statuses, logs = [], []
    handler = None

    class Function:
        def __init__(self, function):
            self.function = function

        def __call__(self, *args):
            return self.function(*args)

    def register(name, callback):
        nonlocal handler
        handler = callback
        return 1

    def status(handle, pointer):
        values = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ulong * 7)).contents
        statuses.append(tuple(values))
        return 1

    def dispatcher(table):
        argv = (ctypes.c_wchar_p * 2)(p0_service.SERVICE_NAME, "status")
        table[0].main(2, argv)
        return 1

    def report(*args):
        logs.append(args[7][0])
        return 1

    functions = {
        "RegisterServiceCtrlHandlerW": register,
        "SetServiceStatus": status,
        "StartServiceCtrlDispatcherW": dispatcher,
        "RegisterEventSourceW": lambda *args: 1,
        "ReportEventW": report,
        "DeregisterEventSource": lambda *args: 1,
    }

    class Api:
        pass

    api = Api()
    for name, function in functions.items():
        setattr(api, name, Function(function))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: api)

    def command(arguments):
        handler(1)
        return 2, json.dumps({"error": "P0_INSTALLATION_AUTHORITY_NOT_ESTABLISHED", "detail": "SECRET"})

    monkeypatch.setattr(p0_service, "execute", command)
    p0_service.run_service()
    assert [s[1] for s in statuses] == [2, 4, 3, 1]
    assert statuses[0][2] == 0 and statuses[1][2] == 5
    assert statuses[-1][4] == 2 and statuses[-1][6] == 0
    assert "SECRET" not in logs[0]
