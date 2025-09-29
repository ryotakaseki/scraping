
import csv
import os
import logging
from datetime import datetime
from urllib.parse import urljoin
import argparse
import config
import utils
import logging_config
import glob

def _parse_dl_tags(section_div):
    """
    dl, dt, ddタグのセットを解析して辞書を返す
    """
    details = {}
    if section_div:
        for dl in section_div.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt:
                key = dt.text.strip()
                value = " ".join(dd.text.strip().split()) if dd else "N/A"
                details[key] = value
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
                break
        if not heading:
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

    return result

def get_job_details(detail_url, site_config, job_card):
    """
    詳細ページから情報を取得する
    """
    if site_config['BASE_URL'] == "https://xn--pckua2a7gp15o89zb.com":
        # kyujinbox: 一覧カードから基本項目を取得 + 外部詳細ページをヒューリスティックに解析
        details = {}
        for key, target in site_config['EXTRACTION_TARGETS'].items():
            cls = target.get("class")
            if isinstance(cls, str) and " " in cls:
                cls = cls.split()
            elem = job_card.find(target["tag"], class_=cls)
            details[key] = elem.get_text(separator=" ", strip=True) if elem else "N/A"

        # 掲載元（カードに表示されていれば）
        source_elem = job_card.find("div", class_="p-result_source")
        if source_elem:
            details["掲載元"] = source_elem.get_text(separator=" ", strip=True)

        # 外部詳細ページから 仕事内容/対象となる方 を抽出（可能な範囲で）
        soup_ext = utils.get_soup(detail_url)
        if soup_ext:
            try:
                ext_details = _extract_sections_from_external(soup_ext)
                details.update(ext_details)
            except Exception as e:
                logging.warning(f"外部詳細ページの解析に失敗: {e} URL: {detail_url}")
        else:
            logging.info(f"外部詳細ページの取得をスキップ/失敗しました: {detail_url}")

        return details

    soup = utils.get_soup(detail_url)
    if not soup:
        logging.error(f"詳細ページ ({detail_url}) の取得に失敗しました。")
        return {}

    details = {}
    
    for key, target in site_config['EXTRACTION_TARGETS'].items():
        if "tag" in target and "class" in target:
            # 通常のタグとクラスによる抽出
            cls = target.get("class")
            if isinstance(cls, str) and " " in cls:
                cls = cls.split()
            elem = soup.find(target["tag"], class_=cls)
            details[key] = elem.get_text(separator=" ", strip=True) if elem else "N/A"
        elif "div_class" in target:
            # dlタグを解析するセクション
            section_div = soup.find("div", class_=target["div_class"])
            details.update(_parse_dl_tags(section_div))
        else:
            logging.warning(f"不明な抽出ターゲット形式: {key} - {target}")

    return details
import math
import re

    # 省略

def main(site, start_page=1, resume=False):
    """
    求人情報をスクレイピングしてCSVに出力する
    """
    logging_config.setup_logging()
    logging.info(f"--- {site} のスクレイピング処理を開始します ---")

    if site not in config.SITE_CONFIGS:
        logging.error(f"設定ファイルにサイト '{site}' の設定が見つかりません。")
        return

    site_config = config.SITE_CONFIGS[site]
    BASE_URL = site_config["BASE_URL"]
    
    all_job_details = []
    page = start_page
    skip_items = 0

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
                continue # スキップ

            if config.MAX_ITEMS is not None and len(all_job_details) >= config.MAX_ITEMS:
                logging.info(f"最大取得件数({config.MAX_ITEMS}件)に達しました。処理を中断します。")
                break

            #広告を除外
            if "p-ad-item" in job_card.get("class", []):
                continue

            detail_link_tag = job_card.find(site_config["DETAIL_URL_TAG"], class_=site_config["DETAIL_URL_CLASS"])
            if not detail_link_tag or not detail_link_tag.has_attr('href'):
                logging.warning(f"[{i+1}/{len(job_cards)}] 詳細ページへのリンクが見つかりませんでした。この求人カードをスキップします。")
                continue
            
            relative_url = detail_link_tag['href']
            detail_url = urljoin(BASE_URL, relative_url)
            logging.info(f"detail_url: {detail_url}")

            job_details = get_job_details(detail_url, site_config, job_card)
            if job_details:
                # 追跡用に求人URLも保存
                job_details.setdefault("求人URL", detail_url)
                all_job_details.append(job_details)
            else:
                logging.warning(f"[{i+1}/{len(job_cards)}] 詳細ページ ({detail_url}) から求人情報を取得できませんでした。スキップします。")

        if config.MAX_ITEMS is not None and len(all_job_details) >= config.MAX_ITEMS:
            break
        
        # 次のページに行く前にスキップ件数をリセット
        skip_items = 0
        page += 1

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
    parser = argparse.ArgumentParser(description='Webスクレイピングを実行します。')
    parser.add_argument('site', help='スクレイピング対象のサイト名 (config.pyで定義)')
    parser.add_argument('--start-page', type=int, default=1, help='スクレイピングを開始するページ番号')
    parser.add_argument('--resume', action='store_true', help='前回の続きからスクレイピングを再開します')
    args = parser.parse_args()
    main(args.site, args.start_page, args.resume)
