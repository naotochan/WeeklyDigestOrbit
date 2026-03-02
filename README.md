# WeeklyDigestOrbit

Robotics / Physical AI / Embodied AI 領域の週次ニュースダイジェストを自動生成し、GitHub Pages で公開する。自分のためのニュース収集サイトです．

pagesをご覧いただければどんな内容かイメージいただけます．

Raspberry Pi 上の systemd timer で定期実行。LAN 内の LM Studio でAI要約を生成する。

## 構成

```
[RSS / arXiv / Scraping] → [Pi: Collector] → [LM Studio API] → [HTML Generator] → [GitHub Pages]
                                                (lfm2-24b)                              git push
```

## 5セクション構成

| セクション | 内容 |
|-----------|------|
| 国内ビジネス動向 | 資金調達・提携・製品発表・政策 |
| 海外ビジネス動向 | グローバル市場のビジネスニュース |
| 国内技術動向 | 技術開発・実証実験・導入事例 |
| 海外技術動向 | 新手法・ベンチマーク・技術ブレイクスルー |
| Research Frontier | 注目論文（arXiv cs.RO / cs.AI） |

各セクションにはサマリー・トレンドタグ・ハイライト（詳細解説付き）・全記事一覧を含む。HTML / Markdown 形式で出力。

## セットアップ

```bash
# 依存インストール
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 設定ファイル
cp config/.env.example config/.env
# config/.env を編集: LM Studio の接続先を設定
```

### config/.env　例

```
LLM_BASE_URL=http://192.168.1.100:1234/v1
LLM_MODEL=liquid/lfm2-24b-a2b
LLM_API_KEY=lm-studio
```

## 実行

```bash
# ドライラン（HTML生成のみ、push なし）
python src/main.py --dry-run

# 本番実行（HTML生成 + git push）
python src/main.py
```

生成されたダイジェストは `docs/index.html`（HTML）と `docs/{week_id}.md`（Markdown）に出力される。

### LM Studio 推奨設定

| 設定 | 推奨値 |
|------|--------|
| Context Length | 32K以上（128K可） |
| Max Tokens | 4096以上 |

## Raspberry Pi へのデプロイ

```bash
# サービスファイルをコピー
sudo cp deploy/weekly-digest.service /etc/systemd/system/
sudo cp deploy/weekly-digest.timer /etc/systemd/system/

# 有効化
sudo systemctl enable weekly-digest.timer
sudo systemctl start weekly-digest.timer

# 手動実行テスト
sudo systemctl start weekly-digest.service
```

## ディレクトリ構成

```
WeeklyDigestOrbit/
├── config/
│   ├── .env                  # 接続情報（gitignore）
│   ├── .env.example
│   ├── feeds.yaml            # RSSフィード一覧（キーワードフィルタ付き）
│   ├── scraping_targets.yaml # スクレイピング対象
│   └── settings.yaml         # 収集・LLM・出力設定
├── src/
│   ├── collectors/
│   │   ├── rss.py            # RSS収集
│   │   ├── arxiv_collector.py # arXiv API収集
│   │   └── scraper.py        # Webスクレイピング
│   ├── summarizer.py         # LM Studio API 要約・分類
│   ├── generator.py          # Jinja2 静的HTML生成
│   └── main.py               # エントリーポイント
├── templates/
│   └── index.html.j2         # ダッシュボードテンプレート
├── docs/                     # GitHub Pages 公開ディレクトリ
├── deploy/                   # systemd timer/service
└── requirements.txt
```

## 技術スタック

- Python 3.10+
- feedparser / arxiv / BeautifulSoup4
- OpenAI互換API（LM Studio）
- Jinja2 + Tailwind CSS（CDN）
- GitHub Pages

## License

[MIT License](LICENSE)
