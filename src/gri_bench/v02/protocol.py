"""Tool descriptions, wire validation, and a host-owned design checkpoint."""
import json
import os
from pathlib import Path
import tempfile
import time

from gri_bench.api import PARAMETERS, validate_design
from gri_bench.runner import ROOT, digest

POLICY_FILE = ROOT / "contract/v0.2/policy.json"
TASK_FILE = ROOT / "docs/v02/AGENT_TASK.md"
SYSTEM = (
    "You are a scientific design agent. Use shell to search the public simulator "
    "and submit_design to register your best legal candidate. A legal submission "
    "is saved immediately. Use the remaining budget to improve it."
)
CORRECTION = (
    "No design has been accepted. Call submit_design with the mode and all "
    "parameters for your best in-bounds design now."
)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run a shell command in the isolated task workspace, within the shared CPU budget.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}, "timeout_seconds": {"type": "number"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_design",
            "description": "Validate and save your latest static design for independent scoring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["responsive", "constant"]},
                    "parameters": {
                        "type": "object",
                        "properties": {name: {"type": "number"} for name in (*PARAMETERS, "theta_c")},
                        "additionalProperties": False,
                    },
                },
                "required": ["mode", "parameters"],
                "additionalProperties": False,
            },
        },
    },
]


def loads_strict(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Nonfinite JSON constant")

    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


def atomic_json(path, value, cutoff=None):
    """Stage a JSON file beside its destination and replace it atomically."""
    path = Path(path)
    encoded = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(encoded)
    try:
        stamp = time.monotonic()
        if cutoff is not None and stamp >= cutoff:
            raise TimeoutError("Submission cutoff reached")
        os.replace(temporary, path)
        return stamp
    finally:
        temporary.unlink(missing_ok=True)


def excluded_model(value):
    name = str(value).lower()
    return "claude" in name or "opus" in name


def accept_design(path, arguments, instance, cutoff):
    if not isinstance(arguments, str) or len(arguments.encode()) > 16_000:
        raise ValueError("submit_design arguments must be JSON up to 16,000 bytes")
    design = validate_design(loads_strict(arguments), instance)
    stamp = atomic_json(path, design, cutoff)
    return stamp, digest(path)


def check_calls(message):
    """Return usable tool calls or reject an incoherent assistant history."""
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("Expected an assistant message")
    calls = message.get("tool_calls")
    if calls is None:
        return []
    if not isinstance(calls, list):
        raise ValueError("Invalid tool call list")
    ids = set()
    for call in calls:
        if not isinstance(call, dict) or call.get("type") != "function":
            raise ValueError("Invalid tool call")
        call_id = call.get("id")
        if not isinstance(call_id, str) or not call_id or call_id in ids:
            raise ValueError("Missing or repeated tool call ID")
        function = call.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            raise ValueError("Invalid tool function")
        if not isinstance(function.get("arguments"), str):
            raise ValueError("Expected tool arguments as JSON text")
        ids.add(call_id)
    return calls
