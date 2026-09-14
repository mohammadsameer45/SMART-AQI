"""
Pollutant/AQI analytical layer for SMART AQI: trend classification, spike
detection, "why is this pollutant high", "why did AQI change", source-category
ranking and the relative-impact breakdown.

Every function here computes from real data already in aqi_service/
weather - nothing is fabricated. Where evidence is thin (too few live
readings, no weather station) the function says so explicitly rather than
guessing. Contributor/source lists are always labelled as *possible* -
general pollutant-chemistry associations or wind/weather evidence, never a
confirmed cause.
"""
from __future__ import annotations

from datetime import timedelta
from statistics import mean, pstdev
from typing import Any

from backend.config.aqi_categories import categorize
from backend.services import aqi_service, weather as weather_service
from backend.services.aqi_service import POLLUTANTS, POLLUTANT_SOURCE_HINTS
from backend.services.location_service import resolve_area
from backend.services.weather import dispersion_condition

# category -> pollutants whose presence/rise is typically associated with it
SOURCE_CATEGORY_MAP: dict[str, list[str]] = {
    "Traffic related": ["NO2", "NO", "NOx", "CO"],
    "Dust/construction": ["PM10"],
    "Biomass burning": ["PM25", "CO"],
    "Industrial emissions": ["SO2", "NH3"],
    "Atmospheric chemistry": ["O3"],
}

_STABLE_BAND = 10  # AQI points; matches health_service._direction's convention
_SPIKE_Z = 2.0
_SPIKE_PCT = 50.0
_RISE_PCT = 20.0        # "rising" pollutant threshold for explanation()/source_analysis()
_ELEVATED_PCT = 10.0    # lower bar used just for source-category ranking


def _asof(rec: dict) -> str:
    return rec.get("date") or (rec["ts"].isoformat() if rec.get("ts") else "")


def dispersion(state: str, area: str) -> dict:
    """Wind dispersion condition for the area (feature: Pollution Dispersion)."""
    w = weather_service.for_area(state, area)
    if not w.get("available"):
        return {"available": False, "reason": w.get("reason")}
    cur = w["current"]
    cond, kmh = dispersion_condition(cur.get("wind_speed"))
    return {
        "available": True,
        "state": state, "area": area,
        "as_of": w.get("as_of"),
        "wind_speed_ms": cur.get("wind_speed"),
        "wind_speed_kmh": kmh,
        "wind_direction": cur.get("wind_direction"),
        "wind_direction_deg": cur.get("wind_direction_deg"),
        "dispersion_condition": cond,
        "note": "Lower wind speeds may reduce pollutant dispersion and allow "
                "pollutants to accumulate. This is one contributing factor "
                "among several, not necessarily the sole cause of high AQI.",
    }


def _pollutant_series_value(rec_prior: dict | None, rec_latest: dict, pollutant: str):
    a = rec_prior.get(pollutant) if rec_prior else None
    b = rec_latest.get(pollutant)
    return a, b


def _area_series(resolved: dict) -> tuple[list[dict], str]:
    """(series, source_label) - historical daily if available, else live."""
    hist = aqi_service._pick_series_docs(resolved)
    if hist:
        return hist, "historical_daily"
    live = aqi_service._area_live_series(resolved)
    return live, "live_readings"


def why_pollutant(state: str, area: str, pollutant: str) -> dict:
    canon = pollutant.strip().upper().replace(".", "").replace(" ", "")
    canon = {"PM25": "PM25", "PM2_5": "PM25"}.get(canon, canon)
    if canon not in POLLUTANTS:
        return {"available": False,
                "reason": f"'{pollutant}' is not a supported pollutant."}

    resolved = resolve_area(state, area)
    series, source = _area_series(resolved)
    if len(series) < 2:
        return {"available": False,
                "reason": "Not enough readings yet to describe a trend for "
                          f"{canon} in this area."}

    latest = series[-1]
    target = latest["ts"] - timedelta(hours=24)
    earlier = [d for d in series if d["ts"] <= target]
    prior = min(earlier, key=lambda d: abs((d["ts"] - target).total_seconds())) \
        if earlier else series[-2]

    a, b = _pollutant_series_value(prior, latest, canon)
    if a is None or b is None:
        return {"available": False,
                "reason": f"No comparable {canon} readings in this area yet."}

    change = aqi_service._value_change(a, b)
    direction = "risen" if change["abs"] > 0 else ("fallen" if change["abs"] < 0 else "stayed flat")
    observed = (f"{canon} has {direction} from {a} to {b} "
                f"({change['pct']:+.1f}%)" if change["pct"] is not None else
                f"{canon} has {direction} from {a} to {b}")

    possible: list[dict] = []
    w = weather_service.for_area(state, area)
    if w.get("available") and change["abs"] > 0:
        cur = w["current"]
        cond, kmh = dispersion_condition(cur.get("wind_speed"))
        if cond == "Low":
            possible.append({
                "factor": "Low wind speed / stagnation",
                "evidence": f"Current wind speed is {cur.get('wind_speed')} m/s "
                            f"(~{kmh} km/h), classified as low-dispersion.",
                "basis": "measured (Open-Meteo)",
            })
        if canon == "O3" and cur.get("temperature") is not None and cur["temperature"] >= 30:
            possible.append({
                "factor": "Atmospheric conditions favouring ozone formation",
                "evidence": f"Current temperature is {cur['temperature']}°C; "
                            "higher temperatures and strong sunlight can "
                            "increase ground-level ozone formation.",
                "basis": "measured (Open-Meteo) + general atmospheric chemistry",
            })
        if cur.get("humidity") is not None and change["abs"] > 0 and canon in ("PM25", "PM10"):
            if cur["humidity"] >= 80:
                possible.append({
                    "factor": "High humidity",
                    "evidence": f"Current relative humidity is {cur['humidity']}%; "
                                "high humidity can promote particulate hygroscopic "
                                "growth and haze formation.",
                    "basis": "measured (Open-Meteo)",
                })

    return {
        "available": True,
        "pollutant": canon,
        "state": state, "area": area,
        "trend_source": source,
        "as_of": _asof(latest),
        "observed": observed,
        "from": a, "to": b, "change": change,
        "possible_contributors_evidence_based": possible,
        "possible_source_categories_general": POLLUTANT_SOURCE_HINTS.get(canon, []),
        "disclaimer": "Evidence-based contributors use measured wind/weather "
                       "data for this area right now. The general source "
                       "categories are typical sources for this pollutant, "
                       "not a claim about what caused this specific reading.",
    }


def trend(state: str, area: str) -> dict:
    resolved = resolve_area(state, area)
    series, source = _area_series(resolved)
    if len(series) < 2:
        return {"available": False,
                "reason": "Not enough data points to compute a trend."}

    latest = series[-1]
    if source == "live_readings":
        target = latest["ts"] - timedelta(hours=24)
        earlier = [d for d in series if d["ts"] <= target]
        prior = min(earlier, key=lambda d: abs((d["ts"] - target).total_seconds())) \
            if earlier else series[-2]
    else:
        prior = series[-2]

    if latest.get("AQI") is None or prior.get("AQI") is None:
        return {"available": False, "reason": "Missing AQI values for comparison."}

    diff = round(latest["AQI"] - prior["AQI"], 1)
    pct = round(100 * diff / prior["AQI"], 1) if prior["AQI"] else None

    if abs(diff) < _STABLE_BAND:
        classification, emoji = "stable", "\U0001F7E1"
    elif diff < 0:
        classification, emoji = "improved", "\U0001F7E2"
    else:
        classification, emoji = "deteriorated", "\U0001F534"

    main_pollutant, main_delta = None, 0.0
    for p in POLLUTANTS:
        a, b = prior.get(p), latest.get(p)
        if a is not None and b is not None and abs(b - a) > abs(main_delta):
            main_pollutant, main_delta = p, b - a

    return {
        "available": True,
        "state": state, "area": area,
        "source": source,
        "previous": {"as_of": _asof(prior), "AQI": prior["AQI"],
                     "AQI_bucket": categorize(prior["AQI"])},
        "current": {"as_of": _asof(latest), "AQI": latest["AQI"],
                    "AQI_bucket": categorize(latest["AQI"])},
        "absolute_change": diff,
        "percent_change": pct,
        "category_change": f"{categorize(prior['AQI'])} -> {categorize(latest['AQI'])}",
        "main_pollutant_change": ({"pollutant": main_pollutant,
                                   "delta": round(main_delta, 2)}
                                  if main_pollutant else None),
        "classification": classification,
        "emoji": emoji,
    }


def spike_detection(state: str, area: str) -> dict:
    """Rolling z-score + percentage-change spike detection on the area's live
    AQI series. Requires >=5 live readings; otherwise reports insufficient
    data rather than guessing from too little history."""
    resolved = resolve_area(state, area)
    series = aqi_service._area_live_series(resolved)
    points = [(d["ts"], d["AQI"]) for d in series if d.get("AQI") is not None]
    if len(points) < 5:
        return {"available": False,
                "reason": f"Not enough live readings yet for reliable spike "
                          f"detection (have {len(points)}, need >= 5)."}

    values = [v for _, v in points]
    latest_ts, latest_val = points[-1]
    baseline = values[-8:-1] if len(values) > 8 else values[:-1]
    baseline_mean = mean(baseline)
    baseline_std = pstdev(baseline) if len(baseline) > 1 else 0.0

    z = round((latest_val - baseline_mean) / baseline_std, 2) if baseline_std > 0 else None
    pct = round(100 * (latest_val - baseline_mean) / baseline_mean, 1) if baseline_mean else None
    spike = (z is not None and z >= _SPIKE_Z) or (pct is not None and pct >= _SPIKE_PCT)

    return {
        "available": True,
        "state": state, "area": area,
        "as_of": latest_ts.isoformat(),
        "latest_AQI": latest_val,
        "baseline_mean": round(baseline_mean, 1),
        "baseline_std": round(baseline_std, 2),
        "baseline_n": len(baseline),
        "z_score": z,
        "pct_change_vs_baseline": pct,
        "spike_detected": spike,
        "method": f"z-score >= {_SPIKE_Z} OR change >= {_SPIKE_PCT}% vs a "
                  f"rolling {len(baseline)}-point baseline mean",
        "series": [{"ts": t.isoformat(), "AQI": v} for t, v in points],
    }


def source_analysis(state: str, area: str) -> dict:
    poll = aqi_service.pollutants(state, area)
    if not poll.get("available"):
        return {"available": False, "reason": poll.get("reason")}

    elevated = [p["pollutant"] for p in poll["pollutants"]
                if p.get("change_24h") and p["change_24h"].get("pct") is not None
                and p["change_24h"]["pct"] >= _ELEVATED_PCT]

    scores: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    for cat, cat_pollutants in SOURCE_CATEGORY_MAP.items():
        hit = [p for p in elevated if p in cat_pollutants]
        if hit:
            scores[cat] = len(hit)
            evidence[cat] = [f"{p} up {next(pp['change_24h']['pct'] for pp in poll['pollutants'] if pp['pollutant'] == p)}% (24h)" for p in hit]

    disp = dispersion(state, area)
    if disp.get("available") and disp["dispersion_condition"] == "Low":
        scores["Weather/stagnation"] = scores.get("Weather/stagnation", 0) + 1
        evidence.setdefault("Weather/stagnation", []).append(
            f"wind {disp['wind_speed_ms']} m/s (low dispersion)")

    ranked = sorted(
        [{"category": c, "score": s, "based_on": evidence[c]} for c, s in scores.items()],
        key=lambda x: -x["score"])

    return {
        "available": True,
        "state": state, "area": area,
        "elevated_pollutants_24h": elevated,
        "ranked": ranked,
        "note": "Ranked by how many currently-elevated pollutants (>= "
                f"{_ELEVATED_PCT}% in 24h) are typically associated with "
                "each source category, plus wind-stagnation evidence. This "
                "is a chemistry-based heuristic, not a confirmed source "
                "attribution.",
    }


def impact_breakdown(state: str, area: str) -> dict:
    """'Relative observed impact' per pollutant: CPCB sub-index magnitude,
    normalised to a share of the total - explicitly not an official
    per-pollutant AQI contribution percentage."""
    from backend.config.aqi_breakpoints import compute_aqi

    resolved = resolve_area(state, area)
    live = aqi_service._live_current(resolved)
    if live:
        concentrations = live["pollutants"]
        as_of = live["as_of"]
    else:
        series = aqi_service._pick_series_docs(resolved)
        if not series:
            return {"available": False, "reason": "No data for this area."}
        latest = series[-1]
        concentrations = {p: latest.get(p) for p in POLLUTANTS}
        as_of = latest["date"]

    aqi, subs, note = compute_aqi(concentrations)
    if not subs:
        return {"available": False, "reason": note or "No sub-indices could be computed."}

    total = sum(subs.values()) or 1
    bars = sorted(
        [{"pollutant": p, "sub_index": v,
          "relative_share_pct": round(100 * v / total, 1)} for p, v in subs.items()],
        key=lambda x: -x["sub_index"])

    return {
        "available": True,
        "state": state, "area": area,
        "as_of": as_of,
        "AQI": aqi,
        "bars": bars,
        "label": "Relative observed impact",
        "note": ("Sub-index magnitude per pollutant (CPCB method); the "
                 "overall AQI equals the single largest sub-index. Shown "
                 "here for relative comparison across pollutants - not an "
                 "official per-pollutant AQI contribution percentage."
                 + (f" ({note})" if note else "")),
    }


def explanation(state: str, area: str) -> dict:
    """'Why is AQI high' dashboard module: current status + spike check +
    rising pollutants + wind context + ranked possible sources."""
    cur = aqi_service.current(state, area)
    if not cur.get("available"):
        return {"available": False, "reason": cur.get("reason")}

    spike = spike_detection(state, area)
    poll = aqi_service.pollutants(state, area)
    rising = []
    if poll.get("available"):
        for p in poll["pollutants"]:
            ch = p.get("change_24h")
            if ch and ch.get("pct") is not None and ch["pct"] >= _RISE_PCT:
                rising.append({"pollutant": p["pollutant"], "change_24h_pct": ch["pct"],
                               "from": ch["from"], "to": ch["to"]})
    rising.sort(key=lambda r: -r["change_24h_pct"])

    disp = dispersion(state, area)
    src = source_analysis(state, area)

    summary_parts = []
    bucket = cur.get("AQI_bucket")
    if bucket:
        summary_parts.append(f"Current AQI is {cur.get('AQI')} ({bucket}).")
    if spike.get("available") and spike.get("spike_detected"):
        summary_parts.append("An abnormal pollution spike was detected "
                             "relative to the recent baseline.")
    if rising:
        names = ", ".join(f"{r['pollutant']} (+{r['change_24h_pct']}%)" for r in rising[:3])
        summary_parts.append(f"Pollutants rising over the last ~24h: {names}.")
    if disp.get("available") and disp["dispersion_condition"] == "Low":
        summary_parts.append(f"Wind is low ({disp['wind_speed_ms']} m/s), which "
                             "may be limiting dispersion.")
    if not summary_parts:
        summary_parts.append("No abnormal spike or notably rising pollutants "
                             "detected in the available data.")

    return {
        "available": True,
        "state": state, "area": area,
        "current_AQI": cur.get("AQI"), "current_bucket": bucket,
        "spike": spike,
        "rising_pollutants_24h": rising,
        "wind": disp if disp.get("available") else None,
        "possible_sources_ranked": src.get("ranked", []) if src.get("available") else [],
        "summary": " ".join(summary_parts),
    }


def why_change(state: str, area: str, frm: str | None = None, to: str | None = None) -> dict:
    """AQI-change explanation between two points. Without explicit from/to
    dates, uses the same latest-vs-~24h-prior comparison as trend()."""
    resolved = resolve_area(state, area)
    series, source = _area_series(resolved)
    if len(series) < 2:
        return {"available": False, "reason": "Not enough data points."}

    if frm and to:
        rec_from = min(series, key=lambda d: abs((_parse(d) - _parse_date_str(frm)).days))
        rec_to = min(series, key=lambda d: abs((_parse(d) - _parse_date_str(to)).days))
    else:
        rec_to = series[-1]
        if source == "live_readings":
            target = rec_to["ts"] - timedelta(hours=24)
            earlier = [d for d in series if d["ts"] <= target]
            rec_from = min(earlier, key=lambda d: abs((d["ts"] - target).total_seconds())) \
                if earlier else series[-2]
        else:
            rec_from = series[-2]

    if rec_from.get("AQI") is None or rec_to.get("AQI") is None:
        return {"available": False, "reason": "Missing AQI values for comparison."}

    change = aqi_service._value_change(rec_from["AQI"], rec_to["AQI"])
    reasons = []
    for p in POLLUTANTS:
        a, b = rec_from.get(p), rec_to.get(p)
        if a is not None and b is not None and b > a:
            pc = aqi_service._value_change(a, b)
            reasons.append({"pollutant": p, **pc,
                            "source_categories": POLLUTANT_SOURCE_HINTS.get(p, [])})
    reasons.sort(key=lambda r: -(r["pct"] or 0))

    return {
        "available": True,
        "state": state, "area": area,
        "source": source,
        "from": {"as_of": _asof(rec_from), "AQI": rec_from["AQI"],
                "AQI_bucket": categorize(rec_from["AQI"])},
        "to": {"as_of": _asof(rec_to), "AQI": rec_to["AQI"],
              "AQI_bucket": categorize(rec_to["AQI"])},
        "change": change,
        "possible_reasons": reasons,
        "note": "Pollutants that increased between the two readings, shown "
                "as evidence for a role in the AQI change - not a confirmed "
                "single cause.",
    }


def _parse(rec: dict):
    return rec["ts"]


def _parse_date_str(s: str):
    from datetime import datetime, timezone
    return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
