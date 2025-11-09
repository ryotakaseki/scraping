# 求人情報スクレイピングツール

`main.py` を実行して、`config.py` に定義された複数の求人サイトから求人情報を取得し、CSV に蓄積する Python スクリプトです。サイトごとの抽出ルールは `scrapers.py` に整理されており、共通ロジックが `BaseScraper` クラスにまとまっています。

---

## 対応サイト

- `01intern` : 01intern（長期インターン）
- `kyujinbox` : 求人BOX（インサイドセールス）
- `kyujinbox_sales` : 求人BOX（営業職）
- `infra` : インフラ長期インターン
- `renew-career` : Renew Career

これらのキーはそのままコマンドライン引数の `site` に指定します。新しいサイトを追加したい場合は `config.py` と `scrapers.py` に設定・クラスを追加します。

---

## 主な機能

- **マルチサイト対応**: `config.SITE_CONFIGS` に登録されたサイトを自由に切り替えて実行可能。
- **再開モード**: `--resume` で既存 CSV を参照し、途中ページから再開。
- **CSV 追記**: `output/{site}_job_listings.csv` にヘッダー付きで追記保存。
- **ログ出力**: `log/` 配下に実行ごとのログファイルを生成し、`--log-level` で詳細度を調整可能。
- **取得件数制限**: `--limit` で最大取得件数を制御。
- **リトライ付き HTTP アクセス**: `tls-client` ベースのセッションで安定した取得を実現し、アクセス間隔をランダム化。

---

## セットアップ

1. リポジトリを取得
   ```bash
   git clone <repository-url>
   cd script
   ```
2. 仮想環境を作成（任意）
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. 依存パッケージをインストール
   ```bash
   pip install requests beautifulsoup4 tls-client
   ```

`tls-client` がインストールされていないとスクリプトは起動時に `ModuleNotFoundError` を送出します。

---

## 設定ファイルの概要

`config.py` にサイトごとの設定を記述します。

- `BASE_URL` / `TARGET_URL`: 一覧ページの URL。
- `ITEMS_PER_PAGE`: 1 ページあたりの求人件数。再開時のページ計算に使用。
- `JOB_CARD_TAG` / `JOB_CARD_CLASS`: 一覧で求人カードを特定するためのタグ・クラス。
- `EXTRACTION_TARGETS`: 詳細ページで抽出すべき要素の指定（サイトによる）。
- `REQUIRED_FIELDS`: CSV に必ず含めたい列。欠損時は `N/A` が補われます。
- `FIELD_ORDER`: CSV の列順を固定したい場合に指定。
- `EXTERNAL_SECTION_RULES`: kyujinbox 系サイトで詳細ページを解析する際の見出しマッチング辞書。

サイト追加時は `scrapers.py` に該当クラスを実装し、`SCRAPER_CLASSES` にマッピングを挿入してください。

---

## 使い方

```text
usage: main.py [-h] [--start-page N] [--resume] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--limit N] site

求人サイトから情報をスクレイピングするツールです。

positional arguments:
  site                  スクレイピング対象のサイト名

optional arguments:
  -h, --help            ヘルプを表示して終了
  --start-page N        開始ページ番号（--resume と併用時は無視）
  --resume              既存 CSV から取得件数を読み取り再開
  --log-level LEVEL     ログ出力レベル（デフォルト: config.LOG_LEVEL）
  --limit N             取得する最大件数（指定なしの場合は config.MAX_ITEMS）
```

### 実行例

```bash
# 01intern を最初から取得
python3 main.py 01intern

# kyujinbox を途中再開し、詳細ログを出力
python3 main.py kyujinbox --resume --log-level DEBUG

# infra を 100 件まで取得
python3 main.py infra --limit 100
```

---

## 出力物

- **CSV**: `output/{site}_job_listings.csv` に追記形式で保存（UTF-8 BOM 付き）。
- **ログファイル**: `log/scraping_YYYYMMDD_HHMMSS.log` として出力。

`--resume` を利用する場合は CSV のヘッダー行が存在する状態である必要があります。

---

## トラブルシューティング

- `ModuleNotFoundError: No module named 'tls_client'`
  - `pip install tls-client` を実行してください。
- SSL ライブラリに関する警告（LibreSSL など）
  - 実行環境の OpenSSL バージョンによっては `urllib3` から警告が出ることがあります。動作に問題がある場合は Python を OpenSSL 対応ビルドへ更新してください。

---

## 注意事項

- スクレイピング前に対象サイトの利用規約や robots.txt を必ず確認し、各サイトのルールに従ってください。
- 本ツール使用によって生じた損害について開発者は責任を負いません。自己責任でご利用ください。
- Web サイトの構造が変更された場合、抽出ロジックの更新が必要になることがあります。
