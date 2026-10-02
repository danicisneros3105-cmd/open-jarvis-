"""Tests for compressing long tool outputs."""

from __future__ import annotations

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.core.types import ToolCall, ToolResult
from openjarvis.tools._stubs import BaseTool, ToolExecutor, ToolSpec
from openjarvis.unified import token_saver
from openjarvis.unified.token_saver import maybe_compress, set_compressor


@pytest.fixture
def config():
    cfg = JarvisConfig()
    cfg.compression.tool_output = True
    cfg.compression.tool_output_min_chars = 100
    yield cfg
    set_compressor(None)


def _halve(text: str, rate: float) -> str:
    return text[: int(len(text) * rate)]


def test_compresses_only_long_outputs_of_allowed_tools(config):
    set_compressor(_halve)
    long_text = "word " * 100
    out, stats = maybe_compress("web_search", long_text, config)
    assert out.startswith("[compressed from 500 to 200 characters")
    assert stats == {"compressed_from_chars": 500, "compressed_chars": 200}

    assert maybe_compress("file_read", long_text, config) == (long_text, {})
    assert maybe_compress("web_search", "short", config) == ("short", {})
    config.compression.tool_output = False
    assert maybe_compress("web_search", long_text, config) == (long_text, {})


def test_failures_keep_the_original(config):
    def boom(text, rate):
        raise RuntimeError("model crashed")

    set_compressor(boom)
    text = "x" * 200
    assert maybe_compress("web_search", text, config) == (text, {})
    set_compressor(lambda t, r: t + "longer")
    assert maybe_compress("web_search", text, config) == (text, {})


def test_missing_llmlingua_disables_quietly(config, monkeypatch):
    set_compressor(None)

    def missing(name):
        raise ImportError("No module named 'llmlingua'")

    monkeypatch.setattr(token_saver, "_load_llmlingua", missing)
    text = "y" * 200
    assert maybe_compress("web_search", text, config) == (text, {})
    assert token_saver._unavailable is True


class _BigSearch(BaseTool):
    tool_id = "web_search"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(name="web_search", description="fake", parameters={})

    def execute(self, **params) -> ToolResult:
        return ToolResult(tool_name="web_search", content="result " * 50)


def test_tool_executor_applies_the_token_saver(config, monkeypatch):
    set_compressor(_halve)
    monkeypatch.setattr(token_saver, "_config_cache", config)
    result = ToolExecutor([_BigSearch()]).execute(
        ToolCall(id="1", name="web_search", arguments="{}")
    )
    assert result.content.startswith("[compressed from 350")
    assert result.metadata["compressed_chars"] == 140
