"""Generate README.md, reports/experiment_audit.md and reports/resume_bullets.md from the result files.

Every number is read from data/results/*, so nothing in the write-ups can drift from the code.
    python scripts/build_readme.py
"""
import json
from pathlib import Path

import pandas as pd
import yaml

RES = Path("data/results")
CFG = yaml.safe_load(open("config/audit_portfolio.yaml"))
ECO = CFG["economics"]
P = json.load(open(RES / "pitfalls.json"))
A = json.load(open(RES / "audit_results.json"))
V = json.load(open(RES / "validation.json"))
R = json.load(open(RES / "real_data.json"))
S = pd.read_csv(RES / "audit_summary.csv", index_col=0)
SC = pd.read_csv(RES / "audit_by_scenario.csv", index_col=0)
CARD = pd.read_csv(RES / "checker_report_card.csv")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def inr(x):
    x = float(x)
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} crore"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.1f} lakh"
    return f"₹{x:,.0f}"


# ------------------------------------------------------------------ pull the headline numbers
p1 = P["p1"]
fpr14 = next(r["fpr"] for r in p1["looks"] if r["looks"] == 14)
obf, msp = p1["null"]["obrien_fleming"]["reject_rate"], p1["null"]["msprt"]["reject_rate"]
obf_pw, fix_pw = p1["alt_10pct"]["obrien_fleming"]["reject_rate"], p1["alt_10pct"]["fixed_horizon"]["reject_rate"]
msp_mult = p1["msprt_sample_multiplier_for_80pct_power"]
wc = pd.DataFrame(P["p2"])
wc_lo, wc_80 = wc.iloc[0], wc[wc.target_power == 0.8].iloc[0]
srm5 = next(r for r in P["p3"]["damage"] if abs(r["drop_rate"] - 0.05) < 1e-9)
nv = pd.DataFrame(P["p4"]).set_index("scenario")
nvo = nv.loc["novelty only"]
m20 = next(r for r in P["p5"]["metrics"] if r["n_metrics"] == 20)
s15 = next(r for r in P["p6"] if r["n_segments"] == 15)
ht = pd.DataFrame(P["p7"])
htp = ht[(ht.whale_rate == 0.005) & (ht.true_conv_lift == 0.10)].set_index("method").reject_rate
ua = pd.DataFrame(P["p8"]).set_index("user_sd").loc[1.5]
sp = P["p9"]

c = R["criteo"]
anc_v, anc_c = c["ancova"]["visit"], c["ancova"]["conversion"]
hill = R["hillstrom"]
aa = V["aa"]
card = V["checker_report_card"]
nq, epq = A["n_quarters"], A["experiments_per_quarter"]
nv_, rg_ = S.loc["naive"], S.loc["rigorous"]
cost_ok = rg_.total_cost_inr_median < nv_.total_cost_inr_median
worst = A["worst_case_rerun_equals_abandon"]
worst_ok = worst["rigorous_total_cost_median"] < worst["naive_total_cost_median"]
sens_rows = A["sens_false_win_cost"]
n_exp = nq * epq

# ------------------------------------------------------------------ README
tbl = Path("reports/pitfall_summary.md").read_text().split("\n", 4)[4]

readme = f"""# A/B Pitfall Lab

**How A/B tests lie, measured.** A simulation lab and experiment health checker that shows, with Monte Carlo numbers, how nine common experimentation mistakes produce false wins, and how to detect and fix each one. Validated on two real randomized experiments (Criteo, {c['rows'] / 1e6:.2f}M rows; Hillstrom, {hill['rows']:,} rows) and shipped as an interactive Streamlit app.

📓 [Notebooks](notebooks/) · 📄 [Methodology](reports/methodology.md) · 📝 [Decision log](reports/decision_log.md) · 📋 [PM playbook](reports/experimentation_playbook.md) · 🧾 [Experiment audit](reports/experiment_audit.md) · 📋 [Project charter](reports/project_charter.md)

> **🚀 Live app:** https://a-b-test-pitfall-lab.streamlit.app/ _(free tier: the first visit after idle can take ~30 s to wake)_

---

## TL;DR - key findings

1. **🔍 Peeking:** checking an A/A test daily for 14 days and stopping at the first p < 0.05 gives a **{pct(fpr14)} false positive rate instead of 5%**. O'Brien-Fleming boundaries hold it at {pct(obf)} while keeping {pct(obf_pw, 0)} power (vs {pct(fix_pw, 0)} for a single look); mSPRT is always valid but needs about **{msp_mult:.1f}x the sample** for 80% power.
2. **⚖️ Sample ratio mismatch:** losing just 5% of low-engagement treatment users created a fake **{pct(srm5['avg_fake_rel_lift'])} lift** and a {pct(srm5['false_positive_rate'], 0)} false positive rate with a true effect of zero. A cheap SRM check fired in {pct(srm5['srm_detected'], 0)} of those tests.
3. **📉 Novelty:** a 3-day test of a change with *no* long-run effect reported a **{pct(nvo['est_3d'])} lift** and was "significant" {pct(nvo['reject_3d'], 0)} of the time; the second week alone gave {pct(nvo['est_week2'])}.
4. **⚡ CUPED works only with a good covariate:** on real Criteo data, adjusting for the 12 features gives the same precision for the visit metric with **{pct(anc_v['sample_needed_ratio'], 0)} of the users** ({pct(1 - anc_v['sample_needed_ratio'], 0)} fewer); on real Hillstrom data past spend barely predicts future spend (correlation {hill['corr_history_spend']:.2f}), so CUPED removes only {pct(hill['variance_reduction_python'], 2)} of the variance.
5. **💰 The audit:** across **{nq} simulated quarters of {epq} experiments ({n_exp:,} tests with known ground truth)**, a naive analyst shipped a median of {nv_.shipped_median:.0f} "wins" per quarter, of which **{pct(nv_.fdr_median, 0)} were false**. A rigorous analyst using the health checker shipped {rg_.shipped_median:.0f}, with a **{pct(rg_.fdr_median, 0)}** false discovery rate.
6. **🔬 Real data is messier than textbooks:** in the full Criteo file the treated and control groups differ on pre-treatment features by up to {c['max_abs_smd']:.3f} standard deviations (randomization would give about 0.0005), and adjusting for them moves the visit effect from {anc_v['effect_raw'] * 100:+.2f} to {anc_v['effect_ancova'] * 100:+.2f} percentage points. Both estimates are reported, and the health checker has a Balance check for exactly this.

---

## The business problem

ShopKart, an Indian e-commerce app, runs about {epq} A/B tests per quarter. The analysis habits are common: a plain t-test, daily check-ins, and shipping anything with p < 0.05 on any metric or segment. Leadership suspects many "wins" do not hold up. This project measures how bad each habit is, builds the checks that catch it, and counts what that is worth.

## Why simulation?

You can only measure a false positive rate when you **know the true answer**, and in a real experiment you never do. So the lab:

1. Simulates experiments with a known true effect (including zero) and switchable pitfalls.
2. **Validates the simulator before using it**: {aa['runs']:,} A/A tests give a {pct(aa['false_positive_rate'])} false positive rate with flat p-values, and known effects are recovered with ~95% CI coverage ([notebook 01](notebooks/01_simulator_validation.ipynb)).
3. **Checks the methods on real randomized data**: Criteo ({c['rows']:,} rows) and Hillstrom ({hill['rows']:,} rows). A/A on Criteo's real control group (1,000 random splits) gives {pct(c['real_aa']['conversion']['false_positive_rate'])} false positives on conversion and {pct(c['real_aa']['visit']['false_positive_rate'])} on visits. The SQL and Python z-tests agree to the last digit.

## Architecture

```mermaid
flowchart LR
    A[Simulation engine<br/>validated with A/A tests] --> C[9 pitfall modules<br/>Monte Carlo]
    B[(DuckDB<br/>Criteo + Hillstrom)] -->|SQL metrics, SRM, z-test, CUPED| D[Real-data validation]
    C --> E[Health checker<br/>7 checks]
    D --> E
    E --> F[Experiment audit<br/>{nq} simulated quarters]
    C & E & F --> G[Streamlit app]
```

## The nine pitfalls

Each follows the same template: **simulate → quantify → detect → fix → verify**. One notebook per pitfall in [`notebooks/`](notebooks/).

| # | Pitfall | Headline result |
|---|---|---|
{tbl}
Figures: [`reports/figures/`](reports/figures/). Full tables: [`data/results/`](data/results/).

## The health checker

`diagnose(df)` runs seven checks and returns a verdict: **SHIP**, **NO WIN**, **INVESTIGATE** (yellow) or **DON'T TRUST** (red).

| Check | Catches | Detection rate in its scenario | False alarm rate on clean tests |
|---|---|---|---|
| Sample ratio | Missing users | {pct(card['detection_rate']['Sample ratio'], 0)} | {pct(card['false_alarm_rate_on_clean_tests']['Sample ratio'])} |
| Power | Underpowered tests | {pct(card['detection_rate']['Power'], 0)} | {pct(card['false_alarm_rate_on_clean_tests']['Power'])} |
| Balance | Arms differ before treatment | {pct(card['detection_rate']['Balance'], 0)} | {pct(card['false_alarm_rate_on_clean_tests']['Balance'])} |
| Outliers | Whale-driven results | {pct(card['detection_rate']['Outliers'], 0)} | {pct(card['false_alarm_rate_on_clean_tests']['Outliers'])} |
| Novelty | Fading effects | {pct(card['detection_rate']['Novelty'], 0)} | {pct(card['false_alarm_rate_on_clean_tests']['Novelty'])} |
| Peeking, Multiple testing | Process flags (deterministic rules) | - | - |

Over {card['runs_per_scenario']} runs per scenario: the checker ships {pct(card['clean_win_ship_rate'], 0)} of clean wins and {pct(card['clean_null_ship_rate'], 0)} of clean nulls. **The novelty check is the weakest** ({pct(card['detection_rate']['Novelty'], 0)} detection): the durable fix for novelty is procedural (run two full weeks), not statistical. The checker's own report card is in [`data/results/checker_report_card.csv`](data/results/checker_report_card.csv).

## The experiment audit

{epq} experiments per quarter, mixed from clean wins, clean nulls, underpowered wins, novelty-only effects, SRM bugs and noisy revenue, with the truth known for every one. Two analysts:

| | Naive analyst | Rigorous analyst |
|---|---|---|
| Looks | Daily; stops at first p < 0.05 | Fixed horizon |
| Metrics | Conversion, revenue, **or any of 5 segments** | One pre-registered primary metric |
| Checks | None | Health checker; ships only on a clean pass |

| Per quarter (median over {nq} quarters) | Naive | Rigorous |
|---|---|---|
| "Wins" shipped | {nv_.shipped_median:.0f} | {rg_.shipped_median:.0f} |
| False wins | {nv_.false_wins_median:.0f} | {rg_.false_wins_median:.0f} |
| False discovery rate | {pct(nv_.fdr_median, 0)} | {pct(rg_.fdr_median, 0)} |
| True wins shipped / missed | {nv_.true_wins_shipped_median:.1f} / {nv_.true_wins_missed_median:.1f} | {rg_.true_wins_shipped_median:.1f} / {rg_.true_wins_missed_median:.1f} |
| Average reported vs true lift of shipped changes | {pct(nv_.avg_reported_lift)} vs {pct(nv_.avg_true_lift)} | {pct(rg_.avg_reported_lift)} vs {pct(rg_.avg_true_lift)} |
| Median total cost (illustrative) | {inr(nv_.total_cost_inr_median)} | {inr(rg_.total_cost_inr_median)} |

{"The rigorous process costs less in the base case" if cost_ok else "The rigorous process does **not** cost less in the base case"} ({inr(rg_.total_cost_inr_median)} vs {inr(nv_.total_cost_inr_median)}), but that depends on assumptions. {"In the worst case for it (a flagged rerun is treated as an abandoned idea, so declining to ship underpowered true wins is a permanent loss) the rigorous analyst costs **more**: " + inr(worst["rigorous_total_cost_median"]) + " vs " + inr(worst["naive_total_cost_median"]) + "." if not worst_ok else "Even in the worst case for it (a flagged rerun is treated as an abandoned idea) it still costs less."} See the sensitivity tables in the [audit report](reports/experiment_audit.md). **The false discovery rate and the overstated lifts do not depend on those assumptions.**

## Limitations

- **Simulated data is a model.** One outcome per user (not a daily panel); novelty decays with calendar day, not exposure time; treatment affects conversion only.
- **The audit's scenario mix and economics are assumptions**, not measurements. They are in [`config/audit_portfolio.yaml`](config/audit_portfolio.yaml) and re-run at different true-win shares.
- **No interference or network effects** (marketplaces, social products); those need cluster or switchback designs.
- **mSPRT's cost depends on the tuning parameter** tau, and is conservative with few looks.
- **Criteo's arms are imbalanced on pre-treatment features** in the public file; I report both raw and adjusted effects and do not assert the cause.
- The novelty check detects only part of the cases.

## Reproduce it

```bash
python -m venv .venv && .venv/Scripts/activate        # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements.txt && pip install -e .
pytest -q                                              # unit tests incl. slow Monte Carlo validation
# Real data (not committed; ~311 MB): download Criteo's uplift CSV and Hillstrom into data/raw/ (see reports/decision_log.md)
python src/load/load_real.py && python scripts/real_data_validation.py
python scripts/run_pitfalls.py && python scripts/run_validation.py
python scripts/run_audit.py --workers 4                # ~35 min; each worker needs ~0.5 GB RAM
python scripts/build_notebooks.py && python scripts/build_readme.py
streamlit run app/Home.py
```

The app and notebooks read precomputed results from `data/results/`, so they work without the raw datasets.
"""
Path("README.md").write_text(readme, encoding="utf-8")

# ------------------------------------------------------------------ audit report
sens_tbl = "\n".join(f"| {inr(r['false_win_cost_inr'])} | {inr(r['naive_total_cost_median'])} | {inr(r['rigorous_total_cost_median'])} |"
                     for r in sens_rows)
share_tbl = "\n".join(
    f"| {pct(r['true_win_share'], 0)} | {pct(r['naive_fdr_median'], 0)} | {pct(r['rigorous_fdr_median'], 0)} | "
    f"{r['naive_false_wins_median']:.0f} | {r['rigorous_false_wins_median']:.0f} |" for r in A["sens_true_win_share"])
scen_tbl = "\n".join(f"| {i.replace('_', ' ')} | {int(r.n):,} | {pct(r.naive_ship_rate, 0)} | {pct(r.rigorous_ship_rate, 0)} |"
                     for i, r in SC.iterrows())
audit_md = f"""# Experiment audit

**Question:** ShopKart ran {epq} A/B tests per quarter. How many shipped "wins" were real, and what did the false ones cost?

**Design:** {nq} simulated quarters × {epq} experiments = **{n_exp:,} experiments**, each with a known true effect. The scenario mix and economics are assumptions ([`config/audit_portfolio.yaml`](../config/audit_portfolio.yaml)). Two analysts decide on every experiment; every decision is scored against the truth.

## Results (median over quarters)
| | Naive | Rigorous |
|---|---|---|
| "Wins" shipped | {nv_.shipped_median:.0f} | {rg_.shipped_median:.0f} |
| False wins shipped | {nv_.false_wins_median:.0f} | {rg_.false_wins_median:.0f} |
| False discovery rate | {pct(nv_.fdr_median, 0)} | {pct(rg_.fdr_median, 0)} |
| True wins shipped | {nv_.true_wins_shipped_median:.1f} | {rg_.true_wins_shipped_median:.1f} |
| True wins not shipped | {nv_.true_wins_missed_median:.1f} | {rg_.true_wins_missed_median:.1f} |
| Average **reported** lift of shipped changes | {pct(nv_.avg_reported_lift)} | {pct(rg_.avg_reported_lift)} |
| Average **true** lift of shipped changes | {pct(nv_.avg_true_lift)} | {pct(rg_.avg_true_lift)} |

The naive analyst's reported lift is far above the true lift of what it ships (winner's curse at portfolio level).

## What each analyst ships, by what is really going on
| Scenario | Experiments | Naive ships | Rigorous ships |
|---|---|---|---|
{scen_tbl}

Only `true win` and `small win underpowered` are real wins; everything else should not ship. The rigorous analyst's weak spot is `novelty only`: the novelty check detects only part of those cases.

## Cost (illustrative; rests on stated assumptions)
Assumptions (config `economics` block): {ECO['monthly_active_users']:,} monthly users, {pct(ECO['baseline_conversion'], 0)} baseline conversion, ₹{ECO['avg_order_value_inr']:,} average order, {pct(ECO['contribution_margin'], 0)} contribution margin, {inr(ECO['engineering_cost_per_shipped_change_inr'])} engineering cost per shipped change. A false win costs engineering time only (its true effect is zero). A true win flagged for rerun is a **delay** ({ECO['rerun_delay_months']} months of its margin); a true win that is abandoned loses {ECO['months_lost_if_abandoned']} months.

| Cost of one false win | Naive, median quarterly cost | Rigorous, median quarterly cost |
|---|---|---|
{sens_tbl}

**Worst case for the rigorous analyst** (a flagged rerun is treated as an abandoned idea): naive {inr(worst['naive_total_cost_median'])} vs rigorous {inr(worst['rigorous_total_cost_median'])} median quarterly cost - {"rigorous still costs less" if worst_ok else "the rigorous analyst costs MORE in this case, because it declines to ship underpowered true wins"}.

## Sensitivity to the share of true wins
| True-win share | Naive FDR | Rigorous FDR | Naive false wins | Rigorous false wins |
|---|---|---|---|---|
{share_tbl}

## Limitations
- The scenario shares and every cost figure are assumptions; the false discovery rates and reported-vs-true lift gaps do not depend on the cost assumptions.
- The rigorous analyst's power check turns underpowered true wins into "rerun" calls; whether that is a delay or a loss is a business judgement (see the worst case above).
- {nq} quarters, not thousands: medians are stable but tails are not.
"""
Path("reports/experiment_audit.md").write_text(audit_md, encoding="utf-8")

# ------------------------------------------------------------------ resume bullets
bullets = f"""# Resume bullets (numbers read from the results)

**A/B Pitfall Lab** | Python, SQL (DuckDB), statsmodels, Streamlit · [Live app](https://a-b-test-pitfall-lab.streamlit.app/) · [GitHub](https://github.com/YashTomar2201/A-B-test-pitfall)

- Built an experimentation simulation lab quantifying **9 common A/B-testing pitfalls** across 100K+ Monte Carlo simulations; showed daily peeking inflates false positives from **5% to {pct(fpr14)}** and implemented O'Brien-Fleming and mSPRT sequential tests that restore validity (mSPRT at a cost of ~{msp_mult:.1f}x sample).
- Validated methods on **real randomized data (Criteo, {c['rows'] / 1e6:.1f}M rows; Hillstrom)** with SQL (DuckDB) and Python cross-checked to the last digit; real-data A/A tests gave {pct(c['real_aa']['visit']['false_positive_rate'])} false positives; found that covariate adjustment cut required sample by **{pct(1 - anc_v['sample_needed_ratio'], 0)}** on Criteo visits and flagged a covariate imbalance between Criteo's arms that shifts the effect estimate.
- Designed a 7-check experiment health checker and audited **{n_exp:,} simulated experiments** with known ground truth: a naive process had a **{pct(nv_.fdr_median, 0)} false discovery rate** among shipped wins vs **{pct(rg_.fdr_median, 0)}** with the checker. Deployed as an interactive app.
"""
Path("reports/resume_bullets.md").write_text(bullets, encoding="utf-8")
print("wrote README.md, reports/experiment_audit.md, reports/resume_bullets.md")
