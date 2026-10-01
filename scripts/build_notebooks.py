"""Generate (and optionally execute) the project notebooks.

    python scripts/build_notebooks.py            # build + execute
    python scripts/build_notebooks.py --no-run   # build only

Each pitfall notebook follows the same template: what goes wrong, simulate, quantify the damage,
detect, fix, verify the fix, so what. Cells run SMALL live simulations (seconds) and read the
big precomputed runs from data/results/.
"""
import argparse
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell as code
from nbformat.v4 import new_markdown_cell as md
from nbformat.v4 import new_notebook

NB = Path("notebooks")
SETUP = """import sys, json, warnings
sys.path.insert(0, "../src")
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, matplotlib.pyplot as plt
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25})
BAD, GOOD, NEUTRAL, ACCENT = "#c0392b", "#1e8449", "#7f8c8d", "#2c6fbb"
RES = "../data/results/"
"""


def nb(name, cells):
    n = new_notebook(cells=[code(SETUP)] + cells)
    n.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbf.write(n, NB / f"{name}.ipynb")


def pitfall(num, title, wrong, sim, quant, detect, fix, verify, sowhat):
    return [
        md(f"# P{num} - {title}\n\n## 1. What goes wrong\n{wrong}"),
        md("## 2. Simulate"), code(sim),
        md("## 3. Quantify the damage"), code(quant),
        md("## 4. Detect"), *([md(detect[0]), code(detect[1])] if isinstance(detect, tuple) else [md(detect)]),
        md("## 5. Fix"), *([md(fix[0]), code(fix[1])] if isinstance(fix, tuple) else [md(fix)]),
        md("## 6. Verify the fix"), code(verify) if verify else md("_The fix is procedural; see the Detect section for how it is checked._"),
        md(f"## So what\n{sowhat}"),
    ]


def build():
    NB.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- 00 toolkit
    nb("00_stats_toolkit", [
        md("# 00 - Statistics toolkit\nEvery later notebook relies on these functions, so each is checked against scipy or statsmodels (see `tests/`)."),
        code("""from abtest.analyze.tests import two_prop_ztest, welch_ttest, bootstrap_diff_ci, delta_method_ratio, srm_test
from abtest.analyze.power import sample_size_proportions, mde_proportions, days_needed
from statsmodels.stats.proportion import proportions_ztest
r = two_prop_ztest(500, 10_000, 560, 10_000)
print(f"ours: p = {r.p_value:.6f}   statsmodels: p = {proportions_ztest([560, 500], [10_000, 10_000])[1]:.6f}")
print(f"effect {r.effect:+.4f} ({r.rel_lift:+.1%}), 95% CI [{r.ci_low:+.4f}, {r.ci_high:+.4f}]")"""),
        md("**When to use which test**\n\n| Metric | Test |\n|---|---|\n| Conversion (0/1) | two-proportion z-test |\n| Continuous, well behaved | Welch t-test |\n| Heavy-tailed (revenue) | bootstrap, winsorising, or CUPED |\n| Ratio of two per-user totals (AOV, CTR) | delta method |\n| Is the split right? | chi-square sample-ratio check |"),
        code("""n = sample_size_proportions(0.05, 0.10)
print(f"To detect a +10% relative lift on a 5% baseline with 80% power you need {n:,} users per arm.")
print(f"At 12,000 users/day that is {days_needed(n, 12_000)} days; MDE with {n:,}/arm is {mde_proportions(0.05, n):.1%}.")"""),
        code("""print("SRM p-value, 50,000 vs 48,500 (expected 50/50):", f"{srm_test(50_000, 48_500):.2e}", "<- flag (p < 0.001)")"""),
        md("**So what:** a trustworthy analysis starts with tests whose error rates are known. The Monte Carlo notebooks that follow measure exactly how those error rates break when the assumptions behind them are violated."),
    ])

    # ---------------------------------------------------------------- 01 validation
    nb("01_simulator_validation", [
        md("# 01 - Simulator validation\n\nEverything downstream relies on the simulator, so it has to pass two tests first:\n1. **A/A tests** (no real effect) must reject about 5% of the time with flat p-values.\n2. **Known effects** must be recovered with about 95% CI coverage."),
        code("""v = json.load(open(RES + "validation.json"))
print("A/A runs:", v["aa"]["runs"], "  false positive rate:", f'{v["aa"]["false_positive_rate"]:.3f}', "  KS test vs uniform p:", f'{v["aa"]["ks_uniform_p"]:.2f}')
pd.DataFrame(v["known_effect"])"""),
        code("""from IPython.display import Image
Image("../reports/figures/sim_validation.png")"""),
        md("**So what:** the simulator behaves like a fair experiment when nothing is going on, and recovers real effects when they exist. Any false positive measured later is therefore caused by the injected pitfall, not by the simulator."),
    ])

    # ---------------------------------------------------------------- 02 real data
    nb("02_real_data", [
        md("# 02 - Validation on real randomized experiments\n\n| Dataset | What it is |\n|---|---|\n| **Criteo Uplift v2.1** | 13.98M users in a real ad experiment (85% treated / 15% control) |\n| **Hillstrom** | 64,000 customers in a real email test |\n\nMetrics, SRM check, z-test and CUPED are implemented in **SQL** (DuckDB, see `sql/`) and cross-checked against Python."),
        code("""r = json.load(open(RES + "real_data.json"))
c = r["criteo"]
print(f'rows {c["rows"]:,}  treatment share {c["treatment_share"]:.6f}  SRM chi2 vs documented 85%: {c["srm_chi2_vs_documented_85pct"]:.2e}  flag: {c["srm_flag"]}')
print("SQL z =", round(c["conversion"]["z_sql"], 4), "  Python z =", round(c["conversion"]["z_python"], 4), "  match:", c["conversion"]["sql_python_match"])
print("Real A/A (control split at random, 1,000 runs):", {k: v["false_positive_rate"] for k, v in c["real_aa"].items()})"""),
        code("""for m in ("visit", "conversion"):
    x = c[m]
    print(f'{m}: control {x["control_rate"]:.4%} -> treatment {x["treatment_rate"]:.4%}  ({x["rel_lift"]:+.1%} relative, 95% CI {x["ci"][0]:.4%} to {x["ci"][1]:.4%})')"""),
        md("## A real-data surprise: the arms are not perfectly balanced\nIn a randomized experiment, pre-treatment features should have the same mean in both arms. With 14M users the standardized difference should be around 0.0005."),
        code("""smd = pd.Series(c["smd"])
ax = smd.plot.bar(color=BAD, figsize=(7, 3)); ax.set(ylabel="Standardized mean difference", title="Criteo covariate balance"); plt.show()
print(f'max |SMD| = {c["max_abs_smd"]:.3f}')
a = c["ancova"]["visit"]
print(f'visit effect: raw {a["effect_raw"]:+.4f}  vs  adjusted for the 12 features {a["effect_ancova"]:+.4f}  ({a["effect_shift_in_se_units"]:+.0f} standard errors apart)')"""),
        md("**Reading this:** covariate adjustment moves the estimate far more than sampling noise could, which means the treated and control groups differ in ways the features capture. I cannot tell from the data whether that comes from the public release or from how the features were built, so both estimates are reported. The health checker's **Balance** check flags this class of problem."),
        md("## CUPED / covariate adjustment on real data"),
        code("""a = c["ancova"]
print(pd.DataFrame(a).T[["se_reduction", "sample_needed_ratio"]].rename(columns={"se_reduction": "SE reduction", "sample_needed_ratio": "sample needed vs unadjusted"}))
h = r["hillstrom"]
print(f'\\nHillstrom: corr(pre-period spend, spend) = {h["corr_history_spend"]:.3f}, variance removed by CUPED = {h["variance_reduction_python"]:.4%}')"""),
        md("**So what:** CUPED's gain scales with the squared correlation between the covariate and the metric. On Criteo the features predict visits well enough to save a meaningful share of users; on Hillstrom, past spend barely predicts future spend (correlation about 0.02), so CUPED does almost nothing. A variance-reduction method is only as good as its covariate."),
    ])

    # ---------------------------------------------------------------- P1
    nb("10_peeking", pitfall(1, "Peeking / optional stopping",
        "You check the p-value every day and stop as soon as it dips below 0.05. Each look is another chance for noise to cross the line.",
        "from abtest.pitfalls import peeking\nfrom abtest.analyze.sequential import calibrate_obf\nlooks = peeking.fpr_by_looks(n_sims=5_000)\nlooks",
        "fig, ax = plt.subplots(figsize=(6, 3.6))\nax.plot(looks.looks, looks.fpr * 100, 'o-', color=BAD); ax.axhline(5, color=NEUTRAL, ls='--')\nax.set(xscale='log', xlabel='looks', ylabel='false positive rate (%)', title='A/A tests: stopping at the first p < 0.05'); plt.show()\nprint(f\"1 look: {looks.fpr.iloc[0]:.1%}   14 looks: {looks[looks.looks == 14].fpr.iloc[0]:.1%}\")",
        "Count how many times the analysis was looked at and whether it was stopped on a fixed-horizon p-value. In the health checker this is the **Peeking** check (red if stopped early without a sequential method).",
        ("Two fixes. **O'Brien-Fleming** boundaries need the looks planned in advance (strict early, about 1.96 at the end). **mSPRT** gives always-valid p-values for any number of looks. The O'Brien-Fleming constant is calibrated by simulation and sanity-checked against the published value (about 2.04 for 5 looks).",
         "print('K=5 constant:', round(calibrate_obf(5, n_sims=100_000), 3), '(published ~2.04)')"),
        "null = peeking.compare_methods(rel_lift=0.0, n_sims=5_000); alt = peeking.compare_methods(rel_lift=0.10, n_sims=5_000)\nrows = [{'method': m, 'false positive rate': null[m]['reject_rate'], 'power at +10% lift': alt[m]['reject_rate'], 'avg looks used (real effect)': alt[m]['avg_looks_used']} for m in ['fixed_horizon','naive_peeking','obrien_fleming','msprt']]\nprint(pd.DataFrame(rows).round(3).to_string(index=False))\nprint()\nprint(peeking.msprt_sample_cost(n_sims=3_000).round(3).to_string(index=False))",
        "Daily peeking inflates false positives several-fold. O'Brien-Fleming fixes it at almost no cost in power. mSPRT also fixes it, but it is conservative at a fixed horizon: it needs about twice the sample for the same power. That is the price of being allowed to look at any time."))

    # ---------------------------------------------------------------- P2
    nb("11_winners_curse", pitfall(2, "Underpowered tests and the winner's curse",
        "With low power the only way to reach significance is to overestimate the effect. Significant results from small tests are exaggerated, and some even have the wrong sign.",
        "from abtest.pitfalls import winners_curse\nwc = winners_curse.exaggeration_vs_power(n_sims=20_000)\nwc.round(3)",
        "fig, ax = plt.subplots(figsize=(6, 3.6))\nax.plot(wc.power * 100, wc.exaggeration_ratio, 'o-', color=BAD); ax.axhline(1, color=NEUTRAL, ls='--')\nax.set(xlabel='power (%)', ylabel='overstatement of the true lift (x)'); plt.show()",
        "Compare the achieved minimum detectable effect with the lift you observed. If the observed lift is near or below the MDE and significant, treat it as exaggerated (health checker: **Power**).",
        ("Size the test with a power analysis before launch and commit to a minimum detectable effect.",
         "from abtest.analyze.power import sample_size_proportions\nprint('users per arm for 80% power to detect +10% on a 5% base:', f'{sample_size_proportions(0.05, 0.10):,}')"),
        "print(wc[['target_power','power','exaggeration_ratio','wrong_sign_share']].round(3).to_string(index=False))",
        "At 10% power a 'significant' result overstated the real lift about 4x; at 80% power the overstatement is about 14%. Underpowered tests do not just miss wins, they report lucky overestimates as the truth."))

    # ---------------------------------------------------------------- P3
    nb("12_srm", pitfall(3, "Sample ratio mismatch (SRM)",
        "The split is meant to be 50/50 but the treatment arm loses users (for example a page that crashes on slow phones, so they never get logged). The arms are no longer comparable and every number from the test is biased, usually in the treatment's favour.",
        "from abtest.pitfalls import srm\nd = srm.srm_damage(drop_rates=(0, 0.01, 0.03, 0.05), n_sims=60, users_per_day=12_000)\nd",
        "fig, ax = plt.subplots(figsize=(6, 3.6))\nax.plot(d.drop_rate * 100, d.avg_fake_rel_lift * 100, 'o-', color=BAD, label='fake lift (%)')\nax.plot(d.drop_rate * 100, d.false_positive_rate * 100, 's-', color=ACCENT, label='false positive rate (%)'); ax.legend(); ax.set(xlabel='treatment users lost (%)'); plt.show()",
        ("The chi-square sample-ratio check at p < 0.001. Detection depends on how many users you have, so measure it.",
         "s = srm.srm_detection_by_size(users_per_day_grid=(1_000, 4_000, 8_000), n_sims=60)\nprint(s.to_string(index=False))"),
        "There is no statistical fix. The fix is to distrust the result, find the root cause (bots, redirects, crashes, logging bugs, filters applied after assignment) and rerun.",
        None,
        "A small, invisible user loss produces a fake lift and inflates false positives. An SRM check is cheap and should run before anyone looks at the metric."))

    # ---------------------------------------------------------------- P4
    nb("13_novelty", pitfall(4, "Novelty effect",
        "Users try something because it is new, then the effect fades. A short test reports the early, inflated lift.",
        "from abtest.pitfalls import novelty\nnv = novelty.novelty_scenarios(n_sims=5_000)\nnv.round(3)",
        "x = np.arange(len(nv)); fig, ax = plt.subplots(figsize=(7, 3.6))\nax.bar(x - .27, nv.est_3d * 100, .27, color=BAD, label='first 3 days'); ax.bar(x, nv.est_14d * 100, .27, color=NEUTRAL, label='all 14 days'); ax.bar(x + .27, nv.est_week2 * 100, .27, color=GOOD, label='week 2 only')\nax.scatter(x, nv.true_long_run_lift * 100, marker='_', s=500, color='k', zorder=5, label='truth'); ax.set_xticks(x); ax.set_xticklabels(nv.scenario, fontsize=7); ax.legend(fontsize=8); plt.show()",
        ("Estimate the effect **per day** and fit a weighted regression of the daily effect on the day. A significantly falling trend signals novelty.",
         "print('flag rate with novelty only:', nv.loc[nv.scenario == 'novelty only', 'novelty_flagged'].iloc[0].round(3))\nprint('false alarm rate with no novelty:', nv.loc[nv.scenario == 'no novelty, no effect', 'novelty_flagged'].iloc[0].round(3))"),
        "Run at least two full weekly cycles and report the effect from mature cohorts (here, week 2).",
        "print(nv[['scenario', 'true_long_run_lift', 'est_3d', 'est_14d', 'est_week2']].round(3).to_string(index=False))",
        "A test with zero long-run effect can look like a clear win after 3 days. Reading the second week recovers the truth. The trend check catches it only part of the time, so the durable fix is procedural: run long enough."))

    # ---------------------------------------------------------------- P5
    nb("14_multiple_testing", pitfall(5, "Multiple metrics and variants",
        "Check twenty metrics and ship if any is significant. Even with no real effect, one usually will be.",
        "from abtest.pitfalls import multiple_testing as mt\nmm = mt.fpr_vs_metrics(n_sims=20_000)\nmm.round(3)",
        "fig, ax = plt.subplots(figsize=(6, 3.6))\nax.plot(mm.n_metrics, mm.uncorrected * 100, 'o-', color=BAD, label='uncorrected'); ax.plot(mm.n_metrics, mm.bh * 100, 's-', color=ACCENT, label='Benjamini-Hochberg'); ax.plot(mm.n_metrics, mm.holm * 100, '^-', color=GOOD, label='Holm'); ax.axhline(5, color=NEUTRAL, ls='--'); ax.legend(); ax.set(xlabel='metrics checked', ylabel='chance of >= 1 false win (%)'); plt.show()",
        "Count the comparisons the team made. If the primary metric is significant raw but not after Holm, flag it (health checker: **Multiple testing**).",
        "Pre-register **one** primary metric. Correct the rest: **Holm** controls the family-wise error rate (use it for decision metrics); **Benjamini-Hochberg** controls the false discovery rate (use it for exploratory metrics). The same applies to A/B/C/D variants that all share one control.",
        "print(mt.multiple_variants(n_sims=20_000).round(3).to_string(index=False))",
        "With 20 metrics the chance of a false win was over half. Holm and BH bring it back to about 5% with correlated metrics too."))

    # ---------------------------------------------------------------- P6
    nb("15_segments", pitfall(6, "Segment p-hacking",
        "The test did not win overall, so you slice by device, city and tier until a segment does. Slicing afterwards almost guarantees a significant slice.",
        "from abtest.pitfalls import segments\nseg = pd.DataFrame([segments.segment_hacking(n_segments=m, n_sims=20_000) for m in (1, 3, 5, 10, 15, 30)])\nseg.round(3)",
        "fig, ax = plt.subplots(figsize=(6, 3.6))\nax.plot(seg.n_segments, seg.any_segment_significant * 100, 'o-', color=BAD, label='any segment wins'); ax.plot(seg.n_segments, seg.bonferroni_any_significant * 100, '^-', color=GOOD, label='with Bonferroni'); ax.axhline(5, color=NEUTRAL, ls='--'); ax.legend(); ax.set(xlabel='segments sliced', ylabel='tests with a winning segment (%)'); plt.show()",
        "Compare the list of segments analysed against the list committed to before launch. Anything analysed after the fact is exploratory.",
        "Pre-register segments, correct for the number you test, and treat post-hoc segment findings as **hypotheses for a new test**, not reasons to ship.",
        "r = segments.segment_hacking(n_segments=15, n_sims=20_000)\nprint(f\"15 segments: {r['any_segment_significant']:.1%} of no-effect tests have a 'winner' (avg reported lift {r['avg_reported_abs_lift_in_winner']:.0%}); a follow-up confirms it {r['followup_confirms']:.1%} of the time\")",
        "A 'winning' segment in a no-effect test is the norm, not the exception, and it shows a large, convincing lift. Follow-up tests almost never confirm it."))

    # ---------------------------------------------------------------- P7
    nb("16_heavy_tails", pitfall(7, "Heavy-tailed revenue metrics",
        "A few whale customers dominate revenue variance. Revenue tests then have very low power, and one whale landing in one arm can swing the result.",
        "from abtest.pitfalls import heavy_tails\nht = heavy_tails.heavy_tail_study(whale_rates=(0, 0.005), lifts=(0.0, 0.10), n_sims=150, users_per_day=2_000)\nht.pivot_table(index=['whale_rate', 'true_conv_lift'], columns='method', values='reject_rate').round(3)",
        "full = pd.read_csv(RES + 'p7_heavy_tails.csv')\nfig, ax = plt.subplots(figsize=(6, 3.6))\nfor m, c in (('welch', BAD), ('winsorized_p99', GOOD), ('cuped', ACCENT), ('bootstrap', NEUTRAL)):\n    d = full[(full.method == m) & (full.true_conv_lift == 0.10)]\n    if len(d): ax.plot(d.whale_rate * 100, d.reject_rate * 100, 'o-', color=c, label=m)\nax.legend(); ax.set(xlabel='whale share of converters (%)', ylabel='power (%)', title='Power with a true +10% conversion lift'); plt.show()",
        "Look at the distribution: share of revenue from the top 0.1% of users, and whether significance flips after winsorising (health checker: **Outliers**).",
        "Winsorise at a cap computed on the **pooled** data (per-arm caps would bias the comparison), or use a bootstrap or CUPED. Note that winsorising changes the question: you estimate the effect on capped revenue, not true revenue.",
        "print(full.pivot_table(index=['whale_rate', 'true_conv_lift'], columns='method', values='reject_rate').round(3).to_string())",
        "Whales destroy the power of a plain t-test on revenue without breaking its false positive rate. Pooled winsorising restores power; be explicit that it answers a slightly different question."))

    # ---------------------------------------------------------------- P8
    nb("17_unit_of_analysis", pitfall(8, "Wrong unit of analysis",
        "Users are randomised but sessions are analysed as if they were independent. Sessions from the same user are correlated, so the standard error is too small and false positives rise.",
        "from abtest.pitfalls import unit_of_analysis\nua = unit_of_analysis.unit_of_analysis_fpr(n_sims=500)\nua.round(3)",
        "fig, ax = plt.subplots(figsize=(6, 3.6))\nax.plot(ua.user_sd, ua.naive_session_level_fpr * 100, 'o-', color=BAD, label='session-level z-test'); ax.plot(ua.user_sd, ua.delta_method_fpr * 100, 's-', color=GOOD, label='delta method (by user)'); ax.axhline(5, color=NEUTRAL, ls='--'); ax.legend(); ax.set(xlabel='how different users are (logit sd)', ylabel='false positive rate (%)'); plt.show()",
        "Ask what the randomisation unit is and whether the denominator of the metric is that unit. Ratio metrics (CTR, AOV) are the usual trap.",
        "Analyse at the randomisation unit. For ratio metrics use the **delta method** (or a bootstrap resampling users).",
        "print(ua[['user_sd', 'naive_session_level_fpr', 'delta_method_fpr']].round(3).to_string(index=False))",
        "The more users differ from each other, the worse the session-level test gets, reaching several times the nominal rate. The delta method stays near 5%."))

    # ---------------------------------------------------------------- P9
    nb("18_simpson", pitfall(9, "Simpson's paradox during ramp-up",
        "A test ramps up at 10% treatment during a high-conversion sale, then runs at 50%. Pooling all days compares a mostly-sale control with a mostly-normal treatment.",
        "from abtest.pitfalls import simpson\nsp = simpson.simpson_study(n_sims=80)\nsp",
        "fig, ax = plt.subplots(figsize=(4.5, 3.4)); ax.bar(['pooled', 'stratified by day'], [sp['pooled_avg_effect'] * 100, sp['stratified_avg_effect'] * 100], color=[BAD, GOOD]); ax.axhline(0, color='k', lw=.8); ax.set(ylabel='estimated effect (pp)'); plt.show()",
        "Plot the treatment share by day. If it changed during the test, pooled results are suspect.",
        "Stratify by day (weighted average of daily differences), or analyse only the period after the ramp finished.",
        None,
        "When allocation changes while the baseline also changes, pooled results can show a large effect that does not exist. Stratifying by day removes the bias."))

    # ---------------------------------------------------------------- 20 cuped
    nb("20_cuped", [
        md("# 20 - CUPED variance reduction\nCUPED subtracts the part of each user's metric that was predictable from before the test, so the remaining noise is smaller. The gain is **rho squared**, where rho is the correlation between the pre-period covariate and the metric."),
        code("""v = json.load(open(RES + "validation.json"))
print(pd.DataFrame(v["cuped_rho"]).round(3).to_string(index=False))
from IPython.display import Image
Image("../reports/figures/cuped_rho2.png")"""),
        code("""print("Simulated sparse revenue metric:", v["cuped_sim"])"""),
        md("Revenue is sparse (only 5% of users convert), so a pre-period spend covariate helps only modestly there. Real data shows the range:"),
        code("""r = json.load(open(RES + "real_data.json"))
a = r["criteo"]["ancova"]
for m in a: print(f'Criteo {m}: SE reduced {a[m]["se_reduction"]:.1%}, same precision with {a[m]["sample_needed_ratio"]:.0%} of the users')
h = r["hillstrom"]; print(f'Hillstrom spend: corr with past spend {h["corr_history_spend"]:.3f}, variance removed {h["variance_reduction_python"]:.3%}')"""),
        md("**So what:** CUPED turns a good covariate into shorter tests (Criteo visits: about a quarter fewer users for the same precision) and does nothing with a weak one (Hillstrom). Always check the covariate's correlation before promising a speed-up, and verify the method keeps the A/A false positive rate at 5%."),
    ])

    # ---------------------------------------------------------------- 30 audit
    nb("30_audit", [
        md("# 30 - The experiment audit\n**ShopKart ran 40 A/B tests a quarter. How many shipped 'wins' were real?** Simulated quarters with known ground truth, analysed by a naive and a rigorous analyst. All money figures rest on assumptions in `config/audit_portfolio.yaml`."),
        code("""s = pd.read_csv(RES + "audit_summary.csv", index_col=0)
res = json.load(open(RES + "audit_results.json"))
print("quarters simulated:", res["n_quarters"], " experiments per quarter:", res["experiments_per_quarter"])
s.T"""),
        code("""sc = pd.read_csv(RES + "audit_by_scenario.csv", index_col=0)
ax = sc[["naive_ship_rate", "rigorous_ship_rate"]].mul(100).plot.bar(color=[BAD, GOOD], figsize=(8, 3.6)); ax.set(ylabel="% shipped"); plt.show()
sc.round(3)"""),
        code("""pd.DataFrame(res["sens_false_win_cost"])"""),
        code("""print("worst case for rigorous (rerun = abandoned):", res["worst_case_rerun_equals_abandon"])
pd.DataFrame(res["sens_true_win_share"])"""),
        md("**So what:** see `reports/experiment_audit.md` for the full write-up, assumptions and limitations."),
    ])


def execute():
    from nbconvert.preprocessors import ExecutePreprocessor
    for p in sorted(NB.glob("*.ipynb")):
        n = nbf.read(p, as_version=4)
        ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(n, {"metadata": {"path": str(NB)}})
        nbf.write(n, p)
        print("executed", p.name, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-run", action="store_true")
    a = ap.parse_args()
    build()
    if not a.no_run:
        execute()
