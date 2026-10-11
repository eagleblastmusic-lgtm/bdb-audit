"""Readback of the actual interpreter/dependencies, never an environment claim."""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import platform
import shutil
import sys

from ..core.errors import ValidationError
from .installation_authority import _locked_file, _protected


def dependency_roots():
    git = shutil.which("git")
    if not git:
        raise ValidationError("P0_GIT_RUNTIME_UNAVAILABLE")
    git_path = Path(git).resolve()
    git_root = git_path.parent.parent if git_path.parent.name.lower() in {"bin", "cmd"} else git_path.parent
    return {"PYTHON_BASE": Path(sys.base_prefix).resolve(), "PYTHON_ENV": Path(sys.prefix).resolve(), "GIT": git_root}


def snapshot(*, stack=None):
    """Inventory complete runtime trees; a signed RQ must bind these exact bytes.

    Qualification and production use the same installation paths and OS build.
    OS administration remains the explicitly approved host trust boundary.
    """
    roots = dependency_roots()
    directories, protected_directories, protected, identities = set(), set(), [], []
    for role, root in sorted(roots.items()):
        # Protect parents as well as leaves against rename/reparse substitution.
        paths = sorted(root.rglob("*"))
        protected_directories.add(root.parent)
        for path in [root, *paths]:
            if path.is_symlink():
                raise ValidationError("P0_ENVIRONMENT_REPARSE_DENIED")
            if stack:
                for parent in reversed((path if path.is_dir() else path.parent).parents):
                    if parent not in directories:
                        stack.enter_context(_locked_file(parent, directory=True, check_acl=False))
                        directories.add(parent)
                if path.is_dir() and path not in directories:
                    stack.enter_context(_locked_file(path, directory=True, check_acl=False))
                    directories.add(path)
                if path.is_dir():
                    protected_directories.add(path)
            if not path.is_file():
                continue
            if stack:
                identity = stack.enter_context(_locked_file(path, check_acl=False, digest_only=True))
                protected.append(path)
            else:
                digest, size = hashlib.sha256(), 0
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        size += len(chunk)
                        digest.update(chunk)
                identity = {"sha256": digest.hexdigest(), "bytes": size}
            identities.append({"role": role, "file": path.relative_to(root).as_posix(), **identity})
    if stack:
        _protected(protected + list(protected_directories))
    return {"format": "BDB_P0_INSTALLED_ENVIRONMENT/1", "os_family": os.name, "os_build": platform.version(),
            "python_version": sys.version, "python_executable": str(Path(sys.executable).resolve()),
            "roots": {k: str(v) for k, v in sorted(roots.items())}, "dependencies": identities}


def verify_environment(expected, stack: ExitStack):
    if not sys.flags.isolated or not sys.flags.ignore_environment or not sys.dont_write_bytecode:
        raise ValidationError("P0_ISOLATED_READ_ONLY_INTERPRETER_REQUIRED")
    if snapshot(stack=stack) != expected:
        raise ValidationError("P0_QUALIFIED_ENVIRONMENT_DRIFT")
