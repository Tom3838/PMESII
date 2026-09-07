"""
collector.py
Collects news for every country defined in config.yaml, scrapes/pulls RSS,
classifies each article into PMESII categories via the Claude API, and
stores everything in a single shared database (with a `country` column)
rather than per-country tables — keeps the schema simple as more countries
get added.

Run manually:  python collector.py
Run on a schedule via GitHub Actions (see .github/workflows/collect.yml)
"""

import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml
import feedparser

from scraper import scrape_listing
from pmesii import classify_batch

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def init_db(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY, country TEXT, source TEXT, title TEXT, url TEXT,
            published TEXT, collected_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pmesii_tags (
            article_id TEXT, category TEXT, summary TEXT,
            PRIMARY KEY (article_id, category),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
        """
    )
    conn.commit()
    return conn


def collect_rss(feeds):
    results = []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as e:
            print(f"    [warn] failed to parse {feed['name']}: {e}")
            continue
        for entry in parsed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            url = entry.get("link", "")
            if not url:
                continue
            published = entry.get("published", entry.get("updated", ""))
            results.append(
                {
                    "id": make_id(url), "source": feed["name"], "title": title, "url": url,
                    "summary": summary,
                    "published": published or datetime.now(timezone.utc).isoformat(),
                }
            )
        print(f"    [ok] {feed['name']}: {len(parsed.entries)} entries scanned")
    return results


def collect_scraped(scrape_targets):
    results = []
    for target in scrape_targets:
        articles = scrape_listing(target["name"], target["listing_url"], target["domain"])
        for a in articles:
            results.append(
                {
                    "id": make_id(a["url"]), "source": target["name"], "title": a["title"],
                    "url": a["url"], "summary": "",
                    "published": datetime.now(timezone.utc).isoformat(),
                }
            )
    return results


def filter_new(conn, results):
    """Skip articles already in the database — no point re-classifying them."""
    existing_ids = {row[0] for row in conn.execute("SELECT id FROM articles").fetchall()}
    return [r for r in results if r["id"] not in existing_ids]


def save_results(conn, results, country_key):
    for r in results:
        conn.execute(
            """INSERT OR IGNORE INTO articles
               (id, country, source, title, url, published, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (r["id"], country_key, r["source"], r["title"], r["url"], r["published"],
             datetime.now(timezone.utc).isoformat()),
        )
        for tag in r.get("pmesii_tags", []):
            conn.execute(
                """INSERT OR IGNORE INTO pmesii_tags (article_id, category, summary)
                   VALUES (?, ?, ?)""",
                (r["id"], tag["category"], tag["summary"]),
            )
    conn.commit()


def main():
    cfg = load_config()
    conn = init_db(cfg["database_path"])
    model = cfg.get("pmesii_model", "claude-haiku-4-5-20251001")

    for country_key, country_cfg in cfg.get("countries", {}).items():
        label = country_cfg.get("label", country_key)
        print(f"\n=== {label} ===")

        print("  Collecting RSS feeds...")
        rss_results = collect_rss(country_cfg.get("feeds", []))

        print("  Scraping sources without RSS...")
        scraped_results = collect_scraped(country_cfg.get("scrape_targets", []))

        all_results = filter_new(conn, rss_results + scraped_results)
        print(f"  {len(all_results)} new articles to classify...")

        all_results = classify_batch(all_results, model, label)

        before = conn.execute("SELECT COUNT(*) FROM articles WHERE country = ?", (country_key,)).fetchone()[0]
        save_results(conn, all_results, country_key)
        after = conn.execute("SELECT COUNT(*) FROM articles WHERE country = ?", (country_key,)).fetchone()[0]
        print(f"  Done. {after - before} new rows added ({after} total for {label}).")

    conn.close()
    print("\nAll countries collected.")


if __name__ == "__main__":
    main()
