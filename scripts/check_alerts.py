"""
check_alerts.py  -  evaluate every user's AQI threshold alert against the
current (post-refresh) data and Web Push-notify newly-triggered ones.

Run after a live-data refresh so alerts reflect the data that was just
pulled; scripts/refresh_worker.py does this each cycle. Also runnable
standalone for Task Scheduler / cron, or by hand to test the push wiring.

Usage:  python scripts/check_alerts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import alert_service, push_service  # noqa: E402


def main() -> None:
    if not push_service.configured():
        print("VAPID keys not configured (backend/.env) — skipping. "
              "Run scripts/generate_vapid_keys.py first.")
        return
    result = alert_service.check_and_notify_all()
    print(f"checked {result['checked']} alert rule(s), "
         f"sent {result['notified']} new push notification(s).")


if __name__ == "__main__":
    main()
