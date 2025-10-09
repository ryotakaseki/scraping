# 🌟 求人情報スクレイピングツール

`main.py` を実行して、`config.py` で定義された求人サイトから求人情報を取得し、CSVファイルに保存・追記できるPythonスクリプトです。

---

## ✨ 特徴

- **マルチサイト対応**: `config.py` に定義された複数サイトのスクレイピングに対応。
- **途中再開機能**: `--resume` オプションで、前回の続きから処理を再開。
- **追記保存**: データを `output/{サイト名}_job_listings.csv` という固定ファイルに追記していくため、データが失われません。
- **安定性**: ネットワークエラー時に自動でリトライする機能と、文字化けを防止するエンコーディング設定を搭載。
- **サーバー負荷軽減**: アクセスごとにランダムな待機時間を設けています。
 

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

コマンドは `python3 main.py --help` で確認できます。

```bash
usage: main.py [-h] [--start-page N] [--resume] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] site

求人サイトから情報をスクレイピングするツールです。

positional arguments:
  site                  スクレイピング対象のサイト名を指定します。
                        利用可能なサイト: 01intern, kyujinbox

options:
  -h, --help            show this help message and exit
  --start-page N        スクレイピングを開始するページ番号を指定します。(デフォルト: 1)
                        --resumeオプションと同時に使用すると、このオプションは無視されます。
  --resume              処理を再開します。outputフォルダ内の既存のCSVファイルから
                        取得済みの件数を読み取り、その続きからスクレイピングを開始します。
                        このオプションを使用すると、--start-pageの値は上書きされます。
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        コンソールとログファイルの出力レベルを指定します。(デフォルト: INFO)

```

### 実行例

```bash
# 01internサイトを最初から実行
python3 main.py 01intern

# kyujinboxサイトを前回の続きから再開（詳細ログ付き）
python3 main.py kyujinbox --resume --log-level DEBUG
```

---

## 📄 出力

- **求人データ**: `output/` ディレクトリに `_job_listings.csv` という名前でサイトごとに作成されます。
  - 例: `output/kyujinbox_job_listings.csv`
- **ログ**: `log/` ディレクトリに実行ごとのログファイルが作成されます。
  - 例: `log/scraping_20251001_120000.log`

---



---

## ⚠️ ご注意（免責事項）

- **利用規約の確認**: スクレイピングを実行する前に、対象サイトの**利用規約**や**robots.txt**を必ず確認し、その指示に従ってください。サイトによってはスクレイピングが禁止されている場合があります。
- **自己責任で利用**: 本ツールを使用したことによるいかなる損害についても、作成者は責任を負いません。常識の範囲内で、自己責任でご利用ください。
- **仕様変更への対応**: ウェブサイトの仕様変更により、スクリプトが正常に動作しなくなる可能性があります。
