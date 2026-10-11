"""Installed HTTPS transport. The caller cannot supply a trusted sink."""
import base64
import http.client
import ssl
from urllib.parse import urlsplit

from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from ..history.limited_model import sha, strict_json


def deliver_installed(files, job, package):
    config = strict_json(files["AUDITOR_TRANSPORT.json"])
    if set(config) != {"auditors"} or not isinstance(config["auditors"], list):
        raise ValidationError("P0_QUALIFIED_TRANSPORT_REQUIRED")
    matches = [d for d in config["auditors"] if d.get("auditor_certificate_sha256") == job["auditor_certificate_sha256"]]
    if len(matches) != 1:
        raise ValidationError("P0_QUALIFIED_AUDITOR_DESTINATION_REQUIRED")
    destination = matches[0]
    if set(destination) != {"auditor_certificate_sha256", "url", "server_certificate_sha256"}:
        raise ValidationError("P0_QUALIFIED_TRANSPORT_REQUIRED")
    url = urlsplit(destination["url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment or url.query:
        raise ValidationError("P0_QUALIFIED_HTTPS_DESTINATION_REQUIRED")
    connection = http.client.HTTPSConnection(url.hostname, url.port or 443, timeout=30, context=ssl.create_default_context())
    try:
        connection.connect()
        if sha(connection.sock.getpeercert(binary_form=True)) != destination["server_certificate_sha256"]:
            raise ValidationError("P0_DELIVERY_SERVER_IDENTITY_MISMATCH")
        headers = {"Content-Type": "application/zip", "Content-Length": str(len(package)),
                   "BDB-Release-Id": job["release_id"], "BDB-Package-SHA256": sha(package),
                   "BDB-Context": base64.b64encode(canonical_bytes(job)).decode("ascii")}
        connection.request("POST", url.path or "/", body=package, headers=headers)
        response = connection.getresponse()
        raw = response.read(65537)
        if len(raw) > 65536 or not 200 <= response.status < 300:
            raise ValidationError("P0_DELIVERY_OUTCOME_UNKNOWN")
        return {"http_status": response.status, "response_sha256": sha(raw), "response_bytes": raw}
    except (OSError, http.client.HTTPException) as exc:
        raise ValidationError("P0_DELIVERY_OUTCOME_UNKNOWN") from exc
    finally:
        connection.close()
