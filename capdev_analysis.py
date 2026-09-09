"""
capdev_analysis.py
Synthesizes accumulated Military/Economic/Infrastructure PMESII-tagged
articles into a capability-development outlook: what's observably happening
(named programs, deals, statements) vs. what can be reasonably inferred as
a likely priority area. This is open-source pattern analysis, NOT a
prediction of specific future decisions — the prompt and UI both frame it
that way explicitly, since overclaiming confidence here would be misleading.
"""

import pandas as pd
from summarizer import _call_claude  # reuse the same API-call helper

RELEVANT_CATEGORIES = ["Military", "Economic", "Infrastructure"]

CAPDEV_PROMPT = """You are an open-source defence analyst studying capability development (capdev)
signals for {country}'s military, based on public news reporting over {scope}.

Below are Military/Economic/Infrastructure-tagged article headlines and their
angles. Produce a structured capdev outlook with exactly two parts:

PART 1 — OBSERVED ACTIVITY: List the concrete, named things actually reported
(specific systems, deals, exercises, budget announcements, official
statements). Cite what was actually said, not inference. If there is very
little material, say so plainly rather than padding this section.

PART 2 — INFERRED PRIORITY AREAS: Based ONLY on patterns in the observed
activity above (repeated themes, stated gaps, direction of spending), suggest
2-4 capability domains that appear to be a current focus. For each, state the
specific evidence from Part 1 that supports it, and how confident that
inference is (high/medium/low) based on how much and how recent the
supporting evidence is.

CRITICAL FRAMING RULES:
- This is pattern-reading from public reporting, not a forecast of any
  specific future purchase or decision. Never state a specific future
  acquisition as if it were confirmed or likely to happen on a timeline.
- Do not invent named systems, deals, or figures not present in the source
  material below.
- If the source material is thin or dominated by one-off/minor items, your
  confidence levels should reflect that honestly — do not manufacture
  significance to fill out the format.

Write in plain prose organized under the two part headers above, no other
markdown formatting, no bullet points within each part (write connected
sentences)."""


def generate_capdev_outlook(tags_df: pd.DataFrame, country_label: str, scope_label: str, model: str) -> str:
    """
    tags_df: the country's full pmesii_tags-joined dataframe (already
    filtered to the desired time period by the caller).
    """
    relevant = tags_df[tags_df["category"].isin(RELEVANT_CATEGORIES)]
    if relevant.empty:
        return (
            f"No Military, Economic, or Infrastructure articles recorded for {country_label} "
            f"in this period — nothing to analyze yet. This section will fill in as more "
            f"relevant articles are collected over time."
        )

    # Dedup by article id since one article can carry multiple relevant tags
    lines = []
    for article_id, group in relevant.groupby("id"):
        title = group["title"].iloc[0]
        angles = "; ".join(f"{row['category']}: {row['summary']}" for _, row in group.iterrows())
        lines.append(f"- {title} — {angles}")
    blob = "\n".join(lines)

    prompt = CAPDEV_PROMPT.format(country=country_label, scope=scope_label)
    return _call_claude(prompt, blob, model, max_tokens=700)
