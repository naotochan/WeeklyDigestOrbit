"""Webスクレイピングでニュース記事を収集する."""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; WeeklyDigestOrbit/1.0; "
    "+https://github.com/your-repo)"
)


def collect_scraping(targets_path: str) -> list[dict]:
    """設定ファイルに基づいてWebサイトをスクレイピングする.

    Args:
        targets_path: scraping_targets.yamlのパス

    Returns:
        記事リスト [{title, url, published, source, content_snippet, source_type}]
    """
    with open(targets_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    articles = []
    seen_urls: set[str] = set()

    for target in config.get("targets", []):
        if not target.get("enabled", True):
            continue

        name = target["name"]
        url = target["url"]
        selectors = target["selectors"]

        logger.info("Scraping: %s (%s)", name, url)
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("Failed to fetch %s", name, exc_info=True)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        article_elements = soup.select(selectors.get("article", "article"))

        count = 0
        for el in article_elements:
            title_el = el.select_one(selectors.get("title", "h2 a"))
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link_el = el.select_one(selectors.get("link", "a"))
            link = link_el.get("href", "") if link_el else ""

            if not link:
                continue
            # 相対URLを絶対URLに変換
            if link.startswith("/"):
                link = urljoin(url, link)

            if link in seen_urls:
                continue

            date_el = el.select_one(selectors.get("date", "time"))
            date_str = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else None

            snippet_el = el.select_one(selectors.get("snippet", "p"))
            snippet = snippet_el.get_text(strip=True)[:500] if snippet_el else ""

            articles.append({
                "title": title,
                "url": link,
                "published": date_str,
                "source": name,
                "source_type": "news",
                "region": target.get("region", "global"),
                "content_snippet": snippet,
            })
            seen_urls.add(link)
            count += 1

        logger.info("Scraped %d articles from %s", count, name)

    logger.info("Total scraped articles: %d", len(articles))
    return articles
