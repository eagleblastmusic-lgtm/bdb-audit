"""Bounded exact-byte source/package/result transforms for approved P0."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import io
import os
import re
import subprocess
import zipfile
from pathlib import Path

from ..assurance.zip_safety import Limits, read_bytes
from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from ..history.limited_model import BASE, sha, strict_json
from ..source.git_resolver import resolve_local_repository, _git_env

SAFE = re.compile(r"[A-Za-z0-9_-]+(?:[.][A-Za-z0-9_-]+)*(?:/[A-Za-z0-9_-]+(?:[.][A-Za-z0-9_-]+)*)*\Z")
RESERVED = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}


def fixed_zip(members):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.create_version = info.extract_version = 20
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])
    return out.getvalue()


class LimitedTransport:
    def __init__(self, corpus):
        self.corpus = corpus

    def archive(self, raw, profile):
        p = strict_json(self.corpus.files[BASE + "profiles/" + profile + ".json"])
        q = p.get("quotas") or strict_json(self.corpus.files[BASE + "profiles/P0_PACKAGE_TRANSPORT_V1.json"])["quotas"]
        members = read_bytes(raw, limits=Limits(input_bytes=q["archive_bytes"], members=q["members"],
                                               member_bytes=q["member_bytes"], expanded_bytes=q["expanded_bytes"]))
        for name, data in members.items():
            if (len(name) > 512 or not SAFE.fullmatch(name)
                    or any(s.split(".")[0].upper() in RESERVED for s in name.split("/"))):
                raise ValidationError("P0_UNSAFE_TRANSPORT_PATH", name)
            if name.endswith(".json"):
                strict_json(data)
        if len({n.casefold() for n in members}) != len(members):
            raise ValidationError("P0_TRANSPORT_PATH_COLLISION")
        # Comparing the entire encoding additionally rules out ZIP64, gaps,
        # local/central substitutions, descriptors, extras and trailing bytes.
        if fixed_zip(members) != raw:
            raise ValidationError("P0_FIXED_ZIP_REQUIRED")
        return members

    def member_records(self, members):
        mime = strict_json(self.corpus.files[BASE + "profiles/P0_PACKAGE_TRANSPORT_V1.json"])["mime_mapping"]
        return [{"path": name, "sha256": sha(data), "bytes": len(data),
                 "media_type": mime.get(Path(name).suffix, mime["default"])} for name, data in sorted(members.items())]

    def manifest_archive(self, raw, profile, schema):
        members = self.archive(raw, profile)
        if "MANIFEST.json" not in members:
            raise ValidationError("P0_MISSING_MANIFEST")
        manifest_raw = members.pop("MANIFEST.json")
        manifest = strict_json(manifest_raw)
        if manifest_raw != canonical_bytes(manifest) + b"\n":
            raise ValidationError("P0_CJSON_TRANSPORT_REQUIRED")
        self.corpus.schemas.validate("wire/" + schema + "__1", manifest)
        if manifest["members"] != self.member_records(members):
            raise ValidationError("P0_TRANSPORT_MEMBERS_MISMATCH")
        return manifest, members

    def source(self, manifest_raw, archive_raw, snapshot):
        manifest = strict_json(manifest_raw)
        self.corpus.schemas.validate("wire/SOURCE_MANIFEST__1", manifest)
        if manifest_raw != canonical_bytes(manifest) + b"\n":
            raise ValidationError("P0_CJSON_TRANSPORT_REQUIRED")
        keys = {"repository_id": "repository_id", "git_object_algorithm": "git_object_algorithm",
                "commit_oid": "git_commit_object_id", "tree_oid": "git_tree_object_id"}
        if any(manifest[k] != snapshot[v] for k, v in keys.items()) or snapshot["approved_view_digest"] != sha(manifest_raw):
            raise ValidationError("P0_SOURCE_IDENTITY_MISMATCH")
        algorithm = manifest["git_object_algorithm"]
        expected_length = {"sha1": 40, "sha256": 64}[algorithm]
        if any(len(manifest[k]) != expected_length for k in ("commit_oid", "tree_oid")) or manifest["commit_oid"] == manifest["tree_oid"]:
            raise ValidationError("P0_SOURCE_OBJECT_TYPE_MISMATCH")
        members = self.archive(archive_raw, "P0_BOOTSTRAP_SOURCE_V1")
        if members.pop("MANIFEST.json", None) != manifest_raw:
            raise ValidationError("P0_SOURCE_MANIFEST_BYTES_MISMATCH")
        entries = manifest["entries"]
        if entries != sorted(entries, key=lambda e: e["source_path"].encode("utf8")) or len({e["source_path"] for e in entries}) != len(entries):
            raise ValidationError("P0_SOURCE_PATH_ORDER")
        if set(members) != {e["transport_path"] for e in entries}:
            raise ValidationError("P0_SOURCE_MEMBERS_MISMATCH")
        for i, e in enumerate(entries):
            raw = members[e["transport_path"]]
            blob = hashlib.new(algorithm, b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if (e["transport_path"] != f"source/{i:08d}.bin" or blob != e["git_blob_oid"]
                    or sha(raw) != e["sha256"] or len(raw) != e["bytes"]
                    or raw.startswith(b"version https://git-lfs.github.com/spec/v1")):
                raise ValidationError("P0_GIT_BLOB_IDENTITY_MISMATCH")
        return manifest, members

    def input_members(self, manifest_raw, source_members, task):
        try:
            task.decode("utf8", "strict")
        except UnicodeDecodeError as exc:
            raise ValidationError("P0_INVALID_TASK_UTF8") from exc
        return {"SOURCE_MANIFEST.json": manifest_raw, "TASK.md": task, **source_members}

    def package(self, raw, assignment, scope, expected_members):
        manifest, members = self.manifest_archive(raw, "P0_PACKAGE_TRANSPORT_V1", "PACKAGE_MANIFEST")
        if (manifest["scope"] != scope or manifest["assignment_cut"] != assignment["assignment_cut"]
                or members != expected_members or manifest["members"] != assignment["input_members"]):
            raise ValidationError("P0_PACKAGE_ASSIGNMENT_MISMATCH")
        return members

    def result(self, raw, expected, source_manifest):
        manifest, members = self.manifest_archive(raw, "P0_RESULT_TRANSPORT_V1", "RESULT_MANIFEST")
        if any(manifest[k] != v for k, v in expected.items()):
            raise ValidationError("P0_RESULT_CONTEXT_MISMATCH")
        payload = manifest["payload"]
        self.corpus.schemas.validate("wire/NORMALIZED_RESULT__1", payload)
        ids = [f["finding_id"] for f in payload["findings"]]
        if ids != sorted(set(ids)):
            raise ValidationError("P0_DUPLICATE_FINDING_ID")
        source_paths = {e["source_path"] for e in source_manifest["entries"]}
        paths = [payload[k] for k in ("report_paths", "evidence_paths", "log_paths")]
        paths += [f["evidence_paths"] for f in payload["findings"]]
        for finding in payload["findings"]:
            selected = finding["source_paths"]
            if selected != sorted(set(selected), key=lambda n: n.encode("utf8")) or not set(selected) <= source_paths:
                raise ValidationError("P0_FINDING_SOURCE_PATH_MISMATCH")
        for selected in paths:
            if selected != sorted(set(selected)) or not set(selected) <= set(members):
                raise ValidationError("P0_RESULT_PATH_MISMATCH")
        declared = {p for selected in paths for p in selected}
        if declared != set(members):
            raise ValidationError("P0_UNDECLARED_RESULT_MEMBER")
        for name in payload["report_paths"]:
            if Path(name).suffix not in {".md", ".txt"}:
                raise ValidationError("P0_REPORT_MEDIA_TYPE")
            try:
                members[name].decode("utf8", "strict")
            except UnicodeDecodeError as exc:
                raise ValidationError("P0_REPORT_UTF8_REQUIRED") from exc
        return payload


def approved_git_view(repository, requested_ref, repository_id, paths):
    """Prepare actual Git bytes for independent approval, never approve them."""
    identity = resolve_local_repository(repository, requested_ref)
    repo = Path(repository).resolve()
    env = {k: v for k, v in _git_env().items() if k not in {
        "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"} and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(args, limit):
        # Files are read from typed Git objects, never the worktree or filters.
        try:
            with subprocess.Popen(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, env=env) as process:
                assert process.stdout is not None
                with ThreadPoolExecutor(max_workers=1) as reader:
                    pending = reader.submit(process.stdout.read, limit + 1)
                    try:
                        raw = pending.result(timeout=30)
                    except TimeoutError as exc:
                        process.kill()
                        process.wait(timeout=5)
                        raise ValidationError("P0_GIT_SOURCE_UNAVAILABLE") from exc
                if len(raw) > limit:
                    process.kill()
                    raise ValidationError("P0_GIT_VIEW_RESOURCE_LIMIT")
                if process.wait(timeout=30):
                    raise ValidationError("P0_GIT_SOURCE_UNAVAILABLE")
                return raw
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValidationError("P0_GIT_SOURCE_UNAVAILABLE") from exc

    metadata_bytes = 0

    def actual_object(kind, oid):
        nonlocal metadata_bytes
        raw = git(["cat-file", kind, oid], 32 * 1024 * 1024)
        if kind != "blob":
            metadata_bytes += len(raw)
            if metadata_bytes > 16 * 1024 * 1024:
                raise ValidationError("P0_GIT_VIEW_RESOURCE_LIMIT")
        actual = hashlib.new(identity.object_format, kind.encode("ascii") + b" " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if actual != oid:
            raise ValidationError("P0_GIT_OBJECT_BYTES_MISMATCH")
        return raw

    commit = actual_object("commit", identity.commit_object_id)
    if commit.split(b"\n", 1)[0] != b"tree " + identity.tree_object_id.encode("ascii"):
        raise ValidationError("P0_ACTUAL_COMMIT_TREE_MISMATCH")
    trees: dict[str, dict[bytes, tuple[str, str]]] = {}

    def tree_entries(oid):
        if oid not in trees:
            raw, entries, offset = actual_object("tree", oid), {}, 0
            width = 20 if identity.object_format == "sha1" else 32
            while offset < len(raw):
                space = raw.find(b" ", offset)
                end = raw.find(b"\0", space + 1)
                if space < offset or end < 0 or end + 1 + width > len(raw):
                    raise ValidationError("P0_MALFORMED_GIT_TREE")
                name = raw[space + 1:end]
                if not name or b"/" in name or name in entries:
                    raise ValidationError("P0_MALFORMED_GIT_TREE")
                entries[name] = (raw[offset:space].decode("ascii"), raw[end + 1:end + 1 + width].hex())
                offset = end + 1 + width
            trees[oid] = entries
        return trees[oid]
    selected = sorted(set(paths), key=lambda n: n.encode("utf8"))
    if not 1 <= len(selected) <= 2044 or len(selected) != len(paths):
        raise ValidationError("P0_GIT_VIEW_MEMBERSHIP")
    entries, members, total = [], {}, 0
    for i, path in enumerate(selected):
        segments, tree_oid = path.encode("utf8").split(b"/"), identity.tree_object_id
        if any(s in {b"", b".", b".."} for s in segments):
            raise ValidationError("P0_GIT_PATH_NOT_IN_TREE", path)
        for index, segment in enumerate(segments):
            entry = tree_entries(tree_oid).get(segment)
            if entry is None:
                raise ValidationError("P0_GIT_PATH_NOT_IN_TREE", path)
            mode, oid = entry
            if index < len(segments) - 1:
                if mode != "40000":
                    raise ValidationError("P0_UNSUPPORTED_GIT_ENTRY", path)
                tree_oid = oid
        if mode not in {"100644", "100755"}:
            raise ValidationError("P0_UNSUPPORTED_GIT_ENTRY", path)
        raw = actual_object("blob", oid)
        total += len(raw)
        if total > 64 * 1024 * 1024 or raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValidationError("P0_UNSUPPORTED_GIT_VIEW")
        transport = f"source/{i:08d}.bin"
        members[transport] = raw
        entries.append({"source_path": path, "transport_path": transport, "git_blob_oid": oid, "mode": mode,
                        "sha256": sha(raw), "bytes": len(raw)})
    manifest = {"repository_id": repository_id, "git_object_algorithm": identity.object_format,
                "commit_oid": identity.commit_object_id, "tree_oid": identity.tree_object_id, "entries": entries}
    manifest_raw = canonical_bytes(manifest) + b"\n"
    return identity, manifest_raw, fixed_zip({"MANIFEST.json": manifest_raw, **members})
