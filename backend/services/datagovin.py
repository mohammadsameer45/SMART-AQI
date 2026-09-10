"""
Client for the data.gov.in CPCB real-time Air Quality Index resource
(3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69).

Returns one dict per monitoring station with its coordinates, the latest
per-pollutant reading and a CPCB-method AQI computed from those readings. Used
by the ingest script (offline) — never called from the browser.
"""
from __future__ import annotations

import json as _json
import shutil
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from backend.config import config
from backend.config.aqi_breakpoints import POLLUTANT_ID_MAP, compute_aqi

BASE = "https://api.data.gov.in/resource/"
# data.gov.in serves small pages fast but stalls on large ones — keep it small.
PAGE = 200


def _num(v: Any):
    if v in (None, "", "NA", "NaN", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_ts(s: str):
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _get_page(offset: int, retries: int = 5, timeout: int = 90) -> dict:
    """One page via curl. `requests`/`urllib` time out against this host on
    Windows even when curl succeeds in <1s, so curl is the transport."""
    if not shutil.which("curl"):
        raise RuntimeError("curl is required to reach data.gov.in from here")
    qs = urllib.parse.urlencode({
        "api-key": config.DATA_GOV_IN_API_KEY, "format": "json",
        "limit": PAGE, "offset": offset})
    url = f"{BASE}{config.DATA_GOV_IN_AQI_RESOURCE}?{qs}"
    last = ""
    for attempt in range(retries):
        try:
            p = subprocess.run(
                ["curl", "-sS", "-m", str(timeout), "--retry", "2", url],
                capture_output=True, text=True, timeout=timeout + 20)
            if p.returncode == 0 and p.stdout.strip():
                return _json.loads(p.stdout)
            last = (p.stderr or p.stdout or "").strip()[:200]
        except Exception as e:                               # noqa: BLE001
            last = str(e)[:200]
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"data.gov.in page offset={offset} failed: {last}")


def fetch_raw() -> list[dict]:
    if not config.DATA_GOV_IN_API_KEY:
        raise RuntimeError("DATA_GOV_IN_API_KEY not set in backend/.env")
    first = _get_page(0)
    total = int(first.get("total", 0))
    out = list(first.get("records", []))
    offset = PAGE
    while offset < total:
        page = _get_page(offset)
        recs = page.get("records", [])
        if not recs:
            break
        out.extend(recs)
        offset += PAGE
    return out


def stations() -> list[dict]:
    """Pivot the raw pollutant rows into one record per station."""
    raw = fetch_raw()
    by_stn: dict[str, dict] = {}
    for rec in raw:
        name = (rec.get("station") or "").strip()
        if not name:
            continue
        st = by_stn.setdefault(name, {
            "station": name,
            "state": (rec.get("state") or "").strip(),
            "city": (rec.get("city") or "").strip(),
            "lat": _num(rec.get("latitude")),
            "lon": _num(rec.get("longitude")),
            "last_update": rec.get("last_update"),
            "pollutants": {},
        })
        canon = POLLUTANT_ID_MAP.get((rec.get("pollutant_id") or "").strip())
        val = _num(rec.get("avg_value"))
        if canon and val is not None:
            # The data.gov.in CAAQMS feed reports every gas in ug/m3, including
            # CO, but the CPCB AQI CO sub-index breakpoints are defined in
            # mg/m3. Convert so CO does not spuriously dominate the AQI.
            if canon == "CO":
                val = val / 1000.0
            st["pollutants"][canon] = val

    result = []
    for st in by_stn.values():
        aqi, subs, note = compute_aqi(st["pollutants"])
        st["ts"] = _parse_ts(st["last_update"])
        st["AQI"] = aqi
        st["AQI_subindices"] = subs
        st["AQI_note"] = note
        result.append(st)
    return result
