"""
pmesii.py
Classifies articles into PMESII categories (Political, Military, Economic,
Social, Information, Infrastructure) using the Claude API. An article can
map to MULTIPLE categories (e.g. a procurement story is both Military and
Economic) — for each applicable category, the model writes a short,
category-specific angle on the story, so the same article doesn't show
identical text repeated across columns.

Requires ANTHROPIC_API_KEY. If missing, classification is skipped
gracefully (article is tagged "Unclassified" rather than crashing the run).
"""

import os
import json
import re
import requests

API_URL = "https://api.anthropic.com/v1/messages"
CATEGORIES = ["Political", "Military", "Economic", "Social", "Information", "Infrastructure"]

def build_system_prompt(country_label: str) -> str:
    return f"""You are a PMESII analysis assistant for a defence analyst covering {country_label}.

STEP 1 — RELEVANCE CHECK (do this first, silently):
Is this article SUBSTANTIVELY about {country_label} — its government, military,
economy, society, or events directly affecting it? News wires (e.g. national
press agencies) often carry generic world/foreign news that has NO real
connection to {country_label} beyond being published by a {country_label}-based
outlet. If the article is really about a different country/region and
{country_label} is not a central subject, return an empty tags list — do not
classify it just because the source happens to be from {country_label}.

STEP 2 — FACTUAL ACCURACY:
Base your classification and summary ONLY on what this specific article
states. Do NOT supply a person's title, role, or position from your own
background knowledge — people's positions change over time and your training
data may be outdated (e.g. do not assume someone is still "defence minister"
if the article doesn't say so, since they may have since become president,
been replaced, etc.). If the article states a role, use it; if it doesn't,
either omit the role or describe the person by name only.

STEP 3 — CATEGORIZATION:
For articles that pass the relevance check, identify which PMESII categories
from {", ".join(CATEGORIES)} are GENUINELY CENTRAL to the story.

Be conservative. Most everyday articles (lifestyle, entertainment, sports,
routine human-interest pieces) do NOT belong in any PMESII category — it is
correct and expected to return an empty tags list for these. Do not stretch a
tangential detail into a category just to fill something in. Only tag a
category when the article's main subject substantively concerns that
dimension — e.g. an actual policy change, military activity, economic
data/investment, a real social or political trend, infrastructure
development, or a notable information/media event.

An article CAN belong to more than one category when multiple dimensions are
genuinely central (e.g. a defence procurement deal is both Military and
Economic). For EACH applicable category, write a short (under 15 words),
CONCRETE, factual summary highlighting that category's specific angle — state
what actually happened, not vague analyst-speak. Do not repeat the same
summary text across categories.

STEP 4 — LANGUAGE:
Always write summaries in English, even if the source article is in
Indonesian, Malay, Chinese, Japanese, or Korean.

Respond ONLY with a JSON object, no other text, in this exact shape:
{{"tags": [{{"category": "<category>", "summary": "<concrete, category-specific angle, under 15 words>"}}, ...]}}

An empty "tags": [] array is a valid and often correct answer — both for
irrelevant articles (Step 1) and for relevant-but-non-PMESII ones (Step 3)."""


def _extract_json(raw_text: str) -> dict:
    """
    Models occasionally wrap JSON in markdown code fences or add stray
    text despite instructions not to. This strips fences and, if direct
    parsing still fails, pulls out the first {...} block found.
    """
    text = raw_text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back: grab the first {...} block anywhere in the text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"no JSON object found in model output: {raw_text[:200]!r}")


def classify_article(title: str, summary: str, model: str, country_label: str = "the country in question") -> list:
    """
    Returns a list of {"category": ..., "summary": ...} dicts, one per
    applicable PMESII category. Falls back to a single
    [{"category": "Unclassified", "summary": "<why>"}] on any failure
    (missing key, API error, bad response) so one failure never stops
    the whole collection run.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return [{"category": "Unclassified", "summary": "no API key configured"}]

    text = f"Title: {title}\nSummary: {summary}".strip()
    system_prompt = build_system_prompt(country_label)

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
                "max_tokens": 300,
                "system": system_prompt,
                "messages": [{"role": "user", "content": text}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        parsed = _extract_json(raw_text)
        tags = parsed.get("tags", [])

        cleaned = []
        for t in tags:
            cat = t.get("category")
            if cat in CATEGORIES:
                cleaned.append({"category": cat, "summary": t.get("summary", "")})

        # An empty list here is a legitimate result (article isn't PMESII-relevant),
        # not a failure — only fall back to "Unclassified" on an actual parsing/API error.
        return cleaned

    except Exception as e:
        return [{"category": "Unclassified", "summary": f"classification failed: {e}"}]


def classify_batch(articles: list, model: str, country_label: str = "the country in question") -> list:
    """Classify a list of {title, summary, ...} dicts in place, adding a
    'pmesii_tags' key (list of {category, summary}) to each."""
    for art in articles:
        art["pmesii_tags"] = classify_article(
            art.get("title", ""), art.get("summary", ""), model, country_label
        )
    return articles

