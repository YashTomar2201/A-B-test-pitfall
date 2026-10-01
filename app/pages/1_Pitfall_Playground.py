import plotly.graph_objects as go
import streamlit as st

from _common import ACCENT, BAD, GOOD, NEUTRAL, pct
from abtest.pitfalls import multiple_testing, novelty, peeking, segments, unit_of_analysis, winners_curse

st.set_page_config(page_title="Pitfall Playground", page_icon="🧪", layout="wide")
st.title("Pitfall Playground")
st.caption("Each run is a live Monte Carlo simulation with no real effect unless you add one. Runs are capped so pages stay fast.")

pitfall = st.selectbox("Pitfall", ["Peeking", "Winner's curse (underpowered tests)", "Multiple metrics",
                                  "Segment hacking", "Wrong unit of analysis", "Novelty effect"])
N_SIMS = 2_000

if pitfall == "Peeking":
    st.markdown("**What goes wrong:** you check the p-value every day and stop at the first p < 0.05. Every look is another chance for noise to cross the line.")
    c1, c2 = st.columns(2)
    n_total = c1.slider("Users per arm at the planned end of the test", 5_000, 100_000, 28_000, step=1_000)
    base = c2.slider("Baseline conversion rate", 0.01, 0.20, 0.05)

    @st.cache_data
    def run_peek(n_total, base):
        return peeking.fpr_by_looks(looks=(1, 2, 3, 5, 7, 14, 28), n_total_per_arm=n_total, p=base, n_sims=N_SIMS)

    d = run_peek(n_total, base)
    fig = go.Figure(go.Scatter(x=d.looks, y=d.fpr * 100, mode="lines+markers", line=dict(color=BAD)))
    fig.add_hline(y=5, line_dash="dash", line_color=NEUTRAL, annotation_text="5% target")
    fig.update_layout(xaxis_title="Number of looks", yaxis_title="False positive rate (%)", xaxis_type="log", height=360,
                      margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.success("**Fix:** plan the number of looks and use O'Brien-Fleming boundaries, or use an always-valid mSPRT p-value. "
               "mSPRT needs roughly twice the sample for the same power; that is the price of looking any time.")

elif pitfall.startswith("Winner"):
    st.markdown("**What goes wrong:** with low power the only significant results are lucky overestimates, and some have the wrong sign.")
    c1, c2, c3 = st.columns(3)
    lift = c1.slider("True relative lift", 0.01, 0.30, 0.10)
    n_arm = c2.slider("Users per arm", 1_000, 100_000, 10_000, step=1_000)
    base = c3.slider("Baseline conversion", 0.01, 0.20, 0.05)
    r = winners_curse.winners_curse(true_rel_lift=lift, p=base, n_per_arm=n_arm, n_sims=20_000)
    m1, m2, m3 = st.columns(3)
    m1.metric("Power", pct(r["power"], 0))
    m2.metric("Significant results overstate the lift by", f"{r['exaggeration_ratio']:.1f}x" if r["power"] > 0.02 else "n/a")
    m3.metric("Significant results with the wrong sign", pct(r["wrong_sign_share"]) if r["power"] > 0.02 else "n/a")
    st.success("**Fix:** run a power analysis before launch and commit to a minimum detectable effect.")

elif pitfall == "Multiple metrics":
    st.markdown("**What goes wrong:** check many metrics and ship if any is significant. With no real effect, one usually is.")
    c1, c2 = st.columns(2)
    m = c1.slider("Metrics checked", 1, 50, 20)
    rho = c2.slider("Correlation between metrics", 0.0, 0.9, 0.3)
    r = multiple_testing.any_false_positive(n_metrics=m, rho=rho, n_sims=N_SIMS * 5)
    a, b, c = st.columns(3)
    a.metric("Chance of at least one false win", pct(r["uncorrected"], 0))
    b.metric("With Benjamini-Hochberg", pct(r["bh"]))
    c.metric("With Holm", pct(r["holm"]))
    st.success("**Fix:** pick one primary metric in advance; correct the rest with Holm (strict) or Benjamini-Hochberg (exploratory).")

elif pitfall == "Segment hacking":
    st.markdown("**What goes wrong:** the test did not win overall, so you slice by device, city and tier until something does.")
    segs = st.slider("Segments sliced after the fact", 1, 40, 15)
    r = segments.segment_hacking(n_segments=segs, n_sims=20_000)
    a, b, c = st.columns(3)
    a.metric("Tests with a 'winning' segment (no real effect)", pct(r["any_segment_significant"], 0))
    b.metric("Average reported lift in the winner", pct(r["avg_reported_abs_lift_in_winner"], 0))
    c.metric("Follow-up tests that confirm it", pct(r["followup_confirms"]))
    st.success("**Fix:** pre-register segments; treat post-hoc segments as hypotheses for a new test.")

elif pitfall == "Wrong unit of analysis":
    st.markdown("**What goes wrong:** users are randomised but sessions are analysed as if independent. Sessions from one user are correlated, so standard errors are too small.")
    sd = st.slider("How different users are from each other", 0.0, 2.5, 1.5)

    @st.cache_data
    def run_unit(sd):
        return unit_of_analysis.unit_of_analysis_fpr(user_sd_grid=(sd,), n_sims=400).iloc[0]

    r = run_unit(sd)
    a, b = st.columns(2)
    a.metric("Session-level test false positive rate", pct(r.naive_session_level_fpr))
    b.metric("Delta method (by user)", pct(r.delta_method_fpr))
    st.success("**Fix:** analyse at the randomisation unit, using the delta method for ratio metrics.")

else:
    st.markdown("**What goes wrong:** users try something because it is new. The lift fades, but a short test reports the early, inflated effect.")
    c1, c2, c3 = st.columns(3)
    boost = c1.slider("Extra day-0 lift from novelty", 0.0, 0.6, 0.3)
    half = c2.slider("Novelty half-life (days)", 1.0, 10.0, 3.0)
    true = c3.slider("True long-run lift", 0.0, 0.2, 0.0)
    r = novelty.novelty_study(true_lift=true, boost=boost, halflife=half, n_sims=N_SIMS * 2)
    a, b, c, d = st.columns(4)
    a.metric("Estimated lift, first 3 days", pct(r["first_3d"]["avg_est_rel_lift"]))
    b.metric("All 14 days", pct(r["first_14d"]["avg_est_rel_lift"]))
    c.metric("Week 2 only", pct(r["second_week"]["avg_est_rel_lift"]))
    d.metric("True long-run lift", pct(true))
    st.info(f"The daily-trend check flags novelty in {pct(r['novelty_flagged'], 0)} of these simulated tests.")
    st.success("**Fix:** run at least two full weeks and report the effect from mature cohorts.")
