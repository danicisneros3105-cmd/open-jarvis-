"""Tests for the bundled-extension supervisor."""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.unified import supervisor as sup_mod
from openjarvis.unified.supervisor import Supervisor, port_open


def _config(tmp_path: Path) -> JarvisConfig:
    cfg = JarvisConfig()
    cfg.intelligence.default_model = "qwen3:8b"
    clacky = tmp_path / "clacky"
    globe = tmp_path / "globe"
    clacky.mkdir()
    (globe / "node_modules").mkdir(parents=True)
    cfg.extensions.clacky.path = str(clacky)
    cfg.extensions.globe.path = str(globe)
    return cfg


def _which_all(name: str) -> str:
    return f"/usr/bin/{name}"


def test_services_resolve_commands_and_shared_model(tmp_path):
    sup = Supervisor(_config(tmp_path), which=_which_all, environ={})
    clacky, globe = sup.services()
    assert clacky.problem == "" and globe.problem == ""
    assert clacky.command[:4] == ["/usr/bin/bundle", "exec", "ruby", "bin/clacky"]
    assert "--strict-port" in clacky.command
    assert clacky.env["CLACKY_MODEL"] == "qwen3:8b"
    assert clacky.env["CLACKY_TELEMETRY"] == "0"
    assert globe.command[:3] == ["/usr/bin/npm", "run", "dev"]
    assert "http://127.0.0.1:5173" in globe.env["GLOBE_FRAME_ANCESTORS"]
    assert globe.needs_install() is False


def test_missing_tooling_or_model_is_reported_not_raised(tmp_path):
    cfg = _config(tmp_path)
    cfg.intelligence.default_model = ""
    sup = Supervisor(cfg, which=lambda name: None, environ={})
    rows = {row["name"]: row for row in sup.status()}
    assert "Ruby" in rows["clacky"]["problem"]
    assert "Node.js" in rows["globe"]["problem"]
    sup = Supervisor(cfg, which=_which_all, environ={})
    assert "default_model" in sup.get("clacky").problem


def test_disabled_and_absent_extensions(tmp_path):
    cfg = _config(tmp_path)
    cfg.extensions.globe.enabled = False
    cfg.extensions.clacky.path = str(tmp_path / "missing")
    sup = Supervisor(cfg, which=_which_all, environ={})
    assert [s.name for s in sup.services()] == ["clacky"]
    assert "not present" in sup.get("clacky").problem
    with pytest.raises(KeyError):
        sup.get("globe")
    assert sup.start(sup.get("clacky")).startswith("skipped")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_start_and_stop_a_real_process(tmp_path, monkeypatch):
    port = _free_port()
    cfg = _config(tmp_path)
    cfg.extensions.clacky.enabled = False
    cfg.extensions.globe.port = port
    sup = Supervisor(cfg, which=_which_all, environ={})
    svc = sup.get("globe")
    svc.command = [
        sys.executable,
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
    ]

    assert sup.start(svc, wait=20).startswith("running")
    assert sup.running(svc)
    assert "already running" in sup.start(svc)
    assert sup.stop("globe") is True
    for _ in range(40):
        if not port_open(port):
            break
        time.sleep(0.1)
    assert not port_open(port)
    assert sup.stop("globe") is False


def test_start_reports_busy_port_and_early_exit(tmp_path):
    cfg = _config(tmp_path)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        cfg.extensions.globe.port = busy.getsockname()[1]
        sup = Supervisor(cfg, which=_which_all, environ={})
        assert "busy" in sup.start(sup.get("globe"))

    cfg.extensions.globe.port = _free_port()
    sup = Supervisor(cfg, which=_which_all, environ={})
    svc = sup.get("globe")
    svc.command = [sys.executable, "-c", "raise SystemExit(3)"]
    assert "exited early" in sup.start(svc, wait=10)


def test_failed_dependency_install_is_reported(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    cfg.extensions.globe.port = _free_port()
    sup = Supervisor(cfg, which=_which_all, environ={})
    svc = sup.get("globe")
    svc.needs_install = lambda: True
    svc.install = [sys.executable, "-c", "raise SystemExit(1)"]
    assert "install failed" in sup.start(svc)


def test_pid_alive_handles_bad_pids():
    assert sup_mod._pid_alive(0) is False
