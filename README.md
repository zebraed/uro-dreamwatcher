# Dreamwatcher

WikiWiki.jpのAPIを使用してページの更新を監視し、変更をDiscordに通知するツールです。

## 主な機能

- 指定したページの更新を検知し、差分プレビューをDiscordに投稿
- RecentCreated, RecentChangesの変更を検知し、最近の更新を監視
- 正規表現パターンに一致する新規ページを自動的に監視対象へ追加

## 必須

- Python 3.10 以上
- [WikiWiki.jp](https://wikiwiki.jp) 任意のWikiのAPIキー（API キー ID・シークレット）
- DiscordのWebhook URL

## インストール

```bash
pip install -r requirements.txt
```

## 設定

プロジェクトルートに `.env` ファイルを作成してください。`settings.env.example` をコピーして編集するのが簡単です。

```bash
cp settings.env.example .env
```

| 変数名 | 必須 | 説明 |
|--------|:----:|------|
| `WIKIWIKI_ID` | ✓ | WikiWiki.jp の Wiki ID |
| `WIKIWIKI_URL_BASE` | ✓ | Wiki のベース URL（例: `https://wikiwiki.jp/`） |
| `WIKIWIKI_API_KEY_ID` | ✓ | WikiWiki API キー ID |
| `WIKIWIKI_API_SECRET` | ✓ | WikiWiki API シークレット |
| `DISCORD_WEBHOOK_URL` | ✓ | Discord Webhook URL |
| `WIKIWIKI_PAGE_NAMES` | ✓ | 監視するページ名（カンマ区切り） |
| `WIKIWIKI_AUTO_TRACK_PATTERNS` | | 自動追跡するページ名の正規表現パターン（カンマ区切り） |
| `WIKIWIKI_DIFF_FULL_PAGES` | | 差分の全追加行を表示するページ名（カンマ区切り） |
| `WIKIWIKI_MONITOR_RECENT_CREATED` | | 新規作成ページを監視するか（`true` / `false`、デフォルト: `false`） |
| `STATE_PATH` | | 状態ファイルのパス（デフォルト: `state.json`） |
| `SNAPSHOTS_DIR_PATH` | | スナップショット保存先ディレクトリ（デフォルト: `.snapshots`） |

## 使い方

ローカル環境やクラウドで定期実行することができます。

`.env` を用意したうえで、以下のコマンドで実行します。

```bash
python -m dreamwatcher.main
```

初回実行時は監視ページの初期設定が行われ、Discord に通知が届きます。2回目以降は前回実行時との差分だけが通知されます。

GitHub Actions を使って定期実行することも可能です。

参考: [.github/workflows/dreamwatcher.yml](.github/workflows/dreamwatcher.yml)

## ライセンス

[MIT License](LICENSE)
