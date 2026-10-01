"""Phase 3 + 5.3: validate the toolkit on two REAL randomized experiments (Criteo, Hillstrom).

Writes data/results/real_data.json. Run after src/load/load_real.py.
"""
import json
from pathlib import Path

import duckdb
import numpy as np

from abtest.analyze.cuped import cuped_adjust, cuped_test, regression_adjusted, variance_reduction
from abtest.analyze.tests import srm_test, two_prop_ztest, welch_ttest

con = duckdb.connect("data/warehouse/lab.duckdb", read_only=True)
OUT = {}


def sql(name):
    return con.execute(Path(f"sql/{name}.sql").read_text()).df()


# ---------------------------------------------------------------- Criteo: SQL layer
arms = sql("metrics_by_arm").set_index("arm")
srm = sql("srm_check").iloc[0]
zt = sql("ztest").iloc[0]
n_c, n_t = int(arms.loc[0, "users"]), int(arms.loc[1, "users"])
OUT["criteo"] = {
    "rows": n_c + n_t, "n_control": n_c, "n_treatment": n_t,
    "treatment_share": n_t / (n_c + n_t),
    "srm_chi2_vs_documented_85pct": float(srm["chi2"]), "srm_flag": bool(srm["srm_flag"]),
}

# Python vs SQL must agree exactly for the conversion z-test
conv_c = arms.loc[0, "conversion_rate"] * n_c
conv_t = arms.loc[1, "conversion_rate"] * n_t
py = two_prop_ztest(round(conv_c), n_c, round(conv_t), n_t)
pooled = (conv_c + conv_t) / (n_c + n_t)
py_z = py.effect / np.sqrt(pooled * (1 - pooled) * (1 / n_c + 1 / n_t))
OUT["criteo"]["conversion"] = {
    "control_rate": float(arms.loc[0, "conversion_rate"]), "treatment_rate": float(arms.loc[1, "conversion_rate"]),
    "effect_abs": py.effect, "rel_lift": py.rel_lift, "ci": [py.ci_low, py.ci_high], "p_value": py.p_value,
    "z_sql": float(zt["z"]), "z_python": float(py_z), "sql_python_match": bool(abs(zt["z"] - py_z) < 1e-6),
}
vis_c, vis_t = arms.loc[0, "visit_rate"], arms.loc[1, "visit_rate"]
pv = two_prop_ztest(round(vis_c * n_c), n_c, round(vis_t * n_t), n_t)
OUT["criteo"]["visit"] = {"control_rate": float(vis_c), "treatment_rate": float(vis_t), "effect_abs": pv.effect,
                          "rel_lift": pv.rel_lift, "ci": [pv.ci_low, pv.ci_high], "p_value": pv.p_value}

# ---------------------------------------------------------------- Criteo: covariate balance (randomization check)
feats = [f"f{i}" for i in range(12)]
agg = con.execute("SELECT treatment, " + ", ".join(f"avg({f}) m{i}, var_samp({f}) v{i}" for i, f in enumerate(feats))
                  + " FROM raw.criteo GROUP BY treatment ORDER BY treatment").df().set_index("treatment")
smd = {f: float((agg.loc[1, f"m{i}"] - agg.loc[0, f"m{i}"]) / np.sqrt((agg.loc[1, f"v{i}"] + agg.loc[0, f"v{i}"]) / 2))
       for i, f in enumerate(feats)}
OUT["criteo"]["max_abs_smd"] = max(abs(v) for v in smd.values())
OUT["criteo"]["smd"] = smd

# ---------------------------------------------------------------- Criteo: real A/A on the control arm
rng = np.random.default_rng(0)
aa = {}
for metric in ("conversion", "visit"):
    y = con.execute(f"SELECT {metric} FROM raw.criteo WHERE treatment = 0").fetchnumpy()[metric].astype(np.int8)
    rej, n_rep = 0, 1_000
    for _ in range(n_rep):
        m = rng.random(len(y)) < 0.5
        a, b = y[~m].sum(), y[m].sum()
        r = two_prop_ztest(a, int((~m).sum()), b, int(m.sum()))
        rej += r.significant
    aa[metric] = {"runs": n_rep, "false_positive_rate": rej / n_rep, "control_rows": int(len(y))}
OUT["criteo"]["real_aa"] = aa

# ---------------------------------------------------------------- Criteo: ANCOVA (outcome ~ treatment + covariates)
# Joint regression with the treatment indicator included: its coefficient is the covariate-adjusted effect.
# (Estimating theta WITHOUT the treatment term is only valid when arms are balanced; see max_abs_smd.)
cols = feats + ["treatment", "visit", "conversion"]
data = con.execute("SELECT " + ", ".join(cols) + " FROM raw.criteo").fetchnumpy()
mu = np.array([data[f].astype(np.float64).mean() for f in feats])
n_rows = len(data["treatment"])


def design(lo, hi):
    Z = np.empty((hi - lo, 14))
    Z[:, 0] = 1.0
    Z[:, 1] = data["treatment"][lo:hi]
    for j, f in enumerate(feats):
        Z[:, 2 + j] = data[f][lo:hi].astype(np.float64) - mu[j]
    return Z


CH = 1_000_000
ra = {}
for metric in ("visit", "conversion"):
    y_all = data[metric].astype(np.float64)
    ztz, zty = np.zeros((14, 14)), np.zeros(14)
    for lo in range(0, n_rows, CH):
        Z = design(lo, min(lo + CH, n_rows))
        ztz += Z.T @ Z
        zty += Z.T @ y_all[lo:lo + CH]
    beta = np.linalg.solve(ztz, zty)
    meat = np.zeros((14, 14))
    for lo in range(0, n_rows, CH):
        Z = design(lo, min(lo + CH, n_rows))
        e = y_all[lo:lo + CH] - Z @ beta
        meat += (Z * (e**2)[:, None]).T @ Z
    inv = np.linalg.inv(ztz)
    cov = inv @ meat @ inv * n_rows / (n_rows - 14)          # HC1
    se_adj = float(np.sqrt(cov[1, 1]))
    t_mask = data["treatment"] == 1
    raw = welch_ttest(y_all[~t_mask], y_all[t_mask])
    resid_var_ratio = float(meat[0, 0] / ztz[0, 0] / y_all.var())
    ra[metric] = {"effect_raw": raw.effect, "se_raw": raw.se,
                  "effect_ancova": float(beta[1]), "se_ancova": se_adj,
                  "effect_shift_in_se_units": float((beta[1] - raw.effect) / se_adj),
                  "se_reduction": float(1 - se_adj / raw.se),
                  "sample_needed_ratio": float((se_adj / raw.se) ** 2),
                  "residual_variance_share": resid_var_ratio}
OUT["criteo"]["ancova"] = ra
del data

# ---------------------------------------------------------------- Hillstrom: CUPED, Python vs SQL
h = con.execute("SELECT * FROM raw.hillstrom WHERE segment IN ('No E-Mail', 'Womens E-Mail')").df()
h["arm"] = np.where(h["segment"] == "No E-Mail", "control", "treatment")
raw = welch_ttest(h.loc[h.arm == "control", "spend"], h.loc[h.arm == "treatment", "spend"])
cp = cuped_test(h, metric="spend", covariate="history")
sqlc = sql("cuped")
vr_sql = float(1 - sqlc["var_cuped"].sum() / sqlc["var_raw"].sum())          # rough (per-arm) cross-check
ra_h = regression_adjusted(h.assign(spend=h["spend"].astype(float)), "spend",
                           ["history", "recency", "mens", "womens", "newbie"])
OUT["hillstrom"] = {
    "rows": int(len(con.execute("SELECT * FROM raw.hillstrom").df())),
    "arms": h["arm"].value_counts().to_dict(),
    "spend_effect_raw": raw.effect, "spend_p_raw": raw.p_value, "se_raw": raw.se,
    "spend_effect_cuped": cp.effect, "spend_p_cuped": cp.p_value, "se_cuped": cp.se,
    "variance_reduction_python": variance_reduction(h["spend"].values, h["history"].values),
    "variance_reduction_sql_arm_avg": float(sqlc["variance_reduction"].mean()),
    "corr_history_spend": float(np.corrcoef(h["spend"], h["history"])[0, 1]),
    "multi_covariate_effect_se_p": list(ra_h),
    "calibration": {
        "control_conversion": float(h.loc[h.arm == "control", "conversion"].mean()),
        "control_visit": float(h.loc[h.arm == "control", "visit"].mean()),
        "log_order_mu": float(np.log(h.loc[h.spend > 0, "spend"]).mean()),
        "log_order_sigma": float(np.log(h.loc[h.spend > 0, "spend"]).std()),
    },
}

Path("data/results").mkdir(parents=True, exist_ok=True)
json.dump(OUT, open("data/results/real_data.json", "w"), indent=2, default=float)
print(json.dumps(OUT, indent=2, default=float))
