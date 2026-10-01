import pandas as pd
import streamlit as st

from _common import ACCENT
from abtest.diagnose.checker import diagnose
from abtest.simulate.engine import ExperimentConfig, simulate

st.set_page_config(page_title="Health Checker", page_icon="🧪", layout="wide")
st.title("Experiment Health Checker")
st.caption("Give it experiment data and it runs seven checks, then says whether to ship. "
           "Required columns: `arm` (control / treatment) and `converted` (0/1). Optional: `day`, `revenue`, `pre_spend`.")

SAMPLES = {
    "Clean win (+15% lift)": dict(lift=0.15),
    "Clean null (no effect)": dict(lift=0.0),
    "Sample ratio mismatch bug": dict(lift=0.0, srm_drop_rate=0.05),
    "Novelty effect only": dict(lift=0.0, novelty_boost=0.30),
    "Underpowered small win": dict(lift=0.04, users_per_day=1_500),
}
src = st.radio("Data", ["Sample scenario", "Upload CSV"], horizontal=True)
df = None
if src == "Sample scenario":
    name = st.selectbox("Scenario", list(SAMPLES))
    cfg = {**dict(days=14, users_per_day=6_000, seed=7), **SAMPLES[name]}
    df = simulate(ExperimentConfig(**cfg))
else:
    up = st.file_uploader("CSV file", type="csv")
    if up is not None:
        df = pd.read_csv(up)
        missing = {"arm", "converted"} - set(df.columns)
        if missing:
            st.error(f"Missing required column(s): {', '.join(sorted(missing))}")
            df = None

with st.expander("Experiment settings", expanded=True):
    c1, c2, c3 = st.columns(3)
    share = c1.number_input("Planned treatment share", 0.05, 0.95, 0.5, step=0.05)
    mde = c2.number_input("Planned minimum detectable effect (relative)", 0.01, 1.0, 0.10, step=0.01)
    early = c3.checkbox("Test was stopped early")
    seq = c3.checkbox("A sequential method was used")

if df is not None:
    covs = [c for c in ("pre_spend",) if c in df.columns]
    rep = diagnose(df, expected_treat_share=share, planned_mde_rel=mde, stopped_early=early, used_sequential=seq,
                   revenue_col="revenue" if "revenue" in df.columns else None, covariates=covs or None)
    v = rep.verdict
    (st.success if rep.ship else st.error if v.startswith("DON'T") else st.warning)(f"**Verdict: {v}**")
    st.markdown(rep.to_markdown().split("\n", 2)[2])
    st.caption(f"{len(df):,} users, {df['arm'].value_counts().to_dict()}")
