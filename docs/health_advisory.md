# SMART AQI — Health Advisory Methodology

## What it is

A decision-support layer that turns the current AQI category (and the near-term
forecast) into plain-language precautionary guidance. **It is not a medical
device.** It does not diagnose, treat or manage asthma or any condition, and it
never prescribes medication or dosage. Every payload carries a disclaimer to
that effect.

## Inputs

- Current AQI + CPCB category for the resolved area (`aqi_service.current`)
- The 7-day forecast when available (`forecast_service.forecast`) — used for
  "Tomorrow's risk" and the "7-day outlook"
- Audience: `general` and `sensitive` (people with respiratory or
  cardiovascular sensitivity, children, older adults)

## Content source

`backend/config/health_advisories_seed.py` — six CPCB categories × two
audiences. The `general` wording follows the **health-impact statements
published with the CPCB National Air Quality Index**; the `sensitive` wording
adds standard public-health precautionary phrasing (reduce/avoid prolonged
exertion, keep prescribed medication available *as directed by your healthcare
professional*, monitor symptoms, prefer indoor alternatives, consider a
particulate-rated mask, use a clean-air room / purifier where available).

Seeded into the `health_advisories` collection
(`_id = "<bucket>:<audience>"`), so the content can be revised without a code
change.

## Output (`GET /api/health-advisory/:state/:area`)

| Field | Meaning |
|---|---|
| `current_AQI`, `current_bucket`, `severity` (0–5) | current status |
| `air_quality_status` | one-line headline for the category |
| `who_should_take_care[]` | audience list, widened at Poor+ to outdoor workers and people exercising outdoors |
| `outdoor_activity` | activity recommendation for the general population |
| `respiratory_precautions[]` | the `sensitive` guidance bullets |
| `cards.general`, `cards.sensitive` | full advisory objects |
| `tomorrow_risk` | day-+1 predicted AQI, bucket, direction (improving/steady/worsening) and the matching sensitive advisory |
| `seven_day_outlook` | per-day buckets + worst day |
| `disclaimer` | the non-medical disclaimer, always present |

## UI

`frontend/src/pages/HealthAdvisory.jsx` renders the cards: **Air Quality
Status**, **Who should take extra care?**, **Outdoor Activity Recommendation**,
**Respiratory Precautions**, **Tomorrow's Risk**, **7-Day Health Outlook**, with
the disclaimer pinned at the bottom. Wording stays precautionary
("General precautionary guidance", "as directed by your healthcare
professional") — never "treatment".

## Roadmap

Phase 19 expansion: separate rows for children, older adults, people with
asthma, people with cardiovascular sensitivity, outdoor workers and people
exercising outdoors; pollutant-specific notes (e.g. high O₃ on sunny
afternoons); and AQI-trend-aware phrasing.
