"""Phase 7: audit a simulated portfolio of experiments with a naive and a rigorous analyst.

Each experiment has a known ground truth (its scenario and true long-run lift), so we can score
every shipping decision as a true win or a false win.
"""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from abtest.analyze.tests import two_prop_ztest, welch_ttest
from abtest.diagnose.checker import diagnose
from abtest.simulate.engine import ExperimentConfig, simulate

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "audit_portfolio.yaml"
Z = stats.norm.ppf(0.975)


def load_config(path=CONFIG_PATH) -> dict:
    return yaml.safe_load(open(path))


def scenario_shares(cfg: dict, true_win_share: float | None = None) -> dict:
    """Shares per scenario; optionally rescale so true_win + small_win sums to a target share."""
    shares = {k: v["share"] for k, v in cfg["scenarios"].items()}
    if true_win_share is not None:
        others = {k: s for k, s in shares.items() if k != "true_win"}
        scale = (1 - true_win_share) / sum(others.values())
        shares = {k: s * scale for k, s in others.items()} | {"true_win": true_win_share}
    return shares


def make_config(cfg: dict, scenario: str, rng: np.random.Generator, seed: int) -> tuple[ExperimentConfig, float]:
    params = {**cfg["defaults"], **{k: v for k, v in cfg["scenarios"][scenario].items() if k != "share"}}
    lift = params["lift"]
    if isinstance(lift, (list, tuple)):
        lift = float(rng.uniform(*lift))
    params["lift"] = lift
    return ExperimentConfig(seed=seed, **params), lift


def naive_analyst(df) -> dict:
    """Checks daily and stops at the first p < .05; also ships if revenue or any of the segments wins."""
    t = (df["arm"] == "treatment").values
    day = df["day"].values
    conv = df["converted"].values
    n_days = day.max() + 1
    ca = np.bincount(day[~t], weights=conv[~t], minlength=n_days).cumsum()
    cb = np.bincount(day[t], weights=conv[t], minlength=n_days).cumsum()
    na = np.bincount(day[~t], minlength=n_days).cumsum()
    nb = np.bincount(day[t], minlength=n_days).cumsum()
    pa, pb = ca / na, cb / nb
    pool = (ca + cb) / (na + nb)
    z = (pb - pa) / np.sqrt(np.maximum(pool * (1 - pool) * (1 / na + 1 / nb), 1e-12))
    hit = np.where((z > Z))[0]
    if len(hit):                                               # stop early on the first winning look
        d = hit[0]
        return {"ship": True, "reported_lift": float((pb[d] - pa[d]) / pa[d]), "how": "peek"}
    y = df["revenue"].values
    r = welch_ttest(y[~t], y[t])
    if r.significant and r.effect > 0:
        return {"ship": True, "reported_lift": float(pb[-1] / pa[-1] - 1), "how": "revenue"}
    seg = df["segment"].values
    for s in np.unique(seg):
        m = seg == s
        a, b = conv[m & ~t], conv[m & t]
        if len(a) and len(b):
            rr = two_prop_ztest(a.sum(), len(a), b.sum(), len(b))
            if rr.significant and rr.effect > 0:
                return {"ship": True, "reported_lift": float(rr.rel_lift), "how": "segment"}
    return {"ship": False, "reported_lift": float(pb[-1] / pa[-1] - 1), "how": "none"}


def rigorous_analyst(df, planned_mde_rel) -> dict:
    """One pre-registered primary metric, fixed horizon, ships only if every health check is green."""
    rep = diagnose(df, planned_mde_rel=planned_mde_rel)
    return {"ship": rep.ship, "reported_lift": float(rep.result.rel_lift), "verdict": rep.verdict}


def run_quarter(args) -> list[dict]:
    quarter, cfg, shares, seed = args
    rng = np.random.default_rng(seed)
    names = list(shares)
    probs = np.array([shares[n] for n in names])
    scen = rng.choice(names, size=cfg["n_experiments"], p=probs / probs.sum())
    rows = []
    for i, sc in enumerate(scen):
        ecfg, lift = make_config(cfg, sc, rng, int(rng.integers(0, 2**31 - 1)))
        df = simulate(ecfg)
        naive = naive_analyst(df)
        rig = rigorous_analyst(df, cfg["planned_mde_rel"])
        rows.append({
            "quarter": quarter, "exp": i, "scenario": sc, "true_lift": lift,
            "true_win": lift > 0 and sc in ("true_win", "small_win_underpowered"),
            "naive_ship": naive["ship"], "naive_lift": naive["reported_lift"], "naive_how": naive["how"],
            "rigorous_ship": rig["ship"], "rigorous_lift": rig["reported_lift"],
            "rigorous_verdict": rig["verdict"],
        })
    return rows


def run_audit(n_quarters=1_000, true_win_share=None, seed=2026, workers=None, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_config()
    shares = scenario_shares(cfg, true_win_share)
    jobs = [(q, cfg, shares, seed * 100_003 + q) for q in range(n_quarters)]
    if workers == 1:
        rows = [r for j in jobs for r in run_quarter(j)]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            rows = [r for chunk in ex.map(run_quarter, jobs, chunksize=4) for r in chunk]
    return pd.DataFrame(rows)


def _missed_cost(g: pd.DataFrame, who: str, annual_margin: float, e: dict) -> float:
    """True wins that were not shipped. A rigorous 'INVESTIGATE / DON'T TRUST' verdict means rerun
    (a delay of rerun_delay_months); a plain 'no win' call, or anything the naive analyst skips,
    is an abandoned idea (months_lost_if_abandoned of the lift's margin)."""
    m = g[g["true_win"] & ~g[f"{who}_ship"]]
    if who == "rigorous":
        delayed = ~m["rigorous_verdict"].str.startswith("NO WIN")
        months = np.where(delayed, e["rerun_delay_months"], e["months_lost_if_abandoned"])
    else:
        months = np.full(len(m), e["months_lost_if_abandoned"])
    return float((m["true_lift"].values * annual_margin * months / 12).sum())


def score(df: pd.DataFrame, cfg: dict | None = None, false_win_cost_inr: float | None = None) -> pd.DataFrame:
    """Per-quarter score for both analysts."""
    cfg = cfg or load_config()
    e = cfg["economics"]
    fw_cost = false_win_cost_inr if false_win_cost_inr is not None else e["engineering_cost_per_shipped_change_inr"]
    annual_margin = (e["monthly_active_users"] * 12 * e["baseline_conversion"]
                     * e["avg_order_value_inr"] * e["contribution_margin"])
    out = []
    for who in ("naive", "rigorous"):
        for q, g in df.groupby("quarter"):
            s = g[g[f"{who}_ship"]]
            f = s[~s["true_win"]]
            m = g[g["true_win"] & ~g[f"{who}_ship"]]
            out.append({
                "analyst": who, "quarter": q, "shipped": len(s), "false_wins": len(f),
                "fdr": len(f) / len(s) if len(s) else np.nan,
                "true_wins_shipped": len(s) - len(f), "true_wins_missed": len(m),
                "avg_reported_lift": s[f"{who}_lift"].mean() if len(s) else np.nan,
                "avg_true_lift": s["true_lift"].mean() if len(s) else np.nan,
                "cost_false_inr": len(f) * fw_cost,
                "cost_missed_inr": _missed_cost(g, who, annual_margin, e),
            })
    q = pd.DataFrame(out)
    q["total_cost_inr"] = q["cost_false_inr"] + q["cost_missed_inr"]
    return q


def summarise(q: pd.DataFrame) -> pd.DataFrame:
    return q.groupby("analyst").agg(
        shipped_median=("shipped", "median"), false_wins_median=("false_wins", "median"),
        fdr_median=("fdr", "median"), true_wins_shipped_median=("true_wins_shipped", "median"),
        true_wins_missed_median=("true_wins_missed", "median"),
        avg_reported_lift=("avg_reported_lift", "mean"), avg_true_lift=("avg_true_lift", "mean"),
        cost_false_inr_median=("cost_false_inr", "median"),
        cost_missed_inr_median=("cost_missed_inr", "median"),
        total_cost_inr_median=("total_cost_inr", "median"))


def break_even_false_win_cost(q: pd.DataFrame) -> float:
    """Cost per false win at which the two analysts cost the same, using mean counts per quarter.
    Below it the naive analyst is cheaper (false wins are cheap); above it the rigorous one is."""
    g = q.groupby("analyst")[["false_wins", "cost_missed_inr"]].mean()
    d_fw = g.loc["naive", "false_wins"] - g.loc["rigorous", "false_wins"]
    d_miss = g.loc["rigorous", "cost_missed_inr"] - g.loc["naive", "cost_missed_inr"]
    return float(d_miss / d_fw) if d_fw > 0 else float("nan")
