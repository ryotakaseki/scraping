"""メインのスクレイピング処理を定義するモジュール。"""

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
        for dl in section_div.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt:
                key = dt.text.strip()
                value = " ".join(dd.text.strip().split()) if dd else "N/A"
                details[key] = value
                logging.debug(
                    "DLタグ解析 - key=%s value_preview=%s",
                    key,
                    value[:80] + ("..." if len(value) > 80 else ""),
                )
            else:
                logging.debug("DLタグ解析 - dt要素が見つからないdlタグをスキップしました。")
    else:
        logging.debug("DLタグ解析 - 対象のセクションが見つかりませんでした。")
    return details

def _extract_sections_from_external(soup):
    """
    外部サイトの求人詳細ページから、代表的な見出しに基づいて
    『仕事内容』『対象となる方』をヒューリスティックに抽出する。
    """
    result = {}

    def norm(text):
        return " ".join(text.split()) if text else ""

    # 見出し候補と抽出対象
    targets = {
        "仕事内容": ["仕事内容", "業務内容", "仕事の内容", "業務詳細", "業務内容・仕事の特色"],
        "対象となる方": ["対象となる方", "応募資格", "求める人物像", "求める人材", "応募要件", "必須条件"],
    }

    # 探索する見出しタグ
    heading_tags = ["h1", "h2", "h3", "h4", "dt", "th", "strong", "p", "div"]

    for out_key, keywords in targets.items():
        if out_key in result:
            continue
        # 見出しに該当する要素を探索
        heading = None
        for tag in heading_tags:
            heading = soup.find(tag, string=lambda s: s and any(k in s for k in keywords))
            if heading:
                logging.debug("外部詳細解析 - '%s' の見出し候補を '%s' タグで検出", out_key, tag)
                break
        if not heading:
            logging.debug("外部詳細解析 - '%s' に該当する見出しが見つかりませんでした。", out_key)
            continue

        # 見出しの直後のコンテンツっぽい要素を探索
        # 段落/リスト/汎用ブロックの順で探す
        content = None
        for finder in [
            lambda h: h.find_next(["p", "ul", "ol", "section"]),
            lambda h: h.find_parent().find_next(["p", "ul", "ol", "section"]) if h.find_parent() else None,
            lambda h: h.find_next("div"),
        ]:
            content = finder(heading)
            if content and norm(content.get_text(strip=True)):
                break

        if content:
            text = content.get_text(separator=" ", strip=True)
            result[out_key] = norm(text)
            logging.debug(
                "外部詳細解析 - '%s' の内容を抽出 (プレビュー: %s)",
                out_key,
                text[:80] + ("..." if len(text) > 80 else ""),
            )
        else:
            logging.debug("外部詳細解析 - '%s' の内容となる要素を特定できませんでした。", out_key)

    return result

def get_job_details(detail_url, site_config, job_card) -> Dict[str, str]:
    """詳細ページ、もしくは一覧ページから求人情報を抽出する。"""

    logging.debug("求人詳細の取得を開始 detail_url=%s", detail_url)
    if site_config['BASE_URL'] == "https://xn--pckua2a7gp15o89zb.com":
        # kyujinbox: 一覧カードから基本項目を取得 + 外部詳細ページをヒューリスティックに解析
        details: Dict[str, str] = {}
        for key, target in site_config['EXTRACTION_TARGETS'].items():
            cls = target.get("class")
            if isinstance(cls, str) and " " in cls:
                cls = cls.split()
            elem = job_card.find(target["tag"], class_=cls)
            details[key] = elem.get_text(separator=" ", strip=True) if elem else "N/A"
            logging.debug(
                "求人カード解析 (kyujinbox) - key=%s value_preview=%s",
                key,
                details[key][:80] + ("..." if len(details[key]) > 80 else ""),
            )

        # 掲載元（カードに表示されていれば）
        source_elem = job_card.find("div", class_="p-result_source")
        if source_elem:
            details["掲載元"] = source_elem.get_text(separator=" ", strip=True)
            logging.debug(
                "求人カード解析 (kyujinbox) - 掲載元 value_preview=%s",
                details["掲載元"][:80] + ("..." if len(details["掲載元"]) > 80 else ""),
            )

        # 外部詳細ページから 仕事内容/対象となる方 を抽出（可能な範囲で）
        soup_ext = utils.get_soup(detail_url)
        if soup_ext:
            try:
                ext_details = _extract_sections_from_external(soup_ext)
                details.update(ext_details)
                logging.debug(
                    "求人カード解析 (kyujinbox) - 外部詳細抽出結果 keys=%s",
                    list(ext_details.keys()),
                )
            except Exception as e:
                logging.warning(f"外部詳細ページの解析に失敗: {e} URL: {detail_url}")
        else:
            logging.info(f"外部詳細ページの取得をスキップ/失敗しました: {detail_url}")

        logging.debug(
            "求人カード解析 (kyujinbox) - 抽出完了 keys=%s",
            sorted(details.keys()),
        )
        return details

    soup = utils.get_soup(detail_url)
    if not soup:
        logging.error(f"詳細ページ ({detail_url}) の取得に失敗しました。")
        return {}

    details: Dict[str, str] = {}

    for key, target in site_config['EXTRACTION_TARGETS'].items():
        if "tag" in target and "class" in target:
            # 通常のタグとクラスによる抽出
            cls = target.get("class")
            if isinstance(cls, str) and " " in cls:
                cls = cls.split()
            elem = soup.find(target["tag"], class_=cls)
            details[key] = elem.get_text(separator=" ", strip=True) if elem else "N/A"
            logging.debug(
                "求人詳細解析 - key=%s value_preview=%s",
                key,
                details[key][:80] + ("..." if len(details[key]) > 80 else ""),
            )
        elif "div_class" in target:
            # dlタグを解析するセクション
            section_div = soup.find("div", class_=target["div_class"])
            details.update(_parse_dl_tags(section_div))
        else:
            logging.warning(f"不明な抽出ターゲット形式: {key} - {target}")

    logging.debug(
        "求人詳細解析 - 抽出完了 keys=%s",
        sorted(details.keys()),
    )
    return details

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

    if site not in config.SITE_CONFIGS:
        logging.error(f"設定ファイルにサイト '{site}' の設定が見つかりません。")
        return

    site_config = config.SITE_CONFIGS[site]
    logging.debug("サイト設定: %s", site_config)
    BASE_URL = site_config["BASE_URL"]

    all_job_details: List[Dict[str, str]] = []
    page = start_page
    skip_items = 0

    if config.MAX_ITEMS is not None:
        logging.info("最大取得件数は %s 件に設定されています。", config.MAX_ITEMS)

    if resume:
        logging.info("再開モードで実行します。最新のCSVファイルを探しています...")
        output_dir = "output"
        list_of_files = glob.glob(os.path.join(output_dir, f'{site}_job_listings_*.csv'))
        if list_of_files:
            latest_file = max(list_of_files, key=os.path.getctime)
            logging.info(f"最新のファイル: {latest_file}")
            with open(latest_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # ヘッダーを除いてカウント
                scraped_count = sum(1 for row in reader) - 1
            logging.info(f"取得済みの件数: {scraped_count}")
            
            items_per_page = 30 # サイトに合わせて調整
            page = (scraped_count // items_per_page) + 1
            skip_items = scraped_count % items_per_page
            logging.info(f"{page}ページ目の{skip_items}件目から再開します。")
        else:
            logging.info("再開できるCSVファイルが見つかりませんでした。最初から開始します。")
            logging.debug("再開モード - outputディレクトリ: %s", os.path.abspath(output_dir))

    # 最初のページで総件数を取得
    first_page_url = site_config["TARGET_URL"]
    logging.info(f"求人一覧の最初のページ ({first_page_url}) を取得します。")
    list_soup = utils.get_soup(first_page_url)
    if not list_soup:
        logging.error(f"{first_page_url} の取得に失敗しました。処理を終了します。")
        return

    # 総件数を取得して、最終ページを計算
    if site == 'kyujinbox':
        total_items_text_element = list_soup.find("div", class_="p-resultArea_num")
    else:
        total_items_text_element = list_soup.find("p", class_="i-recruitment-title")

    if not total_items_text_element:
        logging.error("総件数の取得に失敗しました。処理を終了します。")
        return
    
    total_items_text = total_items_text_element.text.strip()
    match = re.search(r'(\d{1,3}(,\d{3})*)', total_items_text)
    if not match:
        logging.error("総件数の取得に失敗しました。処理を終了します。")
        return
        
    total_items = int(match.group(1).replace(',', ''))
    logging.info(f"総求人件数: {total_items}件")
    # 1ページあたりの件数（サイトに合わせて調整）
    items_per_page = 30 
    last_page = math.ceil(total_items / items_per_page)
    logging.info(f"最終ページ: {last_page}")

    while True:
        if page > last_page:
            logging.info("最終ページまで到達しました。ループを終了します。")
            break

        logging.info(f"--- {page}ページ目の処理を開始します ---")

        # 2ページ目以降はURLにpageパラメータを追加
        if page == 1:
            target_url = first_page_url
        else:
            if site == 'kyujinbox':
                target_url = f"{site_config['TARGET_URL']}?pg={page}"
            else:
                target_url = f'{site_config["TARGET_URL"]}&page={page}'

        logging.info(f"求人一覧ページ ({target_url}) の取得を試行します。")
        logging.debug("現在の進捗: 収集済み=%d件 ページ=%d/%d", len(all_job_details), page, last_page)
        list_soup = utils.get_soup(target_url)
        if not list_soup:
            logging.error(f"{target_url} の取得に失敗しました。このページの処理をスキップします。")
            page += 1
            continue

        job_cards = list_soup.find_all(site_config["JOB_CARD_TAG"], class_=site_config["JOB_CARD_CLASS"])
        if not job_cards:
            logging.warning(f"ページ {page} で求人カードが見つかりませんでした。処理を終了します。")
            break
            
        logging.info(f"ページ {page} で求人カードを {len(job_cards)} 件検出しました。")

        for i, job_card in enumerate(job_cards):
            if i < skip_items:
                logging.debug(
                    "再開モード - ページ%sの先頭から%s件をスキップ中 (現在%s件目)",
                    page,
                    skip_items,
                    i + 1,
                )
                continue # スキップ

            if config.MAX_ITEMS is not None and len(all_job_details) >= config.MAX_ITEMS:
                logging.info(f"最大取得件数({config.MAX_ITEMS}件)に達しました。処理を中断します。")
                break

            #広告を除外
            if "p-ad-item" in job_card.get("class", []):
                logging.debug("広告カードを検出しスキップしました index=%d", i)
                continue

            detail_link_tag = job_card.find(site_config["DETAIL_URL_TAG"], class_=site_config["DETAIL_URL_CLASS"])
            if not detail_link_tag or not detail_link_tag.has_attr('href'):
                logging.warning(f"[{i+1}/{len(job_cards)}] 詳細ページへのリンクが見つかりませんでした。この求人カードをスキップします。")
                continue

            relative_url = detail_link_tag['href']
            detail_url = urljoin(BASE_URL, relative_url)
            logging.info(f"detail_url: {detail_url}")
            logging.debug(
                "求人カード処理 - ページ=%d index=%d/%d 相対URL=%s",
                page,
                i + 1,
                len(job_cards),
                relative_url,
            )

            job_details = get_job_details(detail_url, site_config, job_card)
            if job_details:
                # 追跡用に求人URLも保存
                job_details.setdefault("求人URL", detail_url)
                all_job_details.append(job_details)
                logging.debug(
                    "求人カード処理 - 抽出成功 件数=%d 累計=%d",
                    len(job_details),
                    len(all_job_details),
                )
            else:
                logging.warning(f"[{i+1}/{len(job_cards)}] 詳細ページ ({detail_url}) から求人情報を取得できませんでした。スキップします。")

        if config.MAX_ITEMS is not None and len(all_job_details) >= config.MAX_ITEMS:
            logging.debug("最大取得件数に達したためページループを終了します。")
            break

        # 次のページに行く前にスキップ件数をリセット
        skip_items = 0
        page += 1
        logging.info("ページ処理完了。現在の累計取得件数: %d", len(all_job_details))

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
    fieldnames = sorted(list(fieldnames_set))
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval="N/A")
            writer.writeheader()
            writer.writerows(all_job_details)
        logging.info(f"--- スクレイピング処理が完了しました。結果は {filepath} に保存されました ---")
    except IOError as e:
        logging.error(f"CSVファイルへの書き込みに失敗しました: {e}")


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
