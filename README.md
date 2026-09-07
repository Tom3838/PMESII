# Multi-Country PMESII Tracker

Tracks news from Indonesia, Malaysia, China, USA, Japan, and Korea, classifies
each article into PMESII categories (Political / Military / Economic / Social /
Information / Infrastructure) via the Claude API, and shows each country as
its own dashboard page.

## What's in here

| File | Purpose |
|---|---|
| `config.yaml` | All countries, their sources, and settings — the file you'll edit most |
| `collector.py` | Loops over every country, collects + classifies, saves to SQLite |
| `scraper.py` | Generic listing-page scraper for sites without RSS |
| `pmesii.py` | Calls the Claude API to classify articles, country-aware prompt |
| `summarizer.py` | Generates AI period summaries (week/month/all-time) per country |
| `analysis.py` | Loads articles/tags from the DB, filterable by country |
| `dashboard.py` | Home page — run this one with `streamlit run` |
| `dashboard_common.py` | Shared rendering logic used by every country page |
| `pages/*.py` | One thin file per country — Streamlit auto-adds these as sidebar pages |

## Step 1 — Get an Anthropic API key

1. [platform.claude.com](https://platform.claude.com) → sign up → add billing credit.
2. Generate an API key under **API Keys**, copy it.
3. Without this key, articles still get collected but tagged "Unclassified".

## Step 2 — Test it locally

```bash
cd defcap-tracker
pip install -r requirements.txt

$env:ANTHROPIC_API_KEY="sk-ant-..."     # Windows PowerShell
export ANTHROPIC_API_KEY="sk-ant-..."   # Mac/Linux

python collector.py
```

This now collects **all six countries in one run** and prints progress per
country. Then:

```bash
python -m streamlit run dashboard.py
```

Opens the home page. Countries appear as separate pages in the left sidebar —
click any to see its Executive Summary, category tabs, and full matrix.

## Step 3 — GitHub + free hosting

Same as before:
```bash
git init && git add . && git commit -m "Initial commit"
git branch -M main && git remote add origin <your-repo-url> && git push -u origin main
```
Add `ANTHROPIC_API_KEY` as a repo secret (**Settings → Secrets and variables →
Actions**). The existing workflow already runs `collector.py`, which now
covers all countries automatically — no workflow changes needed.

Deploy on [share.streamlit.io](https://share.streamlit.io) pointing at
`dashboard.py` as before.

## Notes on sources — please read

Several feed URLs in `config.yaml` are marked `# VERIFY` — I found these
through research but couldn't fetch arbitrary websites from my build
environment to confirm every URL is exactly right. **This is expected and
handled gracefully**: if a feed URL is wrong, the collector just logs a
warning and moves on — it won't crash the run for other sources.

After your first `python collector.py` run, check the printed output. Any
source showing `0 entries scanned` needs a URL fix:
1. Search `"<site name> RSS feed"` and swap the correct URL into `config.yaml`, or
2. Tell me which source is broken and I'll look it up.

**China note**: all three configured sources (Xinhua, Global Times, ECNS) are
state-affiliated/state-controlled. There's no independent domestic English
news outlet — this is useful for tracking official framing/narrative, not
independent reporting. Worth keeping in mind when reading PMESII classifications
for China, since they'll reflect what's officially said, not necessarily ground truth.

## Notes on the database

- Single shared `articles` + `pmesii_tags` tables now, with a `country` column
  — not one table per country. Keeps the schema simple as you add more countries.
- Adding a 7th country later is just adding an entry under `countries:` in
  `config.yaml` — no code changes needed, a new page appears automatically
  next time you add a matching file in `pages/`.

## Notes on PMESII classification

- Multi-category: an article can be tagged into more than one PMESII column,
  each with a category-specific angle (not the same text repeated).
- Lifestyle/routine articles with no genuine relevance get zero tags and are
  excluded from the tables entirely — not force-fit into a category.
- Uses `claude-haiku-4-5-20251001` by default — change `pmesii_model` in
  `config.yaml` if you want a stronger (pricier) model.

## Notes on Executive Summaries

- Generated on-demand per country (This week / This month / All time) —
  not auto-generated on page load, so it only costs API credit when you
  actually click Generate.
- Built from the already-classified category summaries, not full article text.
