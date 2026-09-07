"""
summarizer.py
Generates narrative summaries (per PMESII category, and an overall synthesis)
for a chosen time window — this week / this month / since collection began.
Built on top of the already-classified article summaries (cheap: it reads
short one-liners already stored, not full article text).
"""

import os
import json
import re
import requests
import pandas as pd

API_URL = "https://api.anthropic.com/v1/messages"

PERIOD_OPTIONS = {
    "This week": 7,
    "This month": 30,
    "All time": None,  # no cutoff — everything since collection began
}


def filter_by_period(df: pd.DataFrame, period_label: str) -> pd.DataFrame:
    days = PERIOD_OPTIONS.get(period_label)
    if days is None or df.empty:
        return df
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    return df[df["published_dt"] >= cutoff]


def _extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"no JSON object found: {raw_text[:200]!r}")


def _call_claude(system_prompt: str, user_content: str, model: str, max_tokens: int = 500) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠️ No summary generated — ANTHROPIC_API_KEY is not set."

    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_content}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()
    except Exception as e:
        return f"⚠️ Summary generation failed: {e}"


CATEGORY_SUMMARY_PROMPT = """You are a defence/geopolitical analyst writing a brief situation summary
for the {category} dimension of {country}-related news over {scope}.

Below are headlines and their {category}-specific angles from articles collected
in this period. Synthesize them into a tight, analytical paragraph (3-5 sentences)
covering the key developments and any notable pattern or shift. Do not just list
the headlines back — identify what they collectively indicate. If the items are
disconnected/minor, say so plainly rather than manufacturing false significance.

Write in plain prose, no markdown headers, no bullet points."""

OVERALL_SUMMARY_PROMPT = """You are a defence/geopolitical analyst writing a brief executive summary
of {country}-related developments over {scope}, across all PMESII dimensions
(Political, Military, Economic, Social, Information, Infrastructure).

Below are per-category summaries already written for this period. Synthesize
them into a single tight executive-summary paragraph (4-6 sentences) that
highlights the dimensions with the most notable activity and any cross-cutting
theme connecting them. Write in plain prose, no markdown headers, no bullet points."""


def summarize_category(df: pd.DataFrame, category: str, scope_label: str, model: str, country_label: str) -> str:
    """df: tags_df already filtered to this category and period."""
    if df.empty:
        return f"No {category} activity recorded in this period."

    lines = [f"- {row['title']} — {row['summary']}" for _, row in df.iterrows()]
    blob = "\n".join(lines)

    prompt = CATEGORY_SUMMARY_PROMPT.format(category=category, scope=scope_label, country=country_label)
    return _call_claude(prompt, blob, model)


def summarize_overall(category_summaries: dict, scope_label: str, model: str, country_label: str) -> str:
    """category_summaries: {category_name: summary_text}, only non-empty ones."""
    active = {k: v for k, v in category_summaries.items() if v and "No " + k not in v}
    if not active:
        return "No significant PMESII activity recorded in this period."

    blob = "\n\n".join(f"{cat}:\n{summary}" for cat, summary in active.items())
    prompt = OVERALL_SUMMARY_PROMPT.format(scope=scope_label, country=country_label)
    return _call_claude(prompt, blob, model, max_tokens=400)
