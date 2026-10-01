import numpy as np

from abtest.diagnose.checker import diagnose
from abtest.simulate.engine import ExperimentConfig, simulate


def big(**kw):
    kw.setdefault("days", 14)
    kw.setdefault("users_per_day", 6_000)
    return ExperimentConfig(seed=kw.pop("seed", 11), **kw)


def test_clean_win_ships():
    rep = diagnose(simulate(big(lift=0.15)), planned_mde_rel=0.10)
    assert rep.verdict == "SHIP", rep.to_markdown()


def test_clean_null_is_no_win():
    rep = diagnose(simulate(big(lift=0.0, seed=3)), planned_mde_rel=0.10)
    assert rep.verdict.startswith("NO WIN"), rep.to_markdown()


def test_srm_bug_is_not_trusted():
    rep = diagnose(simulate(big(lift=0.0, srm_drop_rate=0.08)))
    assert rep.status_of("Sample ratio") == "red"
    assert rep.verdict.startswith("DON'T TRUST")


def test_early_stop_without_sequential_is_not_trusted():
    rep = diagnose(simulate(big(lift=0.15)), stopped_early=True, used_sequential=False)
    assert rep.verdict.startswith("DON'T TRUST")
    rep2 = diagnose(simulate(big(lift=0.15)), stopped_early=True, used_sequential=True, planned_mde_rel=0.10)
    assert rep2.status_of("Peeking") == "green"


def test_novelty_only_is_flagged():
    flagged = 0
    for s in range(20):
        rep = diagnose(simulate(big(lift=0.0, novelty_boost=0.6, novelty_halflife=3, seed=100 + s)))
        flagged += rep.status_of("Novelty") == "yellow"
    assert flagged >= 10


def test_underpowered_is_flagged():
    rep = diagnose(simulate(big(lift=0.03, users_per_day=1_000)), planned_mde_rel=0.10)
    assert rep.status_of("Power") == "yellow"


def test_multiple_testing_flag():
    rep = diagnose(simulate(big(lift=0.05, seed=5)), all_pvalues=[0.04] + [0.3] * 19)
    assert rep.status_of("Multiple testing") == "yellow"


def test_markdown_renders():
    md = diagnose(simulate(big(lift=0.1))).to_markdown()
    assert "Verdict" in md and "| Check |" in md


def test_unequal_expected_split_is_respected():
    df = simulate(big(lift=0.0))
    rep = diagnose(df, expected_treat_share=0.85)
    assert rep.status_of("Sample ratio") == "red"


def test_balance_green_on_randomized_data():
    df = simulate(big(lift=0.05, seed=21))
    rep = diagnose(df, covariates=["pre_spend"])
    assert rep.status_of("Balance") == "green"


def test_balance_red_when_arms_differ_before_treatment():
    df = simulate(big(lift=0.0, seed=22))
    df.loc[df["arm"] == "treatment", "pre_spend"] *= 1.15          # arms differ BEFORE the change
    rep = diagnose(df, covariates=["pre_spend"])
    assert rep.status_of("Balance") == "red"
    assert rep.verdict.startswith("DON'T TRUST")
