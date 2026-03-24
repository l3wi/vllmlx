"""Reusable helpers for the external vllmlx e2e runner."""

from __future__ import annotations

import os
import pty
import selectors
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import psutil
import toml

from vllmlx.config import Config, get_state_dir
from vllmlx.daemon.launchd import LABEL
from vllmlx.models.aliases import resolve_alias


@dataclass
class CommandResult:
    """Completed CLI command result."""

    args: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


@dataclass
class WorkerSnapshot:
    """Observed backend worker process."""

    pid: int
    argv: list[str]
    env: dict[str, str]
    model: str | None
    port: int | None


@dataclass
class ScenarioResult:
    """Serializable scenario result."""

    name: str
    status: str
    duration_s: float
    details: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None


class E2EError(RuntimeError):
    """Scenario assertion failure."""


class ManagedProcess:
    """Background subprocess tracked by the harness."""

    def __init__(
        self,
        name: str,
        process: subprocess.Popen[str],
        stdout_path: Path,
        stderr_path: Path,
    ) -> None:
        self.name = name
        self.process = process
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    @property
    def pid(self) -> int:
        return self.process.pid

    def is_running(self) -> bool:
        return self.process.poll() is None

    def terminate(self, timeout: float = 15.0) -> None:
        if not self.is_running():
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5.0)


class PtySession:
    """Minimal PTY wrapper for `vllmlx run`."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        master_fd: int,
        stdout_path: Path,
    ) -> None:
        self.process = process
        self.master_fd = master_fd
        self.stdout_path = stdout_path
        self._buffer = ""
        self._selector = selectors.DefaultSelector()
        self._selector.register(master_fd, selectors.EVENT_READ)

    @property
    def pid(self) -> int:
        return self.process.pid

    def send_line(self, value: str) -> None:
        os.write(self.master_fd, value.encode("utf-8") + b"\n")

    def read_until(self, *patterns: str, timeout: float = 30.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for pattern in patterns:
                if pattern in self._buffer:
                    return self._buffer

            remaining = max(0.1, deadline - time.monotonic())
            events = self._selector.select(timeout=min(0.5, remaining))
            if not events:
                continue

            try:
                chunk = os.read(self.master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            decoded = chunk.decode("utf-8", errors="replace")
            self._buffer += decoded
            self.stdout_path.write_text(self._buffer, encoding="utf-8")

        raise E2EError(f"Timed out waiting for PTY output containing one of: {patterns}")

    def close(self) -> None:
        try:
            self.process.terminate()
            self.process.wait(timeout=5.0)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        try:
            self._selector.unregister(self.master_fd)
        except Exception:
            pass
        try:
            os.close(self.master_fd)
        except Exception:
            pass


class ScenarioHarness:
    """Fresh isolated environment for one e2e scenario."""

    def __init__(
        self,
        *,
        repo_root: Path,
        artifacts_root: Path,
        name: str,
        primary_model: str,
        secondary_model: str,
        download_model: str,
        allow_launchd: bool,
    ) -> None:
        self.repo_root = repo_root
        self.name = name
        self.primary_model = resolve_alias(primary_model)
        self.secondary_model = resolve_alias(secondary_model)
        self.download_model = resolve_alias(download_model)
        self.allow_launchd = allow_launchd
        self.started_processes: list[ManagedProcess] = []
        self.sessions: list[PtySession] = []
        self.http_timeout = 30.0

        self.artifacts_dir = artifacts_root / name
        self.home_dir = self.artifacts_dir / "home"
        self.state_dir = self.artifacts_dir / "state"
        self.launchd_dir = self.artifacts_dir / "launchd"
        self.runtime_label = f"dev.vllmlx.e2e.{name}.{os.getpid()}"
        self.api_port = self._free_port()
        self.backend_port = self._free_port(start=self.api_port + 1)

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.launchd_dir.mkdir(parents=True, exist_ok=True)

        python_path = os.pathsep.join(
            [
                str(self.repo_root / "src"),
                str(self.repo_root),
                os.environ.get("PYTHONPATH", ""),
            ]
        ).rstrip(os.pathsep)

        self.env = os.environ.copy()
        self.env.update(
            {
                "HOME": str(self.home_dir),
                "PYTHONPATH": python_path,
                "VLLMLX_HOME": str(self.home_dir),
                "VLLMLX_STATE_DIR": str(self.state_dir),
                "VLLMLX_LAUNCHD_LABEL": self.runtime_label,
                "VLLMLX_LAUNCHD_DIR": str(self.launchd_dir),
            }
        )
        self.api_url = f"http://127.0.0.1:{self.api_port}"

    def cleanup(self) -> None:
        for session in reversed(self.sessions):
            session.close()
        self.sessions.clear()

        for process in reversed(self.started_processes):
            try:
                process.terminate()
            except Exception:
                continue
        self.started_processes.clear()

        if self.runtime_label != LABEL:
            try:
                self.run_cli(["daemon", "stop"], check=False, timeout=20.0)
            except Exception:
                pass

        plist_path = self.launchd_dir / f"{self.runtime_label}.plist"
        if plist_path.exists():
            try:
                plist_path.unlink()
            except OSError:
                pass

        self._kill_stray_workers()

    def base_config(self) -> Config:
        return Config(
            daemon={
                "host": "127.0.0.1",
                "port": self.api_port,
                "idle_timeout": 5,
                "max_loaded_models": 3,
                "min_available_memory_gb": 0.0,
                "health_ttl_seconds": 0.0,
            },
            backend={
                "host": "127.0.0.1",
                "port": self.backend_port,
                "startup_timeout": 600,
                "stop_timeout": 30,
            },
        )

    def write_config(self, config: Config) -> Path:
        path = self.state_dir / "config.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            toml.dump(config.model_dump(), handle)
        return path

    def run_cli(
        self,
        args: list[str],
        *,
        timeout: float = 60.0,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        cmd = [sys.executable, "-m", "vllmlx", *args]
        started = time.monotonic()
        completed = subprocess.run(
            cmd,
            cwd=self.repo_root,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = CommandResult(
            args=cmd,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_s=time.monotonic() - started,
        )
        if check and result.exit_code != 0:
            raise E2EError(
                "Command failed: "
                f"{' '.join(cmd)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def start_process(self, args: list[str], *, name: str) -> ManagedProcess:
        stdout_path = self.artifacts_dir / f"{name}.stdout.log"
        stderr_path = self.artifacts_dir / f"{name}.stderr.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "vllmlx", *args],
            cwd=self.repo_root,
            env=self.env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        managed = ManagedProcess(
            name=name,
            process=process,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        self.started_processes.append(managed)
        return managed

    def start_pty(self, args: list[str], *, name: str) -> PtySession:
        stdout_path = self.artifacts_dir / f"{name}.pty.log"
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "vllmlx", *args],
            cwd=self.repo_root,
            env=self.env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
        )
        os.close(slave_fd)
        session = PtySession(process=process, master_fd=master_fd, stdout_path=stdout_path)
        self.sessions.append(session)
        return session

    def wait_for_health(self, *, timeout: float = 60.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"{self.api_url}/health", timeout=2.0)
                if response.status_code == 200:
                    return response.json()
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise E2EError(f"Timed out waiting for daemon health at {self.api_url}")

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return httpx.request(method, f"{self.api_url}{path}", timeout=self.http_timeout, **kwargs)

    def stream_chat(self, payload: dict[str, Any]) -> str:
        with httpx.stream(
            "POST",
            f"{self.api_url}/v1/chat/completions",
            json=payload,
            timeout=None,
        ) as response:
            if response.status_code != 200:
                raise E2EError(
                    f"Streaming chat failed with {response.status_code}: {response.read().decode()}"
                )
            body = ""
            for line in response.iter_lines():
                if line:
                    body += line + "\n"
            return body

    def is_model_cached(self, model: str) -> bool:
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(resolve_alias(model), local_files_only=True)
            return True
        except Exception:
            return False

    def require_cached_models(self, models: list[str]) -> None:
        missing = [resolve_alias(model) for model in models if not self.is_model_cached(model)]
        if missing:
            raise E2EError("Required cached model(s) are missing: " + ", ".join(sorted(missing)))

    def worker_snapshots(self) -> list[WorkerSnapshot]:
        snapshots: list[WorkerSnapshot] = []
        for process in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = process.info.get("cmdline") or []
                if "vllmlx.backend.worker" not in " ".join(cmdline):
                    continue
                env = process.environ()
            except (psutil.Error, OSError):
                continue
            if env.get("VLLMLX_STATE_DIR") != str(self.state_dir):
                continue
            snapshots.append(
                WorkerSnapshot(
                    pid=process.pid,
                    argv=cmdline,
                    env=env,
                    model=self._extract_arg(cmdline, "--model"),
                    port=self._extract_int_arg(cmdline, "--port"),
                )
            )
        return sorted(snapshots, key=lambda item: item.pid)

    def default_state_dir(self) -> Path:
        env = os.environ.copy()
        for name in ("VLLMLX_HOME", "VLLMLX_STATE_DIR"):
            env.pop(name, None)
        return get_state_dir()

    @staticmethod
    def chat_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        return ""

    def ensure_isolated_launchd(self) -> None:
        if self.runtime_label == LABEL:
            raise E2EError("Refusing to run launchd scenario without an isolated label")

    def launchd_plist_path(self) -> Path:
        return self.launchd_dir / f"{self.runtime_label}.plist"

    def _kill_stray_workers(self) -> None:
        for snapshot in self.worker_snapshots():
            try:
                process = psutil.Process(snapshot.pid)
                process.terminate()
                process.wait(timeout=5.0)
            except Exception:
                try:
                    psutil.Process(snapshot.pid).kill()
                except Exception:
                    continue

    @staticmethod
    def _extract_arg(argv: list[str], name: str) -> str | None:
        if name not in argv:
            return None
        index = argv.index(name)
        if index + 1 >= len(argv):
            return None
        return argv[index + 1]

    @staticmethod
    def _extract_int_arg(argv: list[str], name: str) -> int | None:
        value = ScenarioHarness._extract_arg(argv, name)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _free_port(*, start: int = 8000) -> int:
        port = start
        while port < 65535:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    port += 1
        raise RuntimeError("Unable to allocate a free TCP port")
