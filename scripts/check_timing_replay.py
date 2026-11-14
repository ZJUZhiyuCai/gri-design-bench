"""Verify a Harbor release-timing submission and rerun its script in a fresh container."""

import argparse
import asyncio
from hashlib import sha256
import json
from math import isclose
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from harbor.agents.base import BaseAgent
from harbor.models.task.task import Task
from harbor.models.trial.config import TrialConfig
from harbor.models.trial.result import TrialResult
from harbor.publisher.packager import Packager
from harbor.trial.trial import Trial


OUTPUT = Path("/app/output")
ARTIFACTS = Path("artifacts/app/output")
SCRIPT_LIMIT = 1024 * 1024
RESULT_LIMIT = 16 * 1024 * 1024
REPLAY_TOLERANCE = 1e-10
CHECKS = {
    "test_complete_scenario_matrix",
    "test_responsive_schedule",
    "test_daily_dose_and_timing",
    "test_replayed_glucose_outcomes",
    "test_paired_effects",
}


class ReplayAgent(BaseAgent):
    """Upload only the captured script and execute it as the task's agent."""

    def __init__(self, *, script, **kwargs):
        super().__init__(**kwargs)
        self.script = Path(script)

    @staticmethod
    def name():
        return "gri-release-timing-replay"

    def version(self):
        return "1.0"

    async def setup(self, environment):
        check = await environment.exec(
            "test -d /app/output && test -z \"$(ls -A /app/output)\" "
            "&& test ! -e /solution/solve.py && test ! -e /tests/reference.json",
            cwd="/app", timeout_sec=10,
        )
        if check.return_code:
            raise RuntimeError("Replay container is missing its clean output or isolation setup")

    async def run(self, instruction, environment, context):
        path = str(OUTPUT / "reproduce.py")
        await environment.upload_file(self.script, path)
        result = await environment.exec(f"python -I {path}", cwd="/app")
        self.logs_dir.joinpath("replay-stdout.txt").write_text(result.stdout or "")
        self.logs_dir.joinpath("replay-stderr.txt").write_text(result.stderr or "")
        context.metadata = {"script_exit_code": result.return_code}


def read_artifact(trial, name, limit):
    path = trial / ARTIFACTS / name
    if path.parent.resolve() != path.parent:
        return None, f"Artifact directory for {name} contains a symlink"
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
        return None, f"{name} must be a nonempty regular file of at most {limit} bytes"
    return path.read_bytes(), None


def record_summary(trial, record):
    if record.finished_at is None or record.config.environment.type.value != "docker":
        raise ValueError(f"Expected a finished local Docker trial at {trial}")
    reward = record.verifier_result.rewards.get("reward") if record.verifier_result else None
    checks = {}
    report = trial / "verifier/ctrf.json"
    if report.is_file():
        tests = json.loads(report.read_text())["results"]["tests"]
        checks = {test["name"].rsplit("::", 1)[-1]: test["status"] for test in tests}
        if len(tests) != len(CHECKS) or checks.keys() != CHECKS:
            raise ValueError(f"Unexpected scientific check list at {report}")
        if (reward == 1.0) != all(status == "passed" for status in checks.values()):
            raise ValueError(f"Harbor reward disagrees with {report}")
    elif reward is not None:
        raise ValueError(f"Missing scientific check report at {report}")
    execution = record.agent_execution
    return {
        "trial": str(trial),
        "reward": reward,
        "checks": checks,
        "scientific_pass": (
            record.reward_valid
            and record.verifier_environment_mode == "separate"
            and reward == 1.0
        ),
        "exception": record.exception_info.model_dump(mode="json") if record.exception_info else None,
        "execution_seconds": (
            (execution.finished_at - execution.started_at).total_seconds()
            if execution and execution.finished_at else None
        ),
    }


def numerically_equal(left, right):
    if type(left) in (int, float) and type(right) in (int, float):
        return isclose(left, right, rel_tol=0, abs_tol=REPLAY_TOLERANCE)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(numerically_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(numerically_equal(a, b) for a, b in zip(left, right))
    return left == right


def keyed_results(contents):
    data = json.loads(contents)
    return {
        "rows": {
            (row["patient"], row["seed"], row["variant"], row["arm"]): row
            for row in data["rows"]
        },
        "effects": data["mean_responsive_minus_control"],
    }


def status_of(summary):
    initial, replay = summary["initial"], summary["replay"]
    if initial["exception"] or initial["reward"] is None:
        return "initial_incomplete"
    if initial["script_error"]:
        return "invalid_script"
    if summary["script_sha256"] is None:
        return "missing_script" if initial["scientific_pass"] else "initial_scientific_failure"
    if replay["exception"] or replay["reward"] is None:
        return "replay_incomplete"
    if replay["script_exit_code"] != 0:
        return "script_execution_failed"
    if not initial["scientific_pass"]:
        return "initial_scientific_failure"
    if not replay["scientific_pass"]:
        return "replay_scientific_failure"
    return "accepted" if summary["numeric_match"] else "replay_output_mismatch"


async def run_check(task_dir, initial_dir, out):
    task = Task(task_dir)
    if (task.config.environment.network_mode != "no-network"
            or task.config.agent.network_mode not in (None, "no-network")
            or task.config.verifier.environment_mode != "separate"
            or task.config.verifier.environment is None
            or task.config.verifier.environment.network_mode != "no-network"
            or task.config.verifier.network_mode not in (None, "no-network")
            or task.config.environment.mcp_servers):
        raise ValueError("Replay requires an offline task with a separate offline verifier")
    if any(str(OUTPUT / name) not in task.config.artifacts for name in ("results.json", "reproduce.py")):
        raise ValueError("The timing task must collect results.json and reproduce.py")

    initial_record = TrialResult.model_validate_json((initial_dir / "result.json").read_text())
    task_digest = "sha256:" + Packager.compute_content_hash(task_dir)[0]
    locked_digest = json.loads((initial_dir / "lock.json").read_text())["task"]["digest"]
    if locked_digest != task_digest:
        raise ValueError("The supplied task differs from the original Harbor trial's task")
    initial = record_summary(initial_dir, initial_record)
    initial_json, initial["results_error"] = read_artifact(initial_dir, "results.json", RESULT_LIMIT)
    script, initial["script_error"] = read_artifact(initial_dir, "reproduce.py", SCRIPT_LIMIT)
    initial["results_sha256"] = sha256(initial_json).hexdigest() if initial_json else None
    if initial["scientific_pass"] and not initial_json:
        raise ValueError("The verified results.json artifact is missing")
    if out.is_relative_to(task_dir) or out.is_relative_to(initial_dir):
        raise ValueError("Use a fresh output directory outside the source task and trial")
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    summary = {
        "task_digest": task_digest,
        "script_sha256": sha256(script).hexdigest() if script else None,
        "initial": initial,
        "replay": None,
        "byte_match": False,
        "numeric_match": False,
        "numeric_absolute_tolerance": REPLAY_TOLERANCE,
    }
    if script is not None:
        snapshot = out / "reproduce.py"
        with snapshot.open("xb") as stream:
            stream.write(script)
        snapshot.chmod(0o600)
        trial_name = f"timing-replay__{uuid4().hex[:12]}"
        config = TrialConfig.model_validate({
            "task": {"path": task_dir},
            "trials_dir": out,
            "trial_name": trial_name,
            "environment": {"type": "docker"},
            "agent": {
                "import_path": f"{ReplayAgent.__module__}:ReplayAgent",
                "kwargs": {"script": str(snapshot)},
            },
        })
        replay_record = await (await Trial.create(config)).run()
        replay_dir = out / trial_name
        replay_digest = json.loads((replay_dir / "lock.json").read_text())["task"]["digest"]
        if replay_digest != task_digest:
            raise ValueError("The task digest changed before replay")
        replay = record_summary(replay_dir, replay_record)
        replay["script_exit_code"] = (
            (replay_record.agent_result.metadata or {}).get("script_exit_code")
            if replay_record.agent_result else None
        )
        replay_json, replay["results_error"] = read_artifact(replay_dir, "results.json", RESULT_LIMIT)
        replay["results_sha256"] = sha256(replay_json).hexdigest() if replay_json else None
        if replay["scientific_pass"] and not replay_json:
            raise ValueError("The verified replay results.json artifact is missing")
        summary["replay"] = replay
        if initial_json is not None and replay_json is not None:
            summary["byte_match"] = initial_json == replay_json
            summary["numeric_match"] = summary["byte_match"]
            if not summary["byte_match"] and initial["scientific_pass"] and replay["scientific_pass"]:
                summary["numeric_match"] = numerically_equal(
                    keyed_results(initial_json), keyed_results(replay_json)
                )
    summary["status"] = status_of(summary)
    summary["accepted"] = summary["status"] == "accepted"
    with (out / "comparison.json").open("x") as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, type=Path, help="Original generated Harbor task.")
    parser.add_argument("--trial", required=True, type=Path, help="Original Harbor trial directory.")
    parser.add_argument("--output", required=True, type=Path, help="Fresh directory for the replay and comparison.")
    args = parser.parse_args()
    os.environ["HARBOR_TELEMETRY"] = "0"
    try:
        result = asyncio.run(run_check(args.task.resolve(), args.trial.resolve(), args.output.resolve()))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"{error}\n")
    print(f"{result['status']}: {args.output / 'comparison.json'}")
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
