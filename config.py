# スクレイピング対象サイトの設定ファイル

# 情報を取得したいページのURL
TARGET_URL = "https://01intern.com/job/list.html?jobTypes=1"

# ヘッダー情報
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- 一覧ページのセレクタ設定 ---
# 各求人情報を含む要素のタグ名
JOB_CARD_TAG = "section"
# 各求人情報を含む要素のクラス名
JOB_CARD_CLASS = "i-job-item"

# 詳細ページへのリンクのタグ名
DETAIL_URL_TAG = "a"
# 詳細ページへのリンクのクラス名
DETAIL_URL_CLASS = "i-job-btn--arrow"

# --- 詳細ページの抽出対象設定 ---
EXTRACTION_TARGETS = {
    "会社名": {"tag": "span", "class": "m-job-titleName"},
    "募集要項": {"div_class": "l-job-requirements"},
    "会社概要": {"div_class": "l-job-profile"},
    # 将来的に追加する項目はここに定義
    # "電話番号": {"tag": "span", "class": "phone-number"},
    # "住所": {"tag": "p", "class": "address"},
}

# --- スクレイピング制御設定 ---
# サーバー負荷軽減のためのアクセス間隔（秒）
MIN_INTERVAL = 1
MAX_INTERVAL = 3
# 最大取得件数（Noneなら制限なし）
MAX_ITEMS = 100
