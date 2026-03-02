"""LM Studio APIを使って記事を要約・分類する."""

import json
import logging
import re
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

# --- 記事要約用プロンプト（ビジネス/技術の分類含む） ---

NEWS_BATCH_PROMPT = """\
あなたはロボティクス・Physical AI・Embodied AI領域の専門エディターです。
与えられたニュース・ブログ記事を分析し、以下の構造化JSONを生成してください。

## 出力フォーマット (JSON)
```json
{
  "articles": [
    {
      "title": "元の記事タイトル",
      "url": "元のURL",
      "summary": "記事の要約（日本語、2〜3文）",
      "category": "カテゴリ名",
      "article_type": "business または technology",
      "importance": 5,
      "source": "ソース名"
    }
  ]
}
```

## article_type の判定基準
- **business**: 資金調達、M&A、提携、製品発表、導入事例、市場動向、政策・規制、人事、IPO、事業戦略
- **technology**: 技術開発、アルゴリズム、ベンチマーク、実証実験、新手法、性能向上、技術比較

## カテゴリ一覧
- ヒューマノイド
- 産業用ロボット
- 自動運転・モビリティ
- AI基盤技術
- Embodied AI
- ドローン・無人機
- 国内スタートアップ
- 政策・規制
- その他

## ルール
- importance は 1（低）〜 5（高）の整数
- 必ず有効なJSONのみを出力すること（マークダウンのコードブロックは不要）
"""

# --- 論文用プロンプト ---

PAPERS_BATCH_PROMPT = """\
あなたはロボティクス・Physical AI・Embodied AI領域の研究動向アナリストです。
与えられた学術論文を分析し、以下の構造化JSONを生成してください。

## 出力フォーマット (JSON)
```json
{
  "papers": [
    {
      "title": "元の論文タイトル",
      "url": "元のURL",
      "summary": "論文の貢献と意義を日本語で要約（2〜3文）",
      "category": "カテゴリ名",
      "importance": 5,
      "source": "arXiv",
      "authors": "著者名"
    }
  ]
}
```

## カテゴリ一覧
- ヒューマノイド
- マニピュレーション
- ロコモーション
- シミュレーション・Sim2Real
- 視覚・言語・行動モデル
- 強化学習・模倣学習
- その他

## ルール
- importance は 1（低）〜 5（高）の整数。実応用に近いほど高く。
- 必ず有効なJSONのみを出力すること
"""

# --- セクションサマリー + must_read 生成用テンプレート ---

def _make_synthesis_prompt(section_name: str, focus: str, is_english_source: bool = False) -> str:
    detail_instruction = (
        "detail は原文（英語）を読まなくても内容が十分わかる詳しさで書くこと。日本語で5〜8文。"
        if is_english_source else
        "detail は記事の内容が十分わかる詳しさで書くこと。5〜8文。"
    )
    return f"""\
あなたはロボティクス・Physical AI・Embodied AI領域の専門エディターです。
以下は今週の「{section_name}」に関する要約済み記事一覧です。

{focus}

## 出力フォーマット (JSON)
```json
{{
  "summary": "今週の{section_name}を3〜5文で要約。具体的な企業名・製品名・数字を含めて。",
  "trends": ["トレンド1", "トレンド2", "トレンド3"],
  "must_read": [
    {{
      "title": "記事タイトル",
      "url": "URL",
      "one_liner": "なぜ重要か（1文）",
      "detail": "{detail_instruction}",
      "source": "ソース名"
    }}
  ]
}}
```

## ルール
- must_read は最も重要な3〜5件を厳選
- {detail_instruction}
- summary 内で言及する記事には必ず元のURLを [タイトル](URL) 形式で含めること
- 必ず有効なJSONのみを出力すること
"""


PAPERS_SYNTHESIS_PROMPT = """\
あなたはロボティクス・Physical AI・Embodied AI領域の研究動向アナリストです。
以下は今週の注目論文の要約一覧です。

## 出力フォーマット (JSON)
```json
{
  "summary": "今週の研究動向を3〜5文で要約。summary 内で言及する論文には [タイトル](URL) 形式でリンクを含めること。",
  "trends": ["研究トレンド1", "研究トレンド2", "研究トレンド3"],
  "must_read": [
    {
      "title": "論文タイトル",
      "url": "URL",
      "one_liner": "なぜ注目か（1文）",
      "detail": "論文の内容を日本語で詳しく紹介（5〜8文）。原文を読まなくても価値がわかるように。",
      "source": "arXiv"
    }
  ]
}
```

## ルール
- must_read はインパクトが大きい3〜5件を厳選
- detail は原文（英語）を読まなくても論文の核心がわかる詳しさで書くこと
- 必ず有効なJSONのみを出力すること
"""

BATCH_SIZE = 15


def summarize_articles(
    articles: list[dict],
    base_url: str,
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    api_key: str = "lm-studio",
) -> dict:
    """記事を5セクション（国内BIZ/海外BIZ/国内TECH/海外TECH/論文）に分けて要約する."""
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=600.0)

    # 論文とニュースを分離
    news_raw = [a for a in articles if a.get("source_type") != "research"]
    papers_raw = [a for a in articles if a.get("source_type") == "research"]

    logger.info("Split: %d news/blog, %d papers", len(news_raw), len(papers_raw))

    # --- Step 1: ニュース記事をバッチ要約（article_type: business/technology の分類含む）---
    all_news = _batch_summarize(client, news_raw, model, max_tokens, temperature,
                                NEWS_BATCH_PROMPT, "articles", "news")

    # --- Step 2: 論文をバッチ要約 ---
    all_papers = _batch_summarize(client, papers_raw, model, max_tokens, temperature,
                                  PAPERS_BATCH_PROMPT, "papers", "papers")

    # --- Step 3: region × article_type で4グループに分割 ---
    # region は元記事から引き継ぐ
    region_map = {a.get("url", ""): a.get("region", "global") for a in articles}
    for item in all_news:
        item["region"] = region_map.get(item.get("url", ""), "global")

    japan_biz, global_biz, japan_tech, global_tech = [], [], [], []
    for a in all_news:
        is_japan = a.get("region") == "japan"
        atype = a.get("article_type", "")
        if atype == "technology":
            (japan_tech if is_japan else global_tech).append(a)
        else:
            # business または未分類 → ビジネスに振り分け
            (japan_biz if is_japan else global_biz).append(a)

    for lst in (japan_biz, global_biz, japan_tech, global_tech):
        lst.sort(key=lambda a: a.get("importance", 0), reverse=True)
    all_papers.sort(key=lambda a: a.get("importance", 0), reverse=True)

    logger.info("Groups: JP-biz=%d, GL-biz=%d, JP-tech=%d, GL-tech=%d, papers=%d",
                len(japan_biz), len(global_biz), len(japan_tech), len(global_tech), len(all_papers))

    # --- Step 4: 各セクションのサマリー + must_read を生成 ---
    jp_biz_syn = _synthesize(client, japan_biz, model, temperature,
        _make_synthesis_prompt("国内ビジネス動向", "資金調達、提携、製品発表、政策・規制など国内のビジネス面の動きに焦点。"))
    gl_biz_syn = _synthesize(client, global_biz, model, temperature,
        _make_synthesis_prompt("海外ビジネス動向", "海外の資金調達、M&A、製品発表、市場動向に焦点。", is_english_source=True))
    jp_tech_syn = _synthesize(client, japan_tech, model, temperature,
        _make_synthesis_prompt("国内技術動向", "国内の技術開発、実証実験、導入事例に焦点。"))
    gl_tech_syn = _synthesize(client, global_tech, model, temperature,
        _make_synthesis_prompt("海外技術動向", "海外の技術開発、新手法、ベンチマークに焦点。", is_english_source=True))
    papers_syn = _synthesize(client, all_papers, model, temperature, PAPERS_SYNTHESIS_PROMPT)

    return {
        "japan_biz": {"items": japan_biz, **jp_biz_syn},
        "global_biz": {"items": global_biz, **gl_biz_syn},
        "japan_tech": {"items": japan_tech, **jp_tech_syn},
        "global_tech": {"items": global_tech, **gl_tech_syn},
        "papers": {"items": all_papers, **papers_syn},
    }


def _batch_summarize(
    client: OpenAI, items: list[dict], model: str, max_tokens: int,
    temperature: float, prompt: str, item_key: str, label: str,
) -> list[dict]:
    """バッチ分割して要約."""
    if not items:
        return []
    all_results = []
    batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    logger.info("[%s] %d items -> %d batches", label, len(items), len(batches))
    for idx, batch in enumerate(batches):
        logger.info("[%s] batch %d/%d (%d items)", label, idx + 1, len(batches), len(batch))
        text = _format_articles(batch)
        try:
            resp = _call_llm_with_retry(client, model, prompt, text, max_tokens, temperature)
            content = _extract_json(resp.choices[0].message.content)
            result = json.loads(content)
            all_results.extend(result.get(item_key, []))
        except json.JSONDecodeError:
            logger.error("[%s] Invalid JSON from LLM, using fallback", label)
            all_results.extend(_fallback(batch))
        except Exception:
            logger.error("[%s] LLM call failed", label, exc_info=True)
            all_results.extend(_fallback(batch))
    return all_results


def _synthesize(client: OpenAI, items: list[dict], model: str, temperature: float, prompt: str) -> dict:
    """サマリー + must_read を生成."""
    if not items:
        return {"summary": "", "trends": [], "must_read": []}
    top = items[:30]
    lines = [f"- [{a.get('category', '?')}] {a.get('title', '?')} ({a.get('url', '')}): {a.get('summary', '')}" for a in top]
    user_text = "今週の主要項目:\n" + "\n".join(lines)
    logger.info("Synthesizing %d items", len(top))
    try:
        resp = _call_llm_with_retry(client, model, prompt, user_text, 3072, temperature)
        content = _extract_json(resp.choices[0].message.content)
        return json.loads(content)
    except Exception:
        logger.error("Synthesis failed", exc_info=True)
        return {"summary": "", "trends": [], "must_read": []}


def _call_llm_with_retry(client, model, system_prompt, user_text, max_tokens, temperature, max_retries=3):
    """LLM APIをリトライ付きで呼び出す."""
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_text}],
                max_tokens=max_tokens, temperature=temperature,
            )
        except Exception:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning("LLM call failed (attempt %d/%d), retrying in %ds...",
                               attempt + 1, max_retries, wait)
                time.sleep(wait)
            else:
                raise


def _extract_json(content: str) -> str:
    """LLM出力からJSON部分を抽出する（コードブロック・前後テキスト対応）."""
    content = content.strip()
    # コードブロック内のJSONを抽出
    m = re.search(r'```(?:json)?\s*\n(.*?)\n\s*```', content, re.DOTALL)
    if m:
        return m.group(1).strip()
    # コードブロックなしの場合、最初の { ... } または [ ... ] を抽出
    m = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
    if m:
        return m.group(1).strip()
    return content


def _format_articles(articles: list[dict]) -> str:
    parts = [f"以下の{len(articles)}件を分析してください。\n"]
    for i, a in enumerate(articles, 1):
        parts.append(f"--- {i} ---")
        parts.append(f"タイトル: {a.get('title', '?')}")
        parts.append(f"ソース: {a.get('source', '?')}")
        parts.append(f"URL: {a.get('url', '')}")
        if a.get("authors"):
            parts.append(f"著者: {a['authors']}")
        if a.get("content_snippet"):
            parts.append(f"内容: {a['content_snippet'][:300]}")
        parts.append("")
    return "\n".join(parts)


def _fallback(articles: list[dict]) -> list[dict]:
    return [
        {"title": a.get("title", "?"), "url": a.get("url", ""), "summary": a.get("content_snippet", "")[:200],
         "category": "その他", "article_type": "business", "importance": 3, "source": a.get("source", "?")}
        for a in articles
    ]
