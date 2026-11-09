"""Standard Windows multi-selection, isolated from headless/test execution."""
from __future__ import annotations

import os
from pathlib import Path

# Explorer-style selection supplies NUL-separated long Unicode filenames.
# https://learn.microsoft.com/en-us/windows/win32/api/commdlg/ns-commdlg-openfilenamew
FLAGS = 0x00080000 | 0x00000200 | 0x00001000 | 0x00000800 | 0x00000008 | 0x02000000 | 0x00800000
FILTER = "Wyniki AI (*.json;*.zip)\0*.json;*.zip\0JSON (*.json)\0*.json\0ZIP (*.zip)\0*.zip\0\0"
BUFFER_CHARS = 1024 * 1024


def parse_selection(value: str) -> list[Path]:
    parts = value.split("\0\0", 1)[0].split("\0")
    if not parts or not parts[0]:
        return []
    if len(parts) == 1:
        return [Path(parts[0])]
    return [Path(parts[0]) / name for name in parts[1:] if name]


def _native_dialog() -> list[Path]:
    import ctypes
    from ctypes import wintypes as w

    class OpenFileName(ctypes.Structure):
        _fields_ = [("lStructSize", w.DWORD), ("hwndOwner", w.HWND), ("hInstance", w.HINSTANCE),
                    ("lpstrFilter", w.LPCWSTR), ("lpstrCustomFilter", w.LPWSTR), ("nMaxCustFilter", w.DWORD),
                    ("nFilterIndex", w.DWORD), ("lpstrFile", w.LPWSTR), ("nMaxFile", w.DWORD),
                    ("lpstrFileTitle", w.LPWSTR), ("nMaxFileTitle", w.DWORD), ("lpstrInitialDir", w.LPCWSTR),
                    ("lpstrTitle", w.LPCWSTR), ("Flags", w.DWORD), ("nFileOffset", w.WORD),
                    ("nFileExtension", w.WORD), ("lpstrDefExt", w.LPCWSTR), ("lCustData", w.LPARAM),
                    ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", w.LPCWSTR), ("pvReserved", ctypes.c_void_p),
                    ("dwReserved", w.DWORD), ("FlagsEx", w.DWORD)]

    library = ctypes.WinDLL("comdlg32", use_last_error=True)
    library.GetOpenFileNameW.argtypes = [ctypes.POINTER(OpenFileName)]
    library.GetOpenFileNameW.restype = w.BOOL
    library.CommDlgExtendedError.argtypes = []
    library.CommDlgExtendedError.restype = w.DWORD
    buffer = ctypes.create_unicode_buffer(BUFFER_CHARS)
    options = OpenFileName(lStructSize=ctypes.sizeof(OpenFileName), lpstrFilter=FILTER,
                           nFilterIndex=1, lpstrFile=ctypes.cast(buffer, w.LPWSTR), nMaxFile=BUFFER_CHARS,
                           lpstrTitle="Dodaj wyniki AI — Ctrl/Shift lub Ctrl+A; JSON i ZIP razem", Flags=FLAGS)
    if not library.GetOpenFileNameW(ctypes.byref(options)):
        error = library.CommDlgExtendedError()
        if error:
            raise OSError(f"Okno wyboru plików Windows: 0x{error:08x}")
        return []  # Cancellation is different from GUI unavailability.
    return parse_selection("".join(buffer[:]))


def choose_files(*, interactive: bool) -> list[Path] | None:
    # None means a manual fallback, [] means explicit cancellation. Never infer
    # authorization from a timeout or automatically show GUI in scripted tests.
    if (not interactive or os.name != "nt" or os.environ.get("SESSIONNAME", "").lower() == "services"
            or os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY")):
        return None
    return _native_dialog()
