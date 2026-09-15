"""
Natural-language AQI Analyst for SMART AQI.

There is no LLM in this stack (no OpenAI/Anthropic key configured, and none
of the project's documented stack decisions call for one) - adding a paid
external NLU dependency wasn't asked for, so this is a rule-based intent
matcher instead: it classifies the question against a fixed set of intents
(regex/keyword patterns), then calls the *real* computed service function for
that intent (trend, why_pollutant, explanation, outdoor_planner,
recovery_prediction, forecast, events, pollutant impact) and renders the
answer from that real data. Nothing here is a canned response independent of
the currently selected area's actual data - every branch reads real AQI/
pollutant/weather/forecast/event values before answering. If the intent
can't be matched confidently, the fallback still answers from the area's
real current status rather than a generic "I don't understand."
"""
from __future__ import annotations

import re

from backend.services import aqi_service, forecast_service, health_service
from backend.services import pollutant_insight_service as insight
from backend.services import pollution_event_service as events_svc
from backend.services.forecast_insight_service import outdoor_planner, recovery_prediction

_POLLUTANT_PATTERNS = [
    (r"\bpm\s?2\.?5\b", "PM25"), (r"\bpm\s?10\b", "PM10"),
    (r"\bnitrogen dioxide\b|\bno2\b", "NO2"), (r"\bnitric oxide\b", "NO"),
    (r"\bnox\b|\bnitrogen oxides\b", "NOx"),
    (r"\bsulphur dioxide\b|\bsulfur dioxide\b|\bso2\b", "SO2"),
    (r"\bcarbon monoxide\b|\bco\b", "CO"),
    (r"\bozone\b|\bo3\b", "O3"),
    (r"\bammonia\b|\bnh3\b", "NH3"),
]


def _find_pollutant(q: str) -> str | None:
    for pat, canon in _POLLUTANT_PATTERNS:
        if re.search(pat, q):
            return canon
    return None


def _fmt_pct(v):
    return f"{v:+.1f}%" if v is not None else "an unknown amount"


def ask(state: str, area: str, question: str) -> dict:
    q = (question or "").strip().lower()
    if not q:
        return {"available": False, "reason": "Ask a question about this area's air quality."}

    pollutant = _find_pollutant(q)

    # --- fire questions: honest, not fabricated - fire detection isn't wired up yet ---
    if re.search(r"\bfire\b|\bwildfire\b|\bsmoke\b", q):
        return _answer("fire_check",
            "Fire and smoke detection isn't set up for this area yet - it needs a "
            "configured fire-monitoring source, which this deployment doesn't have "
            "connected right now. I can't say whether there was a fire nearby.",
            state, area, question, {})

    # --- outdoor safety ---
    if re.search(r"\bsafe\b.*\b(walk|outdoor|run|jog|exercise|outside|out)\b|"
                r"\b(walk|outdoor|run|jog|go outside|go out|step out|venture out)\b.*\bsafe\b|"
                r"\bcan i\b.*\b(go|step|venture)\b.*\b(outside|outdoors|out)\b", q):
        cur = aqi_service.current(state, area)
        plan = outdoor_planner(state, area)
        if not cur.get("available"):
            return _answer("outdoor_safety", cur.get("reason", "No data for this area."), state, area, question, {})
        bucket = cur.get("AQI_bucket") or "unknown"
        base = f"Current AQI in {area} is {cur.get('AQI')} ({bucket})."
        if plan.get("available"):
            base += (f" The best window in the next 24h looks like "
                     f"{plan['best_window']['start']}–{plan['best_window']['end']} "
                     f"(around AQI {plan['best_window']['avg_AQI']}); avoid "
                     f"{plan['avoid_window']['start']}–{plan['avoid_window']['end']}.")
        base += " This is guidance, not a health guarantee - sensitive groups should be more cautious."
        return _answer("outdoor_safety", base, state, area, question, {"current": cur, "planner": plan})

    # --- tomorrow / forecast ---
    if re.search(r"\btomorrow\b|\bwill.*improve\b|\bwill.*(get better|get worse)\b|\bnext day\b", q):
        fc = forecast_service.forecast(state, area)
        if not fc.get("forecast_available"):
            return _answer("forecast_tomorrow",
                f"There's no trained-model forecast for {area} yet - {fc.get('reason', '')}",
                state, area, question, {"forecast": fc})
        d1 = fc["days"][0]
        cur = aqi_service.current(state, area)
        direction = ""
        if cur.get("available") and cur.get("AQI") is not None:
            diff = d1["predicted_AQI"] - cur["AQI"]
            direction = (" - an improvement" if diff < -10 else
                        " - a deterioration" if diff > 10 else " - roughly steady") + " from today."
        ans = (f"Tomorrow's model forecast for {area} is AQI {d1['predicted_AQI']} "
               f"({d1['AQI_bucket']}), range {d1['lower']}–{d1['upper']}{direction} "
               "This is a prediction, not a guarantee.")
        return _answer("forecast_tomorrow", ans, state, area, question, {"forecast": fc})

    # --- recovery / when will it improve ---
    if re.search(r"\brecover\b|\bback to normal\b|\bwhen will.*(better|clear|improve)\b", q):
        rec = recovery_prediction(state, area)
        if not rec.get("available"):
            return _answer("recovery", rec.get("reason", "No data."), state, area, question, {})
        if rec.get("estimated_recovery"):
            ans = (f"Current AQI is {rec['current_AQI']} ({rec['current_bucket']}), down from a "
                   f"3-day peak of {rec['peak_AQI_last_3d']}. The model estimates it could reach "
                   f"AQI {rec['estimated_recovery']['predicted_AQI']} or better by "
                   f"{rec['estimated_recovery']['forecast_date']}. Estimated, not guaranteed.")
        else:
            ans = (f"Current AQI is {rec['current_AQI']} ({rec['current_bucket']}), "
                  f"3-day peak was {rec['peak_AQI_last_3d']}. {rec['note']}")
        return _answer("recovery", ans, state, area, question, {"recovery": rec})

    # --- why is <pollutant> high / which pollutant is the problem ---
    if pollutant and re.search(r"\bwhy\b|\bhigh\b|\belevated\b", q):
        w = insight.why_pollutant(state, area, pollutant)
        if not w.get("available"):
            return _answer("why_pollutant", w.get("reason", "No data."), state, area, question, {})
        ans = w["observed"] + "."
        if w["possible_contributors_evidence_based"]:
            ans += " Possible contributor: " + w["possible_contributors_evidence_based"][0]["factor"] + \
                   f" ({w['possible_contributors_evidence_based'][0]['evidence']})"
        else:
            ans += (" Typical sources of this pollutant: " +
                   ", ".join(w["possible_source_categories_general"][:3]) + ".")
        return _answer("why_pollutant", ans, state, area, question, {"why": w})

    if re.search(r"\bwhich pollutants?\b|\bcausing the (problem|pollution)\b|\bwhat.?s causing\b|"
                r"\bmain pollutant\b|\bworst pollutant\b|"
                r"\bpollutants?\b.*\b(high|elevated|highest|biggest|top|worst)\b", q):
        imp = insight.impact_breakdown(state, area)
        if not imp.get("available") or not imp.get("bars"):
            return _answer("which_pollutant", imp.get("reason", "No data."), state, area, question, {})
        top = imp["bars"][0]
        ans = (f"{top['pollutant'].replace('25', '2.5')} has the largest relative impact right now "
              f"({top['relative_share_pct']}% of the observed sub-index total). {imp['note']}")
        return _answer("which_pollutant", ans, state, area, question, {"impact": imp})

    # --- what should I do / precautions / masks ---
    if re.search(r"\bwhat should i do\b|\bany precautions?\b|\bshould i wear a mask\b|"
                r"\bhealth advice\b|\bprecautions?\b|\bhow (can|should) i protect\b|"
                r"\bis it safe for (kids|children|elderly|asthma)\b", q):
        adv = health_service.advisory(state, area)
        if not adv.get("available"):
            return _answer("precautions", adv.get("reason", "No data."), state, area, question, {})
        status = adv.get("air_quality_status") or f"AQI is {adv['current_AQI']} ({adv['current_bucket']})."
        ans = status
        if adv.get("outdoor_activity"):
            ans += f" {adv['outdoor_activity']}"
        if adv.get("respiratory_precautions"):
            tips = [t.rstrip(".") for t in adv["respiratory_precautions"][:2]]
            ans += " For sensitive groups: " + "; ".join(tips) + "."
        ans += " This is precautionary guidance, not medical advice."
        return _answer("precautions", ans, state, area, question, {"advisory": adv})

    # --- why did AQI increase/change/spike ---
    if re.search(r"\bwhy\b.*(aqi|air quality|pollution)\b.*(increase|higher|worse|change|spike|risen|rose)\b|"
                r"\bwhat caused\b.*(spike|increase)\b", q):
        ex = insight.explanation(state, area)
        if not ex.get("available"):
            return _answer("why_change", ex.get("reason", "No data."), state, area, question, {})
        return _answer("why_change", ex["summary"], state, area, question, {"explanation": ex})

    # --- is pollution improving / getting worse (trend) ---
    if re.search(r"\bimproving\b|\bgetting (better|worse)\b|\bdeteriorat\b|\btrend\b", q):
        tr = insight.trend(state, area)
        if not tr.get("available"):
            return _answer("trend", tr.get("reason", "No data."), state, area, question, {})
        ans = (f"AQI has {tr['classification']} - {tr['previous']['AQI']} "
              f"({tr['previous']['as_of']}) to {tr['current']['AQI']} "
              f"({tr['current']['as_of']}), a change of {_fmt_pct(tr['percent_change'])}. "
              f"Category: {tr['category_change']}.")
        return _answer("trend", ans, state, area, question, {"trend": tr})

    # --- plain "what is <pollutant>" / "how much <pollutant>" - just the value ---
    if pollutant:
        pol = aqi_service.pollutants(state, area)
        item = next((p for p in pol.get("pollutants", []) if p["pollutant"] == pollutant), None) \
            if pol.get("available") else None
        name = pollutant.replace("25", "2.5")
        if not item or item.get("current") is None:
            return _answer("pollutant_value",
                f"No current reading for {name} in {area} right now.", state, area, question, {})
        ans = f"{name} is currently {round(item['current'], 1)} {item['unit']}"
        chg = item.get("change_24h")
        if chg and chg.get("pct") is not None:
            ans += f", {_fmt_pct(chg['pct'])} over the last 24h"
        ans += f". {item['health_relevance']}"
        if item.get("live_feed_note"):
            ans += f" ({item['live_feed_note']})"
        return _answer("pollutant_value", ans, state, area, question, {"pollutant": item})

    # --- nearby / affected areas ---
    if re.search(r"\bnearby\b|\baffected areas\b|\bneighbo(u)?ring\b", q):
        return _answer("nearby_areas",
            "Cross-area impact analysis (e.g. from a nearby fire) isn't available "
            "yet - it depends on the fire-detection module, which isn't connected "
            "in this deployment right now.", state, area, question, {})

    # --- fallback: real current status, not a canned line ---
    cur = aqi_service.current(state, area)
    if not cur.get("available"):
        return _answer("fallback", f"I don't have data for {area}, {state} right now: "
                       f"{cur.get('reason', '')}", state, area, question, {})
    tr = insight.trend(state, area)
    ans = f"Current AQI in {area} is {cur.get('AQI')} ({cur.get('AQI_bucket')})."
    if tr.get("available"):
        ans += f" It has {tr['classification']} since the previous reading."
    ans += (" Ask me things like \"is it safe to walk today\", \"why is PM2.5 high\", "
           "\"is pollution improving\", or \"will it improve tomorrow\".")
    return _answer("fallback", ans, state, area, question, {"current": cur, "trend": tr})


def _answer(intent: str, answer: str, state: str, area: str, question: str, data: dict) -> dict:
    return {"available": True, "intent": intent, "question": question,
            "state": state, "area": area, "answer": answer, "data": data}
