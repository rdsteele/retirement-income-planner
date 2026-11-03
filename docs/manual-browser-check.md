# Manual browser check

A 15-minute pass through the five pages in a real browser (written for Brave). The
automated tests cover startup, requests, rendering inputs, and the arguments handed to
Plotly, but not how the pages look or feel, so run this after changes to the pages or
the shared scripts in `api/static/`.

**The expected numbers assume** tax year 2026, filing status Single, and the data files
and `data/config.json` as of the last time this was updated. If a data file changes,
recompute the numbers (the `/api/tax`, `/api/emr`, and `/api/income-plan/*` routes give
the answers) and update this file.

## Setup

- [ ] Open `http://localhost:8000`, then hard-reload each page once (**Cmd+Shift+R**).
- [ ] Open the console (**Cmd+Option+J**) and keep it open throughout.
      **There should be no red errors.** If one appears, note the page and the step.
- [ ] **Real data warning.** The server uses your real `profile/` folder. Do not edit
      anything on the Accounts page. Name every scenario you create **`ZZ Test`**, and
      delete it at the end.

## 1. Scenarios page, to start clean

- [ ] If a scenario is shown as current, click **Clear**. This only unsets which one is
      current; it does not delete it. The next steps use blank inputs.

## 2. Tax Detail

- [ ] **Filing Status** offers *Single* and *Married Filing Jointly*; **Tax Year** offers
      the years that have data files, with the latest selected.
- [ ] Enter **Pension / Annuity** `150000` and **Other Investment Income** `60000`, then
      press Tab. Expect **AGI $210,000**, a **Net Investment Income Tax $380** row, and
      **Total Federal Tax $39,514**.
- [ ] Change Pension to `210000` and Other Investment Income to `0`. The NIIT row should
      **disappear** and Total Federal Tax should read **$39,134**.
- [ ] Toggle **Include Ohio State Tax**. The Ohio card appears and disappears.

## 3. EMR Analysis

- [ ] Enter **Wages / Pension / Annuity** `40000`, then click **Run Analysis**. The
      button says "Running…" and then recovers.
- [ ] Badges: `0% Ordinary Space: None`, `0% LTCG Space: None`, `To 22%: $26,500`,
      `To 24%: $81,800`.
- [ ] The **Sweep Ceiling** placeholder reads `201,775 (24% bracket top)`, **Sweep Step**
      is filled with `100`, and the x-axis title reads "Additional Ordinary Income ($)".
- [ ] Click **Lines**: separate lines plus a bold black Total EMR line. Click
      **Stacked Area** to go back.
- [ ] Set **Sweep Mode** to *Preferential*. A **Variable Ordinary** field appears, and
      after running, the x-axis title reads "Additional Preferential Income ($)".
- [ ] **IRMAA:** turn the IRMAA option on. The x-axis is *additional* income, so the
      first gray dashed line, labeled "IRMAA 1", should sit at **$66,000** (the first
      IRMAA threshold, $106,000, minus your $40,000 of fixed income).

## 4. Income Planning

- [ ] The dropdowns are filled, and **Other Investment Income** sits directly under
      *Tax-Deferred Distributions*.
- [ ] **Before** Calculate, open the **ACA** section. The cliff shows **—**, not a dollar
      amount.
- [ ] Enter **Pension (Gross)** `40000` and **(Taxable)** `40000`, then press Tab. After a
      moment, **Projected MAGI** reads **$40,000**.
- [ ] Click **Calculate**. The button says "Calculating…" and recovers. A chart appears;
      the ACA row reads **`$22,600 under`** (green), with the cliff at **$62,600**. A red
      dotted vertical line is labeled "ACA Cliff $22,600".
- [ ] **ACA MAGI counts the whole Social Security benefit:** set both pensions to `20000`
      and **Social Security Benefit** to `24000`. **MAGI reads $44,000** (not $23,500).
      After Calculate, the ACA row reads `$18,600 under`.
- [ ] **Save As** `ZZ Test`. A **green "Saved" message** appears beside the buttons and
      fades after a few seconds. The bar shows `📋 ZZ Test` and **Save** becomes enabled.
      Click Save once more and check for the message again.
- [ ] Reload the page. ZZ Test loads again with your fields filled.
- [ ] Open **EMR** and **Tax Detail**. Both show `📋 ZZ Test` and pre-fill from it (EMR's
      pension field shows 20000 and its Social Security field shows 24000).

## 5. Scenarios page

- [ ] ZZ Test is listed. **Export** downloads `ZZ_Test.json`.
- [ ] Create a **New Scenario** named `ZZ Test`. It **asks before replacing** the
      existing one. Cancel.
- [ ] **Delete** ZZ Test. After confirming, you see `Deleted "ZZ Test"`, the list updates,
      and the current scenario clears.

## 6. Accounts (look only)

- [ ] The page loads with your accounts and portfolio summary, and the console stays clean.

## 7. Things only your eyes can judge

- [ ] Overlapping or clipped text, and chart legend collisions.
- [ ] The scenario bar's status message wrapping onto its own line.
- [ ] Narrow the window to about half width. Nothing becomes unusable.
- [ ] Anything slow or flickering.

## Reporting a problem

For each: the **page**, the **step**, what you **saw** against what is expected, any
**red console text**, and a screenshot if easy.

## Known issues

As of 2026-11-03. None known. Add an entry here when one is found, and delete it when it is
fixed.
