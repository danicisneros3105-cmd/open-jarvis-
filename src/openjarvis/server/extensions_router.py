"""HTTP API for the bundled extensions (OpenClacky and the 3D globe).

The frontend uses it to embed both apps and to follow ``globe_view``
requests made from chat.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/v1/extensions", tags=["extensions"])


def _supervisor(request: Request):
    from openjarvis.core.config import load_config
    from openjarvis.unified.supervisor import Supervisor

    config = getattr(request.app.state, "config", None) or load_config()
    return Supervisor(config)


@router.get("")
async def list_extensions(request: Request) -> dict[str, Any]:
    from openjarvis.tools.live_world import read_globe_target

    sup = _supervisor(request)
    services = await asyncio.to_thread(sup.status)
    return {"services": services, "globe_target": read_globe_target()}


@router.get("/globe/target")
async def globe_target() -> dict[str, Any]:
    from openjarvis.tools.live_world import read_globe_target

    return {"target": read_globe_target()}


@router.post("/{name}/start")
async def start_extension(name: str, request: Request) -> dict[str, Any]:
    sup = _supervisor(request)
    try:
        svc = sup.get(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    outcome = await asyncio.to_thread(sup.start, svc)
    return {"name": name, "outcome": outcome, "running": sup.running(svc)}


@router.post("/{name}/stop")
async def stop_extension(name: str, request: Request) -> dict[str, Any]:
    if name not in ("clacky", "globe"):
        raise HTTPException(status_code=404, detail=f"Unknown extension: {name}")
    stopped = await asyncio.to_thread(_supervisor(request).stop, name)
    return {"name": name, "stopped": stopped}
