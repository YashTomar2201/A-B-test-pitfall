import streamlit as st

from _common import ACCENT, load_json, pct

st.set_page_config(page_title="A/B Pitfall Lab", page_icon="🧪", layout="wide")
st.title("A/B Pitfall Lab")
st.markdown(
    "**How A/B tests lie, measured.** Nine common experimentation mistakes, simulated thousands of times "
    "so the damage can be counted, each with a detection check and a fix. Use the pages on the left to "
    "play with the pitfalls, size a test, health-check your own experiment, or see the audit of "
    "40-experiment quarters."
)

pit, audit, val, real = (load_json("pitfalls.json"), load_json("audit_results.json"),
                         load_json("validation.json"), load_json("real_data.json"))

c1, c2, c3, c4 = st.columns(4)
if pit:
    fpr14 = next(r["fpr"] for r in pit["p1"]["looks"] if r["looks"] == 14)
    c1.metric("False positive rate with daily peeking (14 looks)", pct(fpr14), "target is 5%", delta_color="inverse")
else:
    c1.metric("Peeking", "run scripts/run_pitfalls.py")
if audit:
    import pandas as pd
    from _common import RES
    s = pd.read_csv(RES / "audit_summary.csv", index_col=0)
    c2.metric("Shipped 'wins' that were false (naive analyst)", pct(s.loc["naive", "fdr_median"], 0),
              f"{pct(s.loc['rigorous', 'fdr_median'], 0)} with the health checker", delta_color="off")
else:
    c2.metric("Audit", "run scripts/run_audit.py")
if real:
    ac = real["criteo"]["ancova"]["visit"]
    c3.metric("Users saved by covariate adjustment, real Criteo data", pct(1 - ac["sample_needed_ratio"], 0),
              "for the same precision (visit metric)", delta_color="off")
else:
    c3.metric("Real data", "run scripts/real_data_validation.py")
if val:
    c4.metric("Simulator A/A false positive rate", pct(val["aa"]["false_positive_rate"]),
              "validated before use", delta_color="off")

st.divider()
st.subheader("What's inside")
st.markdown(
    """
- **Pitfall Playground**: move the sliders and watch false positives, bias and overstated lifts change.
- **Power Calculator**: how many users and days a test needs, with and without variance reduction (CUPED).
- **Health Checker**: upload experiment data (or use a sample) and get a traffic-light verdict.
- **Audit**: a simulated portfolio of experiments analysed two ways, scored against the known truth.
"""
)
st.caption(
    "All simulations have known ground truth, which is the point: you can only measure a false positive "
    "rate when you know the real answer. The simulator is validated with A/A tests and known effects, and "
    "the methods are checked on real randomized data (Criteo, 13.98M rows; Hillstrom, 64K rows)."
)
