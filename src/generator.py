"""ダイジェストJSONから静的HTMLを生成する."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# 5セクション定義
SECTIONS = [
    ("japan_biz", "国内ビジネス動向"),
    ("global_biz", "海外ビジネス動向"),
    ("japan_tech", "国内技術動向"),
    ("global_tech", "海外技術動向"),
    ("papers", "論文"),
]


def _md_links_to_html(text: str) -> str:
    """Markdown [title](url) をHTMLリンクに変換する（XSS対策済み）."""
    if not text:
        return text

    def _replace_link(m: re.Match) -> str:
        # m はエスケープ済みテキスト上でマッチしているので、
        # title はすでにエスケープ済み（安全）
        title = m.group(1)
        url = m.group(2)
        # http/https のみ許可（javascript: 等を排除）
        if not re.match(r'https?://', url):
            return title
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer"'
            f' class="underline hover:text-white transition-colors">{title}</a>'
        )

    # まずテキスト全体をエスケープ → リンク以外のHTMLは無害化
    escaped = html_escape(text, quote=True)
    # エスケープ済みテキスト上でマークダウンリンクを変換
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _replace_link, escaped)


def _group_by_category(items: list[dict]) -> dict[str, list[dict]]:
    """記事リストをカテゴリ別にグループ化する."""
    categories: dict[str, list[dict]] = {}
    for item in items:
        cat = item.get("category", "その他")
        categories.setdefault(cat, []).append(item)
    for cat in categories:
        categories[cat].sort(key=lambda a: a.get("importance", 0), reverse=True)
    return categories


def generate_site(
    digest: dict,
    project_root: str,
    templates_dir: str = "templates",
    docs_dir: str = "docs",
    archives_dir: str = "docs/archives",
    data_dir: str = "data/digests",
) -> None:
    """ダイジェストデータから静的HTMLを生成する."""
    root = Path(project_root)
    now = datetime.now(JST)
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    week_id = now.strftime("%Y-W%W")

    # 全記事数を集計
    total_count = sum(
        len(digest.get(key, {}).get("items", []))
        for key, _ in SECTIONS
    )

    # メタデータ
    digest["meta"] = {
        "week_id": week_id,
        "week_start": week_start.strftime("%Y/%m/%d"),
        "week_end": week_end.strftime("%Y/%m/%d"),
        "generated_at": now.isoformat(),
        "article_count": total_count,
    }

    # 各セクションのカテゴリ別グループ化
    for key, _ in SECTIONS:
        section = digest.get(key, {})
        items = section.get("items", [])
        section["categories"] = _group_by_category(items)

    # 過去のアーカイブ一覧
    digest["archives"] = _get_archives(root / archives_dir)

    # Jinja2テンプレートでHTML生成
    env = Environment(
        loader=FileSystemLoader(str(root / templates_dir)),
        autoescape=True,
    )
    env.filters["md_links"] = lambda text: Markup(_md_links_to_html(text))
    template = env.get_template("index.html.j2")
    html = template.render(digest=digest)

    # docs/index.html に出力
    docs_path = root / docs_dir
    docs_path.mkdir(parents=True, exist_ok=True)
    (docs_path / "index.html").write_text(html, encoding="utf-8")
    logger.info("Generated: %s", docs_path / "index.html")

    # アーカイブに保存
    arch_path = root / archives_dir
    arch_path.mkdir(parents=True, exist_ok=True)
    archive_file = arch_path / f"{week_id}.html"
    archive_file.write_text(html, encoding="utf-8")
    logger.info("Archived: %s", archive_file)

    # JSONバックアップ
    data_path = root / data_dir
    data_path.mkdir(parents=True, exist_ok=True)
    json_file = data_path / f"{week_id}.json"
    json_file.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Data saved: %s", json_file)


def _get_archives(archives_dir: Path) -> list[dict]:
    """過去のアーカイブ一覧を取得する."""
    archives = []
    if not archives_dir.exists():
        return archives

    for f in sorted(archives_dir.glob("*.html"), reverse=True):
        week_id = f.stem
        archives.append({
            "week_id": week_id,
            "filename": f.name,
            "url": f"archives/{f.name}",
        })

    return archives[:12]
