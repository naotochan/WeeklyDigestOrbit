"""RSSフィードからニュース記事を収集する."""

import logging
import re
from datetime import datetime, timedelta, timezone
from time import mktime

import feedparser
import yaml

logger = logging.getLogger(__name__)


def collect_rss(feeds_path: str, days_back: int = 7, max_per_feed: int = 20) -> list[dict]:
    """RSSフィードから記事を収集する.

    Args:
        feeds_path: feeds.yamlのパス
        days_back: 何日前までの記事を取得するか
        max_per_feed: フィードあたりの最大取得数

    Returns:
        記事リスト [{title, url, published, source, content_snippet, source_type}]
    """
    with open(feeds_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    articles = []
    seen_urls: set[str] = set()

    for feed_info in config.get("feeds", []):
        name = feed_info["name"]
        url = feed_info["url"]
        category = feed_info.get("category", "news")
        keywords = feed_info.get("filter_keywords", [])

        logger.info("Fetching RSS: %s (%s)", name, url)
        try:
            parsed = feedparser.parse(url)
        except Exception:
            logger.warning("Failed to fetch RSS: %s", name, exc_info=True)
            continue

        if parsed.bozo and not parsed.entries:
            logger.warning("RSS parse error for %s: %s", name, parsed.bozo_exception)
            continue

        count = 0
        filtered = 0
        for entry in parsed.entries:
            if count >= max_per_feed:
                break

            link = entry.get("link", "")
            if not link or link in seen_urls:
                continue

            published = _parse_date(entry)
            if published and published < cutoff:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            snippet = _extract_snippet(entry)

            # キーワードフィルタ（設定されている場合のみ）
            if keywords and not _matches_keywords(title, snippet, keywords):
                filtered += 1
                continue

            articles.append({
                "title": title,
                "url": link,
                "published": published.isoformat() if published else None,
                "source": name,
                "source_type": category,
                "region": feed_info.get("region", "global"),
                "content_snippet": snippet,
            })
            seen_urls.add(link)
            count += 1

        if keywords and filtered:
            logger.info("Collected %d articles from %s (%d filtered out)", count, name, filtered)
        else:
            logger.info("Collected %d articles from %s", count, name)

    logger.info("Total RSS articles collected: %d", len(articles))
    return articles


def _matches_keywords(title: str, snippet: str, keywords: list[str]) -> bool:
    """タイトルまたは本文抜粋にキーワードが含まれるか判定する."""
    text = (title + " " + snippet).lower()
    return any(kw.lower() in text for kw in keywords)


def _parse_date(entry) -> datetime | None:
    """エントリーから日付を解析する."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None


def _extract_snippet(entry, max_length: int = 500) -> str:
    """エントリーから本文抜粋を取得する."""
    for field in ("summary", "description", "content"):
        value = entry.get(field, "")
        if isinstance(value, list):
            value = value[0].get("value", "") if value else ""
        if value:
            text = re.sub(r"<[^>]+>", "", value).strip()
            return text[:max_length]
    return ""
