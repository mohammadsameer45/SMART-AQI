"""
Baseline health-advisory content for SMART AQI, keyed by CPCB AQI category.

This is informational decision-support content, NOT medical advice. The
"general" wording follows the health-impact statements published with the CPCB
National Air Quality Index; the "sensitive" wording adds standard precautionary
guidance for people with respiratory or cardiovascular sensitivity, children and
older adults. It never prescribes medication or dosage.

Phase 19 (Health Advisory Engine) expands this to per-audience rows for
children, older adults, people with asthma, people with cardiovascular
sensitivity, outdoor workers and people exercising outdoors, and blends in the
7-day forecast. The seed pipeline loads whatever rows are defined here.
"""
from __future__ import annotations

_DISCLAIMER = ("General precautionary guidance only. SMART AQI does not "
               "diagnose, treat or manage any medical condition. Follow the "
               "advice of your healthcare professional and local public-health "
               "authorities.")

# severity: 0 best .. 5 worst  (aligns with the six CPCB categories)
ADVISORIES: list[dict] = [
    # ---------------- Good ----------------
    {"aqi_bucket": "Good", "audience": "general", "severity": 0,
     "headline": "Air quality is good — enjoy normal outdoor activity.",
     "outdoor_activity": "No restrictions. Normal outdoor activity for everyone.",
     "guidance": [
         "Air quality poses little or no risk.",
         "Ventilate indoor spaces with fresh air where possible.",
     ]},
    {"aqi_bucket": "Good", "audience": "sensitive", "severity": 0,
     "headline": "Air quality is good — no special precautions needed.",
     "outdoor_activity": "Normal outdoor activity, including exercise.",
     "guidance": [
         "People with asthma or heart/lung conditions can follow their usual routine.",
         "Keep any prescribed reliever medication available as you normally would.",
     ]},

    # ------------- Satisfactory -------------
    {"aqi_bucket": "Satisfactory", "audience": "general", "severity": 1,
     "headline": "Air quality is acceptable.",
     "outdoor_activity": "Normal outdoor activity for the general population.",
     "guidance": [
         "May cause minor breathing discomfort to unusually sensitive people.",
         "No action needed for most people.",
     ]},
    {"aqi_bucket": "Satisfactory", "audience": "sensitive", "severity": 1,
     "headline": "Mostly fine — very sensitive individuals should stay aware.",
     "outdoor_activity": "Outdoor activity is generally fine; monitor how you feel.",
     "guidance": [
         "A few people who are unusually sensitive may notice minor breathing discomfort.",
         "If you have asthma, keep your reliever inhaler with you as usual.",
         "Reduce exertion if you notice coughing or shortness of breath.",
     ]},

    # ---------------- Moderate ----------------
    {"aqi_bucket": "Moderate", "audience": "general", "severity": 2,
     "headline": "Acceptable for most, but sensitive groups should take care.",
     "outdoor_activity": "General population can continue normal activity; "
                         "consider easing very strenuous prolonged outdoor exertion.",
     "guidance": [
         "May cause breathing discomfort to people with lung conditions such as "
         "asthma, and to people with heart disease, children and older adults.",
         "Take breaks during prolonged or heavy outdoor exertion.",
     ]},
    {"aqi_bucket": "Moderate", "audience": "sensitive", "severity": 2,
     "headline": "Sensitive groups: reduce prolonged or heavy outdoor exertion.",
     "outdoor_activity": "Shorten and lighten strenuous outdoor activity; "
                         "prefer less-polluted times of day and routes away from traffic.",
     "guidance": [
         "People with asthma or respiratory sensitivity may experience breathing discomfort.",
         "Keep prescribed medication available and use it as directed by your healthcare professional.",
         "Watch for symptoms such as coughing, wheezing or breathlessness and rest if they appear.",
         "Children and older adults should take more frequent breaks outdoors.",
     ]},

    # ------------------ Poor ------------------
    {"aqi_bucket": "Poor", "audience": "general", "severity": 3,
     "headline": "Reduce prolonged or heavy outdoor activity.",
     "outdoor_activity": "Cut back on prolonged or heavy outdoor exertion; "
                         "move longer workouts indoors where possible.",
     "guidance": [
         "May cause breathing discomfort to most people on prolonged exposure.",
         "Keep windows closed during peak traffic hours; ventilate when air improves.",
     ]},
    {"aqi_bucket": "Poor", "audience": "sensitive", "severity": 3,
     "headline": "Sensitive groups: avoid prolonged outdoor exertion.",
     "outdoor_activity": "Avoid prolonged or heavy outdoor exertion; "
                         "choose indoor alternatives.",
     "guidance": [
         "People with asthma, respiratory or heart conditions may feel discomfort more strongly.",
         "Keep prescribed medication with you and follow your healthcare professional's directions.",
         "Monitor symptoms closely; seek medical advice if breathing problems persist or worsen.",
         "Consider a well-fitted mask rated for fine particles if you must be outdoors for long.",
     ]},

    # --------------- Very Poor ---------------
    {"aqi_bucket": "Very Poor", "audience": "general", "severity": 4,
     "headline": "Avoid prolonged outdoor exertion.",
     "outdoor_activity": "Avoid prolonged outdoor exertion; keep outdoor time short.",
     "guidance": [
         "Prolonged exposure may cause respiratory illness.",
         "Keep indoor air clean: close windows, and run an air purifier if available.",
     ]},
    {"aqi_bucket": "Very Poor", "audience": "sensitive", "severity": 4,
     "headline": "Sensitive groups: stay indoors as much as possible.",
     "outdoor_activity": "Stay indoors where you can; postpone outdoor exercise.",
     "guidance": [
         "Effects are more pronounced in people with lung and heart disease.",
         "Keep prescribed medication accessible and use it as directed by your healthcare professional.",
         "Have a plan for worsening symptoms and know when to seek medical care.",
         "Children and older adults should remain indoors during peak pollution.",
     ]},

    # ----------------- Severe -----------------
    {"aqi_bucket": "Severe", "audience": "general", "severity": 5,
     "headline": "Minimise outdoor exposure.",
     "outdoor_activity": "Minimise time outdoors; avoid outdoor exertion.",
     "guidance": [
         "May affect healthy people and seriously impact those with existing disease.",
         "Follow advisories from local and public-health authorities.",
         "Keep indoor air as clean as possible and limit activities that add indoor pollution.",
     ]},
    {"aqi_bucket": "Severe", "audience": "sensitive", "severity": 5,
     "headline": "Sensitive groups: remain indoors and limit all exertion.",
     "outdoor_activity": "Remain indoors; avoid any outdoor physical activity.",
     "guidance": [
         "Respiratory effects may occur even with light physical activity.",
         "Keep prescribed medication close and follow your healthcare professional's directions.",
         "Seek prompt medical attention for breathing difficulty, chest tightness or persistent cough.",
         "Where available, use a clean-air room and a particulate air purifier.",
     ]},
]

for _a in ADVISORIES:
    _a["disclaimer"] = _DISCLAIMER
    _a["source"] = "CPCB National Air Quality Index health-impact statements + standard precautionary guidance"
