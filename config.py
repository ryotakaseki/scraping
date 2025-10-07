# スクレイピング対象サイトの設定ファイル

# サイト設定を辞書形式で定義
SITE_CONFIGS = {
    "01intern": {
        "BASE_URL": "https://01intern.com",
        "TARGET_URL": "https://01intern.com/job/list.html?jobTypes=1",
        "ITEMS_PER_PAGE": 30,
        "JOB_CARD_TAG": "section",
        "JOB_CARD_CLASS": "i-job-item",
        "DETAIL_URL_TAG": "a",
        "DETAIL_URL_CLASS": "i-job-btn--arrow",
        "EXTRACTION_TARGETS": {
            "会社名": {"tag": "span", "class": "m-job-titleName"},
            "募集要項": {"div_class": "l-job-requirements"},
            "会社概要": {"div_class": "l-job-profile"},
        },
        # 任意: CSVに常に含めたい列（不足時はN/A）
        "REQUIRED_FIELDS": ["会社名", "募集要項", "会社概要"],
    },
    "kyujinbox": {
        "BASE_URL": "https://xn--pckua2a7gp15o89zb.com",
        "TARGET_URL": "https://xn--pckua2a7gp15o89zb.com/%E3%82%A4%E3%83%B3%E3%82%B5%E3%82%A4%E3%83%89%E3%82%BB%E3%83%BC%E3%83%AB%E3%82%B9%E3%81%AE%E4%BB%95%E4%BA%8B",
        "ITEMS_PER_PAGE": 30,
        "JOB_CARD_TAG": "section",
        "JOB_CARD_CLASS": "p-result_card",
        "DETAIL_URL_TAG": "a",
        "DETAIL_URL_CLASS": "p-result_title_link",
        "EXTRACTION_TARGETS": {
            "会社名": {"tag": "p", "class": "p-result_company"},
            "勤務地": {"tag": "li", "class": "p-result_area"},
            "給与": {"tag": "li", "class": "p-result_pay"},
            "雇用形態": {"tag": "li", "class": "p-result_employType"},
            "求人詳細": {"tag": "p", "class": "p-result_lines s-result_switch_snipet is-hide"}
        },
        "REQUIRED_FIELDS": [
            "会社名", "勤務地", "給与", "雇用形態",
            "求人詳細", "仕事内容", "対象となる方", "掲載元", "求人URL"
        ],
        # 外部サイト解析の見出しルール
        "EXTERNAL_SECTION_RULES": {
            "仕事内容": ["仕事内容", "業務内容", "仕事の内容", "業務詳細", "業務内容・仕事の特色"],
            "対象となる方": ["対象となる方", "応募資格", "求める人物像", "求める人材", "応募要件", "必須条件"],
        },
    },
}

# --- スクレイピング制御設定 (共通) ---
HEADERS = {"User-Agent": "Mozilla/5.0"}
MIN_INTERVAL = 3
MAX_INTERVAL = 10
MAX_ITEMS = 200

# ログ出力のデフォルトレベル
LOG_LEVEL = "INFO"
