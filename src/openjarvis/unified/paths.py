"""Filesystem locations for the bundled extensions and their runtime state."""

from __future__ import annotations

from pathlib import Path

from openjarvis.core.paths import get_config_dir

# src/openjarvis/unified/paths.py -> repository root (source checkouts only).
_REPO_ROOT = Path(__file__).resolve().parents[3]

_DIRNAMES = {"clacky": "clacky", "globe": "globe"}


def extension_dir(name: str, override: str = "") -> Path | None:
    """Return the checkout directory of extension *name*, or ``None``.

    *override* (``[extensions.<name>] path`` in config.toml) wins over the
    bundled ``extensions/<name>`` directory of a source checkout. ``None``
    means the extension is not available in this installation (e.g. a
    PyPI wheel, which does not ship the extensions).
    """
    if name not in _DIRNAMES:
        raise ValueError(f"Unknown extension: {name}")
    candidate = (
        Path(override).expanduser()
        if override
        else _REPO_ROOT / "extensions" / _DIRNAMES[name]
    )
    return candidate if candidate.is_dir() else None


def state_dir() -> Path:
    """Directory for pid files, logs and shared state of the extensions."""
    path = get_config_dir() / "extensions"
    path.mkdir(parents=True, exist_ok=True)
    return path
