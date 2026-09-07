"""
scraper.py
Generic article-listing scraper for news sites that don't expose an RSS
feed. Fetches a listing page, finds links that look like article URLs
(same domain, reasonably long slug), and pairs each with its visible
link text as the title.

This is intentionally generic rather than site-specific with hand-picked
CSS selectors — those break the moment a site redesigns. The tradeoff is
some noise (nav links, footer links) getting picked up, which is why
titles are filtered by length and obvious junk patterns below. If a
particular site turns out too noisy in practice, tighten `_looks_like_article`
for that domain.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# Links that are almost certainly navigation, not articles
JUNK_PATTERNS = re.compile(
    r"(login|subscribe|register|about-us|contact|privacy|terms|advertise|"
    r"newsletter|rss|sitemap|category/|tag/|author/|page/\d+|#)",
    re.IGNORECASE,
)


def _looks_like_article(url: str, text: str, domain: str) -> bool:
    if domain not in url:
        return False
    if JUNK_PATTERNS.search(url):
        return False
    if not text or len(text.strip()) < 25:
        return False
    # Article URLs on most news sites have a longish path (slug), not just "/"
    path = urlparse(url).path.strip("/")
    if len(path) < 15:
        return False
    return True


def scrape_listing(name: str, listing_url: str, domain: str, limit: int = 40):
    """Fetch a listing page and return a list of {title, url} article candidates."""
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [warn] failed to fetch {name}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls = set()
    results = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(listing_url, href)
        text = a.get_text(strip=True)

        if not _looks_like_article(full_url, text, domain):
            continue
        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)
        results.append({"title": text, "url": full_url})

        if len(results) >= limit:
            break

    print(f"  [ok] {name}: {len(results)} candidate articles scraped")
    return results
