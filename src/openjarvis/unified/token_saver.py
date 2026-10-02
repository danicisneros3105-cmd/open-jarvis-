"""Token saver: compress long tool outputs with LLMLingua-2.

Web pages, PDFs and search results are mostly filler for the question at
hand, yet every character is paid for in prompt tokens (and latency on local
models). LLMLingua-2 (https://github.com/microsoft/LLMLingua, MIT) is a small
token-classification model that drops low-information tokens while keeping
the facts, typically shrinking text 2-5x with little quality loss.

Enabled with ``[compression] tool_output = true``. It only touches the tools
listed in ``tool_output_tools`` (never code, files or shell output, where
every character matters) and outputs longer than ``tool_output_min_chars``.
Any failure leaves the original text untouched.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

Compressor = Callable[[str, float], str]

_lock = threading.Lock()
_compressor: Compressor | None = None
_unavailable = False


def _load_llmlingua(model_name: str) -> Compressor:
    from llmlingua import PromptCompressor

    pc = PromptCompressor(model_name=model_name, use_llmlingua2=True, device_map="cpu")

    def compress(text: str, rate: float) -> str:
        out = pc.compress_prompt(
            text,
            rate=rate,
            force_tokens=["\n", ".", "?", "!", ":"],
            force_reserve_digit=True,  # keep prices, dates and phone numbers
        )
        return str(out["compressed_prompt"])

    return compress


def _get_compressor(model_name: str) -> Compressor | None:
    global _compressor, _unavailable
    if _compressor is not None or _unavailable:
        return _compressor
    with _lock:
        if _compressor is None and not _unavailable:
            try:
                _compressor = _load_llmlingua(model_name)
            except Exception as exc:  # ImportError, model download failure…
                _unavailable = True
                logger.warning(
                    "Token saver disabled: LLMLingua could not load (%s). "
                    "Install it with `uv sync --extra token-saver`.",
                    exc,
                )
    return _compressor


def set_compressor(compressor: Compressor | None) -> None:
    """Override the compressor (tests, or a custom backend)."""
    global _compressor, _unavailable
    _compressor, _unavailable = compressor, False


def maybe_compress(tool_name: str, text: str, config: Any) -> tuple[str, dict]:
    """Return ``(text, stats)``; *text* is compressed when the policy allows."""
    cfg = getattr(config, "compression", None)
    if (
        cfg is None
        or not cfg.tool_output
        or tool_name not in cfg.tool_output_tools
        or len(text) < cfg.tool_output_min_chars
    ):
        return text, {}
    compressor = _get_compressor(cfg.tool_output_model)
    if compressor is None:
        return text, {}
    try:
        short = compressor(text, float(cfg.tool_output_rate))
    except Exception:  # noqa: BLE001 — never lose the original output
        logger.debug("Tool output compression failed", exc_info=True)
        return text, {}
    if not short.strip() or len(short) >= len(text):
        return text, {}
    note = (
        f"[compressed from {len(text)} to {len(short)} characters to save "
        "tokens; wording may be terse]\n"
    )
    return note + short, {
        "compressed_from_chars": len(text),
        "compressed_chars": len(short),
    }


_config_cache: Any = None


def runtime_config() -> Any:
    """Config used by the tool executor (loaded once per process)."""
    global _config_cache
    if _config_cache is None:
        from openjarvis.core.config import load_config

        _config_cache = load_config()
    return _config_cache


__all__ = ["maybe_compress", "runtime_config", "set_compressor"]
