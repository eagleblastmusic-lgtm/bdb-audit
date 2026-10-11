"""LOCAL_PINNED authority supplied by the machine owner, never by intake.

The only production root is the OS common-app-data NF02 directory. It must be
owned/writable exclusively by SYSTEM/Administrators. No environment variable,
CLI flag, campaign file, certificate embedded in a ZIP, or constructor flag can
install a root. This module only reads; it never generates keys or approvals.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import base64
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess

from jsonschema import Draft202012Validator

from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError

# §192.2 / roadmap N4 and N5–N9: first-result activation. N10 closes
# NF02 and N11 qualifies the full application; neither is self-issued here.
REQUIRED_GATES = ("Q1", "Q2", "N4", "N5", "N6", "N7", "N8", "N9")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _powershell(script, data):
    if os.name != "nt":
        raise ValidationError("NF02_AUTHORITY_PLATFORM_UNAVAILABLE")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_unicode_buffer(32768)
    if not kernel.GetWindowsDirectoryW(buffer, len(buffer)):
        raise ValidationError("NF02_AUTHORITY_PLATFORM_UNAVAILABLE")
    executable = Path(buffer.value) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        result = subprocess.run([str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                input=json.dumps(data).encode("ascii"), capture_output=True,
                                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationError("NF02_AUTHORITY_VERIFIER_UNAVAILABLE") from exc
    if result.returncode:
        raise ValidationError("NF02_AUTHORITY_VERIFICATION_FAILED")
    try:
        return result.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValidationError("NF02_AUTHORITY_VERIFICATION_FAILED") from exc


def verify_cms(raw: bytes, signature: bytes, certificate_sha256: str, *, at_time=None, signature_limit=65536):
    """Check a detached CMS against an externally pinned certificate identity.

    CheckSignature(true) checks cryptography. Trust comes exclusively from the
    protected OS root pin, rather than a caller-provided certificate/chain.
    Current grants implement revocation; historical facts need no live token.
    """
    if type(signature_limit) is not int or not 1 <= signature_limit <= 2 * 1024 * 1024:
        raise ValidationError("NF02_PRODUCER_SIGNATURE_REQUIRED")
    if type(signature) is not bytes or not signature or len(signature) > signature_limit:
        raise ValidationError("NF02_PRODUCER_SIGNATURE_REQUIRED")
    script = r"""$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Security
$d=([Console]::In.ReadToEnd() | ConvertFrom-Json)
$content=New-Object System.Security.Cryptography.Pkcs.ContentInfo (,[Convert]::FromBase64String($d.content))
$cms=New-Object System.Security.Cryptography.Pkcs.SignedCms ($content,$true)
$cms.Decode([Convert]::FromBase64String($d.signature))
if($cms.SignerInfos.Count -ne 1){throw 'signer count'}
$s=$cms.SignerInfos[0]
if($s.DigestAlgorithm.Value -ne '2.16.840.1.101.3.4.2.1'){throw 'digest algorithm'}
$cms.CheckSignature($true)
$cert=$s.Certificate
$now=if($d.at_time){[DateTime]::ParseExact($d.at_time,'yyyy-MM-ddTHH:mm:ssZ',[Globalization.CultureInfo]::InvariantCulture,([Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal))}else{[DateTime]::UtcNow}
if($now -lt $cert.NotBefore.ToUniversalTime() -or $now -gt $cert.NotAfter.ToUniversalTime()){throw 'certificate expired'}
$hash=[Security.Cryptography.SHA256]::Create().ComputeHash($cert.RawData)
$pin=([BitConverter]::ToString($hash)).Replace('-','').ToLowerInvariant()
if($pin -cne $d.pin){throw 'certificate pin'}
[Console]::Out.Write('VERIFIED')
"""
    if _powershell(script, {"content": base64.b64encode(raw).decode("ascii"),
                            "signature": base64.b64encode(signature).decode("ascii"),
                            "pin": certificate_sha256, "at_time": at_time}) != "VERIFIED":
        raise ValidationError("NF02_AUTHORITY_VERIFICATION_FAILED")


def _machine_root():
    if os.name != "nt":
        raise ValidationError("NF02_INSTALLATION_AUTHORITY_NOT_ESTABLISHED")
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.WinDLL("shell32").SHGetFolderPathW(None, 35, None, 0, buffer):
        raise ValidationError("NF02_INSTALLATION_AUTHORITY_NOT_ESTABLISHED")
    return Path(buffer.value) / "BDB Audit/NF02"


def _protected(path):
    script = r"""$ErrorActionPreference='Stop'
$d=([Console]::In.ReadToEnd() | ConvertFrom-Json)
foreach($path in $d.paths){
$item=Get-Item -LiteralPath $path -Force
if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'reparse point'}
$acl=Get-Acl -LiteralPath $path
$allowed=@('S-1-5-18','S-1-5-32-544')
if($allowed -notcontains $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value){throw 'owner'}
foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
 if(($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) -ne 0){continue}
 if($rule.AccessControlType -eq 'Allow' -and (([long]$rule.FileSystemRights -band [long]$d.mask) -ne 0) -and $allowed -notcontains $rule.IdentityReference.Value){throw 'writable root'}
}
}
[Console]::Out.Write('PROTECTED')
"""
    paths = path if isinstance(path, (list, tuple, set)) else [path]
    if _powershell(script, {"paths": sorted({str(p) for p in paths}), "mask": 0xD0156}) != "PROTECTED":
        raise ValidationError("NF02_UNPROTECTED_INSTALLATION_ROOT")


@contextmanager
def _locked_file(path, *, directory=False, check_acl=True, digest_only=False):
    """Deny write/delete until acceptance/delivery has finished (Windows)."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    # OPEN_REPARSE_POINT makes a last-moment link substitution fail the ACL
    # check; directory handles also prevent parent rename during the lease.
    handle = kernel.CreateFileW(str(path), 0x80 if directory else 0x80000000, 1, None, 3,
                               0x00200000 | (0x02000000 if directory else 0x08000000), None)
    if handle == ctypes.c_void_p(-1).value:
        raise ValidationError("NF02_INSTALLATION_UNAVAILABLE_OR_CHANGING")
    try:
        if check_acl:
            _protected(path)
        if digest_only and not directory:
            digest, size = hashlib.sha256(), 0
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > 512 * 1024 * 1024:
                        raise ValidationError("NF02_INSTALLATION_RESOURCE_LIMIT")
                    digest.update(chunk)
            yield {"sha256": digest.hexdigest(), "bytes": size}
        else:
            raw = b"" if directory else path.read_bytes()
            if len(raw) > 16 * 1024 * 1024:
                raise ValidationError("NF02_INSTALLATION_RESOURCE_LIMIT")
            yield raw
    finally:
        kernel.CloseHandle(handle)


def _relative_file(root, name):
    p = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or p.is_absolute() or any(s in {"", ".", ".."} for s in name.split("/")):
        raise ValidationError("NF02_INSTALLATION_PATH_INVALID")
    target = root.joinpath(*p.parts)
    return target


def verify_q1_record(files, installation, manifest):
    """Validate actual external §187.2 evidence, rather than a PASS label."""
    if manifest.get("revision") != "R5.4.2":
        raise ValidationError("NF02_FRESH_EXACT_SUCCESSOR_Q1_REQUIRED")
    base = str(PurePosixPath(installation["pin_bundle"]).parent)
    governance = parse(files[base + "/governance/GOVERNANCE_CONTRACT.json"])
    schema_raw = files[base + "/" + governance["schema_file"]]
    if len(schema_raw) != governance["byte_length"] or sha(schema_raw) != governance["raw_digest"]:
        raise ValidationError("NF02_GOVERNANCE_SCHEMA_PIN_MISMATCH")
    attestation = parse(files[installation["qualification"]])
    record = parse(files[attestation["gates"]["Q1"]["evidence_file"]])
    if not Draft202012Validator(parse(schema_raw)).is_valid(record):
        raise ValidationError("NF02_Q1_RECORD_SCHEMA_INVALID")
    if (record["candidate_manifest_raw_digest"] != sha(files[installation["candidate_manifest"]])
            or record["normative_candidate_set_digest"] != manifest["normative_candidate_set_sha256"]
            or record["machine_candidate_set_digest"] != manifest["machine_candidate_set_sha256"]
            or record["self_audit_report_raw_digest"] != record["final_reaudit_register_raw_digest"]):
        raise ValidationError("NF02_Q1_RECORD_BINDING_CONFLICT")
    expected = {(group, entry["file"]): entry for group in ("normative", "machine") for entry in manifest[group + "_candidate_files"]}
    actual = {(entry["group"], entry["file"]): entry for entry in record["readback_entries"]}
    if len(actual) != len(record["readback_entries"]) or set(actual) != set(expected):
        raise ValidationError("NF02_Q1_READBACK_MEMBERSHIP_CONFLICT")
    for key, entry in expected.items():
        raw = files[base + "/" + entry["file"]]
        observed = actual[key]
        if (observed["result"] != "PASS" or observed["byte_length"] != len(raw) or entry["bytes"] != len(raw)
                or any(digest != sha(raw) for digest in (entry["sha256"], observed["expected_raw_digest"], observed["observed_raw_digest"]))):
            raise ValidationError("NF02_Q1_READBACK_CONTENT_CONFLICT")
    for group in ("normative", "machine", "total"):
        count = len(expected) if group == "total" else len(manifest[group + "_candidate_files"])
        if record["readback_verified_" + group + "_file_count"] != count:
            raise ValidationError("NF02_Q1_READBACK_COUNT_CONFLICT")
    retained = {sha(raw) for raw in files.values()}
    for field in ("readback_raw_digest", "self_audit_report_raw_digest", "owner_decision_raw_digest", "registry_raw_digest", "golden_vector_set_raw_digest"):
        if record[field] not in retained:
            raise ValidationError("NF02_Q1_EVIDENCE_NOT_RETAINED", field)
    registry = parse(files[base + "/BDB_AUDIT_V2_ARTIFACT_CONTRACT_REGISTRY_R5_4.json"])
    bindings = parse(files[base + "/objects/schema_registry__2.json"])["body"]["bindings"]
    # Complete approved graph, not an opportunistically selected NF02 subset.
    if {row["schema_ref"] for row in registry["contracts"]} != {binding["schema_key"] for binding in bindings if binding["status"] == "ACTIVE"}:
        raise ValidationError("NF02_FULL_SUCCESSOR_SCHEMA_CLOSURE_REQUIRED")


class MachineAuthority:
    """Read-only production adapter. Test doubles belong outside this module."""

    @contextmanager
    def storage_lease(self, path):
        campaigns = _machine_root().parent / "Campaigns"
        target = Path(path).absolute()
        if not target.is_relative_to(campaigns) or target.suffix != ".sqlite":
            raise ValidationError("NF02_PROTECTED_HISTORY_LOCATION_REQUIRED")
        with ExitStack() as stack:
            for parent in reversed(target.parents):
                if parent == campaigns or campaigns in parent.parents:
                    stack.enter_context(_locked_file(parent, directory=True))
            if target.exists():
                _protected(target)
            yield

    @contextmanager
    def lease(self):
        root = _machine_root()
        if not root.is_dir():
            raise ValidationError("NF02_INSTALLATION_AUTHORITY_NOT_ESTABLISHED")
        with ExitStack() as stack:
            stack.enter_context(_locked_file(root.parent, directory=True))
            stack.enter_context(_locked_file(root, directory=True))
            root_raw = stack.enter_context(_locked_file(root / "root.json"))
            trust = parse(root_raw)
            if set(trust) != {"schema", "owner_certificate_sha256", "qualifier_certificate_sha256", "installation_sha256"} or trust["schema"] != "BDB_NF02_MACHINE_ROOT/1":
                raise ValidationError("NF02_INSTALLATION_ROOT_INVALID")
            if any(type(trust[key]) is not str or not re.fullmatch(r"[0-9a-f]{64}", trust[key]) for key in trust if key != "schema"):
                raise ValidationError("NF02_INSTALLATION_ROOT_INVALID")
            if trust["owner_certificate_sha256"] == trust["qualifier_certificate_sha256"]:
                raise ValidationError("NF02_INDEPENDENT_QUALIFIER_REQUIRED")
            installation_raw = stack.enter_context(_locked_file(root / "installation.json"))
            if sha(installation_raw) != trust["installation_sha256"]:
                raise ValidationError("NF02_INSTALLATION_PIN_MISMATCH")
            signature = stack.enter_context(_locked_file(root / "installation.p7s"))
            verify_cms(installation_raw, signature, trust["owner_certificate_sha256"])
            installation = parse(installation_raw)
            required = {"schema", "activation", "files", "candidate_manifest", "pin_bundle", "qualification", "grants", "implementation", "bootstrap_packets", "context_packets"}
            if set(installation) != required or installation["schema"] != "BDB_NF02_INSTALLATION/1" or installation["activation"] != "QUALIFIED_NEW_CAMPAIGNS_ONLY":
                raise ValidationError("NF02_QUALIFIED_ACTIVATION_REQUIRED")
            files = {}
            directories = {root.parent, root}
            protected_files = []
            for name, identity in installation["files"].items():
                target = _relative_file(root, name)
                for parent in reversed(target.parents):
                    if root in parent.parents and parent not in directories:
                        stack.enter_context(_locked_file(parent, directory=True, check_acl=False))
                        directories.add(parent)
                raw = stack.enter_context(_locked_file(target, check_acl=False))
                protected_files.append(target)
                if identity != {"sha256": sha(raw), "bytes": len(raw)}:
                    raise ValidationError("NF02_INSTALLATION_CONTENT_DRIFT", name)
                files[name] = raw
            _protected(protected_files + list(directories))
            qualification = parse(files[installation["qualification"]])
            verify_cms(files[installation["qualification"]], files[installation["qualification"] + ".p7s"], trust["qualifier_certificate_sha256"])
            for grant in installation["grants"]:
                if (set(grant) != {"actor_ref", "campaign_id", "operations", "scope", "not_before", "not_after", "certificate_sha256"}
                        or not re.fullmatch(r"[0-9a-f]{64}", grant["certificate_sha256"])
                        or grant["certificate_sha256"] in {trust["owner_certificate_sha256"], trust["qualifier_certificate_sha256"]}):
                    raise ValidationError("NF02_PRODUCER_CANNOT_QUALIFY_OR_AUTHORIZE_SELF")
                start, end = datetime.fromisoformat(grant["not_before"]), datetime.fromisoformat(grant["not_after"])
                if start.utcoffset() is None or end.utcoffset() is None or start >= end:
                    raise ValidationError("NF02_INVALID_GRANT_VALIDITY")
            manifest_raw = files[installation["candidate_manifest"]]
            manifest = parse(manifest_raw)
            if (qualification.get("candidate_manifest_sha256") != sha(manifest_raw)
                    or qualification.get("normative_candidate_set_digest") != manifest["normative_candidate_set_sha256"]
                    or qualification.get("machine_candidate_set_digest") != manifest["machine_candidate_set_sha256"]
                    or set(qualification.get("gates", {})) != set(REQUIRED_GATES)):
                raise ValidationError("NF02_QUALIFICATION_BINDING_CONFLICT")
            for gate, record in qualification["gates"].items():
                if record.get("verdict") != "PASS" or sha(files[record["evidence_file"]]) != record["evidence_sha256"]:
                    raise ValidationError("NF02_QUALIFICATION_REQUIRED", gate)
            verify_q1_record(files, installation, manifest)
            # Hash the actual executable source closure, not an asserted HEAD.
            code_root = Path(__file__).resolve().parents[1]
            stack.enter_context(_locked_file(code_root, directory=True))
            actual = {}
            code_paths = []
            code_directories = {code_root}
            for path in sorted(code_root.rglob("*")):
                if path.is_file() and path.suffix in {".py", ".json"}:
                    for parent in reversed(path.parents):
                        if code_root in parent.parents and parent not in code_directories:
                            stack.enter_context(_locked_file(parent, directory=True, check_acl=False))
                            code_directories.add(parent)
                    raw = stack.enter_context(_locked_file(path, check_acl=False))
                    code_paths.append(path)
                    actual[str(path.relative_to(code_root)).replace("\\", "/")] = sha(raw)
            _protected(code_paths + list(code_directories))
            if actual != installation["implementation"] or qualification.get("implementation") != actual:
                raise ValidationError("NF02_QUALIFIED_IMPLEMENTATION_DRIFT")
            yield {"identity": sha(installation_raw), "installation": installation, "files": files}

    def authenticate(self, leased, command, signature, scope):
        now = datetime.now(timezone.utc)
        grants = [g for g in leased["installation"]["grants"]
                  if g["actor_ref"] == command.actor_ref and g["campaign_id"] == (command.campaign_ref or command.proposed_campaign_id)
                  and command.command_kind in g["operations"] and g["scope"] == scope
                  and datetime.fromisoformat(g["not_before"]) <= now < datetime.fromisoformat(g["not_after"])]
        if len(grants) != 1:
            raise ValidationError("NF02_PRODUCER_NOT_AUTHORIZED")
        statement = canonical_bytes({"domain": "BDB_NF02_AUTHENTICATED_COMMAND/1", "installation": leased["identity"],
                                     "command_digest": command.digest, "scope": scope})
        verify_cms(statement, signature, grants[0]["certificate_sha256"])
        if not datetime.fromisoformat(grants[0]["not_before"]) <= datetime.now(timezone.utc) < datetime.fromisoformat(grants[0]["not_after"]):
            raise ValidationError("NF02_PRODUCER_NOT_AUTHORIZED")
