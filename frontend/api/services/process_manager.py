"""
Process manager for run_graph.py invocations.

Architecture note (MVP bridge):
    The 'Start Run' button invokes run_graph.py via 'docker exec' into the
    dev container. The dev container holds the full tool stack (claude CLI,
    API keys, appuser setup) that run_graph.py requires. This is an
    intentional MVP shortcut for local use and is NOT a long-term design.

    To override the command, set RUN_COMMAND as a full shell string, e.g.:
        RUN_COMMAND="python /workspace/run_graph.py"   # if running natively
    To change only the target container name:
        RUN_CONTAINER=my-factory-dev

Configuration (env vars):
    RUN_CONTAINER  Target Docker container name  (default: ai-factory-dev)
    RUN_COMMAND    Full command string override   (default: docker exec -i {RUN_CONTAINER} python /workspace/run_graph.py)
"""
import os
import shlex
import subprocess
import threading
from collections import deque
from enum import Enum
from typing import Optional


class RunState(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class ProcessManager:
    _instance: Optional["ProcessManager"] = None

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._stdout_lines: deque = deque(maxlen=500)
        self._lock = threading.Lock()
        self._state = RunState.NOT_STARTED

    @classmethod
    def get(cls) -> "ProcessManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _build_command(self) -> list:
        run_container = os.environ.get("RUN_CONTAINER", "ai-factory-dev")
        default_cmd = f"docker exec -i {run_container} python /workspace/run_graph.py"
        run_command = os.environ.get("RUN_COMMAND", default_cmd)
        return shlex.split(run_command)

    def start(self) -> int:
        """
        Start run_graph.py as a background subprocess.
        Returns the process PID.
        Raises RuntimeError if a run is already in progress.
        """
        with self._lock:
            # Reconcile: if the previous process has already exited, allow restart
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("already running")

            command = self._build_command()
            project_root = os.environ.get("PROJECT_ROOT", "/workspace")
            self._stdout_lines.clear()

            try:
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=project_root,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError as exc:
                self._state = RunState.FAILED
                raise RuntimeError(
                    f"Command not found: {command[0]!r}. "
                    "Is the Docker CLI installed in the ui container?"
                ) from exc

            self._state = RunState.RUNNING
            reader = threading.Thread(target=self._drain_stdout, daemon=True)
            reader.start()
            return self._process.pid

    def _drain_stdout(self) -> None:
        """Background thread: drains stdout line-by-line until the process exits."""
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                self._stdout_lines.append(line.rstrip("\n"))
        finally:
            rc = process.wait()
            with self._lock:
                # Only update state if we're still tracking this same process
                if self._process is process:
                    self._state = RunState.FINISHED if rc == 0 else RunState.FAILED

    def status(self) -> dict:
        """Return a thread-safe snapshot of the current run state."""
        with self._lock:
            process = self._process
            state = self._state

            # Reconcile: if the process exited but _drain_stdout hasn't updated
            # the state yet (narrow race window), check poll() directly
            if state == RunState.RUNNING and process is not None:
                rc = process.poll()
                if rc is not None:
                    state = RunState.FINISHED if rc == 0 else RunState.FAILED
                    self._state = state

            pid = process.pid if process is not None else None
            returncode = (
                process.returncode
                if process is not None and process.poll() is not None
                else None
            )
            stdout_tail = "\n".join(list(self._stdout_lines)[-100:])

        return {
            "state": state.value,
            "running": state == RunState.RUNNING,
            "pid": pid,
            "returncode": returncode,
            "stdout_tail": stdout_tail,
        }
