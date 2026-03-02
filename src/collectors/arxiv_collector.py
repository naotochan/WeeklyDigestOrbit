"""arXiv APIからロボティクス・AI関連論文を収集する."""

import logging
from datetime import datetime, timedelta, timezone

import arxiv

logger = logging.getLogger(__name__)


def collect_arxiv(
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    days_back: int = 7,
    max_results: int = 30,
) -> list[dict]:
    """arXiv APIから論文を収集する.

    Args:
        categories: 対象カテゴリ (例: ["cs.RO", "cs.AI"])
        keywords: フィルタリング用キーワード
        days_back: 何日前までの論文を取得するか
        max_results: 最大取得数

    Returns:
        論文リスト [{title, url, published, source, content_snippet, source_type, authors}]
    """
    if categories is None:
        categories = ["cs.RO", "cs.AI"]
    if keywords is None:
        keywords = ["embodied", "physical AI", "humanoid", "robot learning",
                     "manipulation", "locomotion"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    # カテゴリクエリを構築
    cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
    # キーワードクエリを構築
    kw_query = " OR ".join(f'abs:"{kw}"' for kw in keywords)
    query = f"({cat_query}) AND ({kw_query})"

    logger.info("arXiv query: %s", query)

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    articles = []
    try:
        for result in client.results(search):
            published = result.published.replace(tzinfo=timezone.utc)
            if published < cutoff:
                continue

            authors = ", ".join(a.name for a in result.authors[:5])
            if len(result.authors) > 5:
                authors += f" ほか{len(result.authors) - 5}名"

            articles.append({
                "title": result.title.strip(),
                "url": result.entry_id,
                "published": published.isoformat(),
                "source": "arXiv",
                "source_type": "research",
                "content_snippet": result.summary[:500].strip(),
                "authors": authors,
                "categories": list(result.categories) if result.categories else [],
            })
    except Exception:
        logger.warning("Failed to fetch arXiv papers", exc_info=True)

    logger.info("Total arXiv papers collected: %d", len(articles))
    return articles
