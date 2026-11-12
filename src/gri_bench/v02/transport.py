"""Deadline-bounded OpenAI-compatible transport with private response evidence."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit


@dataclass
class Response:
    status: int | None
    body: bytes
    error: str | None = None


def request(payload, remaining):
    url = os.environ.get("GRI_MODEL_BASE_URL", "http://127.0.0.1:3425/v1").rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None:
        raise ValueError("Expected an HTTP(S) API base URL without embedded credentials")
    seconds = min(120.0, remaining)
    if seconds < 0.05:
        return Response(None, b"", "deadline_before_request")
    command = [
        "curl", "--disable", "--silent", "--show-error", "--proto", "=http,https",
        "--noproxy", "localhost,127.0.0.1,::1", "--max-time", f"{seconds:.3f}",
        "--connect-timeout", f"{min(5.0, seconds):.3f}", "--max-filesize", "4000000",
        "--header", "Content-Type: application/json", "--data-binary", "@-",
        "--write-out", "\n%{http_code}",
    ]
    key = os.environ.get("GRI_MODEL_API_KEY")
    with tempfile.TemporaryDirectory(prefix="gri-headers-") as folder:
        if key:
            if "\n" in key or "\r" in key:
                raise ValueError("Invalid API credential")
            headers = Path(folder) / "headers"
            headers.write_text("Authorization: Bearer " + key + "\n")
            command.extend(["--header", "@" + str(headers)])
        command.extend(["--url", url + "/chat/completions"])
        try:
            proc = subprocess.run(
                command, input=json.dumps(payload, allow_nan=False).encode(),
                capture_output=True, timeout=seconds + 0.2,
            )
        except subprocess.TimeoutExpired as error:
            return Response(None, error.stdout or b"", "response_timeout_unknown_usage")
    body, _, suffix = proc.stdout.rpartition(b"\n")
    status = int(suffix) if len(suffix) == 3 and suffix.isdigit() and suffix != b"000" else None
    if proc.returncode:
        if proc.returncode == 7 and status is None:
            failure = "connection_not_established"
        elif proc.returncode == 28:
            failure = "response_timeout_unknown_usage"
        else:
            failure = "transport_error_unknown_usage"
        return Response(status, body, failure)
    return Response(status, body, None if status == 200 else "http_error")
