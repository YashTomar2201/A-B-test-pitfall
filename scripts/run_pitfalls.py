"""Phase 4: run every pitfall study, save tables + figures, and write reports/pitfall_summary.md.

    python scripts/run_pitfalls.py            # full run (~8-10 min)
    python scripts/run_pitfalls.py --quick    # small run for smoke testing

All headline numbers in the summary are generated from the results, never typed by hand.
"""
import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from abtest.pitfalls import (heavy_tails, multiple_testing, novelty, peeking, segments,  # noqa: E402
                             simpson, srm, unit_of_analysis, winners_curse)

RES, FIG = Path("data/results"), Path("reports/figures")
RES.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)
BAD, GOOD, NEUTRAL, ACCENT = "#c0392b", "#1e8449", "#7f8c8d", "#2c6fbb"

plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10, "axes.titlesize": 11,
                     "axes.titleweight": "bold"})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    q = ap.parse_args().quick
    k = 0.05 if q else 1.0                       # scale factor for simulation counts

    def n(x):
        return max(int(x * k), 50)

    R, H, t0 = {}, {}, time.time()

    # ------------------------------------------------------------ P1 peeking
    looks = peeking.fpr_by_looks(n_sims=n(20_000))
    looks.to_csv(RES / "p1_fpr_by_looks.csv", index=False)
    null = peeking.compare_methods(rel_lift=0.0, n_sims=n(20_000))
    alt = peeking.compare_methods(rel_lift=0.10, n_sims=n(20_000))
    tau = peeking.msprt_tau_sensitivity(n_sims=n(10_000))
    cost = peeking.msprt_sample_cost(n_sims=n(10_000))
    tau.to_csv(RES / "p1_msprt_tau.csv", index=False)
    cost.to_csv(RES / "p1_msprt_cost.csv", index=False)
    need2 = cost.loc[cost.msprt_power >= 0.80, "sample_multiplier"].min()
    R["p1"] = {"looks": looks.to_dict("records"), "null": null, "alt_10pct": alt,
               "msprt_sample_multiplier_for_80pct_power": float(need2)}
    fpr14 = float(looks.loc[looks.looks == 14, "fpr"].iloc[0])
    H["P1 Peeking"] = (f"Checking daily for 14 days raised the false positive rate from 5% to {pct(fpr14)}; "
                       f"O'Brien-Fleming held it at {pct(null['obrien_fleming']['reject_rate'])} and mSPRT at "
                       f"{pct(null['msprt']['reject_rate'])}, but mSPRT needed ~{need2:.1f}x the sample for 80% power.")
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    ax[0].plot(looks.looks, looks.fpr * 100, "o-", color=BAD)
    ax[0].axhline(5, color=NEUTRAL, ls="--")
    ax[0].set(xscale="log", xlabel="Number of looks at the data", ylabel="False positive rate (%)",
              title="Peeking inflates false positives (A/A tests)")
    ax[0].set_xticks(looks.looks)
    ax[0].set_xticklabels(looks.looks)
    names = ["fixed_horizon", "naive_peeking", "obrien_fleming", "msprt"]
    labels = ["Fixed\nhorizon", "Naive\npeeking", "O'Brien-\nFleming", "mSPRT"]
    x = np.arange(4)
    ax[1].bar(x - 0.2, [null[m]["reject_rate"] * 100 for m in names], 0.4, color=[BAD if m == "naive_peeking" else NEUTRAL for m in names], label="No real effect (want 5%)")
    ax[1].bar(x + 0.2, [alt[m]["reject_rate"] * 100 for m in names], 0.4, color=ACCENT, label="True +10% lift (power)")
    ax[1].set_xticks(x)
    ax[1].set_xticklabels(labels)
    ax[1].set(ylabel="Rejection rate (%)", title="Validity vs power by stopping rule")
    ax[1].legend(fontsize=8)
    save(fig, "p1_peeking")

    # ------------------------------------------------------------ P2 winner's curse
    wc = winners_curse.exaggeration_vs_power(n_sims=n(50_000))
    wc.to_csv(RES / "p2_winners_curse.csv", index=False)
    lo, hi = wc.iloc[0], wc[wc.target_power == 0.80].iloc[0]
    R["p2"] = wc.to_dict("records")
    H["P2 Winner's curse"] = (f"At ~{pct(lo.power, 0)} power, significant results overstated the true lift "
                              f"{lo.exaggeration_ratio:.1f}x; at 80% power the overstatement fell to {hi.exaggeration_ratio:.2f}x.")
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    ax.plot(wc.power * 100, wc.exaggeration_ratio, "o-", color=BAD)
    ax.axhline(1, color=NEUTRAL, ls="--")
    ax.set(xlabel="Statistical power (%)", ylabel="Average overstatement of the true lift (x)",
           title="Winner's curse: significant results exaggerate")
    save(fig, "p2_winners_curse")

    # ------------------------------------------------------------ P3 SRM
    sd = srm.srm_damage(n_sims=n(300), users_per_day=12_000)
    sz = srm.srm_detection_by_size(n_sims=n(300))
    sd.to_csv(RES / "p3_srm_damage.csv", index=False)
    sz.to_csv(RES / "p3_srm_detection.csv", index=False)
    R["p3"] = {"damage": sd.to_dict("records"), "detection_by_size": sz.to_dict("records")}
    r5 = sd[sd.drop_rate == 0.05].iloc[0]
    H["P3 Sample ratio mismatch"] = (f"Losing just 5% of low-engagement treatment users produced a fake "
                                     f"{pct(r5.avg_fake_rel_lift)} lift and a {pct(r5.false_positive_rate, 0)} false positive rate "
                                     f"(true effect 0); the SRM check fired in {pct(r5.srm_detected, 0)} of those tests.")
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    ax[0].plot(sd.drop_rate * 100, sd.avg_fake_rel_lift * 100, "o-", color=BAD, label="Fake lift (%)")
    ax[0].plot(sd.drop_rate * 100, sd.false_positive_rate * 100, "s-", color=ACCENT, label="False positive rate (%)")
    ax[0].axhline(5, color=NEUTRAL, ls="--")
    ax[0].set(xlabel="Treatment users lost (%)", title="Damage from a lossy treatment arm (true lift = 0)")
    ax[0].legend(fontsize=8)
    ax[1].plot(sd.drop_rate * 100, sd.srm_detected * 100, "o-", color=GOOD)
    ax[1].set(xlabel="Treatment users lost (%)", ylabel="SRM check fires (%)", title="Would the SRM check catch it?")
    save(fig, "p3_srm")

    # ------------------------------------------------------------ P4 novelty
    nv = novelty.novelty_scenarios(n_sims=n(20_000))
    nv.to_csv(RES / "p4_novelty.csv", index=False)
    R["p4"] = nv.to_dict("records")
    row = nv[nv.scenario == "novelty only"].iloc[0]
    H["P4 Novelty effect"] = (f"A 3-day test of a change with zero long-run effect reported a {pct(row.est_3d)} lift and was "
                              f"'significant' {pct(row.reject_3d, 0)} of the time; the daily-trend check flagged {pct(row.novelty_flagged, 0)}, "
                              f"and using only week 2 cut the estimate to {pct(row.est_week2)}.")
    fig, ax = plt.subplots(figsize=(7, 3.8))
    xx = np.arange(len(nv))
    ax.bar(xx - 0.27, nv.est_3d * 100, 0.27, color=BAD, label="First 3 days")
    ax.bar(xx, nv.est_14d * 100, 0.27, color=NEUTRAL, label="All 14 days")
    ax.bar(xx + 0.27, nv.est_week2 * 100, 0.27, color=GOOD, label="Week 2 only")
    ax.scatter(xx, nv.true_long_run_lift * 100, marker="_", s=600, color="black", zorder=5, label="True long-run lift")
    ax.set_xticks(xx)
    ax.set_xticklabels([s.replace(", ", ",\n").replace(" + ", "\n+ ") for s in nv.scenario], fontsize=8)
    ax.set(ylabel="Estimated relative lift (%)", title="Novelty: early lifts fade")
    ax.legend(fontsize=8)
    save(fig, "p4_novelty")

    # ------------------------------------------------------------ P5 multiple metrics
    mm = multiple_testing.fpr_vs_metrics(n_sims=n(50_000))
    mv = multiple_testing.multiple_variants(n_sims=n(50_000))
    mm.to_csv(RES / "p5_metrics.csv", index=False)
    mv.to_csv(RES / "p5_variants.csv", index=False)
    r20 = mm[mm.n_metrics == 20].iloc[0]
    R["p5"] = {"metrics": mm.to_dict("records"), "variants": mv.to_dict("records")}
    H["P5 Multiple metrics"] = (f"Looking at 20 metrics gave a {pct(r20.uncorrected, 0)} chance of at least one false win with no real "
                                f"effect; Holm correction brought it back to {pct(r20.holm)}.")
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.plot(mm.n_metrics, mm.uncorrected * 100, "o-", color=BAD, label="Uncorrected")
    ax.plot(mm.n_metrics, mm.bh * 100, "s-", color=ACCENT, label="Benjamini-Hochberg")
    ax.plot(mm.n_metrics, mm.holm * 100, "^-", color=GOOD, label="Holm")
    ax.axhline(5, color=NEUTRAL, ls="--")
    ax.set(xlabel="Number of metrics checked", ylabel="Chance of >=1 false win (%)", title="Multiple metrics (no true effects, rho = 0.3)")
    ax.legend(fontsize=8)
    save(fig, "p5_multiple_metrics")

    # ------------------------------------------------------------ P6 segments
    seg = [segments.segment_hacking(n_segments=m, n_sims=n(50_000)) for m in (1, 3, 5, 10, 15, 30)]
    R["p6"] = seg
    s15 = next(s for s in seg if s["n_segments"] == 15)
    H["P6 Segment p-hacking"] = (f"Slicing into 15 segments after the fact produced a 'winning' segment in {pct(s15['any_segment_significant'], 0)} "
                                 f"of no-effect tests (average reported lift {pct(s15['avg_reported_abs_lift_in_winner'], 0)}); "
                                 f"follow-up tests confirmed only {pct(s15['followup_confirms'])}.")
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.plot([s["n_segments"] for s in seg], [s["any_segment_significant"] * 100 for s in seg], "o-", color=BAD, label="Any segment 'wins'")
    ax.plot([s["n_segments"] for s in seg], [s["bonferroni_any_significant"] * 100 for s in seg], "^-", color=GOOD, label="With Bonferroni")
    ax.axhline(5, color=NEUTRAL, ls="--")
    ax.set(xlabel="Segments sliced after the fact", ylabel="Tests with a 'winning' segment (%)", title="Segment hacking (true lift = 0)")
    ax.legend(fontsize=8)
    save(fig, "p6_segments")

    # ------------------------------------------------------------ P7 heavy tails
    ht = heavy_tails.heavy_tail_study(n_sims=n(500), use_bootstrap=not q, n_boot_sims=n(100), users_per_day=2_000)
    ht.to_csv(RES / "p7_heavy_tails.csv", index=False)
    R["p7"] = ht.to_dict("records")
    hv = ht[(ht.whale_rate == 0.005) & (ht.true_conv_lift == 0.10)].set_index("method").reject_rate
    H["P7 Heavy-tailed revenue"] = (f"With 0.5% whale customers, a revenue test with a real +10% conversion lift had {pct(hv['welch'], 0)} power "
                                    f"(plain t-test) vs {pct(hv['winsorized_p99'], 0)} with pooled p99 winsorizing; "
                                    f"false positive rates stayed near 5%.")
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharey=False)
    for a, lift, title in ((ax[0], 0.10, "Power (true +10% conversion lift)"), (ax[1], 0.0, "False positive rate (no effect)")):
        d = ht[ht.true_conv_lift == lift]
        for m, c in (("welch", BAD), ("winsorized_p99", GOOD), ("cuped", ACCENT), ("bootstrap", NEUTRAL)):
            dd = d[d.method == m]
            if len(dd):
                a.plot(dd.whale_rate * 100, dd.reject_rate * 100, "o-", color=c, label=m)
        a.set(xlabel="Whale share of converters (%)", ylabel="Rejection rate (%)", title=title)
        if lift == 0.0:
            a.axhline(5, color="black", ls="--", lw=0.8)
    ax[0].legend(fontsize=8)
    save(fig, "p7_heavy_tails")

    # ------------------------------------------------------------ P8 unit of analysis
    ua = unit_of_analysis.unit_of_analysis_fpr(n_sims=n(2_000))
    ua.to_csv(RES / "p8_unit.csv", index=False)
    R["p8"] = ua.to_dict("records")
    u2 = ua[ua.user_sd == 1.5].iloc[0]
    H["P8 Wrong unit of analysis"] = (f"Analysing sessions instead of users raised the A/A false positive rate from 5% to "
                                      f"{pct(u2.naive_session_level_fpr, 0)} (users moderately different); the delta method held it at {pct(u2.delta_method_fpr)}.")
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.plot(ua.user_sd, ua.naive_session_level_fpr * 100, "o-", color=BAD, label="Session-level z-test")
    ax.plot(ua.user_sd, ua.delta_method_fpr * 100, "s-", color=GOOD, label="Delta method (by user)")
    ax.axhline(5, color=NEUTRAL, ls="--")
    ax.set(xlabel="How different users are from each other (logit sd)", ylabel="False positive rate (%)",
           title="Randomise by user, analyse by user")
    ax.legend(fontsize=8)
    save(fig, "p8_unit_of_analysis")

    # ------------------------------------------------------------ P9 Simpson
    sp = simpson.simpson_study(n_sims=n(500))
    R["p9"] = sp
    direction = "worse" if sp["pooled_avg_effect"] < 0 else "better"
    H["P9 Simpson's paradox in ramp-up"] = (
        f"Ramping treatment up during a high-conversion sale made a no-effect change look {100 * abs(sp['pooled_avg_effect']):.2f} "
        f"percentage points {direction} (false positive rate {pct(sp['pooled_false_positive_rate'], 0)}); stratifying by day brought the "
        f"estimate to {100 * sp['stratified_avg_effect'] + 0.0:+.2f} percentage points.")
    fig, ax = plt.subplots(figsize=(4.8, 3.8))
    ax.bar(["Pooled", "Stratified\nby day"], [sp["pooled_avg_effect"] * 100, sp["stratified_avg_effect"] * 100], color=[BAD, GOOD])
    ax.axhline(0, color="black", lw=0.8)
    ax.set(ylabel="Estimated effect (percentage points)", title="Simpson's paradox (true effect = 0)")
    save(fig, "p9_simpson")

    json.dump(R, open(RES / "pitfalls.json", "w"), indent=2, default=float)
    lines = ["# Pitfall summary", "",
             "_Generated by `scripts/run_pitfalls.py`; every number comes from the Monte Carlo results in `data/results/`._", "",
             "| # | Pitfall | Headline result |", "|---|---|---|"]
    for i, (name, text) in enumerate(H.items(), 1):
        lines.append(f"| {i} | {name.split(' ', 1)[1]} | {text} |")
    Path("reports/pitfall_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
