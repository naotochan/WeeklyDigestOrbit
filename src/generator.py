"""ダイジェストJSONから静的HTMLを生成する."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from html import unescape as html_unescape
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
        # URLはエスケープ済みなのでunescapeしてからhrefに設定（&amp; → &）
        url = html_unescape(m.group(2))
        # http/https のみ許可（javascript: 等を排除）
        if not re.match(r'https?://', url):
            return title
        # href属性値は再度エスケープ
        safe_url = html_escape(url, quote=True)
        return (
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer"'
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
    days_back: int = 7,
) -> None:
    """ダイジェストデータから静的HTMLを生成する."""
    root = Path(project_root)
    now = datetime.now(JST)
    # 収集対象は前週なので、(now - days_back) 基準で週番号を決定
    target = now - timedelta(days=days_back)
    iso = target.isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"
    # ISO週の境界（月曜〜日曜）を表示用日付にする
    week_start = datetime.fromisocalendar(iso[0], iso[1], 1).replace(tzinfo=JST)
    week_end = datetime.fromisocalendar(iso[0], iso[1], 7).replace(tzinfo=JST)

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

    # docs/index.html 用（アーカイブリンクは archives/ 付き）
    html_index = template.render(digest=digest, archive_url_prefix="archives/")
    docs_path = root / docs_dir
    docs_path.mkdir(parents=True, exist_ok=True)
    (docs_path / "index.html").write_text(html_index, encoding="utf-8")
    logger.info("Generated: %s", docs_path / "index.html")

    # アーカイブ用（同ディレクトリなのでプレフィックス不要）
    html_archive = template.render(digest=digest, archive_url_prefix="")
    arch_path = root / archives_dir
    arch_path.mkdir(parents=True, exist_ok=True)
    archive_file = arch_path / f"{week_id}.html"
    archive_file.write_text(html_archive, encoding="utf-8")
    logger.info("Archived: %s", archive_file)

    # Markdown版を生成（docs/ と archives/ の両方）
    md_content = _generate_markdown(digest)
    (docs_path / f"{week_id}.md").write_text(md_content, encoding="utf-8")
    logger.info("Generated MD: %s", docs_path / f"{week_id}.md")
    (arch_path / f"{week_id}.md").write_text(md_content, encoding="utf-8")
    logger.info("Archived MD: %s", arch_path / f"{week_id}.md")

    # JSONバックアップ
    data_path = root / data_dir
    data_path.mkdir(parents=True, exist_ok=True)
    json_file = data_path / f"{week_id}.json"
    json_file.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Data saved: %s", json_file)


SECTION_META = [
    ("japan_biz", "国内ビジネス動向", "資金調達・提携・製品発表・政策"),
    ("global_biz", "海外ビジネス動向", "Industry Now — グローバル市場の動き"),
    ("japan_tech", "国内技術動向", "技術開発・実証実験・導入事例"),
    ("global_tech", "海外技術動向", "新手法・ベンチマーク・技術ブレイクスルー"),
    ("papers", "Research Frontier", "今週の注目論文 — 未来を拓く研究"),
]


def _generate_markdown(digest: dict) -> str:
    """ダイジェストデータからMarkdownを生成する."""
    meta = digest.get("meta", {})
    lines = [
        f'# WeeklyDigestOrbit — {meta.get("week_start", "")} ~ {meta.get("week_end", "")}',
        f'> Robotics / Physical AI / Embodied AI | {meta.get("article_count", 0)}件',
        '',
    ]

    for key, title, subtitle in SECTION_META:
        sec = digest.get(key, {})
        if not sec.get("items") and not sec.get("summary"):
            continue

        lines += ['---', f'## {title}', f'*{subtitle}*', '']

        summary = sec.get("summary", "")
        if summary:
            lines += [summary, '']

        trends = sec.get("trends", [])
        if trends:
            lines += ['**トレンド:** ' + ' / '.join(f'`{t}`' for t in trends), '']

        must_read = sec.get("must_read", [])
        if must_read:
            lines += ['### ハイライト', '']
            for i, mr in enumerate(must_read, 1):
                lines.append(f'**{i}. [{mr.get("title", "")}]({mr.get("url", "")})**')
                lines += [f'> {mr.get("one_liner", "")}', '']
                detail = mr.get("detail", "")
                if detail:
                    lines += [detail, '']
                source = mr.get("source", "")
                if source:
                    lines += [f'*— {source}*', '']

        categories = sec.get("categories", {})
        if categories:
            lines += ['### 全記事一覧', '']
            for cat_name, cat_items in categories.items():
                lines += [f'#### {cat_name}', '']
                for a in cat_items:
                    importance = a.get("importance", 3)
                    stars = "\u2605" * importance + "\u2606" * (5 - importance)
                    lines.append(f'- [{a.get("title", "")}]({a.get("url", "")}) {stars}')
                    lines.append(f'  {a.get("summary", "")}')
                    authors = a.get("authors", a.get("source", ""))
                    lines += [f'  *{authors}*', '']

    lines += ['---', f'*Generated by WeeklyDigestOrbit — {meta.get("generated_at", "")[:10]}*']
    return '\n'.join(lines)


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
        })

    return archives[:12]
