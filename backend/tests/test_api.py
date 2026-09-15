"""Endpoint shape tests against the seeded local DB."""
from __future__ import annotations

import pytest


def _data(client, path, headers):
    r = client.get(path, headers=headers)
    j = r.get_json()
    assert r.status_code == 200, j
    assert j["ok"] is True
    return j["data"]


def test_states(client, auth_headers):
    states = _data(client, "/api/states", auth_headers)
    assert isinstance(states, list) and "Delhi" in states


def test_areas_and_unknown(client, auth_headers):
    d = _data(client, "/api/states/Delhi/districts", auth_headers)
    assert d["level"] in ("district", "city") and d["items"]
    assert client.get("/api/states/Nowhere/districts",
                      headers=auth_headers).status_code == 404


def test_current(client, auth_headers):
    d = _data(client, "/api/aqi/current/Delhi/Delhi", auth_headers)
    assert d["available"] and d["AQI"] is not None
    assert d["AQI_bucket"] in ("Good", "Satisfactory", "Moderate", "Poor",
                               "Very Poor", "Severe")
    assert isinstance(d["is_live"], bool)
    assert d["as_of"] and d["source_note"]          # provenance always stated
    if not d["is_live"]:
        assert "2020" in d["source_note"] or "historical" in d["source_note"].lower()


def test_history_window(client, auth_headers):
    d = _data(client,
              "/api/aqi/history/Delhi/Delhi?from=2018-01-01&to=2018-06-30",
              auth_headers)
    assert 150 < d["count"] < 190
    assert d["series"][0]["date"] <= d["series"][-1]["date"]


def test_pollutants(client, auth_headers):
    d = _data(client, "/api/pollutants/Delhi/Delhi", auth_headers)
    assert d["available"] and len(d["pollutants"]) == 9
    assert {p["pollutant"] for p in d["pollutants"]} >= {"PM25", "PM10", "O3"}


def test_forecast_present_and_absent(client, auth_headers):
    ok = _data(client, "/api/aqi/forecast/Delhi/Delhi", auth_headers)
    assert ok["forecast_available"] and len(ok["days"]) == 7
    assert all(day["horizon_day"] == i + 1 for i, day in enumerate(ok["days"]))
    assert ok["is_prediction"] is True

    absent = _data(client, "/api/aqi/forecast/Mizoram/Aizawl", auth_headers)
    assert absent["forecast_available"] is False and absent["reason"]


def test_health_advisory(client, auth_headers):
    d = _data(client, "/api/health-advisory/Delhi/Delhi", auth_headers)
    assert d["available"]
    assert isinstance(d["respiratory_precautions"], list)
    assert d["disclaimer"] and "not" in d["disclaimer"].lower()


def test_model_metrics_and_insights(client, auth_headers):
    mm = _data(client, "/api/model-metrics", auth_headers)
    names = {m["model_name"] for m in mm["models"]}
    assert names == {"baseline", "lstm", "gru", "transformer"}
    assert mm["best_model"] in names
    assert sum(bool(m.get("is_best")) for m in mm["models"]) == 1

    mi = _data(client, "/api/model-insights/gru", auth_headers)
    assert mi["model"] == "gru" and mi["metrics"]["MAE"] > 0

    assert client.get("/api/model-insights/nope",
                      headers=auth_headers).status_code == 404


def test_dashboard_composite(client, auth_headers):
    d = _data(client, "/api/dashboard/Delhi/Delhi", auth_headers)
    for k in ("coverage", "current", "history_90d", "forecast", "advisory",
              "weather", "live_refresh"):
        assert k in d
    assert len(d["history_90d"]) <= 90
    assert "running" in d["live_refresh"]


def test_live_status(client, auth_headers):
    d = _data(client, "/api/live/status", auth_headers)
    assert isinstance(d["available"], bool)
    if d["available"]:
        assert d["ok"] in (True, False)
        assert d["cpcb_live_stations"] is None or d["cpcb_live_stations"] > 0
    else:
        assert d["reason"]


def test_leaderboard(client, auth_headers):
    d = _data(client, "/api/leaderboard", auth_headers)
    assert d["n_districts"] > 0
    assert len(d["best"]) > 0 and len(d["worst"]) > 0
    # ranked ascending by AQI (best = cleanest = lowest AQI first)
    assert d["best"][0]["aqi"] <= d["best"][-1]["aqi"]
    assert d["worst"][0]["aqi"] >= d["worst"][-1]["aqi"]
    for row in d["best"] + d["worst"]:
        assert row["state"] and row["district"] and row["aqi"] is not None


def test_compare(client, auth_headers):
    d = _data(client, "/api/compare?areas=Delhi:Delhi,Delhi:New Delhi", auth_headers)
    assert len(d["areas"]) == 2
    for a in d["areas"]:
        assert a["state"] == "Delhi" and a["current"] is not None

    assert client.get("/api/compare?areas=Delhi:Delhi",
                      headers=auth_headers).status_code == 400
    assert client.get("/api/compare?areas=NotAPair",
                      headers=auth_headers).status_code == 400


def test_alerts_crud(client, auth_headers):
    empty = _data(client, "/api/alerts", auth_headers)
    assert empty == []

    created = client.post("/api/alerts", headers=auth_headers,
                          json={"state": "Delhi", "area": "New Delhi", "threshold": 50})
    assert created.status_code == 201
    rule = created.get_json()["data"]
    assert rule["state"] == "Delhi" and rule["threshold"] == 50

    rows = _data(client, "/api/alerts", auth_headers)
    assert len(rows) == 1
    assert rows[0]["id"] == rule["id"]
    assert isinstance(rows[0]["triggered"], bool)
    assert rows[0]["current_aqi"] is not None

    bad = client.post("/api/alerts", headers=auth_headers,
                      json={"state": "Delhi", "area": "New Delhi", "threshold": 9999})
    assert bad.status_code == 400

    deleted = client.delete(f"/api/alerts/{rule['id']}", headers=auth_headers)
    assert deleted.status_code == 200
    assert _data(client, "/api/alerts", auth_headers) == []

    missing = client.delete(f"/api/alerts/{rule['id']}", headers=auth_headers)
    assert missing.status_code == 404


def test_state_overview(client, auth_headers):
    d = _data(client, "/api/states/Delhi/overview", auth_headers)
    assert d["state"] == "Delhi"
    assert d["avg_aqi"] and d["avg_bucket"]
    assert d["n_districts"] >= 1 and d["n_stations"] >= 1
    assert len(d["distribution"]) == 6
    assert abs(sum(x["pct"] for x in d["distribution"]) - 100) < 1.0
    assert d["monthly_trend"] and d["monthly_trend"][0]["month"] < d["monthly_trend"][-1]["month"]
    if d["best_districts"] and d["worst_districts"]:
        assert d["best_districts"][0]["avg_aqi"] <= d["worst_districts"][0]["avg_aqi"]
    assert client.get("/api/states/Atlantis/overview",
                      headers=auth_headers).status_code == 404


def test_push_vapid_key(client):
    d = _data(client, "/api/push/vapid-public-key", {})
    assert isinstance(d["configured"], bool)
    if d["configured"]:
        assert d["key"]


def test_push_subscribe_and_unsubscribe(client, auth_headers):
    fake_sub = {
        "endpoint": "https://example.com/push/test-endpoint-pytest",
        "keys": {"p256dh": "fake-p256dh", "auth": "fake-auth"},
    }
    created = client.post("/api/push/subscribe", headers=auth_headers, json=fake_sub)
    assert created.status_code == 201

    bad = client.post("/api/push/subscribe", headers=auth_headers, json={"endpoint": "x"})
    assert bad.status_code == 400

    removed = client.delete("/api/push/subscribe", headers=auth_headers,
                            json={"endpoint": fake_sub["endpoint"]})
    assert removed.status_code == 200


def test_map_india_and_state(client, auth_headers):
    india = _data(client, "/api/map/india", auth_headers)
    assert india["level"] == "state"
    assert india["type"] == "FeatureCollection"
    assert len(india["features"]) > 20
    withdata = [f for f in india["features"] if f["properties"]["has_data"]]
    assert len(withdata) > 10
    f0 = withdata[0]["properties"]
    assert f0["aqi"] is not None and f0["aqi_bucket"]
    assert "geometry" in withdata[0] and withdata[0]["geometry"]["coordinates"]

    delhi = _data(client, "/api/map/state/Delhi", auth_headers)
    assert delhi["level"] == "district" and delhi["state"] == "Delhi"
    assert len(delhi["features"]) >= 1
    assert any(f["properties"].get("aqi") is not None for f in delhi["features"])


def test_aqi_calendar(client, auth_headers):
    d = _data(client, "/api/aqi/calendar/Delhi/Delhi", auth_headers)
    assert d["available"] and d["n_days"] > 0
    assert d["start"] <= d["end"]
    assert len(d["days"]) == d["n_days"]
    first = d["days"][0]
    assert first["AQI"] is not None and first["AQI_bucket"]
    assert d["worst_month"]["avg_AQI"] >= d["best_month"]["avg_AQI"]
    assert "2020" in d["note"] or "historical" in d["note"].lower()

    assert client.get("/api/aqi/calendar/Atlantis/Nowhere",
                      headers=auth_headers).status_code == 404


def test_weather(client, auth_headers):
    d = _data(client, "/api/weather/Delhi/Delhi", auth_headers)
    assert isinstance(d["available"], bool)
    if d["available"]:
        assert d["source"] == "Open-Meteo"
        assert d["current"]["temperature"] is not None
        assert len(d["daily"]) == 7
        assert d["units"]["temperature"] == "°C"
    else:
        assert d["reason"]
