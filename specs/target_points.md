# Spec: Target Income Points (with IRMAA cost)

**Status:** Implemented on the Income and EMR pages
**Covers:** the `irmaa` and `target_points` services, an IRMAA component in `total_cost`, two
target-points routes, and a shared Target Points card with a Tax Map overlay.

---

## Purpose

Given a maximum acceptable effective marginal rate (EMR), find the **target income points**:
the last income before each stretch where the EMR rises above the maximum (SS torpedo, LTCG
stacking, ACA subsidy loss, IRMAA cliffs, higher brackets). For each segment between
targets, report its **average EMR**, and list the segments whose average is at or below the
maximum ("desirable income").

The question it answers: *if I push through a bump, torpedo or cliff, what does that extra
segment of income cost on average, and is it under my maximum?* It is not a question about
the overall effective rate from the first dollar; blending cheap early income into the
average hides what the decision costs.

The method follows Wade Pfau's tax map approach (Advisor Perspectives, "Managing Taxes in
Retirement using the Effective Marginal Tax Rate"). Points taken from it:

- Targets are where the EMR crosses from at or below the maximum to above it.
- A segment's average includes the costly stretch inside it.
- Segments chain: after accepting one, the next is tested from its end.
- When the next segment is too costly, later targets are also tested ("an undesirable dollar
  must be taken to access a larger pool of desirable dollars").
- IRMAA is counted in the year of the income that causes it, although it is billed later.

---

## Definitions

- **Cost at a point** = `total_tax + aca_subsidy_loss + irmaa_surcharge`, annual dollars,
  cumulative from the sweep start. `total_tax` holds federal, NIIT and Ohio, so the maximum
  applies to whatever the request includes: leaving Ohio out removes only the Ohio part.
- **Point rate**: the point's `total_cost_emr`, measured over a window wide enough to be
  free of rounding noise. A cliff shows as a very large rate.
- **Costly point**: its rate is above the maximum. A run of costly points is a candidate
  stretch.
- **Stretch**: a run that begins at its first segment whose own cost rate really exceeds the
  maximum (the point rate looks ahead, so a run can begin early). A run with no such segment
  is rounding noise. A stretch must also cost at least `target_min_excess_cost` dollars more
  than the maximum rate would, summed over its costly segments; smaller ones open no target.
- **Target**: the sweep's first income, the start of each stretch, and the sweep's last
  income.
- **Average of a span** = Δcost ÷ Δincome across it, stretch included. Compared unrounded
  with the maximum, so a rate just over it is never let through.

### Which segments are listed

Walk the targets from the first. At each position:

1. If the span to the next target averages at or below the maximum, it is a **leg**.
2. Otherwise, if some later target's average from the position is at or below the maximum,
   the **farthest** such target ends the leg (the stretch is paid to reach cheaper income).
3. Otherwise the walk **stops**. Income beyond cannot be reached without paying a segment
   nothing recovers, so it is not desirable.

Two further sets, shown only when the user asks:

- **Over max**: every span between neighbouring targets averaging above the maximum.
- **Unreachable**: spans between neighbouring targets averaging at or below the maximum that
  lie past the point where the walk stopped. They are only reached by paying an over-max
  span, which can still be worth it for a short bump.

---

## Layering

| Layer | Change |
|---|---|
| Data | `data/irmaa/irmaa_{year}.json`: monthly Part B and Part D surcharge per tier, with threshold rounding and top-tier indexing rules. Tier thresholds stay in `federal_{year}.json`. |
| Config | `config.json`: `target_emr_rate_default`, `target_min_excess_cost`. |
| Service | `services/irmaa.py`: surcharge from MAGI. `services/total_cost.py`: IRMAA component. `services/target_points.py`: finds targets and segments. |
| API | `api/routers/target_points.py`: thin wrapper, two routes. |
| UI | `target-points.js` (helpers), `target-points-panel.js` (shared card), both pages. |

Services never import from `api/`. `target_points` composes `total_cost`; its pure core
works on a list of cost points so it can be tested and used alone.

---

## IRMAA service

`services/irmaa.py` returns the annual Part B + Part D surcharge for a MAGI:

- The tier is the number of thresholds that MAGI is strictly above. The top tier starts at
  its threshold.
- **Lookback.** IRMAA in year Y+N is set by the MAGI of year Y. The thresholds that apply
  are those of the premium year, which are not yet known, so the year's thresholds are
  grown by `irmaa_inflation_default` compounded over `irmaa_lookback_years`, rounded as the
  data file says, with the top threshold not indexed. The request can override the rate or
  turn the growth off (rate 0).
- **Enrollees** is an explicit number of people, not derived from the 65+ flags: income two
  years before enrollment is what counts. Default is the filing status's filer count.
- MAGI is AGI plus tax-exempt interest.
- Surcharge amounts come from the planning year's file and are not inflated.

### Boundary points

The sweep needs a point at the income where MAGI equals each threshold and one just above
it. Taxable Social Security makes MAGI nonlinear in the sweep, so the crossing is found by
bisection. The points go to `calculate_emr` as extra boundary points, like the ACA ones.

---

## Target points service

`services/target_points.py`:

- `find_target_points(points, max_rate, min_excess)` is pure. Input is a list of
  `CostPoint(income, cost, rate, causes)`. Output is a `TargetPointsResult`:
  - `targets`: incomes.
  - `legs`: `from_income`, `to_income`, `average_emr`, `cost`, `causes`. Desirable only.
  - `over_max_legs` and `unreachable_legs`, as defined above.
  - `irmaa_thresholds`: the thresholds for the requested growth, so a chart draws its
    IRMAA lines where the targets were placed.
- `calculate_target_points(...)` runs `calculate_total_cost` and passes the points through.
  IRMAA thresholds are reported even when IRMAA is left out.
- Causes come from the EMR components: bracket (only when above the maximum), ss_torpedo,
  pref_stacking, niit, aca, irmaa.

Cost is whole-dollar rounded, so the rate between two close points is noisy. That is why a
point's own windowed rate decides whether a stretch is costly, the cost between points only
places where it begins, and `target_min_excess_cost` drops stretches too small to matter.

---

## API

- `POST /api/target-points`: the income-plan request (withdrawals folded in) plus the
  settings. For the Income page.
- `POST /api/total-cost/target-points`: the total-cost sweep request plus the settings. For
  the EMR page.

Settings: `max_emr`, `include_irmaa`, `irmaa_enrollees`, `irmaa_inflation_rate`. Both
routes share one response: `targets`, `legs`, `over_max_legs`, `unreachable_legs`,
`irmaa_thresholds`, `max_emr`, `filing_status`, `tax_year`. Routers convert and return; no
logic. An invalid sweep mode or negative maximum is a 422.

---

## UI

One card, one panel (`createTargetPanel`), the same element ids on both pages:

1. **Max EMR** input, defaulted from `/api/config`.
2. **Include IRMAA**, **Medicare enrollees**, and the IRMAA growth controls (on the EMR page
   these live in the chart toolbar).
3. **Show segments over max** (off by default). Adds the over-max segments (red) and the
   unreachable ones (labelled "Past an over-max span", green) to the table and the chart,
   without a new request.
4. **Table** in income order: From, To (target), Average EMR, Added cost, Includes.
5. **Tax Map overlay** with an on/off checkbox: dots on the max-EMR line at each target, a
   solid green line per desirable leg labelled with its average, and, when the extra
   segments are on, dotted red and dotted green lines for those.
6. A note when no tier lies inside the sweep range, and when no leg is within the maximum.

The IRMAA lines on the chart use the thresholds the targets were placed with, so lines and
targets agree. Target settings are not saved with scenarios. Changing the Ohio or ACA
inclusion needs a new Run Analysis; the card does not recalculate on its own.

---

## Tests

- `tests/unit/test_irmaa.py`, `test_total_cost_irmaa.py`: tiers, enrollees, growth, boundary
  points.
- `tests/unit/test_target_points.py`: the pure algorithm, including noise, skip-ahead,
  unreachable legs and the minimum excess. `test_target_points_compose.py`: the composition.
- `tests/functional/test_target_points_route.py`: both routes with real data.
- `tests/scenarios/test_scenario_target_points_irmaa_single.py`: hand-verified targets and
  legs; `test_scenario_irmaa_surcharges_data.py`: surcharge data against the published
  tables.
- `tests/js/target-points.test.js`: helpers, both pages. Regenerate fixtures with
  `python3 tests/js/fixtures.py`.

---

## Open items

- Whether surcharge amounts should be inflated like the thresholds.
- Whether the default sweep ceiling should extend to the top IRMAA tier; a range hint says
  when tiers lie above it.
- Persisting target settings in scenarios.
- Combined average across an over-max bump and the green segments past it, as one decision.
- The Ohio data for the newest year is a placeholder until the state publishes its figures.
