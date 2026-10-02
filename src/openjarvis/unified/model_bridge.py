"""Share the OpenJarvis model with OpenClacky.

OpenClacky reads its default model from ``CLACKY_*`` environment variables.
This module derives them from the OpenJarvis engine/model configuration so
the user configures one brain and both agents use it.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

_OPENAI_COMPAT_ENGINES = ("vllm", "sglang", "llamacpp", "lmstudio")
_DEFAULT_OLLAMA_HOST = "http://localhost:11434"


class ModelBridgeError(RuntimeError):
    """The current OpenJarvis model cannot be handed to OpenClacky."""


def _v1(host: str) -> str:
    host = host.rstrip("/")
    if host.endswith("/v1"):
        host = host[: -len("/v1")]
    return f"{host}/v1/"


def _env(api_key: str, base_url: str, model: str, anthropic: bool) -> dict[str, str]:
    return {
        "CLACKY_API_KEY": api_key,
        "CLACKY_BASE_URL": base_url,
        "CLACKY_MODEL": model,
        "CLACKY_ANTHROPIC_FORMAT": "true" if anthropic else "false",
    }


def clacky_env(config: Any, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the ``CLACKY_*`` variables matching the OpenJarvis model.

    Telemetry of OpenClacky is always disabled (``CLACKY_TELEMETRY=0``).

    Raises :class:`ModelBridgeError` when no model is configured or the
    cloud provider's API key is missing.
    """
    environ = os.environ if environ is None else environ
    engine = (
        getattr(config.intelligence, "preferred_engine", "") or config.engine.default
    )
    model = (getattr(config.intelligence, "default_model", "") or "").strip()
    if not model:
        raise ModelBridgeError(
            "No default model configured. Set [intelligence] default_model "
            "in ~/.openjarvis/config.toml or run `jarvis model`."
        )

    if engine == "ollama":
        host = (
            config.engine.ollama.host
            or environ.get("OLLAMA_HOST", "")
            or _DEFAULT_OLLAMA_HOST
        )
        if not host.startswith("http"):
            host = f"http://{host}"
        env = _env("ollama", _v1(host), model, anthropic=False)
    elif engine in _OPENAI_COMPAT_ENGINES:
        host = getattr(config.engine, engine).host
        env = _env("local", _v1(host), model, anthropic=False)
    elif engine == "cloud":
        env = _cloud_env(model, environ)
    else:
        raise ModelBridgeError(
            f"Engine '{engine}' is not supported by OpenClacky yet. "
            "Use ollama, vllm, sglang, llamacpp, lmstudio or cloud."
        )
    env["CLACKY_TELEMETRY"] = "0"
    return env


def _cloud_env(model: str, environ: Mapping[str, str]) -> dict[str, str]:
    def key(*names: str) -> str:
        for name in names:
            value = environ.get(name, "").strip()
            if value:
                return value
        raise ModelBridgeError(f"Model '{model}' needs {' or '.join(names)} to be set.")

    if model.startswith("openrouter/"):
        return _env(
            key("OPENROUTER_API_KEY"),
            "https://openrouter.ai/api/v1/",
            model[len("openrouter/") :],
            anthropic=False,
        )
    if model.startswith("claude"):
        return _env(
            key("ANTHROPIC_API_KEY"), "https://api.anthropic.com", model, anthropic=True
        )
    if model.startswith("gemini"):
        return _env(
            key("GEMINI_API_KEY", "GOOGLE_API_KEY"),
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            model,
            anthropic=False,
        )
    return _env(key("OPENAI_API_KEY"), "https://api.openai.com/v1/", model, False)
