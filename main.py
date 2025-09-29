"""
メインのスクレイピング処理を定義するモジュール。
"""

from __future__ import annotations

import argparse
import csv
import glob
import logging
import math
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import config
import logging_config
import utils


def _parse_dl_tags(section_div) -> Dict[str, str]:
    """dlタグ配下の情報を辞書形式に整形する。"""

    details: Dict[str, str] = {}
    if section_div:
        for dl_tag in section_div.find_all("dl"):
            dt = dl_tag.find("dt")
            dd = dl_tag.find("dd")
            if dt:
                key = dt.text.strip()
                value = " ".join(dd.text.strip().split()) if dd else "N/A"
                details[key] = value
                logging.debug("dlタグから抽出: %s=%s", key, value)
    return details


def get_job_details(detail_url, site_config, job_card) -> Dict[str, str]:
    """詳細ページ、もしくは一覧ページから求人情報を抽出する。"""

    logging.debug("詳細ページ (%s) の情報抽出を開始します。", detail_url)

    if site_config["BASE_URL"] == "https://xn--pckua2a7gp15o89zb.com":
        # kyujinbox の場合は一覧ページから必要情報を収集
        details: Dict[str, str] = {}
        for key, target in site_config["EXTRACTION_TARGETS"].items():
            elem = job_card.find(target["tag"], class_=target["class"])
            details[key] = elem.text.strip() if elem else "N/A"
            logging.debug("一覧ページから抽出: %s=%s", key, details[key])
        return details

    soup = utils.get_soup(detail_url)
    if not soup:
        logging.error("詳細ページ (%s) の取得に失敗しました。", detail_url)
        return {}

    details: Dict[str, str] = {}
    logging.debug("抽出対象: %s", site_config["EXTRACTION_TARGETS"])

    for key, target in site_config["EXTRACTION_TARGETS"].items():
        if "tag" in target and "class" in target:
            elem = soup.find(target["tag"], class_=target["class"])
            details[key] = elem.text.strip() if elem else "N/A"
            logging.debug("詳細ページから抽出: %s=%s", key, details[key])
        elif "div_class" in target:
            section_div = soup.find("div", class_=target["div_class"])
            parsed = _parse_dl_tags(section_div)
            details.update(parsed)
        else:
            logging.warning("不明な抽出ターゲット形式: %s - %s", key, target)

    logging.debug("詳細ページ (%s) の抽出結果: %s", detail_url, details)
    return details


def main(site: str, start_page: int = 1, resume: bool = False, log_level: Optional[str] = None) -> None:
    """求人情報をスクレイピングしてCSVに出力する。"""

    logging_config.setup_logging(log_level or config.LOG_LEVEL)
    logging.info("--- %s のスクレイピング処理を開始します ---", site)

    if site not in config.SITE_CONFIGS:
        logging.error("設定ファイルにサイト '%s' の設定が見つかりません。", site)
        return

    site_config = config.SITE_CONFIGS[site]
    base_url = site_config["BASE_URL"]
    logging.debug("サイト設定: %s", site_config)

    all_job_details: List[Dict[str, str]] = []
    page = start_page
    skip_items = 0

    if resume:
        logging.info("再開モードで実行します。最新のCSVファイルを探しています...")
        output_dir = "output"
        list_of_files = glob.glob(os.path.join(output_dir, f"{site}_job_listings_*.csv"))
        if list_of_files:
            latest_file = max(list_of_files, key=os.path.getctime)
            logging.info("最新のファイル: %s", latest_file)
            with open(latest_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                scraped_count = sum(1 for _ in reader) - 1
            logging.info("取得済みの件数: %s", scraped_count)

            items_per_page = 30  # サイトに合わせて調整
            page = (scraped_count // items_per_page) + 1
            skip_items = scraped_count % items_per_page
            logging.info("%sページ目の%s件目から再開します。", page, skip_items)
            logging.debug(
                "再開設定: items_per_page=%s, start_page=%s, skip_items=%s",
                items_per_page,
                page,
                skip_items,
            )
        else:
            logging.info("再開できるCSVファイルが見つかりませんでした。最初から開始します。")

    first_page_url = site_config["TARGET_URL"]
    logging.info("求人一覧の最初のページ (%s) を取得します。", first_page_url)
    list_soup = utils.get_soup(first_page_url)
    if not list_soup:
        logging.error("%s の取得に失敗しました。処理を終了します。", first_page_url)
        return

    if site == "kyujinbox":
        total_items_text_element = list_soup.find("div", class_="p-resultArea_num")
    else:
        total_items_text_element = list_soup.find("p", class_="i-recruitment-title")

    if not total_items_text_element:
        logging.error("総件数の取得に失敗しました。処理を終了します。")
        return

    total_items_text = total_items_text_element.text.strip()
    match = re.search(r"(\d{1,3}(,\d{3})*)", total_items_text)
    if not match:
        logging.error("総件数の取得に失敗しました。処理を終了します。")
        return

    total_items = int(match.group(1).replace(",", ""))
    logging.info("総求人件数: %s件", total_items)

    items_per_page = 30
    last_page = math.ceil(total_items / items_per_page)
    logging.info("最終ページ: %s", last_page)

    while True:
        if config.MAX_ITEMS is not None and len(all_job_details) >= config.MAX_ITEMS:
            logging.info("最大取得件数(%s件)に達しました。処理を中断します。", config.MAX_ITEMS)
            break

        if page > last_page:
            logging.info("最終ページまで到達しました。ループを終了します。")
            break

        logging.info("--- %sページ目の処理を開始します ---", page)

        if page == 1:
            target_url = first_page_url
        else:
            if site == "kyujinbox":
                target_url = f"{site_config['TARGET_URL']}?pg={page}"
            else:
                target_url = f"{site_config['TARGET_URL']}&page={page}"

        logging.info("求人一覧ページ (%s) の取得を試行します。", target_url)
        list_soup = utils.get_soup(target_url)
        if not list_soup:
            logging.error("%s の取得に失敗しました。このページの処理をスキップします。", target_url)
            page += 1
            continue

        job_cards = list_soup.find_all(
            site_config["JOB_CARD_TAG"], class_=site_config["JOB_CARD_CLASS"]
        )
        if not job_cards:
            logging.warning("ページ %s で求人カードが見つかりませんでした。処理を終了します。", page)
            break

        logging.info("ページ %s で求人カードを %s 件検出しました。", page, len(job_cards))

        for i, job_card in enumerate(job_cards):
            if i < skip_items:
                logging.debug("[%s/%s] 再開処理のためスキップします。", i + 1, len(job_cards))
                continue

            if config.MAX_ITEMS is not None and len(all_job_details) >= config.MAX_ITEMS:
                logging.info("最大取得件数(%s件)に達しました。処理を中断します。", config.MAX_ITEMS)
                break

            if "p-ad-item" in job_card.get("class", []):
                logging.debug("[%s/%s] 広告カードのためスキップします。", i + 1, len(job_cards))
                continue

            detail_link_tag = job_card.find(
                site_config["DETAIL_URL_TAG"], class_=site_config["DETAIL_URL_CLASS"]
            )
            if not detail_link_tag or not detail_link_tag.has_attr("href"):
                logging.warning(
                    "[%s/%s] 詳細ページへのリンクが見つかりませんでした。この求人カードをスキップします。",
                    i + 1,
                    len(job_cards),
                )
                continue

            relative_url = detail_link_tag["href"]
            detail_url = urljoin(base_url, relative_url)
            logging.info("detail_url: %s", detail_url)

            job_details = get_job_details(detail_url, site_config, job_card)
            if job_details:
                all_job_details.append(job_details)
                logging.debug(
                    "[%s/%s] 抽出した求人情報: %s",
                    i + 1,
                    len(job_cards),
                    job_details,
                )
            else:
                logging.warning(
                    "[%s/%s] 詳細ページ (%s) から求人情報を取得できませんでした。スキップします。",
                    i + 1,
                    len(job_cards),
                    detail_url,
                )

        skip_items = 0
        page += 1

    if not all_job_details:
        logging.warning("取得できた求人情報がありませんでした。CSVは作成されません。")
        return

    logging.info("合計 %s 件の求人情報を取得しました。CSVファイルに保存します。", len(all_job_details))

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    base_filename = f"{site}_job_listings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, base_filename)
    logging.info("スクレイピング結果を %s に保存しています。", filepath)

    fieldnames_set = set()
    for details in all_job_details:
        fieldnames_set.update(details.keys())
    fieldnames = sorted(list(fieldnames_set))
    logging.debug("CSV 出力項目: %s", fieldnames)

    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval="N/A")
            writer.writeheader()
            writer.writerows(all_job_details)
        logging.info("--- スクレイピング処理が完了しました。結果は %s に保存されました ---", filepath)
    except IOError as e:
        logging.error("CSVファイルへの書き込みに失敗しました: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webスクレイピングを実行します。")
    parser.add_argument("site", help="スクレイピング対象のサイト名 (config.pyで定義)")
    parser.add_argument("--start-page", type=int, default=1, help="スクレイピングを開始するページ番号")
    parser.add_argument("--resume", action="store_true", help="前回の続きからスクレイピングを再開します")
    parser.add_argument(
        "--log-level",
        default=config.LOG_LEVEL,
        help="ログ出力レベル (例: DEBUG, INFO, WARNING)",
    )
    args = parser.parse_args()
    main(args.site, args.start_page, args.resume, args.log_level)
