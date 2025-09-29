# 求人情報スクレイピングツール

`main.py` を実行して、`config.py` で定義された求人サイトから情報を取得し、CSV とログに保存するスクリプトです。

## 主な機能

- サイトごとに一覧ページから求人カードを収集し、詳細情報を抽出
- `config.SITE_CONFIGS` に複数サイト（例: `01intern`, `kyujinbox`）を定義して切り替え可能
- スクレイピング再開機能（`--resume`）で途中まで取得済みの CSV から処理を再開
- 取得した全求人情報を `output/{site}_job_listings_YYYYMMDD_HHMMSS.csv` に保存
- ログを `log/scraping_YYYYMMDD_HHMMSS.log` に保存し、処理状況やエラーを記録
- ランダムな待機時間（`config.MIN_INTERVAL`〜`config.MAX_INTERVAL` 秒）でアクセス間隔を調整

## セットアップ

1. **リポジトリのクローン**
   ```bash
   git clone <repository-url>
   cd script
   ```

2. **Python 仮想環境の作成と有効化（推奨）**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **依存ライブラリのインストール**
   ```bash
   pip install requests beautifulsoup4
   ```

## 使い方

```bash
python main.py <site> [--start-page N] [--resume]
```

- `site`: `config.SITE_CONFIGS` に定義されたキーを指定します（例: `python main.py kyujinbox`）。
- `--start-page`: スクレイピング開始ページ（既定値 1）。
- `--resume`: 最新の CSV から件数を算出して再開します。

処理が完了すると `output/` に CSV が生成されます。失敗や警告は `log/` のログファイルを確認してください。

## 設定のカスタマイズ

`config.py` で以下を調整できます。

- `SITE_CONFIGS`: 取得対象サイトごとの URL、HTML セレクタ、抽出項目
- `HEADERS`: リクエストヘッダ（User-Agent など）
- `MIN_INTERVAL`, `MAX_INTERVAL`: アクセス間隔のランダム待機時間（秒）
- `MAX_ITEMS`: 最大取得件数（`None` にすると制限なし）

サイトを追加したい場合は、新しいキーを `SITE_CONFIGS` に定義し、一覧ページや求人詳細から必要な項目を指定してください。
