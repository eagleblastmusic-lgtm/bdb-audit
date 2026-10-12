"""Windows SCM one-command host; all writes still use installed P0 Store gates.

Installed by the independent OS administrator under a non-admin service account.
SCM arguments carry untrusted packet paths, never roots, grants or signing keys.
"""
import ctypes
from ctypes import wintypes
import io
import os
import sys
import json
import re
import threading
from contextlib import redirect_stderr, redirect_stdout

SERVICE_NAME = "BDBAuditNF02P0"


def diagnostic(code, message):
    """Event log contains fixed codes, never packet/body/path/exception text."""
    error = "P0_SERVICE_COMMAND_FAILED" if code else "NONE"
    try:
        result = json.loads(message)
        token = result.get("error") if isinstance(result, dict) else None
        if isinstance(token, str) and re.fullmatch(r"(?:P0|NF02)_[A-Z0-9_]{1,100}", token):
            error = token
    except (ValueError, TypeError):
        pass
    return json.dumps({"service": SERVICE_NAME, "exit_code": code, "error": error}, sort_keys=True)


def execute(arguments):
    from .product_p0_cli import run_p0
    if (not arguments or arguments[0] not in {"status", "prepare", "accept", "prepare-release", "release"}
            or len(arguments) > 24 or any(len(a) > 4096 for a in arguments)):
        return 2, '{"status":"BLOCKED","error":"P0_SERVICE_FINITE_COMMAND_REQUIRED"}'
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        code = run_p0(arguments)
    return code, output.getvalue()[:30000]


def run_service():
    if os.name != "nt":
        raise RuntimeError("Windows SCM required")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    handler_type = ctypes.WINFUNCTYPE(None, wintypes.DWORD)
    main_type = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR))

    class Status(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in ("service_type", "state", "controls", "win32_exit", "specific_exit", "checkpoint", "wait_hint")]

    class Table(ctypes.Structure):
        _fields_ = [("name", wintypes.LPWSTR), ("main", main_type)]

    advapi.RegisterServiceCtrlHandlerW.argtypes = [wintypes.LPCWSTR, handler_type]
    advapi.RegisterServiceCtrlHandlerW.restype = wintypes.HANDLE
    advapi.SetServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(Status)]
    advapi.SetServiceStatus.restype = wintypes.BOOL
    advapi.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(Table)]
    advapi.StartServiceCtrlDispatcherW.restype = wintypes.BOOL
    advapi.RegisterEventSourceW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    advapi.RegisterEventSourceW.restype = wintypes.HANDLE
    advapi.ReportEventW.argtypes = [wintypes.HANDLE, wintypes.WORD, wintypes.WORD, wintypes.DWORD, ctypes.c_void_p,
                                    wintypes.WORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPCWSTR), ctypes.c_void_p]
    advapi.DeregisterEventSource.argtypes = [wintypes.HANDLE]
    handle = None
    lock = threading.RLock()
    stopped = threading.Event()
    state = Status(0x10, 2, 0, 0, 0, 1, 30000)

    def publish(next_state, code=0):
        with lock:
            state.state = next_state
            state.controls = 5 if next_state == 4 else 0  # STOP and SHUTDOWN
            state.win32_exit = 1066 if code else 0
            state.specific_exit = code
            state.checkpoint = state.checkpoint + 1 if next_state in {2, 3} else 0
            state.wait_hint = 30000 if next_state in {2, 3} else 0
            if handle and not advapi.SetServiceStatus(handle, ctypes.byref(state)):
                raise ctypes.WinError(ctypes.get_last_error())

    @handler_type
    def handler(control):
        if control in {1, 5}:  # Drain admitted transaction; forced termination uses Store recovery.
            stopped.set()
        elif control == 4 and handle:
            advapi.SetServiceStatus(handle, ctypes.byref(state))

    @main_type
    def service_main(argc, argv):
        nonlocal handle
        handle = advapi.RegisterServiceCtrlHandlerW(SERVICE_NAME, handler)
        if not handle:
            return
        code, message = 2, "P0_SERVICE_COMMAND_FAILED"
        try:
            publish(2)
            if argc > 25:
                raise ValueError("Finite SCM arguments required")
            arguments = [argv[i] for i in range(1, argc)]
            publish(4)
            result = []
            done = threading.Event()

            def work():
                try:
                    result.append(execute(arguments))
                except BaseException:
                    result.append((2, "P0_SERVICE_COMMAND_FAILED"))
                finally:
                    done.set()

            worker = threading.Thread(target=work, name="P0-Store-operation")
            worker.start()
            while not done.wait(1):
                if stopped.is_set():
                    publish(3)  # Checkpoint while the bounded operation drains.
            worker.join()
            code, message = result[0]
        except BaseException:
            message = "P0_SERVICE_COMMAND_FAILED"
        finally:
            publish(3)
            event_source = advapi.RegisterEventSourceW(None, SERVICE_NAME)
            if event_source:
                strings = (wintypes.LPCWSTR * 1)(diagnostic(code, message))
                advapi.ReportEventW(event_source, 1 if code else 4, 0, 1001, None, 1, 0, strings, None)
                advapi.DeregisterEventSource(event_source)
            publish(1, code)

    table = (Table * 2)(Table(SERVICE_NAME, service_main), Table(None, main_type()))
    if not advapi.StartServiceCtrlDispatcherW(table):
        raise ctypes.WinError(ctypes.get_last_error())


if __name__ == "__main__":
    run_service()
