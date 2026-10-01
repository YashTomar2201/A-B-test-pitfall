import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from _common import ACCENT, BAD, GOOD, NEUTRAL, RES, load_json, pct

st.set_page_config(page_title="Audit", page_icon="🧪", layout="wide")
st.title("The Experiment Audit")
st.markdown("**ShopKart ran 40 A/B tests a quarter. How many shipped 'wins' were real?** We simulated many quarters where "
            "the true effect of every test is known, then analysed them two ways.")

res = load_json("audit_results.json")
if res is None:
    st.info("Run `python scripts/run_audit.py` to generate the audit results.")
    st.stop()

s = pd.read_csv(RES / "audit_summary.csv", index_col=0)
scen = pd.read_csv(RES / "audit_by_scenario.csv", index_col=0)
st.markdown("""
| | Naive analyst | Rigorous analyst |
|---|---|---|
| Looks | Daily, stops at first p < 0.05 | Fixed horizon |
| Metrics | Ships if conversion, revenue, **or any of 5 segments** wins | One pre-registered primary metric |
| Checks | None | Health checker; ships only on a clean pass |
""")
a, b, c = st.columns(3)
a.metric("Median shipped 'wins' per quarter", f"{s.loc['naive', 'shipped_median']:.0f}", f"rigorous: {s.loc['rigorous', 'shipped_median']:.0f}", delta_color="off")
b.metric("Median false wins per quarter", f"{s.loc['naive', 'false_wins_median']:.0f}", f"rigorous: {s.loc['rigorous', 'false_wins_median']:.0f}", delta_color="off")
c.metric("False discovery rate (median)", pct(s.loc["naive", "fdr_median"], 0), f"rigorous: {pct(s.loc['rigorous', 'fdr_median'], 0)}", delta_color="off")

fig = go.Figure()
fig.add_bar(name="Naive", x=scen.index, y=scen.naive_ship_rate * 100, marker_color=BAD)
fig.add_bar(name="Rigorous", x=scen.index, y=scen.rigorous_ship_rate * 100, marker_color=GOOD)
fig.update_layout(barmode="group", yaxis_title="% of tests shipped", height=360, margin=dict(l=10, r=10, t=30, b=10),
                  title="Share shipped, by what is really going on (true wins should be shipped, the rest should not)")
st.plotly_chart(fig, width="stretch")

st.subheader("What it costs (illustrative economics)")
sens = pd.DataFrame(res["sens_false_win_cost"])
sens.columns = ["Cost per false win (INR)", "Naive, median quarterly cost (INR)", "Rigorous, median quarterly cost (INR)"]
st.dataframe(sens.style.format("{:,.0f}"), hide_index=True, width="stretch")
w = res["worst_case_rerun_equals_abandon"]
st.caption("All money figures rest on stated assumptions in `config/audit_portfolio.yaml`. "
           f"Worst case for the rigorous analyst (a flagged rerun is treated as an abandoned idea): naive "
           f"₹{w['naive_total_cost_median']:,.0f} vs rigorous ₹{w['rigorous_total_cost_median']:,.0f} median quarterly cost.")
st.subheader("Sensitivity to the share of true wins")
st.dataframe(pd.DataFrame(res["sens_true_win_share"]).style.format(
    {"true_win_share": "{:.0%}", "naive_fdr_median": "{:.0%}", "rigorous_fdr_median": "{:.0%}"}), hide_index=True, width="stretch")
