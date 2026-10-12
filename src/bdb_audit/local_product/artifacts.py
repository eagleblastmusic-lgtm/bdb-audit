"""Verified local artifact actions. AI responses never supply an opening path."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import re
from typing import Any

from ..core.errors import ValidationError
from .store import sha


def safe_path(root: Path, path: Path, *, missing_ok: bool = False) -> Path:
    """Check lexical containment and every component before following a path.

    Refuse symlinks and Windows reparse points, including junctions. Checking
    resolve() alone would silently follow a redirected artifact directory.
    """
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(root):
        raise ValidationError("LOCAL_ARTIFACT_OUTSIDE_ROOT", str(path))
    components = [root, *reversed([p for p in path.parents if p != root and p.is_relative_to(root)]), path]
    for component in dict.fromkeys(components):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if missing_ok:
                continue
            raise ValidationError("LOCAL_ARTIFACT_MISSING", str(component)) from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValidationError("LOCAL_ARTIFACT_REDIRECTED", str(component))
    if path.resolve() != path:
        raise ValidationError("LOCAL_ARTIFACT_REDIRECTED", str(path))
    return path


def verified_bytes(root: Path, path: Path, identity: dict[str, Any]) -> bytes:
    path = safe_path(root, path)
    if not path.is_file():
        raise ValidationError("LOCAL_ARTIFACT_NOT_FILE", str(path))
    length = identity.get("byte_length")
    digest = identity.get("raw_digest")
    if (type(length) is not int or not 0 <= length <= 100 * 1024 * 1024
            or not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)):
        raise ValidationError("LOCAL_ARTIFACT_IDENTITY_INVALID", str(path))
    with path.open("rb") as stream:
        raw = stream.read(length + 1)
    safe_path(root, path)  # Recheck a directory/file replacement during read.
    if len(raw) != length or sha(raw) != digest:
        raise ValidationError("LOCAL_ARTIFACT_HASH_MISMATCH", str(path))
    return raw


def package_probe(root: Path, path: Path, identity: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {"path": str(path), "expected_sha256": identity["raw_digest"],
                            "expected_bytes": identity["byte_length"], "actual_sha256": None,
                            "actual_bytes": None, "raw_verified": False, "error": None}
    try:
        checked = safe_path(root, path)
        if not checked.is_file():
            raise ValidationError("LOCAL_ARTIFACT_NOT_FILE", str(checked))
        data["actual_bytes"] = checked.stat().st_size
        with checked.open("rb") as stream:
            raw = stream.read(identity["byte_length"] + 1)
        safe_path(root, checked)
        # Do not hash arbitrary large substituted files in a screen refresh.
        if len(raw) == data["actual_bytes"]:
            data["actual_sha256"] = sha(raw)
        data["raw_verified"] = (data["actual_bytes"] == identity["byte_length"]
                                and data["actual_sha256"] == identity["raw_digest"])
        data["state"] = "GOTOWA" if data["raw_verified"] else "NIESPÓJNA"
        if not data["raw_verified"]:
            data["error"] = "LOCAL_ARTIFACT_HASH_MISMATCH"
    except (ValidationError, OSError) as exc:
        code = getattr(exc, "code", "LOCAL_ARTIFACT_IO_ERROR")
        data.update(state="BRAK PLIKU" if code == "LOCAL_ARTIFACT_MISSING" else "NIESPÓJNA", error=str(exc))
    return data


class WindowsActions:
    """Native Windows calls, with argument vectors and no command shell."""

    def _explorer(self, *arguments: str) -> int:
        executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"
        if os.name != "nt" or not executable.is_file():
            raise OSError("Eksplorator Windows jest niedostępny")
        process = subprocess.Popen([str(executable), *arguments], shell=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return 0  # Explorer remains running; the opening request was delivered.
        return code

    def _select_with_shell(self, path: Path) -> None:
        """Confirm selection through a checked HRESULT, not an exit-code guess.

        Some Explorer instances exit 1 after handing off a successful opening.
        SHOpenFolderAndSelectItems with cidl=0 selects the absolute item in its
        parent. Microsoft documents S_OK as the success result.
        """
        import ctypes
        shell = ctypes.WinDLL("shell32")
        ole = ctypes.WinDLL("ole32")
        ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        ole.CoInitializeEx.restype = ctypes.c_long
        ole.CoUninitialize.argtypes = []
        ole.CoUninitialize.restype = None
        ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole.CoTaskMemFree.restype = None
        shell.SHParseDisplayName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong, ctypes.c_void_p]
        shell.SHParseDisplayName.restype = ctypes.c_long
        shell.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                    ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong]
        shell.SHOpenFolderAndSelectItems.restype = ctypes.c_long
        initialized = ole.CoInitializeEx(None, 2)
        if initialized < 0:
            raise OSError(f"Windows Shell COM: HRESULT 0x{initialized & 0xffffffff:08x}; {path}")
        pidl = ctypes.c_void_p()
        try:
            parsed = shell.SHParseDisplayName(str(path), None, ctypes.byref(pidl), 0, None)
            if parsed != 0:
                raise OSError(f"Windows Shell path: HRESULT 0x{parsed & 0xffffffff:08x}; {path}")
            opened = shell.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
            if opened != 0:
                raise OSError(f"Windows Shell selection: HRESULT 0x{opened & 0xffffffff:08x}; {path}")
        finally:
            if pidl:
                ole.CoTaskMemFree(pidl)
            ole.CoUninitialize()

    def select(self, path: Path) -> None:
        code = self._explorer("/select,", str(path))
        if code == 1:
            self._select_with_shell(path)
        elif code:
            raise OSError(f"Eksplorator zakończył wywołanie kodem {code}; {path}")

    def folder(self, path: Path) -> None:
        code = self._explorer(str(path))
        if code == 1:
            os.startfile(str(path), "explore")
        elif code:
            raise OSError(f"Eksplorator zakończył wywołanie kodem {code}; {path}")

    def clipboard(self, path: Path) -> bool:
        executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "clip.exe"
        if os.name != "nt" or not executable.is_file():
            return False
        try:
            subprocess.run([str(executable)], input=str(path).encode("utf-16le"),
                           shell=False, check=True, timeout=5, capture_output=True)
        except (OSError, subprocess.SubprocessError):
            return False
        return True

    def document(self, path: Path) -> None:
        if os.name != "nt":
            raise OSError("Otwieranie dokumentów przez Windows jest niedostępne")
        try:
            os.startfile(str(path), "open")
        except OSError as exc:
            if getattr(exc, "winerror", None) != 1155:
                raise
            editor = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "notepad.exe"
            if not editor.is_file():
                raise
            subprocess.Popen([str(editor), str(path)], shell=False)


def export_copy(root: Path, source: Path, identity: dict[str, Any], destination: Path) -> Path:
    raw = verified_bytes(root, source, identity)
    destination = Path(os.path.abspath(destination))
    safe_path(destination, destination)
    if not destination.is_dir():
        raise ValidationError("LOCAL_COPY_DIRECTORY_REQUIRED", str(destination))
    if destination.is_relative_to(root):
        raise ValidationError("LOCAL_COPY_PROTECTED_PATH", str(destination))
    target = destination / source.name
    # Exclusive creation refuses existing files, including dangling links.
    with target.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    verified_bytes(destination, target, identity)
    return target
