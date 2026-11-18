# Spec: Target Income Points (with IRMAA cost)

**Status:** Draft, for review
**Covers:** new `irmaa` and `target_points` services, a `target_points` router, an IRMAA
component in `total_cost`, and a Target Points table and Tax Map overlay on `income.html`.

---

## Purpose

Given a maximum acceptable effective marginal rate (EMR), find the **target income points**:
the last income before each stretch where the EMR rises above the maximum (SS torpedo,
LTCG stacking, ACA cliff, IRMAA cliffs). Report the **average EMR of each leg** between
consecutive targets, and list only the legs whose average is at or below the maximum
("desirable income").

Modeled on the Tax Map exhibit used in retirement tax planning seminars: black dots on the
max-EMR line, a green line per desirable leg labelled with its average rate.

---

## Definitions

- **Cost at a point** = `total_tax + aca_subsidy_loss + irmaa_surcharge`, all in annual
  dollars and cumulative from the sweep floor. `total_tax` already holds federal, NIIT and
  Ohio.
- **Segment EMR** between adjacent sweep points = Δcost ÷ Δincome. Using cost, not the
  per-point EMR field, makes cliffs exact: a cliff is a segment whose Δcost is large over a
  $1 step.
- **Hot segment**: segment EMR above the max EMR.
- **Hot zone**: a run of adjacent hot segments.
- **Target point**: the income at the start of each hot zone, plus the sweep floor and the
  sweep ceiling.
- **Leg**: the span between two consecutive targets. Its **average EMR** is
  Δcost ÷ Δincome across the whole leg, including the hot zone it contains.
- **Desirable leg**: a leg whose average EMR is at or below the max EMR. Others are not
  returned.

---

## Layering

| Layer | Change |
|---|---|
| Data | `data/irmaa/irmaa_{year}.json` (new): monthly Part B and Part D surcharge per tier, per filing status. Tier thresholds stay in `federal_{year}.json`. |
| Config | `config.json`: `target_emr_rate_default`. |
| Service | `services/irmaa.py` (new): surcharge from MAGI. `services/total_cost.py`: adds `irmaa_surcharge` and `emr_irmaa`. `services/target_points.py` (new): finds targets and legs. |
| API | `api/routers/target_points.py` (new): thin wrapper. |
| UI | `income.html`: Max EMR input, Target Points table, Tax Map overlay. |

Services never import from `api/`. `target_points` composes `total_cost`; its pure core
works on a list of cost points so it can be tested and used alone.

---

## IRMAA service

`services/irmaa.py`:

- `irmaa_annual_surcharge(magi, filing_status, tax_year, enrollees, threshold_inflation)`
  returns the annual Part B + Part D surcharge: the tier is the number of thresholds that
  MAGI is strictly above (IRMAA applies above a threshold, not at it), times 12 months,
  times the number of enrollees.
- Thresholds come from the year's federal file; surcharge amounts from the IRMAA file.
- **Lookback.** IRMAA in year Y+N is set by the MAGI of year Y, with N from
  `irmaa_lookback_years`. The thresholds that apply are those of the premium year, which are
  not yet known, so the year's thresholds are inflated by `irmaa_inflation_default`
  compounded over the lookback (the same adjustment the EMR page offers). The request may
  override the rate or turn the adjustment off.
- **Enrollees** is an explicit number of people (0 up to the filer count of the filing
  status), not derived from the 65+ flags: income two years before enrollment is what
  counts, so a 63-year-old can already be exposed. Default is the filing status's filer
  count from `config.json`.
- MAGI is the existing `irmaa_magi` (AGI plus tax-exempt interest).
- Surcharge amounts are taken from the planning year's file and not inflated. Assumption to
  document, and revisit if it matters.

Each point's surcharge is attributed to the income that causes it, even though the cost is
paid two years later. This is a planning view, not a cash-flow view.

### Boundary points

The sweep needs a point at the exact income where `irmaa_magi` equals each (adjusted)
threshold, and a point one dollar above it. Taxable Social Security makes MAGI nonlinear in
the sweep, so the sweep value is solved by bisection on the existing
`_agi_at_point` (AGI is monotone in the sweep), not by a closed form. These are passed to
`calculate_emr` through `extra_boundary_points`, as the ACA cliff and schedule points are
today.

### total_cost changes

- `TotalCostPoint` gains `irmaa_surcharge` and `emr_irmaa`.
- `emr_irmaa` for a cliff follows the ACA convention (annual dollars lost per $1,000 of
  income) so the chart and the existing components stay consistent.
- `total_cost_emr` includes `emr_irmaa`.
- New request fields: `include_irmaa`, `irmaa_enrollees`, `irmaa_inflation_adjust`,
  `irmaa_inflation_rate`. Off by default so existing callers and tests are unchanged.

---

## Target points service

`services/target_points.py`:

- `find_target_points(points, max_rate) -> TargetPointsResult`, pure. Input is a list of
  `(income, cost)`. Output:
  - `targets`: list of incomes.
  - `legs`: `from_income`, `to_income`, `average_emr`, `cost`, and `causes` (the components
    that were positive inside the leg: torpedo, LTCG stacking, ACA, IRMAA tier).
  - Only legs with `average_emr <= max_rate`.
- `calculate_target_points(...)` runs `calculate_total_cost` with IRMAA on and passes the
  points through.
- Edge cases to cover: income already inside a hot zone at the floor; no hot zone at all
  (one leg, floor to ceiling); a cliff at the ceiling; coincident cliffs (ACA and IRMAA);
  a zero-width leg.

---

## API

`POST /api/target-points`. The request is the total-cost request plus `max_emr`. The
response lists `targets`, `legs`, and the max EMR used. The router converts and returns;
no logic.

---

## UI (Income page)

1. **Max EMR input**, defaulted from `/api/config`. No literal in the page.
2. **Target Points table** beside the Key Points table: From, To (target), Average EMR,
   and what is inside the leg.
3. **Tax Map overlay** with an on/off checkbox, like the IRMAA one: dots on the max-EMR
   line at each target, a green horizontal line per desirable leg labelled with its average.

The table ships before the overlay; both use the same response.

---

## Tests

- `tests/unit/test_irmaa.py`: tier boundaries (at a threshold costs nothing, one dollar
  above does), enrollee count, inflation adjustment, zero enrollees.
- `tests/unit/test_target_points.py`: the pure algorithm on synthetic points, including
  the edge cases above.
- `tests/functional/`: the route end to end with real data files.
- `tests/scenarios/`: a hand-verified single and a joint scenario with a torpedo and an
  IRMAA cliff.
- `tests/scenarios/test_scenario_irmaa_surcharges_data.py`: surcharge data matches the
  published CMS table, one case per year, like the thresholds data test.
- `tests/js/`: Income page boots with the new fixture; regenerate with
  `python3 tests/js/fixtures.py`.

---

## Implementation order

1. IRMAA surcharge data file, with its data test.
2. `irmaa` service and unit tests.
3. IRMAA boundary points and the `total_cost` component, with tests.
4. `target_points` pure core and unit tests.
5. Composing function, router, functional and scenario tests.
6. Income page: input and table, then the chart overlay, then the JS fixture and tests.

---

## Open items

- Part D surcharge amounts must be copied from the CMS fact sheet for each supported year.
- Whether surcharge amounts should be inflated like the thresholds.
- Whether the sweep ceiling should extend to the top IRMAA tier when IRMAA is on, so the
  high-income cliffs are visible; the default ceiling stops at the 24% bracket.
