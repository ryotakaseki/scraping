"メインのスクレイピング処理を定義するモジュール。"

from __future__ import annotations

import argparse
import csv
import glob
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Type

import config
import logging_config
from scrapers import BaseScraper, InternScraper, KyujinboxScraper, InfraScraper, RenewCareerScraper

# サイト名とスクレイパークラスのマッピング
SCRAPER_CLASSES: Dict[str, Type[BaseScraper]] = {
    "01intern": InternScraper,
    "kyujinbox": KyujinboxScraper,
    "infra": InfraScraper,
    "kyujinbox_sales": KyujinboxScraper,
    "renew-career": RenewCareerScraper,
}

def get_scraper(site_name: str) -> Optional[BaseScraper]:
    """サイト名に対応するスクレイパーインスタンスを返す。"""
    if site_name not in config.SITE_CONFIGS:
        logging.error(f"設定ファイルにサイト '{site_name}' の設定が見つかりません。")
        return None

    if site_name not in SCRAPER_CLASSES:
        logging.error(f"サイト '{site_name}' に対応するスクレイパークラスが見つかりません。")
        return None

    site_config = config.SITE_CONFIGS[site_name]
    scraper_class = SCRAPER_CLASSES[site_name]
    return scraper_class(site_name, site_config)

def save_to_csv(site: str, all_job_details: List[Dict[str, str]], required_fields: List[str], field_order: Optional[List[str]] = None) -> None:
    """スクレイピング結果をCSVファイルに保存する。"""
    if not all_job_details:
        logging.warning("取得できた求人情報がありませんでした。CSVは更新されません。")
        return

    logging.info(f"合計 {len(all_job_details)} 件の新しい求人情報を取得しました。CSVファイルに追記します。")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, f"{site}_job_listings.csv")
    logging.info(f"スクレイピング結果を {filepath} に保存（追記）しています。")

    fieldnames_set = set()
    for details in all_job_details:
        fieldnames_set.update(details.keys())

    if field_order:
        # FIELD_ORDER が指定されている場合、その順序に従う
        final_fieldnames = [field for field in field_order if field in fieldnames_set]
        # FIELD_ORDER に含まれないが、データには存在する列を後ろに追加
        remaining_fields = sorted(list(fieldnames_set - set(final_fieldnames)))
        final_fieldnames.extend(remaining_fields)
    else:
        # 従来どおりのロジック
        fieldnames = required_fields + sorted(list(fieldnames_set - set(required_fields)))
        final_fieldnames = fieldnames

    file_exists = os.path.exists(filepath)

    try:
        with open(filepath, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=final_fieldnames, restval="N/A")
            if not file_exists:
                writer.writeheader()
            writer.writerows(all_job_details)
        logging.info(f"--- スクレイピング処理が完了しました。結果は {filepath} に保存されました ---")
    except IOError as e:
        logging.error(f"CSVファイルへの書き込みに失敗しました: {e}")

def main(
    site: str,
    start_page: int = 1,
    resume: bool = False,
    log_level: Optional[str] = None,
    limit: Optional[int] = None,
) -> None:
    """求人情報をスクレイピングしてCSVに出力する。"""
    logging_config.setup_logging(
        log_level=log_level,
        default_level=getattr(config, "LOG_LEVEL", None),
    )
    
    start_time = time.time()
    logging.info("--- %s のスクレイピング処理を開始します ---", site)

    scraper = get_scraper(site)
    if not scraper:
        return

    scraped_count = 0
    if resume:
        logging.info("再開モードで実行します。既存のCSVファイルを探しています...")
        output_dir = "output"
        resume_file = os.path.join(output_dir, f'{site}_job_listings.csv')

        print(f"CWD: {os.getcwd()}")
        print(f"Checking for file: {os.path.abspath(resume_file)}")

        if os.path.exists(resume_file):
            logging.info(f"既存のファイル: {resume_file}")
            try:
                with open(resume_file, 'r', newline='', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)  # ヘッダー行を読み飛ばす
                    if header:
                        # データ行の数を正確にカウント
                        scraped_count = sum(1 for row in reader if any(row))
                    else:
                        scraped_count = 0 # ファイルが空かヘッダーのみ
            except (csv.Error, UnicodeDecodeError) as e:
                logging.error(f"CSVファイル {resume_file} の読み込みエラー: {e}。ファイルが破損している可能性があるため、処理を中断します。")
                return
            except Exception as e:
                logging.error(f"再開処理中に予期せぬエラーが発生しました: {e}。処理を中断します。")
                return

            if scraped_count > 0:
                items_per_page = scraper.site_config.get("ITEMS_PER_PAGE", 30)
                if items_per_page > 0:
                    start_page = (scraped_count // items_per_page) + 1
                else:
                    start_page = 1
                logging.info(f"取得済みの件数: {scraped_count}。{start_page}ページ目から再開します。")
            else:
                logging.info("有効なデータが見つからなかったため、最初から開始します。")
        else:
            logging.info("再開できるCSVファイルが見つかりませんでした。最初から開始します。")

    max_items_to_scrape = limit if limit is not None else config.MAX_ITEMS

    all_job_details = scraper.scrape(
        start_page=start_page,
        scraped_count=scraped_count,
        max_items=max_items_to_scrape
    )

    save_to_csv(
        site,
        all_job_details,
        scraper.site_config.get("REQUIRED_FIELDS", []),
        scraper.site_config.get("FIELD_ORDER")
    )

    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"全処理が完了しました。所要時間: {duration // 60:.0f}分 {duration % 60:.2f}秒")


if __name__ == "__main__":
    available_sites = list(config.SITE_CONFIGS.keys())

    parser = argparse.ArgumentParser(
        description="求人サイトから情報をスクレイピングするツールです。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "site",
        choices=available_sites,
        help=(
            "スクレイピング対象のサイト名を指定します。\n"
            f"利用可能なサイト: {', '.join(available_sites)}"
        )
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        metavar="N",
        help="スクレイピングを開始するページ番号を指定します。(デフォルト: 1)\n--resumeオプションと同時に使用すると、このオプションは無視されます。"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "処理を再開します。outputフォルダ内の既存のCSVファイルから\n"
            "取得済みの件数を読み取り、その続きからスクレイピングを開始します。\n"
            "このオプションを使用すると、--start-pageの値は上書きされます。"
        )
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="コンソールとログファイルの出力レベルを指定します。(デフォルト: INFO)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="スクレイピングする最大件数を指定します。(デフォルト: config.MAX_ITEMS)"
    )
    args = parser.parse_args()
    main(args.site, args.start_page, args.resume, args.log_level, args.limit)
