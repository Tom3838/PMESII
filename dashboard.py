"""
dashboard.py
Home page — run this with `streamlit run dashboard.py`. Streamlit
auto-detects the pages/ folder and adds each country as a sidebar page.
"""

import streamlit as st
import yaml
from pathlib import Path

from analysis import load_countries_present

CONFIG_PATH = Path(__file__).parent / "config.yaml"
st.set_page_config(page_title="PMESII Tracker — Home", layout="wide")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

db_path = cfg["database_path"]
countries_cfg = cfg.get("countries", {})

st.title("🌏 PMESII News Tracker")
st.caption("Pick a country from the sidebar to see its PMESII breakdown, executive summaries, and category tabs.")

present = set(load_countries_present(db_path))

st.subheader("Countries")
cols = st.columns(3)
for i, (key, c) in enumerate(countries_cfg.items()):
    with cols[i % 3]:
        status = "✅ Data collected" if key in present else "⚪ No data yet"
        st.markdown(f"### {c.get('flag', '')} {c.get('label', key)}")
        st.caption(status)
        n_sources = len(c.get("feeds", [])) + len(c.get("scrape_targets", []))
        st.caption(f"{n_sources} source(s) configured")

st.divider()
st.info(
    "Use the sidebar (or the links above) to open a country's dashboard. "
    "Run `python collector.py` to pull fresh articles for all countries at once."
)
