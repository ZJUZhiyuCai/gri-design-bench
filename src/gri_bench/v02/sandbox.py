"""Reuse the isolated image and cgroup accounting with a v0.2 shell cutoff."""
import math
import subprocess
import time

from gri_bench.runner import Sandbox


class TrialSandbox(Sandbox):
    def run_shell(self, command, timeout, cutoff, limits):
        if self.exhausted:
            return {"error": "shell_budget_exhausted"}
        if not isinstance(command, str) or not command or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Expected a shell command and positive finite timeout")
        start = time.monotonic()
        tool_deadline = min(cutoff, start + limits["tool_wall_seconds"] - self.tool_wall) - 0.25
        if tool_deadline <= start:
            self.exhausted = True
            return {"error": "shell_budget_exhausted"}
        call_deadline = min(tool_deadline, start + timeout, start + 85.0)
        log = self.output / f"tool-{len(list(self.output.glob('tool-*.txt'))):02d}.txt"
        reason = None
        proc = None
        with log.open("wb") as stream:
            try:
                self.unpause()
                available = call_deadline - time.monotonic()
                if available <= 0:
                    reason = "wall_cutoff"
                else:
                    proc = subprocess.Popen(
                        ["docker", "--context", self.context, "exec", self.name,
                         "timeout", "-k", "0.2", f"{available:.3f}", "bash", "-lc", command],
                        stdout=stream, stderr=subprocess.STDOUT,
                    )
                    while True:
                        self.last_cpu = max(0.0, self.cpu_raw() - self.start_cpu)
                        if self.last_cpu >= limits["cpu_seconds"] - 0.5:
                            reason = "cpu_cutoff"
                            self.exhausted = True
                        elif time.monotonic() >= call_deadline:
                            reason = "wall_cutoff"
                            self.exhausted = call_deadline == tool_deadline
                        elif log.stat().st_size > 2_000_000:
                            reason = "tool_output_limit"
                            self.exhausted = True
                        if reason or proc.poll() is not None:
                            break
                        time.sleep(0.08)
            finally:
                try:
                    self.pause()
                finally:
                    if proc is not None and proc.poll() is None:
                        proc.kill()
                        proc.wait()
        self.tool_wall += time.monotonic() - start
        if self.tool_wall >= limits["tool_wall_seconds"]:
            self.exhausted = True
        if proc is not None and proc.returncode == 124 and reason is None:
            reason = "command_timeout"
        with log.open("rb") as stream:
            output = stream.read(12_000).decode(errors="replace")
        return {
            "exit_code": proc.returncode if proc is not None else None,
            "output": output, "stop_reason": reason,
            "cpu_seconds": self.last_cpu,
            "cpu_remaining": max(0.0, limits["cpu_seconds"] - self.last_cpu),
            "tool_wall_seconds": self.tool_wall,
            "shell_budget_exhausted": self.exhausted,
        }
