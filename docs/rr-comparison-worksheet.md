# RR comparison worksheet

Scenarios for checking this tool against the Retirement Researcher (RR) Tax Calculator. All use **Single, tax year 2026**. Expected values come from this tool (federal only; RR has no state tax).

## How RR works (and what to enter)

- RR's **Roth Conversion Amount** and **LTCG Harvest Amount** are **outputs**: the room before your *Proposed EMR Target* rates are passed, like the badges in this tool. Do not type them.
- Enter the **income inputs** and the two targets: **Ordinary 22%** and **Preferential 0%**. RR then fills in the three columns (Initial, With Roth Conversion, With Gains Harvest).
- Setup: Filing Status **Single**, age **61** (use **62** for the Social Security runs), Medicare months in 2028 **0**, ACA **No** (except the A-runs and SS-ACA), everything not listed **$0**.
- Save each RR result as a PDF named with the scenario id (for example `S4 RR.pdf`), in the same folder as before.
- **What I compare:** (1) the **Initial** column exactly; (2) RR's two runway amounts against this tool's runways below; (3) the other two columns by running this tool at *RR's* amounts, so a different runway doesn't hide a tax difference.
- Rounding: this tool rounds each bracket's tax to whole dollars; RR shows cents. Differences under about $3 per line are rounding.
- Priority: **P1** first, then **P2**, then **P3**.

### How the inputs map

| This tool | RR |
|---|---|
| Pension / Wages | Additional Ordinary Income [Not Investment] |
| Taxable Interest | Taxable Interest |
| Non-Qualified Dividends + Qualified Dividends | **Ordinary Dividends** (RR's total includes the qualified part) |
| Qualified Dividends | Qualified Dividends |
| Tax-Deferred Distributions | Distributions from Tax-Deferred Retirement Accounts |
| Other Investment Income | Additional Ordinary Income [Investment] (or Short-Term Gains) |
| Capital Gains (LT) | Realized Long-Term Capital Gains |
| Social Security Benefit | Household Social Security Benefits (annual) |
| Above-the-Line Adjustments | HSA / Deductible Retirement Plan Contributions |
| Additional Deductions (excess over standard) | Below-the-line itemized items |

### What the runways mean here

For an ordinary target of 22%, RR lets ordinary income fill the 22% bracket (a marginal rate equal to the target is allowed, above it is not), so the matching runway is the "To 24%" badge, unless something raises the rate first (gains pushed into 15%, the torpedo, or the itemized medical floor). For the first run (S4) both are $0, and S1 matched on the "LTCG Bump Ordinary Runway" badge. For a preferential target of 0%, it is the "0% LTCG Space" badge. These are the bracket-only runways. RR's amounts may be smaller when other costs push the marginal rate over a target first: the 3.8% NIIT, gains pushed into the 15% bracket, the Social Security torpedo, or ACA. A difference there is expected; the *reason* is what we want to learn.

## Tax scenarios

### S4 (P1): NIIT: investment-heavy, crossing 200,000

NII is 97,000 (interest, dividends, other investment, gains) and MAGI is 217,000, so NIIT is 3.8% of the 17,000 excess.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$120,000**
- Taxable Interest: **$10,000**
- Additional Ordinary Income [Investment]: **$15,000**
- Ordinary Dividends (total, qualified included): **$12,000**
- Qualified Dividends: **$8,000**
- Realized Long-Term Capital Gains: **$60,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$120,000**
- Taxable Interest: **$10,000**
- Other Investment Income: **$15,000**
- Non-Qualified Dividends: **$4,000**
- Qualified Dividends: **$8,000**
- Capital Gains (LT): **$60,000**
- Careful: the $120,000 goes under Wages / Pension, and only the $15,000 under Other Investment Income

| Expected, Initial column | This tool |
|---|---|
| AGI | $217,000 |
| Taxable income | $200,900 |
| Federal ordinary tax | $24,494 |
| Federal preferential tax | $10,200 |
| NIIT | $646 |
| Roth Conversion Amount ("To 24%" badge) | already past ($0) |
| LTCG Harvest Amount (0% space) | already past ($0) |

**Result (run):** every figure matched; both runways $0.

### S5 (P1): NIIT: high income, none of it investment

Pension and IRA income are not NII, so NIIT must be $0.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$130,000**
- Distributions from Tax-Deferred (IRA/401k): **$100,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$130,000**
- Tax-Deferred Distributions: **$100,000**

| Expected, Initial column | This tool |
|---|---|
| AGI | $230,000 |
| Taxable income | $213,900 |
| Federal ordinary tax | $44,904 |
| Federal preferential tax | $0 |
| NIIT | $0 |
| Roth Conversion Amount ("To 24%" badge) | already past ($0) |
| LTCG Harvest Amount (0% space) | already past ($0) |

### S6 (P1): Itemized deductions beat the standard deduction

RR itemizes automatically; this tool takes only the excess over the standard deduction (itemized total 33,500 minus 16,100).

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$60,000**
- Targets: Ordinary **22%**, Preferential **0%**

Itemized items to enter in RR: State and local taxes **$12,000**, Mortgage interest **$11,000**, Charity **$6,000**, Qualified medical **$9,000** (7.5% of AGI is 4,500, so 4,500 counts).

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$60,000**
- Additional Deductions: **$17,400**

| Expected, Initial column | This tool |
|---|---|
| AGI | $60,000 |
| Taxable income | $26,500 |
| Federal ordinary tax | $2,932 |
| Federal preferential tax | $0 |
| NIIT | $0 |
| Roth Conversion Amount ("To 24%" badge) | $79,200 |
| LTCG Harvest Amount (0% space) | $22,950 |

**Result (run):** RR deducted $33,200, not $33,500, because it applies an 8% of AGI floor to medical expenses (the IRS floor is 7.5%). RR tax $2,968 versus this tool $2,932. Not a defect in this tool. RR's Roth Conversion Amount was $21,852 versus this tool's $79,200, and its LTCG Harvest Amount was $0: see Known limitation at the end.

### S1 (P2): Gains stacking across the 0%/15% line

Ordinary income and gains share the 0% bracket.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$20,000**
- Taxable Interest: **$500**
- Ordinary Dividends (total, qualified included): **$3,000**
- Qualified Dividends: **$3,000**
- Realized Long-Term Capital Gains: **$25,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$20,000**
- Taxable Interest: **$500**
- Qualified Dividends: **$3,000**
- Capital Gains (LT): **$25,000**

| Expected, Initial column | This tool |
|---|---|
| AGI | $48,500 |
| Taxable income | $32,400 |
| Federal ordinary tax | $440 |
| Federal preferential tax | $0 |
| NIIT | $0 |
| Roth Conversion Amount ("LTCG Bump Ordinary Runway" badge; "To 22%" is $46,000) | $17,050 |
| LTCG Harvest Amount (0% space) | $17,050 |

**Result (run):** every figure matched, including both runways.

### S7 (P2): Above-the-line adjustments

Adjustments reduce AGI before the deduction.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$70,000**
- Taxable Interest: **$1,500**
- HSA / deductible retirement contributions (above the line): **$11,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$70,000**
- Taxable Interest: **$1,500**
- Above-the-Line Adjustments: **$11,000**

| Expected, Initial column | This tool |
|---|---|
| AGI | $60,500 |
| Taxable income | $44,400 |
| Federal ordinary tax | $5,080 |
| Federal preferential tax | $0 |
| NIIT | $0 |
| Roth Conversion Amount ("To 24%" badge) | $61,300 |
| LTCG Harvest Amount (0% space) | $5,050 |

### S8 (P2): Top brackets and the 20% gains rate

35% ordinary bracket, gains crossing the 15%/20% line, NIIT on the gains.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$400,000**
- Realized Long-Term Capital Gains: **$250,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$400,000**
- Capital Gains (LT): **$250,000**

| Expected, Initial column | This tool |
|---|---|
| AGI | $650,000 |
| Taxable income | $633,900 |
| Federal ordinary tax | $103,134 |
| Federal preferential tax | $41,920 |
| NIIT | $9,500 |
| Roth Conversion Amount ("To 24%" badge) | already past ($0) |
| LTCG Harvest Amount (0% space) | already past ($0) |

### S2 (P3): Ordinary income through the brackets

Taxable ordinary income of 74,900 is in the 22% bracket.

**Enter in RR:**

- Taxable Interest: **$1,000**
- Distributions from Tax-Deferred (IRA/401k): **$90,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Taxable Interest: **$1,000**
- Tax-Deferred Distributions: **$90,000**

| Expected, Initial column | This tool |
|---|---|
| AGI | $91,000 |
| Taxable income | $74,900 |
| Federal ordinary tax | $11,190 |
| Federal preferential tax | $0 |
| NIIT | $0 |
| Roth Conversion Amount ("To 24%" badge) | already past ($0) |
| LTCG Harvest Amount (0% space) | already past ($0) |

### S3 (P3): Other investment income (or short-term gains)

Enter the 15,000 under Investment in one run and as Short-Term Gains in another; this tool treats them the same.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$40,000**
- Additional Ordinary Income [Investment]: **$15,000**
- Ordinary Dividends (total, qualified included): **$2,000**
- Qualified Dividends: **$2,000**
- Realized Long-Term Capital Gains: **$10,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$40,000**
- Other Investment Income: **$15,000**
- Qualified Dividends: **$2,000**
- Capital Gains (LT): **$10,000**

| Expected, Initial column | This tool |
|---|---|
| AGI | $67,000 |
| Taxable income | $50,900 |
| Federal ordinary tax | $4,420 |
| Federal preferential tax | $218 |
| NIIT | $0 |
| Roth Conversion Amount ("To 24%" badge) | $66,800 |
| LTCG Harvest Amount (0% space) | already past ($0) |

## Social Security scenarios

Use RR age **62** (the earliest claiming age, and below every 65+ rule) and enter the benefit as the **annual** amount. ACA **No**. Compare RR's *Taxable Social Security* row first; everything else follows from it. **Age control (do once):** run SS4 at age 61 and again at 62. They should be identical; if not, age affects something in RR this tool doesn't model.

### SS1 (P1): Social Security: first tier (50%)

Provisional income (PI) = other income + tax-exempt interest + half the benefit. PI 26,000 is 1,000 over the first threshold: 50% x 1,000.

**Enter in RR:**

- Household Social Security Benefits: **$24,000**
- Additional Ordinary Income [Not Investment]: **$14,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$24,000**
- Wages / Pension: **$14,000**

| Expected, Initial column | This tool |
|---|---|
| **Taxable Social Security** (hand-checked) | **$500** ($500 computed) |
| AGI | $14,500 |
| Taxable income | $0 |
| Federal ordinary tax | $0 |
| Federal preferential tax | $0 |
| Roth Conversion Amount (read the "To 24%" badge; RR runs through the torpedo, so expect RR to be smaller) | see badge |
| LTCG Harvest Amount (0% space) | $49,450 |

### SS2 (P1): Social Security: the 85% zone

PI 40,000: 4,500 + 85% x 6,000.

**Enter in RR:**

- Household Social Security Benefits: **$30,000**
- Additional Ordinary Income [Not Investment]: **$25,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$30,000**
- Wages / Pension: **$25,000**

| Expected, Initial column | This tool |
|---|---|
| **Taxable Social Security** (hand-checked) | **$9,600** ($9,600 computed) |
| AGI | $34,600 |
| Taxable income | $18,500 |
| Federal ordinary tax | $1,972 |
| Federal preferential tax | $0 |
| Roth Conversion Amount (read the "To 24%" badge; RR runs through the torpedo, so expect RR to be smaller) | see badge |
| LTCG Harvest Amount (0% space) | $30,950 |

### SS3 (P1): Social Security: capped at 85% of the benefit

PI 78,000 would give 41,900, but the cap is 85% x 36,000.

**Enter in RR:**

- Household Social Security Benefits: **$36,000**
- Distributions from Tax-Deferred (IRA/401k): **$60,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$36,000**
- Tax-Deferred Distributions: **$60,000**

| Expected, Initial column | This tool |
|---|---|
| **Taxable Social Security** (hand-checked) | **$30,600** ($30,600 computed) |
| AGI | $90,600 |
| Taxable income | $74,500 |
| Federal ordinary tax | $11,102 |
| Federal preferential tax | $0 |
| Roth Conversion Amount (read the "To 24%" badge; RR runs through the torpedo, so expect RR to be smaller) | see badge |
| LTCG Harvest Amount (0% space) | already past ($0) |

### SS4 (P1): Social Security: the tax torpedo

PI 32,000: 50% x 7,000. RR's Roth conversion amount here runs through the torpedo (each added dollar makes 85 cents more taxable).

**Enter in RR:**

- Household Social Security Benefits: **$24,000**
- Additional Ordinary Income [Not Investment]: **$20,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$24,000**
- Wages / Pension: **$20,000**

| Expected, Initial column | This tool |
|---|---|
| **Taxable Social Security** (hand-checked) | **$3,500** ($3,500 computed) |
| AGI | $23,500 |
| Taxable income | $7,400 |
| Federal ordinary tax | $740 |
| Federal preferential tax | $0 |
| Roth Conversion Amount (read the "To 24%" badge; RR runs through the torpedo, so expect RR to be smaller) | see badge |
| LTCG Harvest Amount (0% space) | $42,050 |

### SS5 (P2): Social Security with tax-exempt interest

PI 10,000 + 8,000 + 12,000 = 30,000: 50% x 5,000 (it would be $0 without the muni interest).

**Enter in RR:**

- Household Social Security Benefits: **$24,000**
- Additional Ordinary Income [Not Investment]: **$10,000**
- Tax-Exempt Interest: **$8,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$24,000**
- Wages / Pension: **$10,000**
- Tax-Exempt Interest: **$8,000**

| Expected, Initial column | This tool |
|---|---|
| **Taxable Social Security** (hand-checked) | **$2,500** ($2,500 computed) |
| AGI | $12,500 |
| Taxable income | $0 |
| Federal ordinary tax | $0 |
| Federal preferential tax | $0 |
| Roth Conversion Amount (read the "To 24%" badge; RR runs through the torpedo, so expect RR to be smaller) | see badge |
| LTCG Harvest Amount (0% space) | $49,450 |

### SS6 (P2): Social Security with adjustments

PI 26,000 + 15,000 = 41,000: 4,500 + 85% x 7,000.

**Enter in RR:**

- Household Social Security Benefits: **$30,000**
- Additional Ordinary Income [Not Investment]: **$30,000**
- HSA / deductible retirement contributions (above the line): **$4,000**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$30,000**
- Wages / Pension: **$30,000**
- Above-the-Line Adjustments: **$4,000**

| Expected, Initial column | This tool |
|---|---|
| **Taxable Social Security** (hand-checked) | **$10,450** ($10,450 computed) |
| AGI | $36,450 |
| Taxable income | $20,350 |
| Federal ordinary tax | $2,194 |
| Federal preferential tax | $0 |
| Roth Conversion Amount (read the "To 24%" badge; RR runs through the torpedo, so expect RR to be smaller) | see badge |
| LTCG Harvest Amount (0% space) | $29,100 |

### SS7 (P1): Social Security and the ACA

The ACA counts the **whole** benefit in MAGI, taxable or not (IRS Pub. 974); this tool does. Same inputs as SS4, but with ACA **Yes**, household 1, full premium **$12,456**, benchmark **$12,456**.

**Enter in RR:** Household Social Security Benefits **$24,000**; Additional Ordinary Income [Not Investment] **$20,000**; Targets Ordinary **22%**, Preferential **0%**.

**Enter in this tool** (Single, 2026; all other fields $0):

- Social Security Benefit: **$24,000**
- Wages / Pension: **$20,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Taxable Social Security | $3,500 |
| ACA MAGI (whole benefit) | $44,000 |
| **Lost ACA Subsidy** (IRS formula) | **$4,130.26** |
| Tool's annual subsidy | $8,321 (implied lost $4,135) |
| If RR counted only the taxable benefit: MAGI / Lost subsidy | $23,500 / $986.46 |

If RR matches the last row, RR counts only taxable Social Security in ACA MAGI. That would be a defect in RR, not here: the IRS adds the nontaxable portion back.

## ACA runs

In RR: ACA subsidies **Yes**, household **1**, full premium **$12,456**, benchmark **$12,456**, Ordinary 22% and Preferential 0%. RR's *Lost ACA Subsidy* is the household's required contribution (applicable % x MAGI); I reproduced RR's earlier $3,489.51 exactly from the IRS table. The $12,456 benchmark is what the single schedule implies at every row, within $10, so the two should agree except where noted. Also note RR's two runway amounts here: with ACA on, the subsidy loss counts toward the marginal rate and can shrink them to $0 (as it did in your first run).

### A2 (P1): Mid-range, MAGI $55,000

**Enter in RR:** Additional Ordinary Income [Not Investment] **$55,000**.

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$55,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $4,420 |
| **Lost ACA Subsidy** (IRS formula) | **$5,478.00** |
| Tool's annual subsidy | $6,984 (implied lost $5,472) |

### A3 (P1): Exactly 400% of the poverty level, MAGI $62,600

Exactly at the cutoff. The IRS table says "not more than 400%", so this is still eligible; this tool zeroes the subsidy at the cliff dollar.

**Enter in RR:** Additional Ordinary Income [Not Investment] **$62,600**.

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$62,600**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $5,332 |
| **Lost ACA Subsidy** (IRS formula) | **$6,234.96** |
| Tool's annual subsidy | $0 (implied lost $12,456) |

### A4 (P1): $400 over the cutoff, MAGI $63,000

**Enter in RR:** Additional Ordinary Income [Not Investment] **$63,000**.

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$63,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $5,380 |
| **Lost ACA Subsidy** (IRS formula) | **$12,456.00** |
| Tool's annual subsidy | $0 (implied lost $12,456) |

### A1 (P2): Lower range, MAGI $25,000

**Enter in RR:** Additional Ordinary Income [Not Investment] **$25,000**.

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$25,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $890 |
| **Lost ACA Subsidy** (IRS formula) | **$1,164.92** |
| Tool's annual subsidy | $11,292 (implied lost $1,164) |

### A5 (P2): Below the schedule, MAGI $18,000

This tool's schedule starts at 22,000 (below that is the Medicaid range), so it returns no subsidy; RR's formula should give a full subsidy.

**Enter in RR:** Additional Ordinary Income [Not Investment] **$18,000**.

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$18,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $190 |
| **Lost ACA Subsidy** (IRS formula) | **$378.00** |
| Tool's annual subsidy | $0 (implied lost $12,456) |

## Exploratory: IRMAA (P3)

This tool draws IRMAA threshold lines but does not price the surcharge, so there is nothing to match. The goal is to learn which thresholds RR uses. **Enter in RR:** Additional Ordinary Income [Not Investment] **$110,000**, Medicare months in 2028 **12**, ACA **No**, then **$105,000**. Record whether and how much IRMAA RR charges at each. This tool's first 2026 threshold is $109,000.

## Known limitation (found in S6)

With itemized medical expenses, the federal deduction is the amount over 7.5% of AGI, so a Roth conversion (which raises AGI) shrinks the deduction. This tool takes Additional Deductions as a fixed amount, so its "To 24%" runway is far too long when medical is itemized (S6: $79,200 versus $21,852 in RR, because the floor lifts the marginal rate in the 22% bracket to about 23.8%, above the target; the same effect gave RR a $0 harvest, which also uses an 8% floor instead of the IRS 7.5%). It does not affect the tax at a given income, only the runway. Noted, not changed.
