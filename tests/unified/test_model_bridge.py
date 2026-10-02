"""Tests for sharing the OpenJarvis model with OpenClacky."""

from __future__ import annotations

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.unified.model_bridge import ModelBridgeError, clacky_env


def _config(engine: str = "ollama", model: str = "qwen3:8b") -> JarvisConfig:
    cfg = JarvisConfig()
    cfg.engine.default = engine
    cfg.intelligence.default_model = model
    return cfg


def test_ollama_uses_openai_compatible_endpoint_and_disables_telemetry():
    cfg = _config()
    cfg.engine.ollama.host = "http://127.0.0.1:11434"
    env = clacky_env(cfg, environ={})
    assert env == {
        "CLACKY_API_KEY": "ollama",
        "CLACKY_BASE_URL": "http://127.0.0.1:11434/v1/",
        "CLACKY_MODEL": "qwen3:8b",
        "CLACKY_ANTHROPIC_FORMAT": "false",
        "CLACKY_TELEMETRY": "0",
    }


def test_ollama_host_falls_back_to_env_then_default():
    cfg = _config()
    cfg.engine.ollama.host = ""
    assert (
        clacky_env(cfg, environ={"OLLAMA_HOST": "gpu-box:11434"})["CLACKY_BASE_URL"]
        == "http://gpu-box:11434/v1/"
    )
    assert clacky_env(cfg, environ={})["CLACKY_BASE_URL"] == (
        "http://localhost:11434/v1/"
    )


def test_openai_compatible_local_engine_does_not_double_v1():
    cfg = _config(engine="vllm", model="qwen")
    cfg.engine.vllm.host = "http://localhost:8000/v1"
    assert clacky_env(cfg, environ={})["CLACKY_BASE_URL"] == "http://localhost:8000/v1/"


def test_preferred_engine_overrides_default():
    cfg = _config(engine="vllm")
    cfg.intelligence.preferred_engine = "ollama"
    assert clacky_env(cfg, environ={})["CLACKY_API_KEY"] == "ollama"


@pytest.mark.parametrize(
    ("model", "environ", "base_url", "clacky_model", "anthropic"),
    [
        (
            "claude-sonnet-5-5",
            {"ANTHROPIC_API_KEY": "a"},
            "https://api.anthropic.com",
            "claude-sonnet-5-5",
            "true",
        ),
        (
            "openrouter/anthropic/claude-sonnet-5-5",
            {"OPENROUTER_API_KEY": "o"},
            "https://openrouter.ai/api/v1/",
            "anthropic/claude-sonnet-5-5",
            "false",
        ),
        (
            "gemini-3-pro",
            {"GOOGLE_API_KEY": "g"},
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "gemini-3-pro",
            "false",
        ),
        (
            "gpt-6",
            {"OPENAI_API_KEY": "k"},
            "https://api.openai.com/v1/",
            "gpt-6",
            "false",
        ),
    ],
)
def test_cloud_models_route_to_their_provider(
    model, environ, base_url, clacky_model, anthropic
):
    env = clacky_env(_config(engine="cloud", model=model), environ=environ)
    assert env["CLACKY_BASE_URL"] == base_url
    assert env["CLACKY_MODEL"] == clacky_model
    assert env["CLACKY_ANTHROPIC_FORMAT"] == anthropic
    assert env["CLACKY_API_KEY"] == next(iter(environ.values()))


def test_cloud_without_key_explains_what_is_missing():
    with pytest.raises(ModelBridgeError, match="ANTHROPIC_API_KEY"):
        clacky_env(_config(engine="cloud", model="claude-sonnet-5-5"), environ={})


def test_missing_model_and_unknown_engine_are_errors():
    with pytest.raises(ModelBridgeError, match="default_model"):
        clacky_env(_config(model=""), environ={})
    with pytest.raises(ModelBridgeError, match="not supported"):
        clacky_env(_config(engine="mlx"), environ={})
