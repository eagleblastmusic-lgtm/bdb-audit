"""Missing declared runtime inputs must not produce a partial standalone."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import PurePosixPath
import subprocess
import sys
from types import SimpleNamespace

import pytest

import build.build_single_file as builder


def distribution(monkeypatch, root, names):
    installed = SimpleNamespace(
        version="1", files=[PurePosixPath(name) for name in names],
        locate_file=lambda path: root / str(path),
    )
    monkeypatch.setattr(builder.importlib.metadata, "distribution", lambda name: installed)


@pytest.mark.parametrize("missing_kind", ["absent", "directory"])
def test_declared_runtime_input_cannot_disappear(monkeypatch, tmp_path, missing_kind):
    (tmp_path / "present.py").write_bytes(b"present runtime input\n")
    if missing_kind == "directory":
        (tmp_path / "required.py").mkdir()
    distribution(monkeypatch, tmp_path, ["present.py", "required.py"])
    with pytest.raises(RuntimeError, match="Declared runtime input missing or not a file"):
        builder.collect_runtime_files({"pinned-runtime": "1"})


def test_declared_runtime_files_retained_and_transport_exclusions_preserved(monkeypatch, tmp_path):
    raw = b"exact runtime input\r\n"
    (tmp_path / "present.py").write_bytes(raw)
    distribution(monkeypatch, tmp_path, ["present.py", "../../../Scripts/entry.exe", "__pycache__/unused.pyc"])
    assert builder.collect_runtime_files({"pinned-runtime": "1"}) == [("present.py", raw)]



def test_concurrent_standalone_startup_publishes_only_complete_runtime_files(tmp_path):
    artifact, _, _ = builder.build_standalone(tmp_path / "standalone.py")
    cache = tmp_path / "cache"
    cache.mkdir()
    env = {**os.environ, "TMP": str(cache), "TEMP": str(cache), "TMPDIR": str(cache)}
    argv = [sys.executable, "-I", "-S", str(artifact), "self-test"]

    def launch():
        return subprocess.run(argv, env=env, capture_output=True, timeout=60)

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(launch) for _ in range(4)]
        for job in jobs:
            result = job.result()
            assert result.returncode == 0, (result.stdout, result.stderr)
