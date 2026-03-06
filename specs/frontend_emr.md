# Spec: EMR Visualization Frontend

**Version:** 1.0
**Status:** Draft
**Covers:** `api/static/index.html`

---

## Purpose

Single-page tool for visualizing the effective marginal tax rate curve. Accepts
income inputs, calls the `/api/emr` endpoint, and renders an interactive Plotly
chart with planning signals. No framework — vanilla JS and HTML in a single file.

---

## Serving

FastAPI serves the file as a static asset. `api/main.py` mounts:
```python
app.mount("/static", StaticFiles(directory="api/static"), name="static")
```
And adds a root redirect:
```python
@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")
```

Accessible at `http://localhost:8000` after `uvicorn api.main:app --reload`.

---

## Layout

Single column, stacked vertically on a 15" MacBook Air screen:

```
┌─────────────────────────────────────────────────────┐
│  Header: "EMR Analyzer"                             │
├─────────────────────────────────────────────────────┤
│  Input Form (collapsible sections)                  │
│    ▼ Ordinary Income                                │
│    ▶ Preferential Income                            │
│    ▶ Social Security                                │
│    ▶ Sweep Settings                                 │
│  [ Run Analysis ]  button                           │
├─────────────────────────────────────────────────────┤
│  Planning Signals bar (appears after first run)     │
├─────────────────────────────────────────────────────┤
│  Chart toolbar: [Stacked Area] [Lines]  [IRMAA ✓]  │
│  Plotly EMR chart                                   │
└─────────────────────────────────────────────────────┘
```

---

## Input Form

### Behavior
- Four collapsible sections using `<details>/<summary>` HTML elements
- "Ordinary Income" section open by default, others collapsed
- All fields are numeric inputs, `min="0"`, `step="1"` (or `step="100"` for sweep step)
- Empty fields treated as `0` when building the request payload
- "Run Analysis" button disabled while a request is in flight
- Button text changes to "Running..." while waiting for response

### Section 1 — Ordinary Income (open by default)
| Label | Field name | Default |
|---|---|---|
| Pension / Annuity | `pension` | blank |
| Taxable Interest | `interest` | blank |
| Ordinary Dividends | `ordinary_dividends` | blank |
| Inherited IRA RMD | `inherited_ira_rmd` | blank |

### Section 2 — Preferential Income (collapsed)
| Label | Field name | Default |
|---|---|---|
| Qualified Dividends | `qualified_dividends` | blank |
| Fixed LTCG | `fixed_ltcg` | blank |

### Section 3 — Social Security (collapsed)
| Label | Field name | Default |
|---|---|---|
| SS Annual Benefit | `ss_benefit` | blank |
| Tax-Exempt Interest | `tax_exempt_interest` | blank |

### Section 4 — Sweep Settings (collapsed)
| Label | Field name | Type | Default |
|---|---|---|---|
| Sweep Mode | `sweep_mode` | select | `ordinary` |
| Variable Ordinary (PREFERENTIAL mode only) | `variable_ordinary` | number | blank |
| Filing Status | `filing_status` | select | `single` |
| Tax Year | `tax_year` | select | `2025` |
| Sweep Floor | `sweep_floor` | number | blank (0) |
| Sweep Ceiling | `sweep_ceiling` | number | blank (null → service default) |
| Sweep Step | `sweep_step` | number | `100` |
| Include Ohio | `include_ohio` | checkbox | unchecked |

**Ohio sub-fields** (shown only when Include Ohio is checked):
| Label | Field name | Default |
|---|---|---|
| Ohio Medical Deduction | `ohio_medical_deduction` | blank |
| Qualifying Retirement Income | `ohio_qualifying_retirement_income` | blank |

**Sweep mode behavior:**
- When `sweep_mode = "preferential"`, show the "Variable Ordinary" field
- When `sweep_mode = "ordinary"`, hide it

---

## API Call

On "Run Analysis" click, collect all field values and POST to `/api/emr`:

```javascript
const payload = {
  pension: parseFloat(field('pension')) || 0,
  interest: parseFloat(field('interest')) || 0,
  // ... all fields
  sweep_ceiling: field('sweep_ceiling') ? parseFloat(field('sweep_ceiling')) : null,
  include_ohio: field('include_ohio').checked,
};

const response = await fetch('/api/emr', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});
```

### Error handling
- HTTP 422: parse `detail` field and display below the Run button in red
- HTTP 500: display "An unexpected error occurred. Please try again." in red
- Network error: display "Could not reach the server. Is the API running?" in red
- Clear any previous error message on each new Run click

---

## Planning Signals Bar

Appears below the form after the first successful run. Updates on each run.
Displayed as a horizontal row of signal badges.

| Signal | Display | Color |
|---|---|---|
| `torpedo_active = true` | "⚡ SS Torpedo Active" | amber |
| `torpedo_active = false` | "SS Torpedo: Inactive" | green |
| `ss_fully_taxable = true` | "SS: Fully Taxable (85%)" | amber |
| `ltcg_0pct_remaining` (not null) | "0% LTCG Space: $X,XXX" | green |
| `ltcg_0pct_remaining = null` | "0% LTCG Space: None" | gray |
| `distance_to_22pct` (not null) | "To 22%: $X,XXX" | blue |
| `distance_to_22pct = null` | "At 22%+" | gray |
| `distance_to_24pct` (not null) | "To 24%: $X,XXX" | blue |
| `distance_to_24pct = null` | "At 24%+" | gray |

Dollar amounts formatted with comma separators, no decimal places.

---

## Plotly Chart

### Shared configuration
- x-axis: "Variable Income ($)", formatted with comma separators
- y-axis: "Effective Marginal Rate", formatted as percentage (e.g. `0.22` → `22%`)
- Responsive width: `100%`
- Height: `500px`
- Legend visible
- Hover: show income, total EMR, and all non-zero components on hover

### Chart type toggle
Three controls above the chart:
- **[Stacked Area]** button — active by default
- **[Lines]** button
- **[IRMAA]** checkbox — show/hide IRMAA reference lines, checked by default

Switching chart type re-renders using data already in memory — no new API call.

### Stacked Area mode
One filled area trace per component, stacked in this order (bottom to top):
1. `ordinary` — steel blue
2. `ss_torpedo` — amber/orange
3. `pref_stacking` — purple
4. `niit` — red
5. `ohio` — teal (only rendered if `include_ohio = true`)

Plotly config:
```javascript
{ type: 'scatter', fill: 'tonexty', stackgroup: 'emr' }
```

Components with all-zero values across the sweep are hidden (not rendered as
flat zero traces — they add visual noise).

### Lines mode
One line trace per component (same colors as stacked area) plus one bold line
for total `emr`. Components with all-zero values hidden.

### IRMAA reference lines
Vertical dashed lines at each threshold in `irmaa_thresholds`.
Rendered as Plotly `shapes` on the chart layout:
```javascript
{
  type: 'line', x0: threshold, x1: threshold,
  y0: 0, y1: 1, yref: 'paper',
  line: { color: 'gray', dash: 'dash', width: 1 }
}
```
Annotated with small labels: "IRMAA 1", "IRMAA 2", etc.
Shown/hidden by toggling the IRMAA checkbox without re-rendering the chart —
update `layout.shapes` and call `Plotly.relayout`.

---

## External Dependencies (CDN)

```html
<script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
```

No other external dependencies. All styling inline or in a `<style>` block
in the same file.

---

## Styling

Clean, functional. Not a design showcase.
- Background: `#f8f9fa` (light gray page), `#ffffff` (white cards)
- Font: system font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`)
- Max page width: `960px`, centered
- Section headers: collapsible with subtle border and padding
- Input fields: full width within their column, consistent height
- Run button: prominent, full width, dark background
- Signal badges: small rounded pills with colored backgrounds
- Chart container: white card with subtle shadow

---

## Out of Scope

- Save / load scenarios
- Pre-populated defaults
- Mobile layout
- Authentication
- Multi-year projection
- Print / export
