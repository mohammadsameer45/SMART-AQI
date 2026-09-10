"""
refresh_worker.py  -  keep the CPCB live feed current.

Runs the two live-data steps on a fixed interval:

  1. scripts/ingest_cpcb_live.py       pull ~500 stations from data.gov.in
  2. scripts/build_station_districts.py point-in-polygon any new coordinates

Each cycle's outcome is written to the `meta` collection
(`_id = "live_refresh"`) so `GET /api/live/status` can report freshness, and to
`data/validation/live_refresh.log`.

Usage
-----
  python scripts/refresh_worker.py                 # loop forever, every 45 min
  python scripts/refresh_worker.py --interval 30   # every 30 min
  python scripts/refresh_worker.py --once          # single cycle then exit
                                                   #   (for Windows Task
                                                   #    Scheduler / cron)

Run it as its own long-lived process, separate from the Flask API.
"""
from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import config  # noqa: E402
from backend.models import mongo_models as M  # noqa: E402

LOG = ROOT / "data" / "validation" / "live_refresh.log"
STEP_TIMEOUT = 600
_stop = False


def _sig(_s, _f):
    global _stop
    _stop = True
    _log("stop signal received; finishing current cycle then exiting")


def _log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _run_step(script: str) -> tuple[bool, str]:
    t0 = time.time()
    try:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            capture_output=True, text=True, timeout=STEP_TIMEOUT, cwd=ROOT)
        ok = p.returncode == 0
        tail = (p.stdout or "").strip().splitlines()[-1:] or \
               (p.stderr or "").strip().splitlines()[-1:]
        return ok, f"{script} {'ok' if ok else 'FAILED'} in " \
                   f"{time.time() - t0:.0f}s :: {tail[0] if tail else ''}"
    except subprocess.TimeoutExpired:
        return False, f"{script} TIMEOUT after {STEP_TIMEOUT}s"
    except Exception as e:                            # noqa: BLE001
        return False, f"{script} error: {e}"


def _cycle() -> dict:
    started = datetime.now(timezone.utc)
    _log("--- refresh cycle start ---")
    ok1, m1 = _run_step("ingest_cpcb_live.py")
    _log("  " + m1)
    ok2, m2 = (False, "skipped (ingest failed)")
    if ok1:
        ok2, m2 = _run_step("build_station_districts.py")
        _log("  " + m2)

    try:
        stations = M.col("cpcb_live").estimated_document_count()
        with_aqi = M.col("cpcb_live").count_documents({"AQI": {"$ne": None}})
    except Exception:                                 # noqa: BLE001
        stations = with_aqi = None

    status = {
        "_id": "live_refresh",
        "last_run": started,
        "finished_at": datetime.now(timezone.utc),
        "ok": bool(ok1 and ok2),
        "ingest": m1, "district_join": m2,
        "cpcb_live_stations": stations,
        "cpcb_live_with_aqi": with_aqi,
    }
    try:
        M.col("meta").replace_one({"_id": "live_refresh"}, status, upsert=True)
    except Exception as e:                            # noqa: BLE001
        _log(f"  [warn] could not write meta.live_refresh: {e}")
    _log(f"--- cycle done: ok={status['ok']} stations={stations} ---")
    return status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int,
                    default=config.LIVE_REFRESH_MINUTES,
                    help="minutes between cycles (default from LIVE_REFRESH_MINUTES)")
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = ap.parse_args()

    if not config.DATA_GOV_IN_API_KEY:
        _log("DATA_GOV_IN_API_KEY not set — nothing to refresh. Exiting.")
        sys.exit(1)

    signal.signal(signal.SIGINT, _sig)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _sig)

    if args.once:
        s = _cycle()
        sys.exit(0 if s["ok"] else 2)

    _log(f"worker started — cycle every {args.interval} min "
         f"(Ctrl+C to stop)")
    while not _stop:
        _cycle()
        for _ in range(args.interval * 60):
            if _stop:
                break
            time.sleep(1)
    _log("worker stopped.")


if __name__ == "__main__":
    main()
