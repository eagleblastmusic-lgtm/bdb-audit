"""Installer-only readback of a signed packet; never establishes OS authority."""
import argparse
import os
from pathlib import Path

from bdb_audit.core.canonical_json import canonical_bytes
from bdb_audit.history.installation_authority import _relative_file
from bdb_audit.history.limited_authority import LimitedMachineAuthority, verify_cms
from bdb_audit.history.limited_environment import snapshot
from bdb_audit.history.limited_model import LimitedCorpus, domain_hash, sha, strict_json
from bdb_audit.history.limited_protocol import LimitedProtocol


def verify_packet(directory, owner_pin, qualifier_pin):
    directory = directory.absolute()

    def read(name):
        path = _relative_file(directory, name)
        for component in (path, *path.parents):
            if component == directory.parent:
                break
            if component.is_symlink() or getattr(component.stat(), "st_file_attributes", 0) & 0x400:
                raise ValueError("Packet reparse substitution denied")
        with path.open("rb") as stream:
            limit = 2 * 1024 * 1024 if path.suffix.lower() in {".json", ".p7s"} else 16 * 1024 * 1024
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Packet resource limit")
        return raw

    root_raw, installation_raw = read("root.json"), read("installation.json")
    root = strict_json(root_raw)
    if owner_pin == qualifier_pin or (root["owner_certificate_sha256"], root["qualifier_certificate_sha256"]) != (owner_pin, qualifier_pin):
        raise ValueError("Independent out-of-band owner/qualifier pins required")
    if root["installation_sha256"] != sha(installation_raw):
        raise ValueError("Installation raw identity mismatch")
    signature = read("installation.p7s")
    verify_cms(installation_raw, signature, owner_pin)
    installation = strict_json(installation_raw)
    files = {}
    for entry in installation["installed_files"]:
        raw = read(entry["file"])
        if entry != {"file": entry["file"], "bytes": len(raw), "sha256": sha(raw)} or entry["file"] in files:
            raise ValueError("Installed asset identity mismatch")
        files[entry["file"]] = raw
    corpus = LimitedCorpus(files)
    corpus.external("ROOT", root_raw)
    corpus.external("INSTALLATION_RECORD", installation_raw)
    namespace = domain_hash("BDB-NF02-P0-NAMESPACE/1", {k: root[k] for k in (
        "model_id", "root_id", "namespace_id", "owner_certificate_sha256", "qualifier_certificate_sha256")})
    if namespace != root["namespace_authority_digest"] or namespace != installation["namespace_authority_digest"]:
        raise ValueError("Namespace identity mismatch")
    import bdb_audit
    code_root = Path(bdb_audit.__file__).resolve().parent
    code = [{"file": p.relative_to(code_root).as_posix(), "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
            for p in sorted(code_root.rglob("*")) if p.is_file() and p.suffix in {".py", ".json"}]
    if code != installation["implementation_files"] or strict_json(files["ENVIRONMENT.json"]) != snapshot():
        raise ValueError("Actual final code/environment mismatch")
    leased = {"corpus": corpus, "files": files, "root": root, "installation": installation,
              "identity": sha(installation_raw), "root_raw": root_raw, "installation_raw": installation_raw,
              "installation_signature": signature}
    authority = LimitedMachineAuthority()
    authority.verify_qualification(leased)
    LimitedProtocol(authority, leased)  # Six exact roots/eight pins, schema-root precedence.
    if not os.name == "nt" or not installation["coordinator_os_identity"]["sid"].startswith("S-1-5-80-"):
        raise ValueError("This deployment script uses a Windows virtual service account")
    print(canonical_bytes({"status": "SIGNED_PACKET_READBACK_PASS_OS_INSTALLATION_NOT_YET_QUALIFIED",
        "installation_sha256": sha(installation_raw), "namespace_authority_digest": namespace,
        "service_sid": installation["coordinator_os_identity"]["sid"], "code_root": str(code_root),
        "python_executable": str(Path(__import__("sys").executable).resolve())}).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--owner-pin", required=True)
    parser.add_argument("--qualifier-pin", required=True)
    args = parser.parse_args()
    verify_packet(args.packet, args.owner_pin, args.qualifier_pin)
