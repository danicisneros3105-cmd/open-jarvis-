"""Tests for live world data tools and globe control."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from openjarvis.tools.live_world import (
    GlobeViewTool,
    LiveEarthquakesTool,
    LiveFlightsTool,
    UpcomingLaunchesTool,
    read_globe_target,
)


class FakeHttp:
    def __init__(self, responses: dict[str, object]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, params: dict):
        self.calls.append((url, params))
        for prefix, payload in self.responses.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f"unexpected URL {url}")


NOMINATIM = {
    "https://nominatim.openstreetmap.org": [
        {"lat": "40.4168", "lon": "-3.7038", "display_name": "Madrid, España"}
    ]
}


def test_live_flights_sorts_by_distance_and_converts_radius():
    http = FakeHttp(
        {
            **NOMINATIM,
            "https://api.adsb.lol/v2/point/": {
                "ac": [
                    {
                        "flight": "FAR1  ",
                        "r": "EC-AAA",
                        "t": "A320",
                        "alt_baro": 30000,
                        "gs": 450.4,
                        "lat": 41.4,
                        "lon": -3.7,
                    },
                    {
                        "flight": "NEAR1",
                        "r": "EC-BBB",
                        "t": "B738",
                        "alt_baro": 5000,
                        "gs": 220,
                        "lat": 40.42,
                        "lon": -3.70,
                    },
                    {"hex": "abc123"},
                ]
            },
        }
    )
    result = LiveFlightsTool(http_get=http).execute(place="Madrid", radius_km=185)
    assert result.success, result.content
    lines = result.content.splitlines()
    assert lines[0].startswith("3 aircraft within 185 km of Madrid")
    assert lines[1].startswith("- NEAR1 (EC-BBB, B738) alt 5000 ft, 220 kt")
    assert lines[2].startswith("- FAR1 (EC-AAA, A320)")
    assert "position unknown" in lines[3]
    assert http.calls[-1][0].endswith("/40.4168/-3.7038/100")  # 185 km = 100 nm


def test_live_flights_validates_location():
    tool = LiveFlightsTool(http_get=FakeHttp({}))
    assert "place" in tool.execute().content
    assert not tool.execute(lat=91, lon=0).success
    empty = LiveFlightsTool(http_get=FakeHttp({"https://api.adsb.lol": {"ac": []}}))
    assert "No aircraft" in empty.execute(lat=1, lon=2).content


def test_live_earthquakes_near_place():
    http = FakeHttp(
        {
            **NOMINATIM,
            "https://earthquake.usgs.gov": {
                "features": [
                    {
                        "properties": {
                            "mag": 4.6,
                            "place": "10 km S of Granada",
                            "time": 1790000000000,
                        },
                        "geometry": {"coordinates": [-3.6, 37.1, 12.0]},
                    }
                ]
            },
        }
    )
    result = LiveEarthquakesTool(http_get=http).execute(
        place="Madrid", min_magnitude=4, days=7
    )
    assert result.success, result.content
    assert (
        "M4.6 10 km S of Granada" in result.content and "depth 12 km" in result.content
    )
    params = http.calls[-1][1]
    assert params["latitude"] == 40.4168 and params["maxradiuskm"] == 500
    assert params["minmagnitude"] == 4


def test_live_earthquakes_worldwide_and_provider_errors():
    http = FakeHttp({"https://earthquake.usgs.gov": {"features": []}})
    result = LiveEarthquakesTool(http_get=http).execute()
    assert "No earthquakes" in result.content and "worldwide" in result.content
    assert "latitude" not in http.calls[-1][1]
    broken = FakeHttp({"https://earthquake.usgs.gov": RuntimeError("503")})
    failed = LiveEarthquakesTool(http_get=broken).execute()
    assert not failed.success and "503" in failed.content


def test_upcoming_launches_handles_list_and_detail_shapes():
    http = FakeHttp(
        {
            "https://ll.thespacedevs.com": {
                "results": [
                    {
                        "name": "Falcon 9 | Starlink",
                        "net": "2026-10-02T10:00:00Z",
                        "status": {"name": "Go"},
                        "location": "Cape Canaveral",
                    },
                    {
                        "name": "Ariane 6",
                        "net": "2026-10-05",
                        "pad": {"location": {"name": "Kourou"}},
                    },
                ]
            }
        }
    )
    result = UpcomingLaunchesTool(http_get=http).execute(limit=2)
    assert (
        "Falcon 9 | Starlink — 2026-10-02T10:00:00Z — Cape Canaveral (Go)"
        in result.content
    )
    assert "Ariane 6 — 2026-10-05 — Kourou" in result.content


def test_globe_view_writes_target_for_the_ui():
    result = GlobeViewTool(http_get=FakeHttp(NOMINATIM)).execute(
        place="Madrid", style="night_vision", altitude_m=500_000
    )
    assert result.success, result.content
    target = read_globe_target()
    assert target["label"] == "Madrid, España"
    params = parse_qs(target["hash"])
    assert params["style"] == ["nvg"] and params["pitch"] == ["-90"]
    assert target["url"].startswith("http://127.0.0.1:4173/#lat=40.41680")
    assert json.loads(json.dumps(target)) == target

    bad = GlobeViewTool(http_get=FakeHttp({})).execute(lat=1, lon=1, style="laser")
    assert not bad.success and "Unknown style" in bad.content
