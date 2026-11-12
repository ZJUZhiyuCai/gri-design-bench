import json
import threading
import time
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from gri_bench.evaluate import strict_json
from gri_bench.runner import load_case
from gri_bench.v02.protocol import POLICY_FILE, accept_design
from gri_bench.v02.transport import Response, request
from gri_bench.v02 import trial

DESIGN = {"mode": "constant", "parameters": {"theta_c": 0.0002, "theta_L": 1.0}}


def test_bad_and_late_submissions_preserve_last_legal_design(tmp_path):
    instance, _ = load_case("dev-01")
    path = tmp_path / "design.json"
    accept_design(path, json.dumps(DESIGN), instance, time.monotonic() + 1)
    with pytest.raises(ValueError, match="Duplicate"):
        accept_design(path, '{"mode":"constant","mode":"responsive","parameters":{}}',
                      instance, time.monotonic() + 1)
    with pytest.raises(ValueError, match="outside"):
        accept_design(path, '{"mode":"constant","parameters":{"theta_c":9,"theta_L":1}}',
                      instance, time.monotonic() + 1)
    with pytest.raises(TimeoutError):
        accept_design(path, json.dumps({**DESIGN, "parameters": {"theta_c": 0.0, "theta_L": 1.0}}),
                      instance, time.monotonic() - 1)
    assert strict_json(path) == DESIGN


def completion(finish="stop", calls=None, model="test-model", tokens=15):
    msg = {"role": "assistant", "content": None, "tool_calls": calls}
    data = {"model": model, "choices": [{"finish_reason": finish, "message": msg}],
            "usage": {"completion_tokens": tokens}}
    return Response(200, json.dumps(data).encode())


def structured():
    return [{"id": "test-1", "type": "function",
             "function": {"name": "submit_design", "arguments": json.dumps(DESIGN)}}]


def agent(tmp_path, monkeypatch, responses):
    payloads = []
    replies = iter(responses)

    def mocked(payload, remaining):
        payloads.append(json.loads(json.dumps(payload)))
        return next(replies)

    monkeypatch.setattr(trial, "request", mocked)
    instance, _ = load_case("dev-01")
    meta = {"requested_model": "test-model", "calls": [], "submissions": [], "shell_calls": [],
            "timing": {"api_seconds": 0.0, "sandbox_queue_seconds": 0.0}, "resource_violations": []}
    start = time.monotonic()
    reason = trial.run_agent(tmp_path, instance, meta, None, start + 30, start,
                            strict_json(POLICY_FILE), nullcontext())
    return reason, meta, payloads


def test_truncated_tool_is_ignored_and_one_correction_can_recover(tmp_path, monkeypatch):
    truncated = [{"id": "bad", "type": "function",
                  "function": {"name": "shell", "arguments": '{"command":'}}]
    reason, meta, payloads = agent(tmp_path, monkeypatch, [
        completion("length", truncated, tokens=6000),
        completion("tool_calls", structured()),
        completion(),
    ])
    assert reason == "final_response"
    assert len(meta["submissions"]) == 1 and meta["shell_calls"] == []
    assert meta["charged_completion_tokens"] == 6030
    assert meta["calls"][0]["correction_sent"]
    assert payloads[1]["messages"][-1]["role"] == "user"
    assert strict_json(tmp_path / "design.json") == DESIGN
    assert strict_json(tmp_path / "transcript.json")[-1]["role"] == "assistant"


def test_single_correction_and_failed_requests_have_bounded_allowance(tmp_path, monkeypatch):
    reason, meta, _ = agent(tmp_path, monkeypatch, [
        Response(502, b"empty reasoning only", "http_error"),
        completion(),
        completion(),
    ])
    assert reason == "no_tool_after_correction"
    assert meta["calls"][0]["error"] == "http_error_reasoning_only_at_output_limit"
    assert meta["token_accounting"][0]["charged_completion_tokens"] == 6000
    assert sum(c.get("correction_sent", False) for c in meta["calls"]) == 1
    assert not (tmp_path / "design.json").exists()


def test_excluded_upstream_response_cannot_submit(tmp_path, monkeypatch):
    reason, meta, _ = agent(tmp_path, monkeypatch, [
        completion("tool_calls", structured(), model="claude-unexpected"),
    ])
    assert reason == "excluded_returned_model"
    assert meta["resource_violations"] == ["excluded_returned_model"]
    assert not meta["submissions"]


def test_transport_stops_at_an_absolute_deadline(monkeypatch):
    class Slow(BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(1.0)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Slow) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            monkeypatch.setenv("GRI_MODEL_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
            monkeypatch.delenv("GRI_MODEL_API_KEY", raising=False)
            began = time.monotonic()
            response = request({"model": "mock"}, 0.2)
            assert response.error == "response_timeout_unknown_usage"
            assert time.monotonic() - began < 0.9
        finally:
            server.shutdown()
            thread.join()
