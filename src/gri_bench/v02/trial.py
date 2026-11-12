"""Run and grade one v0.2 attempt. Trusted submissions live on the host."""
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from gri_bench.evaluate import strict_json
from gri_bench.native import verify_design
from gri_bench.runner import digest
from gri_bench.token_accounting import CompletionBudget, TokenUsageViolation

from .protocol import (
    CORRECTION, POLICY_FILE, SYSTEM, TASK_FILE, TOOLS, accept_design, atomic_json,
    check_calls, excluded_model, loads_strict,
)
from .sandbox import TrialSandbox
from .transport import request


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def route_label(value):
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:/+-]{1,150}", value):
        return value
    return None


def remaining_result(result, record, budget, cutoff, limits):
    return {
        **result,
        "model_calls_remaining": limits["max_calls"] - len(record["calls"]),
        "completion_tokens_remaining": budget.remaining,
        "agent_wall_seconds_remaining": max(0.0, cutoff - time.monotonic()),
    }


def save_submission(output, args, instance, record, cutoff, start):
    stamp, checksum = accept_design(output / "design.json", args, instance, cutoff)
    record["submissions"].append({"at_seconds": stamp - start, "design_sha256": checksum})
    return {"accepted": True, "submission_number": len(record["submissions"])}


def execute_tool(call, output, instance, record, sandbox, cutoff, start, limits, gate):
    name, arguments = call["name"], call["arguments"]
    try:
        if name == "submit_design":
            return save_submission(output, arguments, instance, record, cutoff, start)
        if name != "shell":
            raise ValueError("Unknown tool")
        args = loads_strict(arguments)
        if not isinstance(args, dict) or set(args) - {"command", "timeout_seconds"}:
            raise ValueError("Invalid shell arguments")
        timeout = args.get("timeout_seconds", 85.0)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("Expected numeric timeout_seconds")
        queued = time.monotonic()
        with gate:
            record["timing"]["sandbox_queue_seconds"] += time.monotonic() - queued
            result = sandbox.run_shell(args["command"], float(timeout), cutoff, limits)
        record["shell_calls"].append({k: v for k, v in result.items() if k != "output"})
        return result
    except (ValueError, KeyError, TypeError, OverflowError, UnicodeError, TimeoutError) as error:
        return {"accepted": False, "error": str(error)[:500]}


def run_agent(output, instance, record, sandbox, cutoff, start, policy, gate):
    limits = policy["budget"]
    budget = CompletionBudget(total=limits["completion_total"], per_call=limits["completion_per_call"])
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": TASK_FILE.read_text() + "\nYOUR INSTANCE:\n" + json.dumps(instance)},
    ]
    correction_used = False
    api_errors = 0
    try:
        for index in range(limits["max_calls"]):
            remaining = cutoff - time.monotonic()
            if remaining <= 0.1:
                return "wall_limit"
            if budget.remaining == 0:
                return "completion_limit"
            call = {"index": index, "started_seconds": time.monotonic() - start}
            record["calls"].append(call)
            payload = {
                "model": record["requested_model"], "messages": messages, "tools": TOOLS,
                "max_tokens": budget.reserve(index), **policy["model_request"],
            }
            sent = time.monotonic()
            response = request(payload, cutoff - sent)
            call.update(http_status=response.status, api_seconds=time.monotonic() - sent)
            record["timing"]["api_seconds"] += call["api_seconds"]
            response_file = output / f"response-{index:02d}.bin"
            response_file.write_bytes(response.body)
            call["response_sha256"] = digest(response_file)
            usage = None
            failure = response.error
            if failure == "http_error" and b"reasoning" in response.body.lower() and b"empty" in response.body.lower():
                failure = "http_error_reasoning_only_at_output_limit"
            if failure is None:
                try:
                    data = loads_strict(response.body)
                    usage = data.get("usage")
                    choice = data["choices"][0]
                    message = choice["message"]
                    truncated = choice.get("finish_reason") in ("length", "max_tokens")
                    calls = [] if truncated else check_calls(message)
                    call.update(
                        returned_model=route_label(data.get("model")),
                        finish_reason=route_label(choice.get("finish_reason")),
                        tool_call_count=len(calls),
                    )
                    details = usage.get("completion_tokens_details") if isinstance(usage, dict) else None
                    if isinstance(details, dict) and type(details.get("reasoning_tokens")) is int:
                        call["reasoning_tokens"] = details["reasoning_tokens"]
                except (ValueError, AttributeError, KeyError, TypeError, IndexError):
                    failure = "malformed_response"
            try:
                budget.settle(usage, failed=failure is not None, http_status=response.status)
            except TokenUsageViolation:
                record["resource_violations"].append("reported_completion_exceeds_call_limit")
                return "provider_token_violation"
            if failure is not None:
                call["error"] = failure
                api_errors += 1
                if api_errors >= limits["api_errors"]:
                    return "api_error_limit"
                continue
            if excluded_model(data.get("model")):
                record["resource_violations"].append("excluded_returned_model")
                return "excluded_returned_model"
            if time.monotonic() >= cutoff:
                call["after_cutoff"] = True
                return "wall_limit"
            if not truncated:
                messages.append(message)
            if not calls:
                if record["submissions"]:
                    return "truncated_after_submission" if truncated else "final_response"
                if correction_used:
                    return "truncated_without_submission" if truncated else "no_tool_after_correction"
                correction_used = True
                call["correction_sent"] = True
                messages.append({"role": "user", "content": CORRECTION})
                continue
            for tool in calls:
                if time.monotonic() >= cutoff:
                    return "wall_limit"
                result = execute_tool(tool["function"], output, instance, record, sandbox, cutoff, start, limits, gate)
                messages.append({
                    "role": "tool", "tool_call_id": tool["id"],
                    "content": json.dumps(remaining_result(result, record, budget, cutoff, limits), allow_nan=False),
                })
        return "call_limit"
    finally:
        if budget.pending is not None:
            budget.settle(failed=True)
        record["token_accounting"] = budget.entries
        record["charged_completion_tokens"] = budget.charged
        atomic_json(output / "transcript.json", messages)


def run_baseline(output, instance, record, sandbox, cutoff, start, policy, gate):
    with gate:
        result = sandbox.run_shell(
            "python /work/baseline_worker.py --mode " + record["method"],
            85.0, cutoff, policy["budget"],
        )
    record["shell_calls"].append({k: v for k, v in result.items() if k != "output"})
    path = sandbox.output / "tool-00.txt"
    candidates = []
    if path.exists():
        for line in path.read_bytes().splitlines():
            try:
                value = loads_strict(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(value, dict) and value.get("kind") in ("candidate", "complete"):
                candidates.append(value)
    if candidates:
        record["baseline_training"] = candidates[-1]
        save_submission(output, json.dumps(candidates[-1]["design"]), instance, record, cutoff, start)
    return "baseline_finished" if result.get("exit_code") == 0 else "baseline_cutoff"


def run_trial(output, instance, method, model, context, image, provenance, gate=None):
    policy = strict_json(POLICY_FILE)
    limits = policy["budget"]
    if method not in ("agent", "constant", "responsive"):
        raise ValueError("Unknown trial method")
    if method == "agent" and (route_label(model) is None or excluded_model(model)):
        raise ValueError("Invalid or excluded model route")
    gate = gate if gate is not None else nullcontext()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    work = output / "sandbox"
    work.mkdir()
    began = time.monotonic()
    record = {
        "trial_id": output.name, "case": instance["id"], "split": instance["split"], "method": method,
        "requested_model": model, "started_utc": utc_now(), "status": "running", "provenance": provenance,
        "calls": [], "shell_calls": [], "submissions": [], "resource_violations": [],
        "timing": {"api_seconds": 0.0, "sandbox_queue_seconds": 0.0},
    }
    atomic_json(output / "metadata.json", record)
    sandbox = None
    start = None
    try:
        with gate:
            sandbox = TrialSandbox(work, instance, context, image)
            if method != "agent":
                sandbox.put_file("/work/baseline_search.py", Path(__file__).with_name("search.py").read_bytes())
                sandbox.put_file("/work/baseline_worker.py", Path(__file__).with_name("baseline_worker.py").read_bytes())
                sandbox.unpause()
                sandbox.start_cpu = sandbox.cpu_raw()
                sandbox.pause()
        start = time.monotonic()
        record["timing"]["setup_seconds"] = start - began
        cutoff = start + limits["agent_wall_seconds"]
        run = run_agent if method == "agent" else run_baseline
        record["stop_reason"] = run(output, instance, record, sandbox, cutoff, start, policy, gate)
        record["status"] = "submitted" if record["submissions"] else "submission_failure"
    except Exception as error:
        record.update(status="infrastructure_error", error_type=type(error).__name__)
        (output / "infrastructure-error.txt").write_text(str(error))
    finally:
        end = time.monotonic()
        if start is not None:
            record["timing"]["active_seconds"] = min(end - start, limits["agent_wall_seconds"])
            record["timing"]["after_cutoff_seconds"] = max(0.0, end - start - limits["agent_wall_seconds"])
        if sandbox is not None:
            record["cpu_seconds"] = sandbox.last_cpu
            record["timing"]["tool_seconds"] = sandbox.tool_wall
            if sandbox.last_cpu > limits["cpu_seconds"]:
                record["resource_violations"].append("cpu")
            if sandbox.tool_wall > limits["tool_wall_seconds"]:
                record["resource_violations"].append("tool_wall")
            with gate:
                snapshot_start = time.monotonic()
                try:
                    if method == "agent":
                        files = sandbox.collect()
                        record["auxiliary_files"] = {name: files.get(name) for name in ("search.py", "rationale.md")}
                except Exception as error:
                    record["auxiliary_error_type"] = type(error).__name__
                record["timing"]["auxiliary_snapshot_seconds"] = time.monotonic() - snapshot_start
                cleanup = time.monotonic()
                try:
                    sandbox.close()
                except Exception as error:
                    record["cleanup_error_type"] = type(error).__name__
                record["timing"]["cleanup_seconds"] = time.monotonic() - cleanup
        record["timing"]["total_seconds"] = time.monotonic() - began
        record["finished_utc"] = utc_now()
        atomic_json(output / "metadata.json", record)
    return record


def grade_trial(output, instance, seeds):
    output = Path(output)
    meta = strict_json(output / "metadata.json")
    if meta["status"] == "running":
        raise ValueError("Trial has not finalized")
    path = output / "score.json"
    if path.exists():
        raise FileExistsError(path)
    score = {"status": meta["status"], "format_valid": False, "feasible": False, "safe_tir": 0.0}
    if meta["submissions"]:
        design_file = output / "design.json"
        if digest(design_file) != meta["submissions"][-1]["design_sha256"]:
            raise ValueError("Submission hash does not match the final receipt")
        score["format_valid"] = True
        if meta["resource_violations"]:
            score.update(status="resource_violation", reason=meta["resource_violations"])
        else:
            try:
                design = strict_json(design_file)
                score = verify_design(instance, design, seeds)
                failed = sum(
                    m["tbr70"] > 4.0 or m["tbr54"] > 1.0 or m["minimum"] < 40.0
                    for m in (r["metrics"] for r in score["rows"])
                )
                score.update(status="verified" if score["feasible"] else "safety_failure",
                             failed_trajectories=failed,
                             violation_fraction=failed / score["trajectories"])
            except (ValueError, RuntimeError, FloatingPointError) as error:
                score.update(status="simulation_failure", reason=type(error).__name__)
    elif meta["resource_violations"]:
        score.update(status="resource_violation", reason=meta["resource_violations"])
    atomic_json(path, score)
    return score
