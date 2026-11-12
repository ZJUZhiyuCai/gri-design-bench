"""Check real provider tool and history handling without using benchmark instances."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from gri_bench.evaluate import strict_json
from gri_bench.v02.protocol import POLICY_FILE, TOOLS, atomic_json, check_calls, excluded_model, loads_strict
from gri_bench.v02.transport import request


def probe(route):
    policy = strict_json(POLICY_FILE)
    messages = [
        {"role": "system", "content": "This is a mock tool protocol check. No command will run."},
        {"role": "user", "content": "Call shell once with command 'printf GRI_V02_OK'. "
         "After the mock tool response, call submit_design in constant mode with theta_c 0 and theta_L 1."},
    ]
    result = {"requested_model": route, "calls": [], "passed": False}
    for expected in ("shell", "submit_design"):
        start = time.monotonic()
        response = request({
            "model": route, "messages": messages, "tools": TOOLS, "max_tokens": 6000,
            **policy["model_request"],
        }, 90)
        call_record = {"http_status": response.status, "elapsed_seconds": time.monotonic() - start}
        result["calls"].append(call_record)
        try:
            if response.error:
                raise ValueError(response.error)
            data = loads_strict(response.body)
            choice = data["choices"][0]
            call_record.update(
                returned_model=data.get("model"), finish_reason=choice.get("finish_reason"), usage=data.get("usage"),
            )
            message = choice["message"]
            calls = check_calls(message)
            if excluded_model(data.get("model")) or len(calls) != 1 or calls[0]["function"]["name"] != expected:
                raise ValueError("Unexpected model or tool call")
            args = loads_strict(calls[0]["function"]["arguments"])
            call_record["mock_arguments"] = args
            if expected == "shell":
                if "GRI_V02_OK" not in args["command"]:
                    raise ValueError("Unexpected shell arguments")
                messages.extend([message, {
                    "role": "tool", "tool_call_id": calls[0]["id"],
                    "content": json.dumps({"output": "GRI_V02_OK\n" + "candidate stats\n" * 200, "exit_code": 0}),
                }])
            elif args != {"mode": "constant", "parameters": {"theta_c": 0, "theta_L": 1}}:
                raise ValueError("Unexpected design arguments")
        except (ValueError, KeyError, TypeError, IndexError) as error:
            call_record["error"] = str(error)
            return result
    result["passed"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(excluded_model(route) for route in args.routes):
        raise ValueError("Excluded model family")
    with ThreadPoolExecutor(max_workers=len(args.routes)) as pool:
        records = list(pool.map(probe, args.routes))
    atomic_json(args.output, records)
    for record in records:
        print(record["requested_model"], record["passed"],
              [(call["http_status"], call.get("error")) for call in record["calls"]], flush=True)


if __name__ == "__main__":
    main()
