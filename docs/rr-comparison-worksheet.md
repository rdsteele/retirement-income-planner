# RR comparison worksheet

## Summary of results

Compared this tool with the Retirement Researcher (RR) Tax Calculator for a single filer, age 61 (62 for the Social Security runs), tax year 2026. Federal figures only; RR has no state tax.

**Result:** every figure compared agrees with RR, apart from the two RR differences below. Nothing found in this tool's tax or ACA calculations needed changing except one edge case, fixed during the comparison.

| Area | Runs | Result |
|---|---|---|
| Ordinary brackets, standard deduction, above-the-line adjustments | S1, S7 | Match exactly |
| Gains stacking (0% / 15% / 20%) and NIIT | S1, S4, S8 | Match exactly |
| Social Security taxability: 50% tier, 85% tier, 85% cap, tax-exempt interest | SS1, SS2, SS3, SS4, SS5 | Match exactly |
| ACA subsidy (full range, cliff, over the cliff) | A1, A2, A3, A4 | Within $6 (schedule rounding); cliff edge fixed |
| ACA with Social Security (whole benefit counts in ACA income) | SS7 | Match: RR counts the whole benefit |
| Poverty-level formula at low income | A5 | Match with RR's formula ($378) |

**Not run (repeat confirmed areas):** S5, S2, S3, SS6.

### Differences, and which tool is right

1. **Medical-expense floor (S6).** RR deducts medical expenses over 8% of AGI. The IRS floor is 7.5%. RR's deduction was $300 lower and its tax $36 higher. This tool follows the IRS. RR's 8% also shaped its runway amounts in that run.
2. **Medicaid range (A5).** This tool returns no ACA subsidy below the start of its schedule (the Medicaid range); RR has no such range and applies its formula down to 100% of the poverty level.

### Fixed during the comparison

- **ACA cliff dollar (A3).** A household at exactly 400% of the poverty level is still eligible under the IRS wording ("not more than 400%"); this tool had treated that dollar as ineligible. It now agrees with RR, and the subsidy holds up to the cliff instead of sloping to zero.
- **0% LTCG space (S7).** The badge now shows the space whenever it exists, including when no gains are entered.

### Runways are not like-for-like

RR's Roth Conversion and LTCG Harvest amounts are suggestions based on the effective marginal rate (EMR) target you type. This tool's badges only show the space left in the brackets. Differences always trace to a rate effect the badges leave out: the Social Security torpedo, gains pushed into 15%, the ACA subsidy, or the itemized medical floor. This tool's EMR sweep reproduces RR's stopping point in 11 of the 12 cases checked (see "EMR sweep versus RR's amounts"); the exception is a 0.2-point plateau in SS4 that RR converts through.

### Known limitation

With itemized medical expenses, this tool treats Additional Deductions as fixed, so its runway is too long when the medical floor is binding (see "Known limitation" at the end). It does not change the tax at a given income.

Scenarios for checking this tool against the Retirement Researcher (RR) Tax Calculator. All use **Single, tax year 2026**, except the "Married filing jointly scenarios" section. Expected values come from this tool (federal only; RR has no state tax).

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

The two tools' runways are different things, so they are not expected to match:

- **RR's Roth Conversion and LTCG Harvest amounts** are *suggestions*. They are the amount you can add before the effective marginal rate (EMR) passes the target you typed, and the EMR includes everything that moves tax: the Social Security torpedo, gains pushed into the 15% bracket, NIIT, the ACA subsidy, and the itemized medical floor.
- **This tool's badges** ("To 22%", "To 24%", "0% LTCG Space", "LTCG Bump Ordinary Runway") are *helpers that show the space left* in the brackets. They do not recommend an amount. The decision (cap AGI to avoid a high EMR, or push through to the next step) is made from the EMR chart.

So the comparison is: (1) the Initial column must match exactly; (2) where the two runways differ, the reason should be an EMR effect the badges don't include; (3) the other two columns are checked by running this tool at RR's amounts.

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
| Roth Conversion Amount ("To 24%" badge) | see badge |
| LTCG Harvest Amount (0% space) | $49,450 |

**Result (run):** every figure matched (taxable Social Security $500, AGI $14,500, tax $0). RR Roth $87,400 equals "To 24%". RR LTCG Harvest $3,200 versus this tool's bracket-only space $49,450: harvested gains pull in half as much Social Security, which fills the unused $1,600 of standard deduction after $3,200 of gains; beyond that each gain dollar adds taxable benefit at 10%, above the 0% target.

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
| Roth Conversion Amount ("To 24%" badge) | see badge |
| LTCG Harvest Amount (0% space) | $30,950 |

**Result (run):** every figure matched (taxable Social Security $9,600, AGI $34,600, tax $1,972). RR runways $0 and $0: in the 85% zone the 12% bracket costs about 22.2% per dollar, just over the 22% target. This tool shows "To 24%" $71,300 and 0% LTCG Space $30,950, bracket-only ceilings. Note SS4 passed through the same zone; RR appears to test the rate where it starts (15% in SS4, 22.2% here).

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
| Roth Conversion Amount ("To 24%" badge) | see badge |
| LTCG Harvest Amount (0% space) | already past ($0) |

**Result (run):** every figure matched, including the 85% cap ($30,600) and both runways ($31,200 and $0).

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
| Roth Conversion Amount ("To 24%" badge) | see badge |
| LTCG Harvest Amount (0% space) | $42,050 |

**Result (run):** every figure matched. RR Roth Conversion Amount $81,400 equals the "To 24%" badge; RR runs through the torpedo because the torpedo's marginal rate (about 15% to 22%) stays within the 22% target, and stops where taxable income reaches the 24% bracket. With the 0% gains target, the torpedo cost on harvested gains exceeds the target, hence $0. RR's LTCG Harvest Amount was $0 while this tool shows 0% LTCG Space $42,050: harvested gains raise provisional income and make more Social Security taxable, so RR counts a cost the badge (bracket space only) does not.

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
| Roth Conversion Amount ("To 24%" badge) | see badge |
| LTCG Harvest Amount (0% space) | $49,450 |

**Result (run):** every figure matched (taxable Social Security $2,500, AGI $12,500, tax $0; RR shows taxable income $-3,600, this tool floors it at $0). RR Roth $91,400 equals "To 24%". RR LTCG Harvest $5,882 versus bracket-only $49,450: the same torpedo effect as SS1 (3,600 of unused deduction absorbed by the added taxable benefit: 2,000 over the first 4,000 of gains, then 85 cents per dollar).

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
| Roth Conversion Amount ("To 24%" badge) | see badge |
| LTCG Harvest Amount (0% space) | $29,100 |

### SS7 (P1): Social Security and the ACA

**Why this run:** the IRS counts the *whole* Social Security benefit in ACA MAGI, taxable or not (IRS Pub. 974). This tool does. The run shows whether RR does too.

Same income as SS4, with the ACA turned on.

**Enter in RR:**

| Field | Value |
|---|---|
| Filing status | Single |
| Age | 61 |
| Medicare months in 2028 | 0 |
| Do you qualify for ACA premium subsidies | **Yes** |
| Household size | **1** |
| Household location | **Contiguous 48 states & DC** |
| Full (pre-subsidy) premium per year | **$12,456** |
| Benchmark plan full subsidy amount per year | **$12,456** |
| Household Social Security Benefits | **$24,000** |
| Additional Ordinary Income [Not Investment] | **$20,000** |
| Proposed EMR target, ordinary | **22%** |
| Proposed EMR target, preferential | **0%** |

Everything else stays $0.

**Enter in this tool** (Single, 2026; all other fields $0):

| Field | Value |
|---|---|
| Social Security Benefit | **$24,000** |
| Wages / Pension | **$20,000** |
| Include ACA subsidy calculation (Income Planning page) | **On** (the tool uses its own schedule; no premium or benchmark to enter) |

**What to expect:**

| Item | Expected |
|---|---|
| Taxable Social Security | $3,500 |
| AGI | $23,500 |
| Federal tax | $740 |
| ACA MAGI (includes the whole benefit) | **$44,000** |

**The key row, Lost ACA Subsidy in RR's Initial column:**

| If RR... | Lost ACA Subsidy | ACA MAGI |
|---|---|---|
| counts the whole benefit (the IRS rule) | **$4,130.26** | $44,000 |
| counts only the taxable $3,500 | $986.46 | $23,500 |

This tool: annual subsidy $8,321, so $4,135 lost, within $5 of the IRS figure.

A result of $986.46 would mean RR leaves out the nontaxable part of the benefit. That would be a defect in RR, not in this tool.

**Result (run):** RR Lost ACA Subsidy **$4,130.26**, so RR counts the whole benefit, as the IRS does. This tool: APTC $693 a month, ACA MAGI $44,000, about $4,140 lost (within $10). Taxable Social Security, AGI ($23,500), taxable income ($7,400) and federal tax ($740) matched. RR runways were $0 and $0 (the subsidy cost is over the targets); this tool shows "To 24%" $81,400 and 0% LTCG Space $42,050 as bracket-only ceilings.

## ACA runs

In RR: ACA subsidies **Yes**, household **1**, full premium **$12,456**, benchmark **$12,456**, Ordinary 22% and Preferential 0%. RR's *Lost ACA Subsidy* is the household's required contribution (applicable % x MAGI); I reproduced RR's earlier $3,489.51 exactly from the IRS table. The $12,456 benchmark is what the single schedule implies at every row, within $10, so the two should agree except where noted. Also note RR's two runway amounts here: with ACA on, the subsidy loss counts toward the marginal rate and can shrink them to $0 (as it did in your first run).

### A2 (P1): Mid-range, MAGI $55,000

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$55,000**
- Do you Qualify for ACA Premium Subsidies: **Yes**
- Household size: **1**; location: **Contiguous 48 states & DC**
- Full (pre-subsidy) premium per year: **$12,456**
- Benchmark plan full subsidy amount per year: **$12,456**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$55,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $4,420 |
| **Lost ACA Subsidy** (IRS formula) | **$5,478.00** |
| Tool's annual subsidy | $6,984 (implied lost $5,472) |

**Result (run):** Lost ACA Subsidy RR $5,478.00 versus this tool $5,472 (annual subsidy $6,984), a $6 difference. RR Roth Conversion Amount $7,600 equals the distance to the cliff (above 300% of the poverty level the subsidy costs 9.96% plus the 12% bracket = 21.96%, within the 22% target).

Re-run: federal tax $4,420 and taxable income $38,900 matched; this tool shows Distance to Cliff $7,600, 0% LTCG Space $10,550 (RR harvest $0 because of the ACA cost).

### A3 (P1): Exactly 400% of the poverty level, MAGI $62,600

Exactly at the cutoff. The IRS table says "not more than 400%", so this is still eligible; this tool now agrees (it zeroes the subsidy only above the cliff dollar).

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$62,600**
- Do you Qualify for ACA Premium Subsidies: **Yes**
- Household size: **1**; location: **Contiguous 48 states & DC**
- Full (pre-subsidy) premium per year: **$12,456**
- Benchmark plan full subsidy amount per year: **$12,456**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$62,600**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $5,332 |
| **Lost ACA Subsidy** (IRS formula) | **$6,234.96** |
| Tool's annual subsidy | $6,240 (implied lost $6,216) |

**Result (run):** RR counts MAGI $62,600 as eligible (lost subsidy $6,234.96), as the IRS reads it. This tool showed $0 APTC before the fix; it now shows $6,240 a year. Federal tax $5,332 matched. RR Roth/harvest were $0 because the next dollar loses the whole remaining subsidy.

**Re-run after the fix:** APTC $520 a month and "Distance to Cliff $0 under" (RR still eligible, lost $6,234.96; this tool about $6,216). Federal tax $5,332 matched.

### A4 (P1): $400 over the cutoff, MAGI $63,000

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$63,000**
- Do you Qualify for ACA Premium Subsidies: **Yes**
- Household size: **1**; location: **Contiguous 48 states & DC**
- Full (pre-subsidy) premium per year: **$12,456**
- Benchmark plan full subsidy amount per year: **$12,456**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$63,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $5,380 |
| **Lost ACA Subsidy** (IRS formula) | **$12,456.00** |
| Tool's annual subsidy | $0 (implied lost $12,456) |

**Result (run):** Lost ACA Subsidy matched ($12,456, full loss, MAGI $400 over the cliff). RR runways: Roth $58,800, harvest $2,550 (the tool should show "To 24%" $58,800 and 0% LTCG Space $2,550 for taxable income $46,900). The saved EMR and Tax Detail PDFs showed no income, so rerun those from the saved scenario.

### A1 (P2): Lower range, MAGI $25,000

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$25,000**
- Do you Qualify for ACA Premium Subsidies: **Yes**
- Household size: **1**; location: **Contiguous 48 states & DC**
- Full (pre-subsidy) premium per year: **$12,456**
- Benchmark plan full subsidy amount per year: **$12,456**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$25,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $890 |
| **Lost ACA Subsidy** (IRS formula) | **$1,164.92** |
| Tool's annual subsidy | $11,292 (implied lost $1,164) |

**Result (run):** Lost ACA Subsidy RR $1,164.92 versus this tool $1,164 (annual subsidy $11,292); federal tax $890 matched; RR runways $0 and $0 because the subsidy phase-out cost is over the targets.

### A5 (P2): Below the schedule, MAGI $18,000

This tool's schedule starts at 22,000 (below that is the Medicaid range), so it returns no subsidy; RR's formula should give a full subsidy.

**Enter in RR:**

- Additional Ordinary Income [Not Investment]: **$18,000**
- Do you Qualify for ACA Premium Subsidies: **Yes**
- Household size: **1**; location: **Contiguous 48 states & DC**
- Full (pre-subsidy) premium per year: **$12,456**
- Benchmark plan full subsidy amount per year: **$12,456**
- Targets: Ordinary **22%**, Preferential **0%**

**Enter in this tool** (Single, 2026; all other fields $0):

- Wages / Pension: **$18,000**
- Income Planning page: ACA on (the tool uses its own schedule; no premium or benchmark to enter)

| Expected, Initial column | This tool |
|---|---|
| Federal tax | $190 |
| **Lost ACA Subsidy** (IRS formula) | **$378.00** |
| Tool's annual subsidy | $0 (implied lost $12,456) |

**Result (run):** the first RR run had $8,000 of tax-exempt interest left over from SS5 (RR showed $1,291.59, the formula value at ACA income $26,000). Clean re-run: RR Lost ACA Subsidy **$378.00** (2.10% of $18,000), federal tax $190 matched, AGI $18,000. This tool returns no subsidy below the start of its schedule; RR has no Medicaid range. RR's Roth amount stopped at $2,814 (AGI $20,814, about 133% of the poverty level, where the applicable percentage starts rising).

## Married filing jointly scenarios

The scenarios above are all Single. These repeat the areas where the MFJ numbers differ (different bracket, deduction, NIIT, Social Security and ACA data) so the joint data and its wiring are checked against RR too. The calculation code is shared with Single; only the data behind each filing status differs.

**How to read the tables:** the expected values are this tool's own output, hand-checked. Compare RR's Initial column to the tax lines (AGI, taxable income, ordinary tax, preferential tax, NIIT, taxable Social Security) and expect them to match exactly. The runway rows are this tool's bracket-only badges; RR's Roth Conversion and LTCG Harvest amounts are EMR-based and are expected to differ (often $0), so record RR's amounts in the result but don't expect them to equal the badges.

**Setup:** in RR choose Filing Status **Married Filing Jointly**, both spouses age **61** (**62** for the Social Security runs), Medicare months in 2028 **0**, ACA **No** (except the ACA-runs), everything not listed **$0**. In this tool choose **Married Filing Jointly**, tax year 2026, all other fields $0. Targets: Ordinary **22%**, Preferential **0%**. Not modeled, and not tested: the extra 65+ deduction and the senior deduction. All expected values were hand-checked against the 2026 joint brackets (standard deduction 32,200; 10% to 24,800; 12% to 100,800; 22% to 211,400; 0% gains to 98,900; NIIT above 250,000; Social Security thresholds 32,000 and 44,000).

### M1 (P1): Gains stacking across the joint 0%/15% line

Taxable ordinary income is 8,800, which leaves 90,100 of 0% space; gains of 106,000 put 15,900 into the 15% bracket.

**Inputs** (everything not listed is $0)

| Income | RR field | Enter in RR | This tool field | Enter in this tool |
|---|---|---|---|---|
| Wages / pension | Additional Ordinary Income [Not Investment] | $40,000 | Pension / Annuity (Taxable) on Income Planning; Wages / Pension elsewhere | $40,000 |
| Interest | Taxable Interest | $1,000 | Taxable Interest | $1,000 |
| Total dividends | Ordinary Dividends (total, qualified included) | $6,000 | Non-Qualified Dividends | $0 |
| Qualified dividends | Qualified Dividends | $6,000 | Qualified Dividends | $6,000 |
| Long-term gains | Realized Long-Term Capital Gains | $100,000 | Capital Gains (LT) | $100,000 |

**Expected, Initial column** (this tool)

| Line | Expected |
|---|---|
| AGI | $147,000 |
| Taxable income | $114,800 (ordinary $8,800 + preferential $106,000) |
| Federal ordinary tax | $880 |
| Federal preferential tax | $2,385 (15% of $15,900) |
| NIIT | $0 |
| Roth Conversion Amount ("To 22%" badge) | $92,000 |
| LTCG Harvest Amount (0% space) | already past ($0) |

**Result (run):** every figure matched, with both tools set to Married Filing Jointly (age 61 each). RR: AGI $147,000, taxable income $114,800, ordinary tax $880, preferential tax $2,385, total $3,265, NIIT and lost ACA subsidy $0. This tool: the same figures (taxable ordinary $8,800, preferential $106,000, 0% gains space used $90,100 and $15,900 taxed at 15%).

Runways differ for the usual reason. RR's Roth Conversion Amount is **$0** and LTCG Harvest **-$1**: its ordinary EMR starts at 25% (10% bracket plus 15% from pushing gains out of the 0% bracket), above the 22% target. This tool's badges are bracket-only space ("To 22%" $92,000, "To 24%" $202,600), and its EMR sweep shows the same 25% from the first dollar and 27% from about $16,000. A first run with the tool set to Single (and Ohio ticked) differed only because of the setup; the Ohio tax ($3,554 here) is not part of the RR comparison.

### M2 (P2): Ordinary income through the 22% bracket

**Inputs** (everything not listed is $0)

| Income | RR field | Enter in RR | This tool field | Enter in this tool |
|---|---|---|---|---|
| Wages / pension | Additional Ordinary Income [Not Investment] | $150,000 | Wages / Pension | $150,000 |

**Expected, Initial column** (this tool)

| Line | Expected |
|---|---|
| AGI | $150,000 |
| Taxable income | $117,800 |
| Federal ordinary tax | $15,340 (2,480 + 9,120 + 3,740) |
| Federal preferential tax | $0 |
| Roth Conversion Amount ("To 24%" badge) | $93,600 |
| LTCG Harvest Amount (0% space) | already past ($0) |

**Result (run):** _fill in_

### M3 (P1): NIIT: crossing the joint 250,000

NII is 130,000 (interest, qualified dividends, other investment, gains) and MAGI is 310,000, so NIIT is 3.8% of the 60,000 excess.

**Inputs** (everything not listed is $0)

| Income | RR field | Enter in RR | This tool field | Enter in this tool |
|---|---|---|---|---|
| Wages / pension | Additional Ordinary Income [Not Investment] | $180,000 | Wages / Pension (not Other Investment Income) | $180,000 |
| Interest | Taxable Interest | $20,000 | Taxable Interest | $20,000 |
| Other investment income | Additional Ordinary Income [Investment] | $20,000 | Other Investment Income | $20,000 |
| Total dividends | Ordinary Dividends (total, qualified included) | $20,000 | Non-Qualified Dividends | $0 |
| Qualified dividends | Qualified Dividends | $20,000 | Qualified Dividends | $20,000 |
| Long-term gains | Realized Long-Term Capital Gains | $70,000 | Capital Gains (LT) | $70,000 |

**Expected, Initial column** (this tool)

| Line | Expected |
|---|---|
| AGI | $310,000 |
| Taxable income | $277,800 (ordinary $187,800 + preferential $90,000) |
| Federal ordinary tax | $30,740 |
| Federal preferential tax | $13,500 (15% of $90,000) |
| NIIT | $2,280 |
| Roth Conversion Amount ("To 24%" badge) | $23,600 |
| LTCG Harvest Amount (0% space) | already past ($0) |

**Result (run):** every tax figure matched (Married Filing Jointly, both age 61, Ohio unticked in this tool). RR and this tool: AGI $310,000, taxable income $277,800, ordinary tax $30,740, preferential tax $13,500, NIIT $2,280, total $46,520. Runways differ for the usual reason: RR's Roth Conversion and LTCG Harvest are both **$0** because the ordinary rate is already 25.8% (22% bracket plus 3.8% NIIT), above the 22% target. This tool's EMR chart shows the same stack (22% ordinary plus NIIT), and its badges show the bracket-only space ("At 22%+", "To 24%" $23,600).

### SS-M1 (P1): Social Security: the 85% zone, joint thresholds

Use RR age **62** for both spouses. Provisional income = 35,000 + 20,000 (half the benefit) = 55,000, which is 11,000 over the second threshold (44,000): 6,000 + 85% x 11,000 = 15,350.

**Inputs** (everything not listed is $0)

| Income | RR field | Enter in RR | This tool field | Enter in this tool |
|---|---|---|---|---|
| Social Security | Household Social Security Benefits (annual) | $40,000 | Social Security Benefit | $40,000 |
| Wages / pension | Additional Ordinary Income [Not Investment] | $35,000 | Pension / Annuity (Taxable) and (Gross) on Income Planning; Wages / Pension elsewhere | $35,000 |

**Expected, Initial column** (this tool)

| Line | Expected |
|---|---|
| **Taxable Social Security** (hand-checked) | **$15,350** |
| AGI | $50,350 |
| Taxable income | $18,150 |
| Federal ordinary tax | $1,815 |
| Federal preferential tax | $0 |
| Roth Conversion Amount ("To 22%" badge) | $64,000 |
| LTCG Harvest Amount (0% space) | $80,750 |

RR's runways will differ from the badges (the torpedo raises the marginal rate), as in SS1 to SS4. Compare taxable Social Security and the tax lines exactly.

**Result (run):** every tax figure matched (Married Filing Jointly, both age 62, ACA off). RR and this tool: taxable Social Security $15,350, AGI $50,350, taxable income $18,150, ordinary tax $1,815, preferential tax $0, NIIT $0. This confirms the joint 32,000 and 44,000 thresholds.

Runways: RR Roth Conversion Amount is **$174,600**, which equals this tool's "To 24%" badge exactly (RR's run ends at taxable income $211,400, the top of the 22% bracket, AGI $243,600, tax $35,932, with all Social Security taxable at $34,000). RR passes through the torpedo band to the 24% bracket, as it did in SS4; this tool's "To 22%" badge ($64,000) stops where the torpedo's 22.2% starts. RR LTCG Harvest is **$0** versus this tool's 0% LTCG Space of $80,750: gains raise taxable Social Security, so RR's effective rate on the first harvested dollar is above its 0% target (same reason as SS1 to SS4). RR's EMR map (18.5%, then 22.2%, then 12%, then 22%) and this tool's chart (torpedo band, then 12%, then 22%) show the same shape; the exact break points were not compared. Ohio was ticked in this tool's screens ($446); it is not part of the RR comparison.

### SS-M2 (P1): Social Security: capped at 85%, joint

Provisional income = 70,000 + 18,000 = 88,000 would give 43,400, but the cap is 85% x 36,000 = 30,600. Use RR age **62** for both spouses.

**Inputs** (everything not listed is $0)

| Income | RR field | Enter in RR | This tool field | Enter in this tool |
|---|---|---|---|---|
| Social Security | Household Social Security Benefits (annual) | $36,000 | Social Security Benefit | $36,000 |
| Wages / pension | Additional Ordinary Income [Not Investment] | $70,000 | Pension / Annuity (Taxable) and (Gross) on Income Planning; Wages / Pension elsewhere | $70,000 |

**Expected, Initial column** (this tool)

| Line | Expected |
|---|---|
| **Taxable Social Security** (hand-checked) | **$30,600** |
| AGI | $100,600 |
| Taxable income | $68,400 |
| Federal ordinary tax | $7,712 |
| Federal preferential tax | $0 |
| Roth Conversion Amount ("To 22%" badge) | $32,400 |
| LTCG Harvest Amount (0% space) | $30,500 |

**Result (run):** every figure matched (Married Filing Jointly, both age 62, ACA off). RR and this tool: taxable Social Security $30,600 (the 85% cap), AGI $100,600, taxable income $68,400, ordinary tax $7,712, preferential tax $0, NIIT $0.

Runways also matched this time, because Social Security is already fully taxable (no torpedo), so nothing in RR's EMR differs from the brackets: RR Roth Conversion Amount **$143,000** equals this tool's "To 24%" badge, and RR LTCG Harvest **$30,500** equals this tool's 0% LTCG Space (RR's harvest column: taxable income $98,900, tax unchanged at $7,712). This tool's "To 22%" badge is $32,400. Ohio was ticked in this tool's screens ($1,422); it is not part of the RR comparison.

### ACA runs, joint (P2)

Only worth running if RR's ACA section accepts a household of **2**. The joint schedule in `aca_2026.json` implies a household benchmark of about $12,456 a year at every point above 300% of the poverty level (63,450), so the two tools should agree within schedule rounding. This tool uses its own schedule; there is no premium to enter.

**Settings (all three runs)**

| Setting | RR | This tool |
|---|---|---|
| ACA | Do you Qualify for ACA Premium Subsidies: **Yes** | Income Planning page: **Include ACA subsidy calculation** ticked |
| Household | Household size **2**; location **Contiguous 48 states & DC** | (from Married Filing Jointly) |
| Premium | Full (pre-subsidy) premium per year **$12,456**; benchmark plan full subsidy amount per year **$12,456** | not needed |
| Income field | Additional Ordinary Income [Not Investment] | Wages / Pension |

**Runs**

| Run | MAGI to enter (RR and this tool) | Federal tax | RR Lost ACA Subsidy (9.96% x MAGI) | This tool's annual subsidy (implied lost) |
|---|---|---|---|---|
| A-M1, mid-range | $75,000 | $4,640 | $7,470.00 | $4,992 ($7,464) |
| A-M2, exactly 400% | $84,600 | $5,792 | $8,426.16 | $4,092 ($8,364) |
| A-M3, $400 over | $85,000 | $5,840 | $12,456.00 | $0 ($12,456) |

- A-M1 should agree within the same few dollars of schedule rounding seen in the Single runs.
- **A-M2 is expected to differ by about $62.** The schedule's last real point is 84,000, and this tool holds that subsidy flat up to the cliff (84,600), so it is about $62 above RR's formula. In the Single runs the last point was 100 below the cliff, so the gap was only about $19. This is the schedule's spacing, not a calculation error; adding a point near the cliff would close it.
- A-M3: both tools lose the whole subsidy above the cliff.

**Result (run):** _fill in_

## Age 65 or older scenarios

These check the additional standard deduction for filers aged 65 or older (2026: $2,050 single; $1,650 per spouse on a joint return). This tool takes it from the "Age 65 or older" and "Spouse age 65 or older" checkboxes instead of an age.

**Why the incomes are high:** RR takes ages, so for a filer aged 65 or older it probably also applies the temporary **senior deduction** from the 2025 tax law ($6,000 per person, reduced by 6% of income over $75,000 single or $150,000 joint). This tool does not model the senior deduction yet. The first three runs use income above the point where that deduction has phased out completely (single $175,000; joint $250,000 for one person, $350,000 for two), so any difference comes from the additional standard deduction alone. The last two runs use lower income on purpose, to learn whether RR applies the senior deduction.

**Setup:** RR Filing Status as shown, ages as shown, Medicare months in 2028 **0**, ACA **No**, everything not listed **$0**, targets Ordinary **22%** and Preferential **0%**. In this tool: tax year 2026, the filing status shown, **Include Ohio State Tax unticked**, and the checkboxes shown. Enter the income in RR as Additional Ordinary Income [Not Investment], and in this tool as Wages / Pension. Compare the tax lines (AGI, taxable income, ordinary tax); runways are bracket-only in this tool and are expected to differ.

### AG1 (P1): Single, age 66

| Setting | RR | This tool |
|---|---|---|
| Age | first person **66** | **Age 65 or older** ticked |
| Income | Additional Ordinary Income [Not Investment] **$200,000** | Wages / Pension **$200,000** |

| Line | Expected (this tool) |
|---|---|
| AGI | $200,000 |
| Standard deduction | $16,100 + $2,050 = $18,150 |
| Taxable income | $181,850 |
| Federal ordinary tax | $36,242 (1,240 + 4,560 + 12,166 + 18,276) |

**Result (run):** matched RR (reported by the tester; screens not reviewed).

### AG2 (P1): Joint, one spouse 66 (the other 61)

| Setting | RR | This tool |
|---|---|---|
| Ages | first person **66**, second person **61** | **Age 65 or older** ticked, spouse box unticked |
| Income | Additional Ordinary Income [Not Investment] **$400,000** | Wages / Pension **$400,000** |

| Line | Expected (this tool) |
|---|---|
| AGI | $400,000 |
| Standard deduction | $32,200 + $1,650 = $33,850 |
| Taxable income | $366,150 |
| Federal ordinary tax | $73,072 (2,480 + 9,120 + 24,332 + 37,140) |

**Result (run):** matched RR (reported by the tester; screens not reviewed).

### AG3 (P1): Joint, both spouses 66

| Setting | RR | This tool |
|---|---|---|
| Ages | first person **66**, second person **66** | both boxes ticked |
| Income | Additional Ordinary Income [Not Investment] **$400,000** | Wages / Pension **$400,000** |

| Line | Expected (this tool) |
|---|---|
| AGI | $400,000 |
| Standard deduction | $32,200 + $3,300 = $35,500 |
| Taxable income | $364,500 |
| Federal ordinary tax | $72,676 (35,932 + 36,744) |

**Result (run):** matched RR (reported by the tester; screens not reviewed).

### AG4 (P2): Does RR apply the senior deduction? Single, age 66, income $50,000

Exploratory. This tool does not model the senior deduction, so if RR applies it, RR's taxable income will be **$6,000 lower** than the figures below and its tax $720 lower. Record the difference.

| Setting | RR | This tool |
|---|---|---|
| Age | first person **66** | **Age 65 or older** ticked |
| Income | Additional Ordinary Income [Not Investment] **$50,000** | Wages / Pension **$50,000** |

| Line | Expected (this tool, additional standard deduction only) |
|---|---|
| AGI | $50,000 |
| Taxable income | $31,850 |
| Federal ordinary tax | $3,574 |
| If RR also applies the $6,000 senior deduction | taxable income $25,850; tax $2,854 |

**Result (run):** RR **does** apply the senior deduction. RR's Below-the-line Deduction is $24,150 = $16,100 standard + $2,050 additional (65+) + **$6,000 senior**, so its taxable income is $25,850 and its tax $2,854. This tool shows $3,574 (taxable $31,850): $720 higher, exactly the unmodeled $6,000 senior deduction at the 12% bracket. Everything else in the run agrees (AGI $50,000, ACA off, NIIT $0).

RR's ordinary EMR map also shows the phase-out: the rate steps up from the start of the phase-out near $75,000 (about 23.3%, the 22% bracket plus 6% x 22%), then to about 25.5% in the 24% bracket (6% x 24%), and drops back near $175,000 where the deduction is gone. That matches the 6% reduction over $75,000 for a single filer (gone at $175,000).

### AG5 (P2): Senior deduction, joint, both spouses 66, income $100,000

Exploratory, same purpose as AG4. Both spouses' senior deductions would total $12,000 and are below the $150,000 phase-out start.

| Setting | RR | This tool |
|---|---|---|
| Ages | first person **66**, second person **66** | both boxes ticked |
| Income | Additional Ordinary Income [Not Investment] **$100,000** | Wages / Pension **$100,000** |

| Line | Expected (this tool, additional standard deduction only) |
|---|---|
| AGI | $100,000 |
| Taxable income | $64,500 |
| Federal ordinary tax | $7,244 |
| If RR also applies $12,000 of senior deductions | taxable income $52,500; tax $5,804 |

**Result (run):** _fill in_

## Exploratory: IRMAA (P3)

This tool draws IRMAA threshold lines but does not price the surcharge, so there is nothing to match. The goal is to learn which thresholds RR uses. **Enter in RR:** Additional Ordinary Income [Not Investment] **$110,000**, Medicare months in 2028 **12**, ACA **No**, then **$105,000**. Record whether and how much IRMAA RR charges at each. This tool's first 2026 threshold is $109,000.

## EMR sweep versus RR's amounts

I ran this tool's EMR sweep (ordinary mode for conversions, preferential mode for harvests, ACA runs through total cost) at each scenario's inputs and compared where the EMR crosses the target against RR's amounts. The EMR is smoothed over a 500 look-ahead, so a step shows as a ramp that ends at the true point.

| Run | RR amount | This tool's EMR sweep | Agree |
|---|---|---|---|
| SS1 harvest | $3,200 | 0% until 3,200, then 5% (10% bracket x 0.5 torpedo) | yes |
| SS5 harvest | $5,882 | 0% until about 5,900, then climbs | yes |
| SS4 harvest | $0 | 5% from the first dollar | yes |
| S7 harvest | $5,050 | 0% until 5,050, then 15% | yes |
| S1 convert | $17,050 | 12%, then 27% from 17,050 | yes |
| S7 convert | $61,300 | 12%, 22% from 6,000, 24% bracket from 61,300 | yes |
| SS2 convert | $0 | 22.2% from the first dollar | yes |
| SS4 convert | $81,400 | 15% rising to 22.2% (plateau to 20,000), then 12% | RR passes the plateau |
| A2 convert | $7,600 | about 21.8%, spike at 7,600 (the cliff) | yes |
| A1 convert | $0 | about 22.4% from the first dollar | yes |
| SS7 convert | $0 | about 32% from the first dollar | yes |
| SS7 harvest | $0 | about 22% from the first dollar | yes |

One case differs in a small way: in SS4 the EMR sits at 22.2% (12% x 1.85) across the torpedo, just over the 22% target, and RR still converts through it, while in SS2 the same 22.2% from the start gives RR $0. RR appears to react to the rate at the start (SS4 starts at 15%) and to jumps, not to a plateau a fraction of a point over the target.

## Known limitation (found in S6)

With itemized medical expenses, the federal deduction is the amount over 7.5% of AGI, so a Roth conversion (which raises AGI) shrinks the deduction. This tool takes Additional Deductions as a fixed amount, so its "To 24%" runway is far too long when medical is itemized (S6: $79,200 versus $21,852 in RR, because the floor lifts the marginal rate in the 22% bracket to about 23.8%, above the target; the same effect gave RR a $0 harvest, which also uses an 8% floor instead of the IRS 7.5%). It does not affect the tax at a given income, only the runway. Noted, not changed.
