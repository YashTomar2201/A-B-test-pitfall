import numpy as np
import plotly.graph_objects as go
import streamlit as st

from _common import ACCENT, GOOD
from abtest.analyze.power import days_needed, mde_proportions, sample_size_proportions

st.set_page_config(page_title="Power Calculator", page_icon="🧪", layout="wide")
st.title("Power Calculator")
st.caption("Plan a conversion-rate test before launch. CUPED shrinks variance, so the same precision needs fewer users.")

c1, c2, c3 = st.columns(3)
base = c1.number_input("Baseline conversion rate", 0.001, 0.9, 0.05, step=0.005, format="%.3f")
mde = c2.number_input("Minimum detectable effect (relative)", 0.005, 1.0, 0.10, step=0.01, format="%.3f")
traffic = c3.number_input("Users entering the test per day (both arms)", 100, 10_000_000, 12_000, step=500)
c4, c5, c6 = st.columns(3)
alpha = c4.selectbox("Significance level (two-sided)", [0.05, 0.01, 0.10], index=0)
power = c5.selectbox("Power", [0.8, 0.9, 0.7], index=0)
vr = c6.slider("CUPED variance reduction (from a pre-period covariate)", 0.0, 0.8, 0.0, step=0.05)

n_arm = sample_size_proportions(base, mde, alpha=alpha, power=power)
n_cuped = int(np.ceil(n_arm * (1 - vr)))
days = days_needed(n_arm, traffic)
days_c = days_needed(n_cuped, traffic)

a, b, c = st.columns(3)
a.metric("Users needed per arm", f"{n_arm:,}")
b.metric("Days to run (50/50 split)", f"{days}", "a full 2 weeks is safer" if days < 14 else None, delta_color="off")
c.metric("Days with CUPED", f"{days_c}", f"{days_c - days:+d} days" if vr else None, delta_color="inverse")
if days < 14:
    st.warning("Shorter than two weeks: run at least two full weekly cycles anyway to average out day-of-week effects and novelty.")

grid = np.linspace(0.02, 0.5, 40)
fig = go.Figure(go.Scatter(x=grid * 100, y=[sample_size_proportions(base, m, alpha=alpha, power=power) for m in grid],
                           mode="lines", line=dict(color=ACCENT)))
fig.update_layout(xaxis_title="Minimum detectable effect (% relative)", yaxis_title="Users per arm", yaxis_type="log",
                  height=340, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")
st.caption(f"With {n_arm:,} users per arm, the smallest relative lift you can reliably detect is "
           f"{mde_proportions(base, n_arm, alpha=alpha, power=power):.1%}. Smaller real effects will be missed, and the ones you do "
           "'detect' will be exaggerated (see the winner's curse page).")
