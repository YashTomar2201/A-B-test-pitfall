import numpy as np

from abtest.audit.portfolio import (break_even_false_win_cost, load_config, run_audit, scenario_shares,
                                    score, summarise)


def test_scenario_shares_sum_to_one_and_rescale():
    cfg = load_config()
    assert abs(sum(scenario_shares(cfg).values()) - 1) < 1e-9
    s = scenario_shares(cfg, true_win_share=0.15)
    assert abs(s["true_win"] - 0.15) < 1e-9 and abs(sum(s.values()) - 1) < 1e-9


def test_small_audit_runs_and_scores():
    cfg = load_config()
    df = run_audit(n_quarters=3, workers=1, cfg=cfg)
    assert len(df) == 3 * cfg["n_experiments"]
    assert {"scenario", "true_win", "naive_ship", "rigorous_ship", "rigorous_verdict"} <= set(df.columns)
    q = score(df, cfg)
    s = summarise(q)
    assert set(s.index) == {"naive", "rigorous"}
    assert (q["false_wins"] <= q["shipped"]).all()
    assert np.isfinite(break_even_false_win_cost(q)) or np.isnan(break_even_false_win_cost(q))


def test_ground_truth_flags():
    df = run_audit(n_quarters=2, workers=1)
    assert not df.loc[df.scenario.isin(["true_null", "novelty_only", "srm_bug", "noisy_revenue"]), "true_win"].any()
    assert df.loc[df.scenario == "true_win", "true_win"].all()
