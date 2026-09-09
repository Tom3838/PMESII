"""
dashboard_common.py
Shared rendering logic for a single country's PMESII dashboard page.
Each file in pages/ calls render_country_dashboard() with its own country
key/label/flag — keeps every country page in sync without duplicating code.
"""

import streamlit as st
import pandas as pd
import yaml
from pathlib import Path

from analysis import load_pmesii_tags, CATEGORIES
from summarizer import PERIOD_OPTIONS, filter_by_period, summarize_category, summarize_overall
from capdev_analysis import generate_capdev_outlook

CONFIG_PATH = Path(__file__).parent / "config.yaml"

CATEGORY_ICONS = {
    "Political": "🏛️",
    "Military": "🪖",
    "Economic": "💰",
    "Social": "👥",
    "Information": "📡",
    "Infrastructure": "🏗️",
}


def render_country_dashboard(country_key: str, country_label: str, flag: str):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db_path = cfg["database_path"]
    summary_model = cfg.get("pmesii_model", "claude-haiku-4-5-20251001")

    st.title(f"{flag} {country_label} PMESII Tracker")

    tags_df = load_pmesii_tags(db_path, country=country_key)

    if tags_df.empty:
        st.warning(
            f"No data yet for {country_label}. Run `python collector.py` at least once. "
            f"Note: PMESII classification requires ANTHROPIC_API_KEY to be set — "
            f"without it, articles are tagged 'Unclassified'."
        )
        return

    unclassified = (tags_df["category"] == "Unclassified").sum()
    if unclassified:
        st.info(
            f"{unclassified} article(s) came back 'Unclassified' — usually means "
            f"ANTHROPIC_API_KEY wasn't set when they were collected."
        )
        tags_df = tags_df[tags_df["category"] != "Unclassified"]

    if tags_df.empty:
        st.warning("All collected articles are unclassified — set ANTHROPIC_API_KEY and re-run the collector.")
        return

    earliest = tags_df["published_dt"].min()
    st.caption(f"Tracking since {earliest.strftime('%d %b %Y')} — archive grows with every collection run.")

    # ── Executive Summary (on-demand, AI-generated) ─────────────────────
    st.subheader("📋 Executive Summary")
    ec1, _ = st.columns([1, 3])
    period_label = ec1.selectbox("Time window", options=list(PERIOD_OPTIONS.keys()), key=f"{country_key}_period")
    generate = ec1.button("Generate summary", type="primary", key=f"{country_key}_generate")

    session_key = f"{country_key}_summary"

    if generate:
        period_df = filter_by_period(tags_df, period_label)
        if period_df.empty:
            st.warning(f"No articles found in the '{period_label}' window yet.")
        else:
            with st.spinner("Synthesizing category summaries..."):
                cat_summaries = {}
                for cat in CATEGORIES:
                    cat_df = period_df[period_df["category"] == cat]
                    cat_summaries[cat] = summarize_category(
                        cat_df, cat, period_label.lower(), summary_model, country_label
                    )

            with st.spinner("Writing overall executive summary..."):
                overall = summarize_overall(cat_summaries, period_label.lower(), summary_model, country_label)

            st.session_state[session_key] = {
                "overall": overall, "cat_summaries": cat_summaries, "period": period_label,
            }

    if session_key in st.session_state:
        s = st.session_state[session_key]
        st.markdown(f"**Overall — {s['period']}**")
        st.write(s["overall"])
        with st.expander("Per-category breakdown"):
            for cat in CATEGORIES:
                st.markdown(f"**{CATEGORY_ICONS[cat]} {cat}**")
                st.write(s["cat_summaries"].get(cat, ""))
    else:
        st.caption("Pick a time window and click Generate to get an AI-written synthesis.")

    st.divider()

    # ── Capability Development Outlook (on-demand, AI-generated) ────────
    st.subheader("🎯 Capability Development Outlook")
    st.caption(
        "Pattern analysis of Military/Economic/Infrastructure signals — what's "
        "concretely been reported, and what that pattern may suggest as a current "
        "priority area. This is inference from public reporting, not a forecast "
        "or confirmation of any specific future decision — treat it as a starting "
        "point for your own analysis, not a conclusion."
    )
    cd1, _ = st.columns([1, 3])
    cd_period = cd1.selectbox("Time window", options=list(PERIOD_OPTIONS.keys()), key=f"{country_key}_cd_period")
    cd_generate = cd1.button("Generate outlook", type="primary", key=f"{country_key}_cd_generate")

    cd_session_key = f"{country_key}_capdev"

    if cd_generate:
        cd_period_df = filter_by_period(tags_df, cd_period)
        with st.spinner("Analyzing capability development signals..."):
            outlook = generate_capdev_outlook(cd_period_df, country_label, cd_period.lower(), summary_model)
        st.session_state[cd_session_key] = {"outlook": outlook, "period": cd_period}

    if cd_session_key in st.session_state:
        cd = st.session_state[cd_session_key]
        st.markdown(f"**Outlook — {cd['period']}**")
        st.write(cd["outlook"])
    else:
        st.caption("Pick a time window and click Generate.")

    st.divider()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total articles", tags_df["id"].nunique())
    c2.metric("Total category tags", len(tags_df))
    c3.metric(
        "Avg categories/article",
        round(len(tags_df) / tags_df["id"].nunique(), 1) if tags_df["id"].nunique() else 0,
    )

    st.subheader("Category volume (all time)")
    vol_cols = st.columns(len(CATEGORIES))
    counts_by_cat = tags_df["category"].value_counts()
    for col, cat in zip(vol_cols, CATEGORIES):
        col.metric(f"{CATEGORY_ICONS[cat]} {cat}", int(counts_by_cat.get(cat, 0)))

    st.divider()

    # ── Per-category tabs ─────────────────────────────────────────────
    st.subheader("Articles by category")
    st.caption(
        "Each tab shows only articles genuinely relevant to that category, with "
        "that category's specific angle on the story. Purely lifestyle/routine "
        "pieces with no real PMESII relevance are excluded entirely."
    )

    tab_labels = [f"{CATEGORY_ICONS[c]} {c} ({int(counts_by_cat.get(c, 0))})" for c in CATEGORIES]
    tabs = st.tabs(tab_labels)

    for tab, cat in zip(tabs, CATEGORIES):
        with tab:
            sub = tags_df[tags_df["category"] == cat].sort_values("published_dt", ascending=False)
            if sub.empty:
                st.write("No articles tagged in this category yet.")
                continue

            display = sub[["published_dt", "source", "title", "summary", "url"]].rename(
                columns={
                    "published_dt": "Published", "source": "Source", "title": "Headline",
                    "summary": f"{cat} angle", "url": "Link",
                }
            )
            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Link": st.column_config.LinkColumn("Link", display_text="Open ↗", width="small"),
                    "Published": st.column_config.DatetimeColumn("Published", format="D MMM, HH:mm", width="small"),
                    "Source": st.column_config.TextColumn("Source", width="small"),
                    "Headline": st.column_config.TextColumn("Headline", width="large"),
                    f"{cat} angle": st.column_config.TextColumn(f"{cat} angle", width="large"),
                },
                height=min(600, 60 + 45 * len(display)),
            )

    st.divider()

    with st.expander("Show full cross-category matrix instead"):
        cat_filter = st.multiselect(
            "Filter — only show articles tagged with:", options=CATEGORIES, key=f"{country_key}_matrix_filter"
        )
        pivot_rows = []
        for article_id, group in tags_df.groupby("id"):
            row = {
                "Published": group["published_dt"].iloc[0], "Source": group["source"].iloc[0],
                "Headline": group["title"].iloc[0], "Link": group["url"].iloc[0],
            }
            article_cats = set(group["category"])
            if cat_filter and not article_cats.intersection(cat_filter):
                continue
            for cat in CATEGORIES:
                match = group[group["category"] == cat]
                row[cat] = match["summary"].iloc[0] if not match.empty else ""
            pivot_rows.append(row)

        pivot_df = pd.DataFrame(pivot_rows).sort_values("Published", ascending=False)
        column_config = {
            "Link": st.column_config.LinkColumn("Link", display_text="Open ↗", width="small"),
            "Published": st.column_config.DatetimeColumn("Published", format="D MMM, HH:mm", width="small"),
            "Source": st.column_config.TextColumn("Source", width="small"),
            "Headline": st.column_config.TextColumn("Headline", width="medium"),
        }
        for cat in CATEGORIES:
            column_config[cat] = st.column_config.TextColumn(cat, width="medium")

        st.dataframe(
            pivot_df, use_container_width=True, hide_index=True,
            column_config=column_config, height=min(600, 60 + 45 * len(pivot_df)),
        )
