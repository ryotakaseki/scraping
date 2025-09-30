# 🌟 求人情報スクレイピングツール

`main.py` を実行して、`config.py` で定義された求人サイトから求人情報を取得し、CSV & ログに保存できるPythonスクリプトです。

---

## ✨ 特徴

- **マルチサイト対応**  
  サイトごとに一覧ページから求人カードを収集し、詳細情報を自動抽出  
  `config.SITE_CONFIGS` に複数サイト（例: `01intern`, `kyujinbox`）を定義して切り替え可能
- **途中再開機能**  
  `--resume` オプションで、取得済みCSVから処理を再開
- **自動保存**  
  取得した求人情報を `output/{site}_job_listings_YYYYMMDD_HHMMSS.csv` に保存
- **詳細なログ出力**  
  ログを `log/scraping_YYYYMMDD_HHMMSS.log` に記録し、進捗やエラーを追跡可能
- **アクセス間隔調整**  
  ランダムな待機時間（`config.MIN_INTERVAL`〜`config.MAX_INTERVAL`秒）でサーバー負荷を軽減

---

## ⚙️ セットアップ

1. **リポジトリのクローン**
   ```bash
   git clone <repository-url>
   cd script
   ```

2. **Python仮想環境の作成（推奨）**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **依存ライブラリのインストール**
   ```bash
   pip install requests beautifulsoup4
   ```

---

## 🚀 使い方

```bash
python main.py <site> [--start-page N] [--resume] [--log-level LEVEL]
```

**引数:**

- `<site>` : `config.SITE_CONFIGS` に定義されたキーを指定（例: `python main.py kyujinbox`）
- `--start-page N` : スクレイピング開始ページ番号（デフォルト: 1）
- `--resume` : 既存のCSVから件数を算出して途中から再開
- `--log-level LEVEL` : ログ出力レベルを指定（例: `DEBUG`, `INFO`, `WARNING` など）

**例:**

```bash
# kyujinboxサイトを1ページ目からINFOレベルで取得
python main.py kyujinbox --log-level INFO

# 01internサイトを5ページ目からDEBUGレベルで再開
python main.py 01intern --start-page 5 --resume --log-level DEBUG
```

**出力:**  
処理が完了すると `output/` にCSVが生成されます。失敗や警告は `log/` ディレクトリのログファイルをご確認ください。

---

## 📦 実行例

```bash
# 01internサイトを通常実行（デフォルト: INFOログ）
python main.py 01intern

# kyujinboxサイトを途中再開＆詳細なDEBUGログで実行
python main.py kyujinbox --resume --log-level DEBUG
```

出力ファイル例:
```
output/kyujinbox_job_listings_20240101_120000.csv
log/scraping_20240101_120000.log
```

---

## 🛠️ 設定のカスタマイズ

`config.py` で以下を柔軟に調整できます。

| 設定項目         | 内容                                                         |
|------------------|--------------------------------------------------------------|
| `SITE_CONFIGS`   | サイトごとのURL, HTMLセレクタ, 抽出対象項目                  |
| `HEADERS`        | リクエストヘッダ（User-Agent等）                             |
| `MIN_INTERVAL`   | アクセス間隔の最小待機秒数                                   |
| `MAX_INTERVAL`   | アクセス間隔の最大待機秒数                                   |
| `MAX_ITEMS`      | 最大取得件数（`None`で制限なし）                             |
| `LOG_LEVEL`      | デフォルトのログレベル（`INFO`, `DEBUG`など）                |

### サイト追加も簡単！
新しいサイトを追加する場合は、`SITE_CONFIGS` に新しいキーを定義し、一覧ページや求人詳細から必要な項目を指定してください。

---
