"""Tests for the /v1/extensions API."""

from __future__ import annotations

import json

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.server.extensions_router import router  # noqa: E402
from openjarvis.tools.live_world import globe_target_file  # noqa: E402


@pytest.fixture
def client(tmp_path):
    cfg = JarvisConfig()
    cfg.intelligence.default_model = "qwen3:8b"
    cfg.extensions.clacky.path = str(tmp_path / "absent")
    cfg.extensions.globe.enabled = False
    app = FastAPI()
    app.state.config = cfg
    app.include_router(router)
    return TestClient(app)


def test_list_reports_services_and_globe_target(client):
    globe_target_file().write_text(
        json.dumps({"label": "Tokyo", "hash": "lat=1&lon=2"})
    )
    body = client.get("/v1/extensions").json()
    assert [s["name"] for s in body["services"]] == ["clacky"]
    assert body["services"][0]["available"] is False
    assert body["globe_target"]["label"] == "Tokyo"
    assert (
        client.get("/v1/extensions/globe/target").json()["target"]["label"] == "Tokyo"
    )


def test_start_and_stop_validate_names(client):
    assert client.post("/v1/extensions/globe/start").status_code == 404
    started = client.post("/v1/extensions/clacky/start").json()
    assert started["outcome"].startswith("skipped") and started["running"] is False
    assert client.post("/v1/extensions/nope/stop").status_code == 404
    assert client.post("/v1/extensions/clacky/stop").json() == {
        "name": "clacky",
        "stopped": False,
    }
