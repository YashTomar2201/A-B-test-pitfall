"""Experiment health checker: run the pitfall detectors on one experiment and return a verdict.

Expected columns: arm ('control' | 'treatment'), converted (0/1).
Optional columns: day (int, days since launch), revenue, pre_spend (or any pre-treatment covariates).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from abtest.analyze.power import mde_proportions
from abtest.analyze.tests import srm_test, two_prop_ztest, welch_ttest
from abtest.pitfalls.heavy_tails import winsorize_pooled
from abtest.pitfalls.multiple_testing import holm_reject

GREEN, YELLOW, RED = "green", "yellow", "red"
ICON = {GREEN: "🟢", YELLOW: "🟡", RED: "🔴"}


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class Report:
    checks: list = field(default_factory=list)
    result: object = None

    def status_of(self, name: str) -> str:
        return next(c.status for c in self.checks if c.name == name)

    @property
    def verdict(self) -> str:
        if any(c.status == RED for c in self.checks):
            return "DON'T TRUST - fix and rerun"
        if any(c.status == YELLOW for c in self.checks):
            return "INVESTIGATE before shipping"
        win = self.result.significant and self.result.effect > 0
        return "SHIP" if win else "NO WIN - don't ship"

    @property
    def ship(self) -> bool:
        return self.verdict == "SHIP"

    def to_markdown(self) -> str:
        r = self.result
        lines = [f"**Verdict: {self.verdict}**", "",
                 f"Effect on conversion: {r.effect:+.4f} ({r.rel_lift:+.1%} relative), "
                 f"95% CI [{r.ci_low:+.4f}, {r.ci_high:+.4f}], p = {r.p_value:.3g}", "",
                 "| Check | Status | Detail |", "|---|---|---|"]
        lines += [f"| {c.name} | {ICON[c.status]} | {c.detail} |" for c in self.checks]
        return "\n".join(lines)


def novelty_slope_z(df) -> tuple[float, float, float]:
    """Weighted regression of the DAILY effect on the day. Returns (slope, z, first-vs-second-half gap)."""
    g = df.groupby(["day", "arm"])["converted"].agg(["mean", "count"]).unstack("arm")
    pa, pb = g[("mean", "control")].values, g[("mean", "treatment")].values
    na, nb = g[("count", "control")].values, g[("count", "treatment")].values
    eff = pb - pa
    se = np.sqrt(np.maximum(pa * (1 - pa) / na + pb * (1 - pb) / nb, 1e-12))
    x = g.index.values.astype(float)
    w = 1 / se**2
    xw, yw = (w * x).sum() / w.sum(), (w * eff).sum() / w.sum()
    sxx = (w * (x - xw) ** 2).sum()
    slope = (w * (x - xw) * (eff - yw)).sum() / sxx
    half = len(x) // 2
    gap = eff[:half].mean() - eff[half:].mean()
    return float(slope), float(slope * np.sqrt(sxx)), float(gap)


def balance_check(df: pd.DataFrame, covariates, alpha=0.001) -> tuple[float, float, float]:
    """Pre-treatment covariate balance. Returns (max |SMD|, max |z|, Bonferroni critical z)."""
    t = (df["arm"] == "treatment").values
    n_c, n_t = int((~t).sum()), int(t.sum())
    smds = []
    for c in covariates:
        a, b = df.loc[~t, c].astype(float), df.loc[t, c].astype(float)
        smds.append((b.mean() - a.mean()) / np.sqrt((a.var() + b.var()) / 2))
    smds = np.abs(np.array(smds))
    scale = 1 / np.sqrt(1 / n_c + 1 / n_t)            # SMD has sd ~ sqrt(1/n_c + 1/n_t) under randomization
    crit = stats.norm.ppf(1 - alpha / (2 * len(smds)))
    return float(smds.max()), float(smds.max() * scale), float(crit)


def diagnose(df: pd.DataFrame, *, expected_treat_share=0.5, planned_mde_rel=None, all_pvalues=None,
             stopped_early=False, used_sequential=False, revenue_col=None, covariates=None) -> Report:
    rep = Report()
    g = df.groupby("arm")["converted"].agg(["sum", "count"])
    rep.result = two_prop_ztest(g.loc["control", "sum"], g.loc["control", "count"],
                                g.loc["treatment", "sum"], g.loc["treatment", "count"])
    n_c, n_t = int(g.loc["control", "count"]), int(g.loc["treatment", "count"])

    # 1. Sample ratio mismatch
    p_srm = srm_test(n_c, n_t, expected_treat_share)
    rep.checks.append(Check("Sample ratio", RED if p_srm < 0.001 else GREEN,
                            f"{n_t / (n_c + n_t):.1%} treatment vs {expected_treat_share:.0%} expected, SRM p = {p_srm:.2g}"))

    # 2. Peeking
    if stopped_early and not used_sequential:
        rep.checks.append(Check("Peeking", RED, "Stopped early on a fixed-horizon p-value"))
    else:
        rep.checks.append(Check("Peeking", GREEN, "Fixed horizon or sequential method used"))

    # 3. Power
    base = g.loc["control", "sum"] / g.loc["control", "count"]
    mde = mde_proportions(base, min(n_c, n_t))
    low_power = planned_mde_rel is not None and mde > planned_mde_rel
    rep.checks.append(Check("Power", YELLOW if low_power else GREEN,
                            f"Achieved MDE {mde:.1%} relative" +
                            (f" > planned {planned_mde_rel:.0%}: winner's-curse risk" if low_power else "")))

    # 4. Multiple comparisons (Holm over every p-value the team looked at)
    if all_pvalues is not None and len(all_pvalues) > 1:
        p = np.asarray(all_pvalues, float)[None, :]
        raw_sig, holm_sig = bool(p[0, 0] < 0.05), bool(holm_reject(p)[0, 0])
        bad = raw_sig and not holm_sig
        rep.checks.append(Check("Multiple testing", YELLOW if bad else GREEN,
                                f"{p.shape[1]} comparisons; primary " +
                                ("significant raw but not after Holm" if bad else "survives Holm correction")))
    else:
        rep.checks.append(Check("Multiple testing", GREEN, "Single primary metric"))

    # 5. Novelty trend
    if "day" in df and df["day"].nunique() >= 7:
        slope, z, gap = novelty_slope_z(df)
        flag = z < stats.norm.ppf(0.01) and gap > 0
        rep.checks.append(Check("Novelty", YELLOW if flag else GREEN,
                                f"Daily-effect slope z = {z:+.2f}; first half minus second half = {gap:+.4f}"))
    else:
        rep.checks.append(Check("Novelty", GREEN, "Too few days to test a trend"))

    # 6. Outlier sensitivity on revenue
    if revenue_col and revenue_col in df:
        t = (df["arm"] == "treatment").values
        y = df[revenue_col].values
        raw, win = welch_ttest(y[~t], y[t]), welch_ttest(*(lambda w: (w[~t], w[t]))(winsorize_pooled(y)))
        flips = raw.significant != win.significant
        rep.checks.append(Check("Outliers", YELLOW if flips else GREEN,
                                f"Revenue p = {raw.p_value:.3g} raw vs {win.p_value:.3g} winsorized at p99"))
    else:
        rep.checks.append(Check("Outliers", GREEN, "No revenue metric supplied"))

    # 7. Randomization balance on pre-treatment covariates
    if covariates:
        smd, z, crit = balance_check(df, covariates)
        bad = z > crit
        rep.checks.append(Check("Balance", RED if bad else GREEN,
                                f"max |SMD| = {smd:.4f} (z = {z:.1f} vs critical {crit:.1f})"
                                + ("; arms differ before treatment" if bad else "")))
    else:
        rep.checks.append(Check("Balance", GREEN, "No pre-treatment covariates supplied"))
    return rep
