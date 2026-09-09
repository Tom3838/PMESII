"""
reclassify_unclassified.py
Finds articles tagged "Unclassified" (usually a transient API hiccup, not a
real problem) and retries classification for just those — leaves everything
else untouched. Safe to run anytime.

Usage:  python reclassify_unclassified.py
"""

import sqlite3
import yaml
from pathlib import Path

from pmesii import classify_article

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db_path = cfg["database_path"]
    model = cfg.get("pmesii_model", "claude-haiku-4-5-20251001")
    countries = cfg.get("countries", {})

    conn = sqlite3.connect(db_path)

    stuck = conn.execute(
        """
        SELECT a.id, a.country, a.title
        FROM articles a
        JOIN pmesii_tags t ON a.id = t.article_id
        WHERE t.category = 'Unclassified'
        """
    ).fetchall()

    if not stuck:
        print("No unclassified articles found — nothing to do.")
        conn.close()
        return

    print(f"Found {len(stuck)} unclassified article(s). Retrying...\n")

    fixed, still_stuck = 0, 0
    for article_id, country_key, title in stuck:
        country_label = countries.get(country_key, {}).get("label", country_key)
        result = classify_article(title, "", model, country_label)

        # Clear the old "Unclassified" row first
        conn.execute("DELETE FROM pmesii_tags WHERE article_id = ? AND category = 'Unclassified'", (article_id,))

        if result and result[0]["category"] != "Unclassified":
            for tag in result:
                conn.execute(
                    "INSERT OR IGNORE INTO pmesii_tags (article_id, category, summary) VALUES (?, ?, ?)",
                    (article_id, tag["category"], tag["summary"]),
                )
            print(f"  [fixed] {title[:60]} -> {[t['category'] for t in result]}")
            fixed += 1
        else:
            reason = result[0]["summary"] if result else "unknown error"
            conn.execute(
                "INSERT OR IGNORE INTO pmesii_tags (article_id, category, summary) VALUES (?, 'Unclassified', ?)",
                (article_id, reason),
            )
            print(f"  [still stuck] {title[:60]} -> {reason}")
            still_stuck += 1

    conn.commit()
    conn.close()
    print(f"\nDone. Fixed: {fixed}, still stuck: {still_stuck}.")


if __name__ == "__main__":
    main()
