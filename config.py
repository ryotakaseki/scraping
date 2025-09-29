# スクレイピング対象サイトの設定ファイル

# サイト設定を辞書形式で定義
SITE_CONFIGS = {
    "01intern": {
        "BASE_URL": "https://01intern.com",
        "TARGET_URL": "https://01intern.com/job/list.html?jobTypes=1",
        "JOB_CARD_TAG": "section",
        "JOB_CARD_CLASS": "i-job-item",
        "DETAIL_URL_TAG": "a",
        "DETAIL_URL_CLASS": "i-job-btn--arrow",
        "EXTRACTION_TARGETS": {
            "会社名": {"tag": "span", "class": "m-job-titleName"},
            "募集要項": {"div_class": "l-job-requirements"},
            "会社概要": {"div_class": "l-job-profile"},
        },
    },
    "kyujinbox": {
        "BASE_URL": "https://xn--pckua2a7gp15o89zb.com",
        "TARGET_URL": "https://xn--pckua2a7gp15o89zb.com/%E3%82%A4%E3%83%B3%E3%82%B5%E3%82%A4%E3%83%89%E3%82%BB%E3%83%BC%E3%83%AB%E3%82%B9%E3%81%AE%E4%BB%95%E4%BA%8B",
        "JOB_CARD_TAG": "section",
        "JOB_CARD_CLASS": "p-result_card",
        "DETAIL_URL_TAG": "a",
        "DETAIL_URL_CLASS": "p-result_title_link",
        "EXTRACTION_TARGETS": {
            "会社名": {"tag": "p", "class": "p-result_company"},
            "勤務地": {"tag": "li", "class": "p-result_area"},
            "給与": {"tag": "li", "class": "p-result_pay"},
            "雇用形態": {"tag": "li", "class": "p-result_employType"},
            "求人詳細": {"tag": "div", "class": "p-preview_body s-preview-body"}
        },
    },
}

# --- スクレイピング制御設定 (共通) ---
HEADERS = {"User-Agent": "Mozilla/5.0"}
MIN_INTERVAL = 1
MAX_INTERVAL = 5
MAX_ITEMS = 50

# ログ出力レベル (logging モジュール準拠)
LOG_LEVEL = "DEBUG"
