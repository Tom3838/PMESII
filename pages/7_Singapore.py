import streamlit as st
from dashboard_common import render_country_dashboard
st.set_page_config(page_title="Singapore PMESII", layout="wide")
render_country_dashboard("singapore", "Singapore", "🇸🇬")
