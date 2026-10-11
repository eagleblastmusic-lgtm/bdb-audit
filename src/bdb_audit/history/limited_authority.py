"""Read-only independently installed P0 authority; no issuer or caller root."""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from pathlib import Path

from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from .installation_authority import (_machine_root, _locked_file, _relative_file,
                                     _protected, _powershell, verify_cms)
from .limited_model import BASE, MODEL_ID, LimitedCorpus, sha, domain_hash, strict_json
from .limited_environment import verify_environment

ROLE_OPERATIONS = {
    "COORDINATOR": {"INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT",
                    "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT", "RELEASE_PACKAGE"},
    "AUDITOR": {"ACK_DELIVERY", "RETURN_AUDIT"},
    "OWNER_RECOVERY": {"ABORT_ATTEMPT"},
}


def instant(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValidationError("P0_INVALID_AUTHORITY_TIME") from exc


def valid_now(grant, now):
    if not instant(grant["not_before"]) <= now < instant(grant["not_after"]):
        raise ValidationError("P0_CURRENT_AUTHORITY_REQUIRED")


def machine_root():
    return _machine_root().parent / "NF02-P0-Limited"


def verify_service(sid, paths=()):
    script = r"""$ErrorActionPreference='Stop'
$d=([Console]::In.ReadToEnd() | ConvertFrom-Json)
$me=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal $me
if($me.User.Value -cne $d.sid -or $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or $me.Groups.Value -contains 'S-1-5-32-544' -or $me.User.Value -eq 'S-1-5-18'){throw 'non admin service required'}
foreach($path in $d.paths){
 $item=Get-Item -LiteralPath $path -Force
 if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'reparse point'}
 $acl=Get-Acl -LiteralPath $path
 $allowed=@('S-1-5-18','S-1-5-32-544',$d.sid)
 if($allowed -notcontains $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value){throw 'storage owner'}
 foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if(($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) -ne 0){continue}
  if($rule.AccessControlType -eq 'Allow' -and (([long]$rule.FileSystemRights -band 0xD0156) -ne 0) -and $allowed -notcontains $rule.IdentityReference.Value){throw 'untrusted storage writer'}
 }
}
[Console]::Out.Write('SERVICE')
"""
    if _powershell(script, {"sid": sid, "paths": [str(p) for p in paths]}) != "SERVICE":
        raise ValidationError("P0_NON_ADMIN_SERVICE_REQUIRED")


class LimitedMachineAuthority:
    @contextmanager
    def lease(self):
        root = machine_root()
        if not root.is_dir():
            raise ValidationError("P0_INSTALLATION_AUTHORITY_NOT_ESTABLISHED")
        with ExitStack() as stack:
            directories = set()
            protected_files = []

            def read(name):
                target = _relative_file(root, name)
                for parent in reversed(target.parents):
                    if (parent == root.parent or parent == root or root in parent.parents) and parent not in directories:
                        stack.enter_context(_locked_file(parent, directory=True, check_acl=False))
                        directories.add(parent)
                protected_files.append(target)
                return stack.enter_context(_locked_file(target, check_acl=False))

            root_raw, install_raw, install_sig = read("root.json"), read("installation.json"), read("installation.p7s")
            _protected(protected_files + list(directories))
            # The OS-protected root is authoritative before any schema or ZIP.
            trust = strict_json(root_raw)
            if trust.get("model_id") != MODEL_ID or trust.get("installation_sha256") != sha(install_raw):
                raise ValidationError("P0_INSTALLATION_ROOT_MISMATCH")
            if trust["owner_certificate_sha256"] == trust["qualifier_certificate_sha256"]:
                raise ValidationError("P0_INDEPENDENT_QUALIFIER_REQUIRED")
            verify_cms(install_raw, install_sig, trust["owner_certificate_sha256"])
            installation = strict_json(install_raw)
            files = {}
            for entry in installation["installed_files"]:
                raw = read(entry["file"])
                if entry != {"file": entry["file"], "sha256": sha(raw), "bytes": len(raw)} or entry["file"] in files:
                    raise ValidationError("P0_INSTALLATION_CONTENT_DRIFT")
                files[entry["file"]] = raw
            corpus = LimitedCorpus(files)
            corpus.external("ROOT", root_raw)
            corpus.external("INSTALLATION_RECORD", install_raw)
            namespace = domain_hash("BDB-NF02-P0-NAMESPACE/1", {k: trust[k] for k in (
                "model_id", "root_id", "namespace_id", "owner_certificate_sha256", "qualifier_certificate_sha256")})
            if trust["namespace_authority_digest"] != namespace or installation["namespace_authority_digest"] != namespace:
                raise ValidationError("P0_NAMESPACE_MISMATCH")
            if installation["external_schema_root_sha256"] != sha(files[BASE + "schemas/canonical/schema_registry__3.schema.json"]):
                raise ValidationError("P0_EXTERNAL_SCHEMA_ROOT_MISMATCH")
            sid = installation["coordinator_os_identity"]["sid"]
            verify_service(sid)
            code_root = Path(__file__).resolve().parents[1]
            stack.enter_context(_locked_file(code_root.parent, directory=True, check_acl=False))
            directories.add(code_root.parent)
            actual = []
            for path in sorted(code_root.rglob("*")):
                if path.is_file() and path.suffix in {".py", ".json"}:
                    for parent in reversed(path.parents):
                        if (parent == code_root or code_root in parent.parents) and parent not in directories:
                            stack.enter_context(_locked_file(parent, directory=True, check_acl=False))
                            directories.add(parent)
                    raw = stack.enter_context(_locked_file(path, check_acl=False))
                    protected_files.append(path)
                    actual.append({"file": path.relative_to(code_root).as_posix(), "sha256": sha(raw), "bytes": len(raw)})
            if actual != installation["implementation_files"]:
                raise ValidationError("P0_QUALIFIED_IMPLEMENTATION_DRIFT")
            leased = {"identity": sha(install_raw), "installation": installation, "files": files, "corpus": corpus,
                      "root": trust, "root_raw": root_raw, "installation_raw": install_raw, "installation_signature": install_sig}
            self.verify_qualification(leased)
            if "ENVIRONMENT.json" not in files:
                raise ValidationError("P0_QUALIFIED_ENVIRONMENT_REQUIRED")
            verify_environment(strict_json(files["ENVIRONMENT.json"]), stack)
            grants = []
            grant_dir = root / "grants"
            stack.enter_context(_locked_file(grant_dir, directory=True, check_acl=False))
            directories.add(grant_dir)
            for path in sorted(grant_dir.glob("*.json")):
                raw = read("grants/" + path.name)
                sig = read("grants/" + path.name + ".p7s")
                grant = corpus.external("PRINCIPAL_GRANT", raw)
                if path.stem != sha(raw) or grant["installation_digest"] != leased["identity"]:
                    raise ValidationError("P0_GRANT_INSTALLATION_MISMATCH")
                verify_cms(raw, sig, trust["owner_certificate_sha256"])
                if not set(grant["operations"]) <= ROLE_OPERATIONS[grant["role"]]:
                    raise ValidationError("P0_ROLE_OPERATION_MISMATCH")
                if grant["role"] != "OWNER_RECOVERY" and grant["certificate_sha256"] in {
                        trust["owner_certificate_sha256"], trust["qualifier_certificate_sha256"]}:
                    raise ValidationError("P0_PRODUCER_CANNOT_AUTHORIZE_SELF")
                grants.append({"body": grant, "raw": raw, "signature": sig, "digest": sha(raw)})
            coordinators = {g["body"]["certificate_sha256"] for g in grants if g["body"]["role"] == "COORDINATOR"}
            auditors = {g["body"]["certificate_sha256"] for g in grants if g["body"]["role"] == "AUDITOR"}
            if coordinators & auditors:
                raise ValidationError("P0_INDEPENDENT_AUDITOR_REQUIRED")
            leased["grants"] = grants
            _protected(protected_files + list(directories))
            yield leased

    def verify_qualification(self, leased):
        c, files, installation, root = leased["corpus"], leased["files"], leased["installation"], leased["root"]

        def evidence(digest, name=None, signer=None):
            matches = [(n, raw) for n, raw in files.items() if sha(raw) == digest]
            if not matches:
                raise ValidationError("P0_QUALIFICATION_EVIDENCE_MISSING", str(name))
            filename, raw = matches[0]
            if signer:
                verify_cms(raw, files[filename + ".p7s"], root[signer + "_certificate_sha256"])
            return c.external(name, raw) if name else raw

        freeze = evidence(installation["freeze_sha256"], "INDEPENDENT_FREEZE", "qualifier")
        decision = evidence(freeze["owner_decision_sha256"], "OWNER_MODEL_DECISION", "owner")
        if decision["scope_graph_sha256"] != sha(files[BASE + "DEPENDENCY_GRAPH.json"]):
            raise ValidationError("P0_OWNER_GRAPH_MISMATCH")
        author = evidence(freeze["author_qualification_sha256"], "AUTHOR_QUALIFICATION", "owner")
        expected = {e["file"]: e for g in ("normative", "machine") for e in c.manifest[g + "_files"]}
        if author["readback_files"] != [expected[n] for n in sorted(expected)] or author["owner_decision_sha256"] != freeze["owner_decision_sha256"]:
            raise ValidationError("P0_Q1_EXACT_READBACK_REQUIRED")
        evidence(author["final_audit_sha256"])
        evidence(freeze["independent_review_sha256"])
        if installation["mode"] == "QUALIFICATION_ONLY":
            if installation["runtime_qualification_sha256"] is not None:
                raise ValidationError("P0_QUALIFICATION_MODE_MISMATCH")
            mandate = evidence(installation["qualification_mandate_sha256"], "QUALIFICATION_MANDATE", "owner")
            # The qualifier also signs the same mandate bytes; no test factory.
            mandate_file = next(n for n, raw in files.items() if sha(raw) == installation["qualification_mandate_sha256"])
            verify_cms(files[mandate_file], files[mandate_file + ".qualifier.p7s"], root["qualifier_certificate_sha256"])
            valid_now(mandate, datetime.now(timezone.utc))
            if mandate["freeze_sha256"] != installation["freeze_sha256"] or mandate["qualification_namespace"] != root["namespace_id"]:
                raise ValidationError("P0_QUALIFICATION_MANDATE_MISMATCH")
            qualified = mandate
        else:
            if installation["qualification_mandate_sha256"] is not None:
                raise ValidationError("P0_PRODUCTION_MODE_MISMATCH")
            qualified = evidence(installation["runtime_qualification_sha256"], "RUNTIME_QUALIFICATION", "qualifier")
            if qualified["independent_freeze_sha256"] != installation["freeze_sha256"] or qualified["qualification_namespace"] == root["namespace_id"]:
                raise ValidationError("P0_RQ_BINDING_MISMATCH")
            for field in ("environment_evidence_sha256", "real_external_run_evidence_sha256", "executor_boundary_evidence_sha256"):
                evidence(qualified[field])
            if qualified["environment_evidence_sha256"] != sha(files.get("ENVIRONMENT.json", b"")):
                raise ValidationError("P0_RQ_ENVIRONMENT_BINDING_MISMATCH")
            for entry in qualified["test_evidence"]:
                if entry["file"] not in files or entry != {"file": entry["file"], "sha256": sha(files[entry["file"]]), "bytes": len(files[entry["file"]])}:
                    raise ValidationError("P0_RQ_TEST_EVIDENCE_MISMATCH")
        if qualified["implementation_files"] != installation["implementation_files"]:
            raise ValidationError("P0_QUALIFIED_IMPLEMENTATION_DRIFT")

    @contextmanager
    def storage_lease(self, path, leased):
        campaigns = machine_root().parent / "P0-Campaigns" / leased["root"]["namespace_authority_digest"]
        target = Path(path).absolute()
        if not target.is_relative_to(campaigns) or target.suffix != ".sqlite":
            raise ValidationError("P0_PROTECTED_HISTORY_LOCATION_REQUIRED")
        with ExitStack() as stack:
            paths = []
            storage_parent = campaigns.parent
            stack.enter_context(_locked_file(storage_parent, directory=True))
            for parent in reversed(target.parents):
                if parent == campaigns or campaigns in parent.parents:
                    stack.enter_context(_locked_file(parent, directory=True, check_acl=False))
                    paths.append(parent)
            if target.exists():
                paths.append(target)
            verify_service(leased["installation"]["coordinator_os_identity"]["sid"], paths)
            _protected(machine_root().parent)
            yield

    def select_grant(self, leased, *, operation, actor=None, certificate=None, digest=None, scope, at=None):
        now = instant(at) if at else datetime.now(timezone.utc)
        matches = []
        for item in leased["grants"]:
            g = item["body"]
            if (g["installation_digest"] == leased["identity"] and set(g["operations"]) <= ROLE_OPERATIONS[g["role"]]
                    and (g["role"] == "OWNER_RECOVERY" or g["certificate_sha256"] not in {leased["root"]["owner_certificate_sha256"], leased["root"]["qualifier_certificate_sha256"]})
                    and operation in g["operations"] and operation in ROLE_OPERATIONS[g["role"]]
                    and (actor is None or g["actor_ref"] == actor) and (certificate is None or g["certificate_sha256"] == certificate)
                    and (digest is None or item["digest"] == digest)
                    and all(g[k] == scope[k] for k in ("campaign_id", "source_scope_digest", "view_task_digest", "assignment_scope_digest"))
                    and instant(g["not_before"]) <= now < instant(g["not_after"])):
                matches.append(item)
        if len(matches) != 1:
            raise ValidationError("P0_CURRENT_SCOPED_GRANT_REQUIRED", operation)
        return matches[0]

    def authenticate(self, leased, command, signature, scope):
        b = command.body()
        if (b["installation_digest"] != leased["identity"] or b["namespace_authority_digest"] != leased["root"]["namespace_authority_digest"]
                or b["mode"] != leased["installation"]["mode"]):
            raise ValidationError("P0_COMMAND_INSTALLATION_MISMATCH")
        grant = self.select_grant(leased, operation=b["operation"], actor=b["actor_ref"], digest=b["grant_digest"], scope=scope)
        verify_cms(command.signing_bytes(), signature, grant["body"]["certificate_sha256"])
        valid_now(grant["body"], datetime.now(timezone.utc))
        return grant
