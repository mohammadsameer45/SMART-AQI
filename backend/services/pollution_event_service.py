"""
Pollution event detection for SMART AQI.

An "event" is a contiguous run of real recorded AQI readings for an area
that stay above the CPCB "Satisfactory" ceiling (AQI > 100, i.e. Moderate or
worse), detected directly from aqi_records (live readings where available,
otherwise the historical daily series) - never invented. Detection is
threshold-crossing on the area's own data, computed on demand; nothing is
persisted to a new collection because nothing here needs to survive a
process restart to stay correct - it's cheap to recompute and always
reflects the current data.

Likely contributors for an event are the pollutants that rose most between
its start and its peak - evidence from the event's own readings, not a
general/fabricated source claim.
"""
from __future__ import annotations

from datetime import timedelta

from backend.config.aqi_categories import categorize
from backend.services import aqi_service
from backend.services.aqi_service import POLLUTANTS
from backend.services.location_service import resolve_area
from backend.services.pollutant_insight_service import _area_series

EVENT_THRESHOLD = 100      # CPCB "Satisfactory" ceiling; above this = an event
_WINDOW_DAYS = 90           # only look at recent history, like the dashboard's 90d view
_MAX_EVENTS = 20


def detect_events(state: str, area: str) -> dict:
    resolved = resolve_area(state, area)
    series, source = _area_series(resolved)
    if not series:
        return {"available": False, "reason": "No AQI records for this area."}

    cutoff = series[-1]["ts"] - timedelta(days=_WINDOW_DAYS)
    series = [d for d in series if d["ts"] >= cutoff and d.get("AQI") is not None]
    if not series:
        return {"available": False, "reason": "No AQI readings in the recent window."}

    raw_events: list[list[dict]] = []
    current: list[dict] | None = None
    for d in series:
        if d["AQI"] > EVENT_THRESHOLD:
            if current is None:
                current = []
                raw_events.append(current)
            current.append(d)
        else:
            current = None

    events = []
    for readings in raw_events[-_MAX_EVENTS:]:
        start, end = readings[0], readings[-1]
        peak = max(readings, key=lambda r: r["AQI"])
        ongoing = end is series[-1] and series[-1]["AQI"] > EVENT_THRESHOLD
        duration_h = round((end["ts"] - start["ts"]).total_seconds() / 3600, 1)

        contributors = []
        for p in POLLUTANTS:
            a, b = start.get(p), peak.get(p)
            if a is not None and b is not None and b > a:
                contributors.append({"pollutant": p, "from": a, "to": b,
                                     "delta": round(b - a, 2)})
        contributors.sort(key=lambda c: -c["delta"])

        events.append({
            "event_id": start["ts"].strftime("%Y%m%dT%H%M"),
            "state": state, "area": area,
            "source": source,
            "started_at": start["ts"].isoformat(),
            "ended_at": None if ongoing else end["ts"].isoformat(),
            "ongoing": ongoing,
            "duration_hours": duration_h,
            "start_AQI": start["AQI"],
            "current_AQI": end["AQI"],
            "peak_AQI": peak["AQI"],
            "peak_at": peak["ts"].isoformat(),
            "peak_bucket": categorize(peak["AQI"]),
            "likely_contributors": contributors[:3],
            "n_readings": len(readings),
        })

    events.sort(key=lambda e: e["started_at"], reverse=True)
    return {
        "available": True,
        "state": state, "area": area,
        "source": source,
        "window_days": _WINDOW_DAYS,
        "threshold": EVENT_THRESHOLD,
        "count": len(events),
        "events": events,
        "note": f"Periods where recorded AQI stayed above {EVENT_THRESHOLD} "
                "(CPCB 'Moderate' or worse), detected from this area's own "
                f"{source.replace('_', ' ')} readings over the last "
                f"{_WINDOW_DAYS} days. Likely contributors are the "
                "pollutants that rose most between an event's start and "
                "its peak - evidence from that event, not a general claim.",
    }


def event_detail(state: str, area: str, event_id: str) -> dict:
    all_events = detect_events(state, area)
    if not all_events.get("available"):
        return all_events
    for e in all_events["events"]:
        if e["event_id"] == event_id:
            return {"available": True, **e}
    return {"available": False, "reason": f"Event '{event_id}' not found in the current window."}
