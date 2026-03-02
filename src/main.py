"""WeeklyDigestOrbit — メインエントリーポイント.

RSS・arXiv・スクレイピングで記事を収集し、LM Studioで要約して静的サイトを生成する。
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

from collectors import collect_arxiv, collect_rss, collect_scraping
from generator import generate_site
from summarizer import summarize_articles

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("weekly-digest")


def load_settings() -> dict:
    """config/settings.yaml と config/.env を読み込む."""
    # .env から秘密情報を読み込み
    load_dotenv(PROJECT_ROOT / "config" / ".env")

    settings_path = PROJECT_ROOT / "config" / "settings.yaml"
    with open(settings_path, encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    # .env の値を settings に反映
    settings.setdefault("llm", {})
    settings["llm"]["base_url"] = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
    settings["llm"]["model"] = os.getenv("LLM_MODEL", "liquid/lfm2-24b-a2b")

    return settings


def collect_all(settings: dict) -> list[dict]:
    """全ソースから記事を収集する."""
    all_articles = []
    collection = settings.get("collection", {})
    days_back = collection.get("days_back", 7)
    max_per_feed = collection.get("max_articles_per_feed", 20)

    # 1. RSS収集
    logger.info("=== RSS Collection ===")
    feeds_path = PROJECT_ROOT / "config" / "feeds.yaml"
    rss_articles = collect_rss(str(feeds_path), days_back=days_back, max_per_feed=max_per_feed)
    all_articles.extend(rss_articles)

    # 2. arXiv収集
    logger.info("=== arXiv Collection ===")
    arxiv_settings = settings.get("arxiv", {})
    arxiv_articles = collect_arxiv(
        categories=arxiv_settings.get("categories"),
        keywords=arxiv_settings.get("keywords"),
        days_back=days_back,
        max_results=arxiv_settings.get("max_results", 30),
    )
    all_articles.extend(arxiv_articles)

    # 3. スクレイピング
    logger.info("=== Web Scraping ===")
    targets_path = PROJECT_ROOT / "config" / "scraping_targets.yaml"
    if targets_path.exists():
        scraped = collect_scraping(str(targets_path))
        all_articles.extend(scraped)

    # 重複排除 (URLベース)
    seen_urls: set[str] = set()
    unique = []
    for article in all_articles:
        url = article.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append(article)

    logger.info("Total unique articles: %d", len(unique))
    return unique


def deploy(dry_run: bool, settings: dict) -> None:
    """git commit & push で GitHub Pages にデプロイする."""
    if dry_run:
        logger.info("Dry run mode: skipping deploy")
        return

    deploy_settings = settings.get("deploy", {})
    if not deploy_settings.get("auto_push", True):
        logger.info("Auto push disabled: skipping deploy")
        return

    branch = deploy_settings.get("branch", "main")
    prefix = deploy_settings.get("commit_message_prefix", "digest:")
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    message = f"{prefix} {now.strftime('%Y-W%W')} weekly digest"

    try:
        subprocess.run(
            ["git", "add", "docs/", "data/"],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        # 変更がない場合はスキップ
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0:
            logger.info("No changes to commit, skipping deploy")
            return
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        logger.info("Deployed successfully: %s", message)
    except subprocess.CalledProcessError:
        logger.error("Deploy failed", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="WeeklyDigestOrbit")
    parser.add_argument("--dry-run", action="store_true", help="HTMLを生成するがpushしない")
    args = parser.parse_args()

    logger.info("=== WeeklyDigestOrbit Start ===")

    settings = load_settings()

    # 1. 収集
    articles = collect_all(settings)

    if not articles:
        logger.warning("No articles collected, generating empty digest")

    # 2. AI要約
    logger.info("=== AI Summarization ===")
    llm = settings.get("llm", {})
    digest = summarize_articles(
        articles,
        base_url=llm.get("base_url", "http://localhost:1234/v1"),
        model=llm.get("model", "liquid/lfm2-24b-a2b"),
        max_tokens=llm.get("max_tokens", 4096),
        temperature=llm.get("temperature", 0.3),
    )

    # 3. HTML生成
    logger.info("=== Site Generation ===")
    output = settings.get("output", {})
    collection = settings.get("collection", {})
    generate_site(
        digest,
        project_root=str(PROJECT_ROOT),
        docs_dir=output.get("docs_dir", "docs"),
        archives_dir=output.get("archives_dir", "docs/archives"),
        data_dir=output.get("data_dir", "data/digests"),
        days_back=collection.get("days_back", 7),
    )

    # 4. デプロイ
    logger.info("=== Deploy ===")
    deploy(args.dry_run, settings)

    logger.info("=== WeeklyDigestOrbit Complete ===")


if __name__ == "__main__":
    main()
