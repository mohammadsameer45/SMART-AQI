"""
geolocate_stations.py  -  fuzzy-match the historical stations that did NOT match
a current CPCB station by exact name, so more of them get coordinates (and then
districts + weather).

Strategy
--------
The station name format is "<location>, <city> - <agency>". Exact matching in
ingest_cpcb_live.py fails when the agency suffix or a word in the location
differs. Here we:

  1. normalise: lowercase, drop the " - <agency>" suffix, strip punctuation
  2. for each unmatched historical station, find the best current CPCB station
     IN THE SAME STATE by difflib ratio on the normalised "<location> <city>"
  3. auto-apply matches at ratio >= 0.90; list 0.75-0.90 for review; the rest
     are treated as "not in the current feed" and keep no coordinates
     (honest - many are discontinued IMD/PCB stations).

Usage
-----
  python scripts/geolocate_stations.py            # dry run: show the matches
  python scripts/geolocate_stations.py --apply    # write coords for >= 0.90
  python scripts/geolocate_stations.py --apply --threshold 0.85
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import mongo_models as M  # noqa: E402

CPCB_JSON = ROOT / "data" / "metadata" / "cpcb_stations.json"


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.split(" - ")[0]                       # drop the agency suffix
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / len(ta | tb) if (ta | tb) else 0
    return round(0.6 * ratio + 0.4 * jacc, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.90)
    args = ap.parse_args()

    if not CPCB_JSON.exists():
        print("run scripts/ingest_cpcb_live.py first (need cpcb_stations.json)")
        return
    cpcb = [c for c in json.loads(CPCB_JSON.read_text(encoding="utf-8"))
            if c.get("lat") and c.get("lon")]
    by_state: dict[str, list[dict]] = {}
    for c in cpcb:
        by_state.setdefault((c.get("state") or "").strip(), []).append(c)

    unmatched = list(M.col(M.LOCATIONS).find(
        {"level": "station", "$or": [{"lat": None}, {"lat": {"$exists": False}}]},
        {"_id": 1, "station_id": 1, "station": 1, "state": 1, "city": 1}))
    print(f"{len(unmatched)} historical stations without coordinates\n")

    applied = review = nomatch = 0
    for d in unmatched:
        pool = by_state.get((d.get("state") or "").strip(), []) or cpcb
        best, best_s = None, 0.0
        for c in pool:
            s = _score(f'{d["station"]} {d.get("city","")}',
                       f'{c["station"]} {c.get("city","")}')
            if s > best_s:
                best, best_s = c, s

        tag = "no match"
        if best and best_s >= args.threshold:
            tag = f"APPLY  ({best_s})"
            applied += 1
            if args.apply:
                M.col(M.LOCATIONS).update_one(
                    {"_id": d["_id"]},
                    {"$set": {"lat": best["lat"], "lon": best["lon"],
                              "geolocated_by": "fuzzy_cpcb", "match_score": best_s,
                              "matched_station": best["station"]}})
        elif best and best_s >= 0.75:
            tag = f"review ({best_s})"
            review += 1
        else:
            nomatch += 1

        m = best["station"] if best else "-"
        print(f"  {d['station_id']:8} {d['station'][:42]:42} -> {tag:16} {m[:42]}")

    print(f"\n{'applied' if args.apply else 'would apply'}: {applied}  "
          f"| review 0.75-{args.threshold}: {review}  | no match: {nomatch}")
    if args.apply and applied:
        print("\nnow run:  python scripts/build_station_districts.py")
    elif not args.apply:
        print("\ndry run - add --apply to write coordinates")


if __name__ == "__main__":
    main()
