# 求人情報スクレイピングツール

このプロジェクトは、指定されたWebサイトから求人情報をスクレイピングし、CSVファイルとして出力するPythonスクリプトです。

## 機能

- 求人一覧ページから各求人の詳細ページURLを収集
- 各詳細ページから情報を抽出（会社名、給与、勤務地など）
- 抽出した全求人情報を一つのCSVファイルにまとめて出力

## セットアップ方法

1.  **リポジトリをクローンします**
    ```bash
    git clone <repository-url>
    cd script
    ```

2.  **Python仮想環境の作成と有効化**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **必要なライブラリをインストールします**
    ```bash
    pip install -r requirements.txt
    ```

## 実行方法

以下のコマンドでスクリプトを実行します。

```bash
python main.py
```

実行が完了すると、`output`ディレクトリ内に`job_listings_YYYYMMDD_HHMMSS.csv`という名前で結果が出力されます。

## 設定

スクレイピング対象のURLや、HTML要素のセレクタ（タグやクラス名）は`config.py`ファイルで変更できます。
