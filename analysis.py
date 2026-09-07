"""
analysis.py
Loads collected articles and PMESII tags, filterable by country.
"""

import sqlite3
import pandas as pd

from pmesii import CATEGORIES  # fixed PMESII column order for dashboards


def load_countries_present(db_path: str) -> list:
    """Which country keys actually have data collected."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT country FROM articles").fetchall()
    except Exception:
        rows = []
    conn.close()
    return [r[0] for r in rows]


def load_pmesii_tags(db_path: str, country: str = None) -> pd.DataFrame:
    """Tags joined with article metadata — one row per (article, category).
    Pass country to filter to one country's data; omit for all countries."""
    conn = sqlite3.connect(db_path)
    query = """
        SELECT a.id, a.country, a.source, a.title, a.url, a.published, a.collected_at,
               t.category, t.summary
        FROM articles a
        JOIN pmesii_tags t ON a.id = t.article_id
    """
    params = ()
    if country:
        query += " WHERE a.country = ?"
        params = (country,)

    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()

    if df.empty:
        return df

    df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    df = df.dropna(subset=["published_dt"])
    df["date"] = df["published_dt"].dt.date
    return df
