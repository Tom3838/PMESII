import streamlit as st
from dashboard_common import render_country_dashboard
st.set_page_config(page_title="USA PMESII", layout="wide")
render_country_dashboard("usa", "United States", "🇺🇸")
