"""Shared helpers for the Streamlit app: import path, precomputed results, palette."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))                 # lets Streamlit Cloud import abtest without an install

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

RES = ROOT / "data" / "results"
BAD, GOOD, NEUTRAL, ACCENT = "#c0392b", "#1e8449", "#7f8c8d", "#2c6fbb"


@st.cache_data
def load_json(name: str):
    p = RES / name
    return json.loads(p.read_text()) if p.exists() else None


@st.cache_data
def load_csv(name: str):
    p = RES / name
    return pd.read_csv(p) if p.exists() else None


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"
