"""Live world data from the God's Eye View sources, plus globe control.

The globe extension (``extensions/globe``) shows aircraft, earthquakes and
launches on a 3D map. These tools let the assistant answer questions with the
same public, keyless sources and point the embedded globe at a place:

* ``live_flights`` — aircraft near a point (adsb.lol, ADS-B).
* ``live_earthquakes`` — recent earthquakes (USGS FDSN).
* ``upcoming_launches`` — next rocket launches (The Space Devs).
* ``globe_view`` — fly the embedded globe to a place with a visual style.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_USER_AGENT = "OpenJarvis/1.0 (+https://github.com/open-jarvis/OpenJarvis)"
_TIMEOUT = 15.0

HttpGet = Callable[[str, dict[str, Any]], Any]


def _default_get(url: str, params: dict[str, Any]) -> Any:
    import httpx

    resp = httpx.get(
        url, params=params, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def _num(value: Any, name: str, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{name}' must be a number") from None
    if not math.isfinite(out) or not lo <= out <= hi:
        raise ValueError(f"'{name}' must be between {lo} and {hi}")
    return out


def geocode(place: str, http_get: HttpGet = _default_get) -> tuple[float, float, str]:
    """Resolve a place name with OpenStreetMap Nominatim (same as the globe)."""
    rows = http_get(
        "https://nominatim.openstreetmap.org/search",
        {"q": place, "format": "json", "limit": 1},
    )
    if not rows:
        raise ValueError(f"Place not found: {place}")
    row = rows[0]
    return float(row["lat"]), float(row["lon"]), str(row.get("display_name", place))


def _location(params: dict[str, Any], http_get: HttpGet) -> tuple[float, float, str]:
    place = str(params.get("place") or "").strip()
    if params.get("lat") is not None and params.get("lon") is not None:
        lat = _num(params["lat"], "lat", -90, 90)
        lon = _num(params["lon"], "lon", -180, 180)
        return lat, lon, place or f"{lat:.4f}, {lon:.4f}"
    if place:
        return geocode(place, http_get)
    raise ValueError("Give either 'place' or both 'lat' and 'lon'.")


_LOCATION_PROPS = {
    "place": {"type": "string", "description": "Place name, e.g. 'Madrid'."},
    "lat": {"type": "number", "description": "Latitude (instead of place)."},
    "lon": {"type": "number", "description": "Longitude (instead of place)."},
}


class _WorldTool(BaseTool):
    def __init__(self, *, http_get: HttpGet = _default_get) -> None:
        self._get = http_get

    def _ok(self, content: str, **meta: Any) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=content, metadata=meta)

    def _fail(self, message: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=message, success=False)

    def execute(self, **params: Any) -> ToolResult:
        try:
            return self._run(params)
        except ValueError as exc:
            return self._fail(str(exc))
        except Exception as exc:  # network / provider errors
            return self._fail(f"{self.tool_id} failed: {exc}")

    def _run(self, params: dict[str, Any]) -> ToolResult:  # pragma: no cover
        raise NotImplementedError


@ToolRegistry.register("live_flights")
class LiveFlightsTool(_WorldTool):
    tool_id = "live_flights"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "List aircraft flying right now near a place (live ADS-B data): "
                "callsign, registration, type, altitude, speed and position."
            ),
            parameters={
                "type": "object",
                "properties": {
                    **_LOCATION_PROPS,
                    "radius_km": {
                        "type": "number",
                        "description": "Search radius in km (1-460, default 50).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows (default 15).",
                    },
                },
            },
            category="world",
            timeout_seconds=30.0,
        )

    def _run(self, params: dict[str, Any]) -> ToolResult:
        lat, lon, label = _location(params, self._get)
        radius_km = _num(params.get("radius_km", 50), "radius_km", 1, 460)
        limit = int(_num(params.get("limit", 15), "limit", 1, 100))
        radius_nm = max(1, round(radius_km / 1.852))
        data = self._get(f"https://api.adsb.lol/v2/point/{lat}/{lon}/{radius_nm}", {})
        aircraft = [a for a in (data or {}).get("ac", []) if isinstance(a, dict)]
        aircraft.sort(key=lambda a: _distance_km(lat, lon, a.get("lat"), a.get("lon")))
        if not aircraft:
            return self._ok(f"No aircraft within {radius_km:.0f} km of {label}.")
        lines = [f"{len(aircraft)} aircraft within {radius_km:.0f} km of {label}:"]
        for a in aircraft[:limit]:
            dist = _distance_km(lat, lon, a.get("lat"), a.get("lon"))
            lines.append(
                "- {cs} ({reg}, {typ}) alt {alt} ft, {gs} kt, {d}".format(
                    cs=(a.get("flight") or a.get("hex") or "?").strip(),
                    reg=a.get("r") or "?",
                    typ=a.get("t") or "?",
                    alt=a.get("alt_baro", "?"),
                    gs=round(a["gs"]) if isinstance(a.get("gs"), (int, float)) else "?",
                    d=f"{dist:.0f} km away"
                    if math.isfinite(dist)
                    else "position unknown",
                )
            )
        return self._ok("\n".join(lines), count=len(aircraft), lat=lat, lon=lon)


def _distance_km(lat1: float, lon1: float, lat2: Any, lon2: Any) -> float:
    if not isinstance(lat2, (int, float)) or not isinstance(lon2, (int, float)):
        return math.inf
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


@ToolRegistry.register("live_earthquakes")
class LiveEarthquakesTool(_WorldTool):
    tool_id = "live_earthquakes"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Recent earthquakes from USGS, worldwide or near a place: "
                "magnitude, location, depth and time."
            ),
            parameters={
                "type": "object",
                "properties": {
                    **_LOCATION_PROPS,
                    "radius_km": {
                        "type": "number",
                        "description": "Radius around the place (default 500).",
                    },
                    "min_magnitude": {
                        "type": "number",
                        "description": "Minimum magnitude (default 4.0).",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Look-back days (default 1).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows (default 10).",
                    },
                },
            },
            category="world",
            timeout_seconds=30.0,
        )

    def _run(self, params: dict[str, Any]) -> ToolResult:
        days = int(_num(params.get("days", 1), "days", 1, 30))
        limit = int(_num(params.get("limit", 10), "limit", 1, 100))
        query: dict[str, Any] = {
            "format": "geojson",
            "orderby": "time",
            "limit": limit,
            "minmagnitude": _num(
                params.get("min_magnitude", 4.0), "min_magnitude", 0, 10
            ),
            "starttime": (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        }
        label = "worldwide"
        if params.get("place") or params.get("lat") is not None:
            lat, lon, label = _location(params, self._get)
            query.update(
                latitude=lat,
                longitude=lon,
                maxradiuskm=_num(params.get("radius_km", 500), "radius_km", 1, 20000),
            )
            label = f"near {label}"
        data = self._get("https://earthquake.usgs.gov/fdsnws/event/1/query", query)
        quakes = (data or {}).get("features", [])
        if not quakes:
            return self._ok(
                f"No earthquakes M{query['minmagnitude']}+ {label} in {days} day(s)."
            )
        lines = [f"Earthquakes M{query['minmagnitude']}+ {label}, last {days} day(s):"]
        for q in quakes:
            p = q.get("properties", {})
            coords = (q.get("geometry") or {}).get("coordinates") or [None, None, None]
            when = datetime.fromtimestamp(p.get("time", 0) / 1000, tz=timezone.utc)
            depth = coords[2] if len(coords) > 2 else None
            lines.append(
                f"- M{p.get('mag')} {p.get('place', '?')} — {when:%Y-%m-%d %H:%M} UTC"
                + (f", depth {depth:.0f} km" if isinstance(depth, (int, float)) else "")
            )
        return self._ok("\n".join(lines), count=len(quakes))


@ToolRegistry.register("upcoming_launches")
class UpcomingLaunchesTool(_WorldTool):
    tool_id = "upcoming_launches"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description="Next scheduled rocket launches worldwide (The Space Devs).",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many (default 5)."}
                },
            },
            category="world",
            timeout_seconds=30.0,
        )

    def _run(self, params: dict[str, Any]) -> ToolResult:
        limit = int(_num(params.get("limit", 5), "limit", 1, 20))
        data = self._get(
            "https://ll.thespacedevs.com/2.3.0/launches/upcoming/",
            {"limit": limit, "mode": "list"},
        )
        rows = (data or {}).get("results", [])
        if not rows:
            return self._ok("No upcoming launches found.")
        lines = ["Upcoming launches:"]
        for r in rows:
            status = r.get("status")
            status = status.get("name") if isinstance(status, dict) else status
            pad = r.get("pad")
            where = r.get("location") or (
                ((pad or {}).get("location") or {}).get("name")
                if isinstance(pad, dict)
                else ""
            )
            lines.append(
                f"- {r.get('name', '?')} — {r.get('net', '?')}"
                + (f" — {where}" if where else "")
                + (f" ({status})" if status else "")
            )
        return self._ok("\n".join(lines), count=len(rows))


# Visual styles of the globe (URL names used by its share links).
GLOBE_STYLES = {
    "normal": "normal",
    "night_vision": "nvg",
    "thermal": "flir",
    "retro": "crt",
    "noir": "noir",
    "snow": "snow",
    "anime": "anime",
}


def globe_target_file():
    from openjarvis.unified.paths import state_dir

    return state_dir() / "globe_target.json"


def read_globe_target() -> dict[str, Any] | None:
    try:
        return json.loads(globe_target_file().read_text())
    except (OSError, ValueError):
        return None


@ToolRegistry.register("globe_view")
class GlobeViewTool(_WorldTool):
    tool_id = "globe_view"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Show a place on the live 3D globe (Globe tab of the app), "
                "optionally with a visual style such as night vision or thermal."
            ),
            parameters={
                "type": "object",
                "properties": {
                    **_LOCATION_PROPS,
                    "altitude_m": {
                        "type": "number",
                        "description": "Camera height in meters (default 1500).",
                    },
                    "style": {"type": "string", "enum": sorted(GLOBE_STYLES)},
                },
            },
            category="world",
            timeout_seconds=20.0,
        )

    def _run(self, params: dict[str, Any]) -> ToolResult:
        from openjarvis.core.config import load_config

        lat, lon, label = _location(params, self._get)
        alt = _num(params.get("altitude_m", 1500), "altitude_m", 50, 40_000_000)
        style_key = str(params.get("style") or "normal")
        if style_key not in GLOBE_STYLES:
            choices = ", ".join(sorted(GLOBE_STYLES))
            raise ValueError(f"Unknown style '{style_key}'. Use one of: {choices}")
        pitch = -90 if alt > 200_000 else -35
        fragment = urlencode(
            {
                "lat": f"{lat:.5f}",
                "lon": f"{lon:.5f}",
                "alt": f"{alt:.0f}",
                "heading": 0,
                "pitch": pitch,
                "style": GLOBE_STYLES[style_key],
            }
        )
        port = load_config().extensions.globe.port
        target = {
            "label": label,
            "lat": lat,
            "lon": lon,
            "style": style_key,
            "hash": fragment,
            "url": f"http://127.0.0.1:{port}/#{fragment}",
            "updated_at": time.time(),
        }
        path = globe_target_file()
        path.write_text(json.dumps(target))
        return self._ok(
            f"Globe pointed at {label} ({style_key}). "
            f"Open the Globe tab or {target['url']}",
            **target,
        )


__all__ = [
    "GLOBE_STYLES",
    "GlobeViewTool",
    "LiveEarthquakesTool",
    "LiveFlightsTool",
    "UpcomingLaunchesTool",
    "geocode",
    "read_globe_target",
]
