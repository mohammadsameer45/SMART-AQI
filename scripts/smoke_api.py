"""Quick end-to-end smoke test of the SMART AQI API (expects it running on :5000)."""
from __future__ import annotations

import sys
import requests

B = "http://127.0.0.1:5000/api"
PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    cond = bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    PASS += cond
    FAIL += not cond


s = requests.Session()

h = s.get(f"{B}/health").json()
check("health", h["ok"] and h["data"]["mongo_ok"], h["data"]["mongo"])

email = "smoke_user@example.com"
pw = "Str0ng#Pass1"
r = s.post(f"{B}/auth/register", json={"name": "Smoke User", "email": email,
           "password": pw, "confirm_password": pw})
if r.status_code == 409:
    r = s.post(f"{B}/auth/login", json={"email": email, "password": pw})
d = r.json()
check("auth register/login", d["ok"] and "token" in d["data"], r.status_code)
tok = d["data"]["token"]
H = {"Authorization": f"Bearer {tok}"}

check("weak password rejected",
      s.post(f"{B}/auth/register", json={"name": "X Y", "email": "w@e.com",
             "password": "weak", "confirm_password": "weak"}).status_code == 400)
check("no token -> 401", s.get(f"{B}/states").status_code == 401)
check("bad token -> 401",
      s.get(f"{B}/states", headers={"Authorization": "Bearer nope"}).status_code == 401)

me = s.get(f"{B}/auth/me", headers=H).json()
check("me", me["ok"] and me["data"]["user"]["email"] == email)

states = s.get(f"{B}/states", headers=H).json()["data"]
check("states list", len(states) == 21, f"{len(states)} states")

da = s.get(f"{B}/states/Delhi/districts", headers=H).json()["data"]
check("Delhi areas", da["level"] in ("district", "city") and len(da["items"]) > 0,
      f"{da['level']}: {da['items'][:3]}")

check("unknown state -> 404",
      s.get(f"{B}/states/Atlantis/districts", headers=H).status_code == 404)

cur = s.get(f"{B}/aqi/current/Delhi/Delhi", headers=H).json()["data"]
check("current Delhi", cur["available"] and cur["AQI"] is not None,
      f"AQI={cur.get('AQI')} {cur.get('AQI_bucket')} as_of={cur.get('as_of')}")

hist = s.get(f"{B}/aqi/history/Delhi/Delhi?from=2019-01-01&to=2019-03-31",
             headers=H).json()["data"]
check("history window", hist["count"] > 0 and hist["count"] < 120,
      f"{hist['count']} points")

pol = s.get(f"{B}/pollutants/Delhi/Delhi", headers=H).json()["data"]
check("pollutants", pol["available"] and len(pol["pollutants"]) == 9)

fc = s.get(f"{B}/aqi/forecast/Delhi/Delhi", headers=H).json()["data"]
check("forecast Delhi", fc["forecast_available"] and len(fc["days"]) == 7,
      f"model={fc.get('model')}")

fc2 = s.get(f"{B}/aqi/forecast/Mizoram/Aizawl", headers=H).json()["data"]
check("forecast unavailable handled",
      fc2["forecast_available"] is False and "reason" in fc2)

adv = s.get(f"{B}/health-advisory/Delhi/Delhi", headers=H).json()["data"]
check("health advisory", adv["available"] and adv["current_bucket"] and
      isinstance(adv["respiratory_precautions"], list),
      f"bucket={adv.get('current_bucket')} tomorrow={bool(adv.get('tomorrow_risk'))}")

mm = s.get(f"{B}/model-metrics", headers=H).json()["data"]
check("model metrics", len(mm["models"]) == 4 and mm["best_model"],
      f"best={mm['best_model']}")

mi = s.get(f"{B}/model-insights/lstm", headers=H).json()["data"]
check("model insights", mi["model"] == "lstm" and mi["actual_vs_predicted"],
      f"{len(mi['actual_vs_predicted'])} points")

dash = s.get(f"{B}/dashboard/Delhi/Delhi", headers=H).json()["data"]
check("dashboard composite",
      all(k in dash for k in ("current", "history_90d", "forecast", "advisory")),
      f"history={len(dash['history_90d'])}")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
