"""メインのスクレイピング処理を定義するモジュール。"""

from __future__ import annotations

import argparse
import csv
import glob
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Type

import config
import logging_config
from scrapers import BaseScraper, InternScraper, KyujinboxScraper

# サイト名とスクレイパークラスのマッピング
SCRAPER_CLASSES: Dict[str, Type[BaseScraper]] = {
    "01intern": InternScraper,
    "kyujinbox": KyujinboxScraper,
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

def save_to_csv(site: str, all_job_details: List[Dict[str, str]], required_fields: List[str]) -> None:
    """スクレイピング結果をCSVファイルに保存する。"""
    if not all_job_details:
        logging.warning("取得できた求人情報がありませんでした。CSVは作成されません。")
        return

    logging.info(f"合計 {len(all_job_details)} 件の求人情報を取得しました。CSVファイルに保存します。")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    base_filename = f"{site}_job_listings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, base_filename)
    logging.info(f"スクレイピング結果を {filepath} に保存しています。")

    fieldnames_set = set()
    for details in all_job_details:
        fieldnames_set.update(details.keys())

    fieldnames = required_fields + sorted(list(fieldnames_set - set(required_fields)))

    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval="N/A")
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
) -> None:
    """求人情報をスクレイピングしてCSVに出力する。"""
    logging_config.setup_logging(
        log_level=log_level,
        default_level=getattr(config, "LOG_LEVEL", None),
    )
    logging.info("--- %s のスクレイピング処理を開始します ---", site)

    scraper = get_scraper(site)
    if not scraper:
        return

    scraped_count = 0
    if resume:
        logging.info("再開モードで実行します。最新のCSVファイルを探しています...")
        output_dir = "output"
        list_of_files = glob.glob(os.path.join(output_dir, f'{site}_job_listings_*.csv'))
        if list_of_files:
            latest_file = max(list_of_files, key=os.path.getctime)
            logging.info(f"最新のファイル: {latest_file}")
            with open(latest_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                scraped_count = sum(1 for _ in reader) - 1  # ヘッダー分を引く
            
            items_per_page = scraper.site_config.get("ITEMS_PER_PAGE", 30)
            start_page = (scraped_count // items_per_page) + 1
            logging.info(f"取得済みの件数: {scraped_count}。{start_page}ページ目から再開します。")
        else:
            logging.info("再開できるCSVファイルが見つかりませんでした。最初から開始します。")

    all_job_details = scraper.scrape(
        start_page=start_page,
        scraped_count=scraped_count,
        max_items=config.MAX_ITEMS
    )

    save_to_csv(site, all_job_details, scraper.site_config.get("REQUIRED_FIELDS", []))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webスクレイピングを実行します。")
    parser.add_argument("site", help="スクレイピング対象のサイト名 (config.pyで定義)")
    parser.add_argument("--start-page", type=int, default=1, help="スクレイピングを開始するページ番号")
    parser.add_argument("--resume", action="store_true", help="前回の続きからスクレイピングを再開します")
    parser.add_argument(
        "--log-level",
        default=None,
        help="ログ出力レベル (例: DEBUG, INFO, WARNING)",
    )
    args = parser.parse_args()
    main(args.site, args.start_page, args.resume, args.log_level)