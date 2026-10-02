"""Start, stop and inspect the bundled extensions as background services.

Each extension runs as its own process (OpenClacky is Ruby, the globe is a
Node/Vite app), detached into its own process group so a single ``stop``
tears down the whole tree. Pid files and logs live in
``~/.openjarvis/extensions/``.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from openjarvis.unified.model_bridge import ModelBridgeError, clacky_env
from openjarvis.unified.paths import extension_dir, state_dir

_IS_WINDOWS = sys.platform == "win32"


@dataclass
class Service:
    """One extension process."""

    name: str
    title: str
    port: int
    cwd: Path | None
    command: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    install: list[str] = field(default_factory=list)
    # Returns True when dependencies must be installed before starting.
    needs_install: Callable[[], bool] = lambda: False
    problem: str = ""  # Why it cannot run (empty when it can)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if _IS_WINDOWS:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
        )
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Supervisor:
    """Manage the OpenClacky and globe services for one OpenJarvis config."""

    def __init__(
        self,
        config: Any,
        *,
        which: Callable[[str], str | None] = shutil.which,
        environ: dict[str, str] | None = None,
    ) -> None:
        self._config = config
        self._which = which
        self._environ = dict(os.environ if environ is None else environ)
        self._state = state_dir()

    # ------------------------------------------------------------------
    # Service definitions
    # ------------------------------------------------------------------

    def services(self) -> list[Service]:
        ext = self._config.extensions
        out: list[Service] = []
        if ext.clacky.enabled:
            out.append(self._clacky(ext.clacky))
        if ext.globe.enabled:
            out.append(self._globe(ext.globe))
        return out

    def _clacky(self, cfg: Any) -> Service:
        svc = Service(
            "clacky", "OpenClacky agent", cfg.port, extension_dir("clacky", cfg.path)
        )
        if svc.cwd is None:
            svc.problem = "extensions/clacky is not present in this installation"
            return svc
        bundle = self._which("bundle")
        if self._which("ruby") is None or bundle is None:
            svc.problem = "Ruby >= 3.1 and Bundler are required (run the installer)"
            return svc
        try:
            svc.env = clacky_env(self._config, self._environ)
        except ModelBridgeError as exc:
            svc.problem = str(exc)
            return svc
        svc.install = [bundle, "install"]
        cwd = svc.cwd
        svc.needs_install = lambda: (
            subprocess.run(
                [bundle, "check"], cwd=cwd, capture_output=True, check=False
            ).returncode
            != 0
        )
        svc.command = [
            bundle,
            "exec",
            "ruby",
            "bin/clacky",
            "server",
            "--port",
            str(cfg.port),
            "--strict-port",
        ]
        return svc

    def _globe(self, cfg: Any) -> Service:
        svc = Service(
            "globe", "God's Eye View globe", cfg.port, extension_dir("globe", cfg.path)
        )
        if svc.cwd is None:
            svc.problem = "extensions/globe is not present in this installation"
            return svc
        npm = self._which("npm") or self._which("npm.cmd")
        if npm is None:
            svc.problem = "Node.js 24+ and npm are required (run the installer)"
            return svc
        # Let the OpenJarvis UI (Vite dev server or the API's static build)
        # embed the globe; the globe denies all other embedders.
        ui_ports = sorted({5173, int(getattr(self._config.server, "port", 8000))})
        svc.env = {
            "GLOBE_FRAME_ANCESTORS": " ".join(
                f"http://{host}:{port}"
                for port in ui_ports
                for host in ("127.0.0.1", "localhost")
            )
        }
        svc.install = [npm, "ci"]
        modules = svc.cwd / "node_modules"
        svc.needs_install = lambda: not modules.is_dir()
        svc.command = [
            npm,
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(cfg.port),
            "--strictPort",
        ]
        return svc

    def get(self, name: str) -> Service:
        for svc in self.services():
            if svc.name == name:
                return svc
        raise KeyError(f"Extension '{name}' is disabled or unknown")

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    def _pid_file(self, name: str) -> Path:
        return self._state / f"{name}.pid"

    def log_file(self, name: str) -> Path:
        return self._state / f"{name}.log"

    def _pid(self, name: str) -> int:
        try:
            return int(self._pid_file(name).read_text().strip())
        except (OSError, ValueError):
            return 0

    def running(self, svc: Service) -> bool:
        return _pid_alive(self._pid(svc.name)) and port_open(svc.port)

    def start(self, svc: Service, *, wait: float = 60.0) -> str:
        """Start *svc*; return a short human-readable outcome."""
        if svc.problem:
            return f"skipped: {svc.problem}"
        if self.running(svc):
            return f"already running at {svc.url}"
        if port_open(svc.port):
            return f"port {svc.port} is busy (another program uses it)"
        log = self.log_file(svc.name).open("ab")
        env = {**self._environ, **svc.env}
        if svc.needs_install():
            done = subprocess.run(
                svc.install, cwd=svc.cwd, env=env, stdout=log, stderr=log, check=False
            )
            if done.returncode != 0:
                return f"dependency install failed, see {self.log_file(svc.name)}"
        kwargs: dict[str, Any] = {}
        if _IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            svc.command,
            cwd=svc.cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **kwargs,
        )
        self._pid_file(svc.name).write_text(str(proc.pid))
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                self._pid_file(svc.name).unlink(missing_ok=True)
                return f"exited early, see {self.log_file(svc.name)}"
            if port_open(svc.port):
                return f"running at {svc.url}"
            time.sleep(0.5)
        return f"started but not answering yet, see {self.log_file(svc.name)}"

    def stop(self, name: str) -> bool:
        pid = self._pid(name)
        self._pid_file(name).unlink(missing_ok=True)
        if not _pid_alive(pid):
            return False
        if _IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True
            )
            return True
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return False
        for _ in range(20):
            if not _pid_alive(pid):
                break
            time.sleep(0.25)
        else:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return True

    def start_all(self) -> dict[str, str]:
        return {svc.name: self.start(svc) for svc in self.services()}

    def stop_all(self) -> dict[str, bool]:
        return {name: self.stop(name) for name in ("clacky", "globe")}

    def status(self) -> list[dict[str, Any]]:
        rows = []
        for svc in self.services():
            rows.append(
                {
                    "name": svc.name,
                    "title": svc.title,
                    "url": svc.url,
                    "running": self.running(svc),
                    "available": not svc.problem,
                    "problem": svc.problem,
                }
            )
        return rows
