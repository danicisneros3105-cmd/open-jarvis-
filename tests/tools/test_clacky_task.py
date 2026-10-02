"""Tests for delegating tasks to OpenClacky."""

from __future__ import annotations

import json
import subprocess

from openjarvis.core.config import JarvisConfig
from openjarvis.tools.clacky_task import ClackyTaskTool, summarize_events


def _ndjson(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events) + "\n"


def _config(tmp_path) -> JarvisConfig:
    cfg = JarvisConfig()
    cfg.intelligence.default_model = "qwen3:8b"
    root = tmp_path / "clacky"
    (root / "bin").mkdir(parents=True, exist_ok=True)
    cfg.extensions.clacky.path = str(root)
    cfg.extensions.clacky.timeout_seconds = 42
    return cfg


def _which(name: str) -> str:
    return f"/usr/bin/{name}"


def test_summarize_events_keeps_last_message_tools_and_cost():
    out = _ndjson(
        {"type": "system", "message": "Agent started"},
        {"type": "assistant_message", "content": "Working on it"},
        {"type": "tool_call", "name": "terminal", "args": {}},
        {"type": "tool_call", "name": "write"},
        {"type": "assistant_message", "content": "Moved 3 files."},
        {"type": "done", "total_cost": 0.0123},
    )
    assert summarize_events("noise\n" + out + "{bad json") == (
        "Moved 3 files.",
        ["terminal", "write"],
        "",
        0.0123,
    )


def test_execute_runs_clacky_with_shared_model(tmp_path):
    calls = {}

    def runner(cmd, **kwargs):
        calls["cmd"], calls["kwargs"] = cmd, kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=_ndjson(
                {"type": "tool_call", "name": "browser"},
                {"type": "assistant_message", "content": "Done."},
                {"type": "done", "total_cost": 0.5},
            ),
            stderr="",
        )

    tool = ClackyTaskTool(config=_config(tmp_path), runner=runner, which=_which)
    assert tool.spec.requires_confirmation is True
    assert tool.spec.timeout_seconds == 42
    result = tool.execute(task="Open example.com", working_dir=str(tmp_path))

    assert result.success, result.content
    assert result.content.startswith("Done.")
    assert "browser" in result.content
    assert result.cost_usd == 0.5
    cmd = calls["cmd"]
    assert cmd[:3] == ["/usr/bin/bundle", "exec", "ruby"]
    assert cmd[-2:] == ["-m", "Open example.com"]
    assert "--json" in cmd and cmd[cmd.index("--path") + 1] == str(tmp_path)
    env = calls["kwargs"]["env"]
    assert env["CLACKY_MODEL"] == "qwen3:8b"
    assert env["BUNDLE_GEMFILE"].endswith("Gemfile")
    assert calls["kwargs"]["timeout"] == 42


def test_execute_reports_agent_errors_and_timeouts(tmp_path):
    def failing(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout=_ndjson({"type": "error", "message": "401 bad key"}),
            stderr="",
        )

    tool = ClackyTaskTool(config=_config(tmp_path), runner=failing, which=_which)
    result = tool.execute(task="x", working_dir=str(tmp_path))
    assert not result.success and "401 bad key" in result.content

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 42)

    tool = ClackyTaskTool(config=_config(tmp_path), runner=slow, which=_which)
    assert "did not finish" in tool.execute(task="x", working_dir=str(tmp_path)).content


def test_execute_validates_inputs_and_environment(tmp_path):
    cfg = _config(tmp_path)
    tool = ClackyTaskTool(config=cfg, runner=None, which=_which)
    assert "required" in tool.execute(task="  ").content
    assert (
        "does not exist"
        in tool.execute(task="x", working_dir=str(tmp_path / "nope")).content
    )

    assert (
        "Ruby"
        in ClackyTaskTool(config=cfg, which=lambda n: None).execute(task="x").content
    )

    cfg.intelligence.default_model = ""
    assert (
        "default_model"
        in ClackyTaskTool(config=cfg, which=_which).execute(task="x").content
    )

    cfg.extensions.clacky.enabled = False
    assert (
        "disabled" in ClackyTaskTool(config=cfg, which=_which).execute(task="x").content
    )

    cfg.extensions.clacky.enabled = True
    cfg.extensions.clacky.path = str(tmp_path / "missing")
    assert (
        "not installed"
        in ClackyTaskTool(config=cfg, which=_which).execute(task="x").content
    )
