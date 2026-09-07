import sqlite3
conn = sqlite3.connect('data/tracker.db')
rows = conn.execute("SELECT summary FROM indonesia_pmesii_tags WHERE category='Unclassified' LIMIT 5").fetchall()
for r in rows:
    print(r)