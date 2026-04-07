# スクレイピング対象サイトの設定ファイル

# サイト設定を辞書形式で定義
SITE_CONFIGS = {
    "01intern": {
        "BASE_URL": "https://01intern.com",
        "TARGET_URL": "https://01intern.com/job/list.html?jobTypes=1",
        "ITEMS_PER_PAGE": 35,
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
        "ITEMS_PER_PAGE": 25,
        "JOB_CARD_TAG": "section",
        "JOB_CARD_CLASS": "p-result_card",
        "DETAIL_URL_TAG": "a",
        "DETAIL_URL_CLASS": "p-result_title_link",
        "HEADERS": {
            "referer": "https://xn--pckua2a7gp15o89zb.com/",
        },
        "EXTRACTION_TARGETS": {
            "会社名": {"tag": "p", "class": "p-result_company"},
            "勤務地": {"tag": "li", "class": "p-result_area"},
            "給与": {"tag": "li", "class": "p-result_pay"},
            "雇用形態": {"tag": "li", "class": "p-result_employType"},
            "求人詳細": {
                "tag": "p",
                "class": "p-result_lines s-result_switch_snipet is-hide",
            },
        },
        "REQUIRED_FIELDS": [
            "会社名",
            "勤務地",
            "給与",
            "雇用形態",
            "求人詳細",
            "仕事内容",
            "対象となる方",
            "掲載元",
            "求人URL",
        ],
        # 外部サイト解析の見出しルール
        "EXTERNAL_SECTION_RULES": {
            "仕事内容": [
                "仕事内容",
                "業務内容",
                "仕事の内容",
                "業務詳細",
                "業務内容・仕事の特色",
            ],
            "対象となる方": [
                "対象となる方",
                "応募資格",
                "求める人物像",
                "求める人材",
                "応募要件",
                "必須条件",
            ],
        },
    },
    "infra": {
        "BASE_URL": "https://www.in-fra.jp",
        "TARGET_URL": "https://www.in-fra.jp/long-internships?occupation%5B0%5D=3&prefecture%5B0%5D=13&area%5B0%5D=1&area%5B1%5D=2&area%5B2%5D=3&area%5B3%5D=4&area%5B4%5D=5&area%5B5%5D=12&order=recommended",
        "ITEMS_PER_PAGE": 50,
        "JOB_CARD_TAG": "a",
        "JOB_CARD_CLASS": "js-card-link",
        "REQUIRED_FIELDS": ["会社名", "タイトル"],
        "FIELD_ORDER": [
            "会社名",
            "場所",
            "アクセス",
            "交通費",
            "奨学金",
            "給与",
            "タイトル",
            "このインターンですること",
            "求人URL",
        ],
    },
    "kyujinbox_sales": {
        "BASE_URL": "https://xn--pckua2a7gp15o89zb.com",
        "TARGET_URL": "https://xn--pckua2a7gp15o89zb.com/%E5%96%B6%E6%A5%AD%E3%81%AE%E4%BB%95%E4%BA%8B-%E6%9D%B1%E4%BA%AC%E9%83%BD?e=4",
        "ITEMS_PER_PAGE": 25,
        "JOB_CARD_TAG": "section",
        "JOB_CARD_CLASS": "p-result_card",
        "DETAIL_URL_TAG": "a",
        "DETAIL_URL_CLASS": "p-result_title_link",
        "HEADERS": {
            "referer": "https://xn--pckua2a7gp15o89zb.com/",
        },
        "EXTRACTION_TARGETS": {
            "会社名": {"tag": "p", "class": "p-result_company"},
            "勤務地": {"tag": "li", "class": "p-result_area"},
            "給与": {"tag": "li", "class": "p-result_pay"},
            "雇用形態": {"tag": "li", "class": "p-result_employType"},
            "求人詳細": {
                "tag": "p",
                "class": "p-result_lines s-result_switch_snipet is-hide",
            },
        },
        "REQUIRED_FIELDS": [
            "会社名",
            "勤務地",
            "給与",
            "雇用形態",
            "求人詳細",
            "仕事内容",
            "対象となる方",
            "掲載元",
            "求人URL",
        ],
        "EXTERNAL_SECTION_RULES": {
            "仕事内容": [
                "仕事内容",
                "業務内容",
                "仕事の内容",
                "業務詳細",
                "業務内容・仕事の特色",
            ],
            "対象となる方": [
                "対象となる方",
                "応募資格",
                "求める人物像",
                "求める人材",
                "応募要件",
                "必須条件",
            ],
        },
    },
    "renew-career": {
        "BASE_URL": "https://renew-career.com",
        "TARGET_URL": "https://renew-career.com/search?keyword=&occupation_type%5B%5D=2&sort=",
        "ITEMS_PER_PAGE": 20,
        "JOB_CARD_TAG": "div",
        "JOB_CARD_CLASS": "relative.mb-4.mx-3.md\\:mx-0.md\\:p-3.border-2.border-gray-100.rounded-lg.group.hover\\:bg-gray-50.transition-colors",
        "DETAIL_URL_TAG": "a",
        "REQUIRED_FIELDS": ["タイトル", "会社名", "求人URL", "勤務地", "職種", "給与", "勤務時間", "アクセス", "特徴"],
        "FIELD_ORDER": ["会社名", "タイトル", "勤務地", "職種", "給与", "勤務時間", "アクセス", "特徴", "求人URL"],
    },
    "sokudan": {
        "BASE_URL": "https://sokudan.work",
        "TARGET_URL": "https://sokudan.work/top/projects/professions/sales?search_project%5Bprofession_ids%5D%5B%5D=105",
        "API_BASE_URL": "https://sokudan.work/api/v2",
        "LOGIN_URL": "https://sokudan.work/login",
        "SESSION_COOKIE_ENV": "SOKUDAN_SESSION_COOKIE",
        "EMAIL_ENV": "SOKUDAN_EMAIL",
        "PASSWORD_ENV": "SOKUDAN_PASSWORD",
        "ITEMS_PER_PAGE": 40,
        "REQUIRED_FIELDS": ["会社名", "タイトル", "月収下限", "月収上限", "稼働日数", "リモート可否", "契約形態", "求人URL"],
        "FIELD_ORDER": [
            "会社名", "タイトル", "月収下限", "月収上限", "稼働日数", "リモート可否", "契約形態", "副業制限", "勤務地", 
            "電話番号", "メールアドレス", "必須スキル", "歓迎スキル", "求める人物像", "特徴", "仕事内容", "応募後の流れ", "求人URL"
        ],
    },
    "sukiiki": {
        "BASE_URL": "https://suki-iki.mynavi.jp",
        "TARGET_URL": "https://suki-iki.mynavi.jp/job/?sm=true&s=06",
        "API_BASE_URL": "https://suki-iki.mynavi.jp/public-api-v1",
        "SEARCH_PATH": "/jobs",
        "ITEMS_PER_PAGE": 20,
        "HEADERS": {
            "referer": "https://suki-iki.mynavi.jp/job/?sm=true&s=06",
            "origin": "https://suki-iki.mynavi.jp",
        },
        "SEARCH_PAYLOAD": {
            "jobCategories": [],
            "skills": [],
            "workStyles": [],
            "locations": [],
            "minUnitPrice": {"name": "", "code": None},
            "maxUnitPrice": {"name": "", "code": None},
            "workingTimes": [],
            "frequenciesOfGoingToOffice": [],
            "features": [],
            "skillMatchEnabled": True,
            "onlyNewJobs": False,
            "onlyHiringJobs": False,
            "keyword": None,
            "skillKeyword": None,
            "companyId": 0,
            "page": 1,
            "sort": "06",
            "pageSize": 20,
            "preview": False,
        },
        "REQUIRED_FIELDS": [
            "会社名",
            "タイトル",
            "仕事カテゴリ",
            "働き方",
            "想定報酬",
            "稼働時間",
            "エリア",
            "仕事内容",
            "求人URL",
        ],
        "FIELD_ORDER": [
            "会社名",
            "タイトル",
            "仕事カテゴリ",
            "職種詳細",
            "働き方",
            "想定報酬",
            "稼働時間",
            "エリア",
            "住所",
            "出社頻度",
            "契約期間",
            "契約形態",
            "特徴",
            "必須スキル",
            "歓迎スキル",
            "仕事内容",
            "会社紹介",
            "公開日",
            "募集終了日",
            "求人URL",
        ],
    },
}

# --- スクレイピング制御設定 (共通) ---
HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-language": "ja,en-US;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
}
MIN_INTERVAL = 3
MAX_INTERVAL = 10
MAX_ITEMS = 200

# ログ出力のデフォルトレベル
LOG_LEVEL = "INFO"
