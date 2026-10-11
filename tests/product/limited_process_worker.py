"""Subprocess crash/replay probe using explicit TEST ONLY OS/CMS simulation."""

import base64
import json
import os
from pathlib import Path
import sys

from bdb_audit.history import limited_protocol, limited_authority
from bdb_audit.history.limited_model import LimitedCorpus
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake, LimitedRequest
from test_limited_p0 import (
    SimulatedOsAuthority,
    simulated_verify,
    test_signature,
    COORDINATOR,
)


def main():
    state_path, path, boundary = sys.argv[1:]
    value = json.loads(Path(state_path).read_bytes())
    leased = value["leased"]
    for key in ("root_raw", "installation_raw", "installation_signature"):
        leased[key] = base64.b64decode(leased[key])
    leased["files"] = {k: base64.b64decode(v) for k, v in leased["files"].items()}
    for grant in leased["grants"]:
        for key in ("raw", "signature"):
            grant[key] = base64.b64decode(grant[key])
    leased["corpus"] = LimitedCorpus(leased["files"])
    authority = SimulatedOsAuthority(leased)
    limited_protocol.LimitedMachineAuthority = lambda: authority
    limited_protocol.verify_cms = limited_authority.verify_cms = simulated_verify
    store = TransactionalHistoryStore.open_p0(path)
    if boundary == "VERIFY":
        head = store.head()
        print(
            json.dumps(
                {
                    "head": head.as_dict() if head else None,
                    "projection": store.rebuild_projection() if head else None,
                }
            )
        )
        return 0
    runtime = store._nf02
    packet = value["packet"]
    command = LimitedCommand(packet["command"], runtime)
    request = LimitedRequest(
        command,
        tuple(
            runtime.object(o["kind"], o["body"], o["version"])
            for o in packet["objects"]
        ),
        tuple(command.body()["events"]),
        {k: base64.b64decode(v) for k, v in value["raw"].items()},
    )

    def crash(name):
        if name == boundary:
            os._exit(91)  # No exception, finally, connection close or rollback.

    store.crash_hook = crash
    LimitedIntake(store).accept(
        request, test_signature(request.signing_bytes(), COORDINATOR)
    )
    raise AssertionError("Crash boundary was not reached")


if __name__ == "__main__":
    raise SystemExit(main())
