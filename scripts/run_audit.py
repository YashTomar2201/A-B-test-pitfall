"""Phase 7: run the experiment audit (simulated quarters of 40 experiments) + sensitivity runs.

    python scripts/run_audit.py            # full run: 500 quarters + 2 x 150 sensitivity quarters
    python scripts/run_audit.py --quick    # 40 quarters, for a smoke test
    (each worker process needs ~0.5 GB of RAM; lower --workers on a small machine)
"""
import argparse
import json
import time
from pathlib import Path

import pandas as pd

from abtest.audit.portfolio import (break_even_false_win_cost, load_config, run_audit, score,
                                    summarise)

OUT = Path("data/results")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    nq_main, nq_sens = (40, 20) if args.quick else (500, 150)
    cfg = load_config()
    OUT.mkdir(parents=True, exist_ok=True)

    t = time.time()
    df = run_audit(n_quarters=nq_main, seed=2026, cfg=cfg, workers=args.workers)
    df.to_parquet(OUT / "audit_experiments.parquet")
    print(f"main audit: {len(df):,} experiments in {time.time() - t:.0f}s", flush=True)

    q = score(df, cfg)
    q.to_parquet(OUT / "audit_quarters.parquet")
    summary = summarise(q)
    summary.to_csv(OUT / "audit_summary.csv")
    by_scen = df.groupby("scenario").agg(n=("exp", "size"), naive_ship_rate=("naive_ship", "mean"),
                                         rigorous_ship_rate=("rigorous_ship", "mean"))
    by_scen.to_csv(OUT / "audit_by_scenario.csv")

    res = {"n_quarters": nq_main, "experiments_per_quarter": cfg["n_experiments"],
           "break_even_false_win_cost_inr": break_even_false_win_cost(q)}
    # sensitivity 1: cost per false win
    rows = []
    for c in (0, 500_000, 2_000_000, 5_000_000):
        qq = score(df, cfg, false_win_cost_inr=c)
        g = qq.groupby("analyst")["total_cost_inr"].median()
        rows.append({"false_win_cost_inr": c, "naive_total_cost_median": g["naive"],
                     "rigorous_total_cost_median": g["rigorous"]})
    res["sens_false_win_cost"] = rows
    # sensitivity 2: worst case for the rigorous analyst - a flagged rerun is treated as an abandoned idea
    cfg_worst = json.loads(json.dumps(cfg))
    cfg_worst["economics"]["rerun_delay_months"] = cfg["economics"]["months_lost_if_abandoned"]
    g = score(df, cfg_worst).groupby("analyst")["total_cost_inr"].median()
    res["worst_case_rerun_equals_abandon"] = {"naive_total_cost_median": g["naive"],
                                              "rigorous_total_cost_median": g["rigorous"]}
    # sensitivity 3: share of true wins in the portfolio
    sens = []
    for share in (0.15, 0.35):
        d = run_audit(n_quarters=nq_sens, true_win_share=share, seed=7, cfg=cfg, workers=args.workers)
        qs = score(d, cfg)
        s = summarise(qs)
        sens.append({"true_win_share": share,
                     "naive_fdr_median": s.loc["naive", "fdr_median"],
                     "rigorous_fdr_median": s.loc["rigorous", "fdr_median"],
                     "naive_false_wins_median": s.loc["naive", "false_wins_median"],
                     "rigorous_false_wins_median": s.loc["rigorous", "false_wins_median"],
                     "naive_total_cost_median": s.loc["naive", "total_cost_inr_median"],
                     "rigorous_total_cost_median": s.loc["rigorous", "total_cost_inr_median"]})
        print(f"sensitivity {share:.0%} done", flush=True)
    res["sens_true_win_share"] = sens
    json.dump(res, open(OUT / "audit_results.json", "w"), indent=2, default=float)
    print(summary.T.to_string())
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()
