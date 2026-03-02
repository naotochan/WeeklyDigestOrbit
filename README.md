# WeeklyDigestOrbit

Robotics / Physical AI / Embodied AI 領域の週次ニュースダイジェストを自動生成し、GitHub Pages で公開する。

Raspberry Pi 上の systemd timer で毎週月曜に実行。LAN 内の LM Studio API でAI要約を生成する。

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

各セクションにはサマリー・トレンドタグ・「これだけは見とけ」（詳細解説付き）・全記事一覧を含む。

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

### config/.env

```
LLM_BASE_URL=http://192.168.1.100:1234/v1
LLM_MODEL=liquid/lfm2-24b-a2b
```

## 実行

```bash
# ドライラン（HTML生成のみ、push なし）
python src/main.py --dry-run

# 本番実行（HTML生成 + git push）
python src/main.py
```

生成されたダイジェストは `docs/index.html` に出力される。

## Raspberry Pi へのデプロイ

```bash
# サービスファイルをコピー
sudo cp deploy/weekly-digest.service /etc/systemd/system/weekly-digest@.service
sudo cp deploy/weekly-digest.timer /etc/systemd/system/weekly-digest.timer

# 有効化（pi ユーザーで実行）
sudo systemctl enable weekly-digest@pi.timer
sudo systemctl start weekly-digest@pi.timer

# 手動実行テスト
sudo systemctl start weekly-digest@pi.service
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
