"""Phase 2.4 + 5 + 6.3: simulator validation, CUPED study, and the health checker's own report card.

    python scripts/run_validation.py            # full (~5 min)
    python scripts/run_validation.py --quick
Writes data/results/validation.json and figures in reports/figures/.
"""
import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from abtest.analyze.cuped import cuped_adjust, variance_reduction  # noqa: E402
from abtest.analyze.power import sample_size_means  # noqa: E402
from abtest.analyze.tests import two_prop_ztest, welch_ttest  # noqa: E402
from abtest.diagnose.checker import diagnose  # noqa: E402
from abtest.simulate.engine import ExperimentConfig, simulate  # noqa: E402

RES, FIG = Path("data/results"), Path("reports/figures")
BAD, GOOD, NEUTRAL, ACCENT = "#c0392b", "#1e8449", "#7f8c8d", "#2c6fbb"
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10, "axes.titleweight": "bold"})


def conv_test(df):
    g = df.groupby("arm")["converted"].agg(["sum", "count"])
    return two_prop_ztest(g.loc["control", "sum"], g.loc["control", "count"],
                          g.loc["treatment", "sum"], g.loc["treatment", "count"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    q = ap.parse_args().quick
    k = 0.1 if q else 1.0
    n = lambda x: max(int(x * k), 30)  # noqa: E731
    RES.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    OUT, t0 = {}, time.time()

    # ------------------------------------------------ A/A validation of the simulator
    pv = np.array([conv_test(simulate(ExperimentConfig(days=7, users_per_day=2_000, seed=s))).p_value
                   for s in range(n(2_000))])
    fpr = float((pv < 0.05).mean())
    ks = float(__import__("scipy.stats", fromlist=["kstest"]).kstest(pv, "uniform").pvalue)
    OUT["aa"] = {"runs": len(pv), "false_positive_rate": fpr, "ks_uniform_p": ks}

    # known-effect recovery + CI coverage
    rows = []
    for lift in (0.0, 0.05, 0.10, 0.20):
        est, cov = [], 0
        true_abs = 0.05 * lift
        m = n(1_000)
        for s in range(m):
            r = conv_test(simulate(ExperimentConfig(days=7, users_per_day=4_000, lift=lift, seed=10_000 + s)))
            est.append(r.effect)
            cov += r.ci_low <= true_abs <= r.ci_high
        rows.append({"true_rel_lift": lift, "true_abs_effect": true_abs, "mean_estimate": float(np.mean(est)),
                     "ci_coverage": cov / m})
    known = pd.DataFrame(rows)
    OUT["known_effect"] = known.to_dict("records")
    known.to_csv(RES / "sim_known_effect.csv", index=False)

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ax[0].hist(pv, bins=20, color=ACCENT, edgecolor="white")
    ax[0].axhline(len(pv) / 20, color=BAD, ls="--")
    ax[0].set(xlabel="p-value", ylabel="Count", title=f"A/A tests: p-values are flat (FPR {fpr:.1%})")
    ax[1].plot(known.true_abs_effect * 100, known.mean_estimate * 100, "o-", color=ACCENT, label="Mean estimate")
    ax[1].plot(known.true_abs_effect * 100, known.true_abs_effect * 100, "--", color=NEUTRAL, label="Truth")
    ax[1].set(xlabel="True effect (percentage points)", ylabel="Estimated effect (pp)", title="Known effects are recovered")
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "sim_validation.png")
    plt.close(fig)
    print("validation gate done", f"FPR={fpr:.3f}", flush=True)

    # ------------------------------------------------ CUPED: variance reduction follows rho^2
    rng = np.random.default_rng(0)
    rows = []
    for rho in (0.0, 0.2, 0.4, 0.6, 0.8, 0.9):
        nn = 200_000
        x = rng.standard_normal(nn)
        y = rho * x + np.sqrt(1 - rho**2) * rng.standard_normal(nn)
        rows.append({"rho": rho, "measured_reduction": variance_reduction(y, x), "theory_rho2": rho**2})
    rho_tab = pd.DataFrame(rows)
    rho_tab.to_csv(RES / "cuped_rho.csv", index=False)

    # A/A false positive rate and power with / without CUPED on the simulator's (sparse) revenue metric
    def reject(lift, m, whale=0.0):
        a = b = 0
        for s in range(m):
            df = simulate(ExperimentConfig(days=14, users_per_day=2_000, lift=lift, whale_rate=whale, seed=50_000 + s))
            t = (df.arm == "treatment").values
            y = df.revenue.values
            a += welch_ttest(y[~t], y[t]).significant
            yc = cuped_adjust(y, df.pre_spend.values)
            b += welch_ttest(yc[~t], yc[t]).significant
        return a / m, b / m
    m = n(600)
    aa_raw, aa_cup = reject(0.0, m)
    pw_raw, pw_cup = reject(0.10, m)
    OUT["cuped_sim"] = {"aa_fpr_raw": aa_raw, "aa_fpr_cuped": aa_cup, "power_raw": pw_raw, "power_cuped": pw_cup,
                        "note": "revenue is sparse (5% convert), so the pre-period covariate helps only modestly"}
    OUT["cuped_rho"] = rho_tab.to_dict("records")
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    ax.plot(rho_tab.rho, rho_tab.measured_reduction * 100, "o", color=ACCENT, label="Measured")
    xs = np.linspace(0, 0.9, 50)
    ax.plot(xs, xs**2 * 100, "-", color=NEUTRAL, label="Theory: rho^2")
    ax.set(xlabel="Correlation between pre-period covariate and metric", ylabel="Variance removed (%)",
           title="CUPED: the gain is rho^2")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "cuped_rho2.png")
    plt.close(fig)
    # translate a variance reduction into test length
    vr = 0.30
    n_raw = sample_size_means(sd=1.0, mde_abs=0.05)
    n_cup = sample_size_means(sd=np.sqrt(1 - vr), mde_abs=0.05)
    OUT["cuped_days_example"] = {"variance_reduction": vr, "sample_ratio": n_cup / n_raw}
    print("CUPED done", flush=True)

    # ------------------------------------------------ Health checker report card
    cases = {
        "clean_null": (dict(lift=0.0), {}),
        "clean_win": (dict(lift=0.15), {}),
        "srm_bug": (dict(lift=0.0, srm_drop_rate=0.04), {}),
        "novelty_only": (dict(lift=0.0, novelty_boost=0.30, novelty_halflife=3.0), {}),
        "underpowered": (dict(lift=0.04, users_per_day=1_500), {}),
        "whale_revenue": (dict(lift=0.10, whale_rate=0.005), {"revenue_col": "revenue"}),
        "imbalanced_arms": (dict(lift=0.0), {"imbalance": 1.08}),
    }
    target = {"srm_bug": "Sample ratio", "novelty_only": "Novelty", "underpowered": "Power",
              "whale_revenue": "Outliers", "imbalanced_arms": "Balance"}
    checks = ["Sample ratio", "Novelty", "Power", "Outliers", "Balance"]
    m = n(300)
    card = []
    for name, (cfg_kw, dkw) in cases.items():
        fired = {c: 0 for c in checks}
        verdicts = {"SHIP": 0, "NO WIN": 0, "INVESTIGATE": 0, "DON'T TRUST": 0}
        for s in range(m):
            base = dict(days=14, users_per_day=6_000, seed=90_000 + s)
            df = simulate(ExperimentConfig(**{**base, **cfg_kw}))
            dkw2 = dict(dkw)
            imb = dkw2.pop("imbalance", None)
            if imb:
                df.loc[df.arm == "treatment", "pre_spend"] *= imb
            rep = diagnose(df, planned_mde_rel=0.10, covariates=["pre_spend"], **dkw2)
            for c in checks:
                fired[c] += rep.status_of(c) != "green"
            verdicts[next(v for v in verdicts if rep.verdict.startswith(v))] += 1
        row = {"scenario": name, **{f"fires_{c}": fired[c] / m for c in checks},
               **{f"verdict_{v}": c / m for v, c in verdicts.items()}}
        card.append(row)
        print("  scenario", name, flush=True)
    card = pd.DataFrame(card)
    card.to_csv(RES / "checker_report_card.csv", index=False)
    clean = card[card.scenario.isin(["clean_null", "clean_win"])]
    OUT["checker_report_card"] = {
        "runs_per_scenario": m,
        "detection_rate": {c: float(card.loc[card.scenario == s, f"fires_{c}"].iloc[0]) for s, c in target.items()},
        "false_alarm_rate_on_clean_tests": {c: float(clean[f"fires_{c}"].mean()) for c in checks},
        "clean_win_ship_rate": float(card.loc[card.scenario == "clean_win", "verdict_SHIP"].iloc[0]),
        "clean_null_ship_rate": float(card.loc[card.scenario == "clean_null", "verdict_SHIP"].iloc[0]),
    }
    json.dump(OUT, open(RES / "validation.json", "w"), indent=2, default=float)
    print(json.dumps(OUT, indent=2, default=float))
    print(card.round(3).to_string())
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
