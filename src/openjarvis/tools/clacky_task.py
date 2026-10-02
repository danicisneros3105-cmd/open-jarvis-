"""Delegate hands-on tasks to the bundled OpenClacky agent.

OpenClacky drives the terminal, the file system and the user's real Chrome
(via chrome-devtools-mcp). OpenJarvis keeps planning, memory and scheduling,
and hands concrete computer work to OpenClacky with this tool. Both agents
share the same model through :mod:`openjarvis.unified.model_bridge`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_TOOL_NAME = "clacky_task"
_MAX_OUTPUT_CHARS = 8000

Runner = Callable[..., subprocess.CompletedProcess]


def summarize_events(stdout: str) -> tuple[str, list[str], str, float]:
    """Parse OpenClacky NDJSON output.

    Returns ``(final_message, tool_names, error, cost_usd)``.
    """
    messages: list[str] = []
    tools: list[str] = []
    error = ""
    cost = 0.0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "assistant_message" and event.get("content"):
            messages.append(str(event["content"]))
        elif kind == "tool_call" and event.get("name"):
            tools.append(str(event["name"]))
        elif kind == "error":
            error = str(event.get("message") or event.get("error") or "unknown error")
        elif kind == "done":
            try:
                cost = float(event.get("total_cost") or 0.0)
            except (TypeError, ValueError):
                cost = 0.0
    return (messages[-1] if messages else ""), tools, error, cost


@ToolRegistry.register(_TOOL_NAME)
class ClackyTaskTool(BaseTool):
    """Run one task end-to-end with the OpenClacky agent."""

    tool_id = _TOOL_NAME

    def __init__(
        self,
        *,
        config: Any = None,
        runner: Runner = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        if config is None:
            from openjarvis.core.config import load_config

            config = load_config()
        self._config = config
        self._runner = runner
        self._which = which

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=_TOOL_NAME,
            description=(
                "Delegate a hands-on computer task to the OpenClacky agent, which "
                "can run terminal commands, read and write files, search the web "
                "and control the user's Chrome browser (open sites, click, type, "
                "fill forms). Use it for multi-step tasks on the user's computer "
                "such as organizing files, installing apps or operating a website. "
                "Describe the goal completely; the agent works autonomously and "
                "returns a summary of what it did."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Complete description of the task to perform.",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Directory to work in (default: user's home).",
                    },
                },
                "required": ["task"],
            },
            category="agent",
            requires_confirmation=True,
            timeout_seconds=float(self._config.extensions.clacky.timeout_seconds),
        )

    def _fail(self, message: str) -> ToolResult:
        return ToolResult(tool_name=_TOOL_NAME, content=message, success=False)

    def execute(self, **params: Any) -> ToolResult:
        from openjarvis.unified.model_bridge import ModelBridgeError, clacky_env
        from openjarvis.unified.paths import extension_dir

        task = str(params.get("task") or "").strip()
        if not task:
            return self._fail("The 'task' parameter is required.")
        cfg = self._config.extensions.clacky
        if not cfg.enabled:
            return self._fail("OpenClacky is disabled ([extensions.clacky] enabled).")
        root = extension_dir("clacky", cfg.path)
        if root is None:
            return self._fail(
                "OpenClacky is not installed (extensions/clacky missing)."
            )
        bundle = self._which("bundle")
        if bundle is None or self._which("ruby") is None:
            return self._fail("OpenClacky needs Ruby and Bundler; run the installer.")
        try:
            env = {**os.environ, **clacky_env(self._config)}
        except ModelBridgeError as exc:
            return self._fail(str(exc))
        env["BUNDLE_GEMFILE"] = str(root / "Gemfile")

        workdir = Path(params.get("working_dir") or Path.home()).expanduser()
        if not workdir.is_dir():
            return self._fail(f"Working directory does not exist: {workdir}")

        cmd = [
            bundle, "exec", "ruby", str(root / "bin" / "clacky"), "agent",
            "--json", "--path", str(workdir), "-m", task,
        ]  # fmt: skip
        try:
            done = self._runner(
                cmd,
                cwd=str(workdir),
                env=env,
                capture_output=True,
                text=True,
                timeout=float(cfg.timeout_seconds),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._fail(
                f"OpenClacky did not finish within {cfg.timeout_seconds:.0f}s."
            )
        except OSError as exc:
            return self._fail(f"Could not start OpenClacky: {exc}")

        final, tools, error, cost = summarize_events(done.stdout or "")
        if done.returncode != 0 or error:
            detail = error or (done.stderr or "").strip()[-1000:] or "no output"
            return ToolResult(
                tool_name=_TOOL_NAME,
                content=f"OpenClacky failed: {detail}",
                success=False,
                cost_usd=cost,
                metadata={"tools_used": tools},
            )
        lines = [final or "Task finished (no summary returned)."]
        if tools:
            lines.append(f"\nActions taken: {', '.join(tools)}")
        return ToolResult(
            tool_name=_TOOL_NAME,
            content="\n".join(lines)[:_MAX_OUTPUT_CHARS],
            cost_usd=cost,
            metadata={"tools_used": tools},
        )


__all__ = ["ClackyTaskTool", "summarize_events"]
