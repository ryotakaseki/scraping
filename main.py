import csv
import os
import logging
from datetime import datetime
from urllib.parse import urljoin
import config
import utils
import logging_config

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

def get_job_details(detail_url):
    """
    詳細ページから情報を取得する
    """
    soup = utils.get_soup(detail_url)
    if not soup:
        logging.error(f"詳細ページ ({detail_url}) の取得に失敗しました。")
        return {}

    details = {}
    
    for key, target in config.EXTRACTION_TARGETS.items():
        if "tag" in target and "class" in target:
            # 通常のタグとクラスによる抽出
            elem = soup.find(target["tag"], class_=target["class"])
            details[key] = elem.text.strip() if elem else "N/A"
        elif "div_class" in target:
            # dlタグを解析するセクション
            section_div = soup.find("div", class_=target["div_class"])
            details.update(_parse_dl_tags(section_div))
        else:
            logging.warning(f"不明な抽出ターゲット形式: {key} - {target}")

    return details

def main():
    """
    求人情報をスクレイピングしてCSVに出力する
    """
    logging_config.setup_logging()
    logging.info("--- スクレイピング処理を開始します ---")

    BASE_URL = "https://01intern.com"
    
    logging.info(f"求人一覧ページ ({config.TARGET_URL}) の取得を試行します。")
    list_soup = utils.get_soup(config.TARGET_URL)
    if not list_soup:
        logging.error(f"{config.TARGET_URL} の取得に失敗しました。処理を終了します。")
        return

    job_cards = list_soup.find_all(config.JOB_CARD_TAG, class_=config.JOB_CARD_CLASS)
    if not job_cards:
        logging.warning("求人カードが見つかりませんでした。処理を終了します。")
        return
        
    logging.info(f"求人カードを {len(job_cards)} 件検出しました。")
    all_job_details = []
    
    for i, job_card in enumerate(job_cards):
        if config.MAX_ITEMS is not None and i >= config.MAX_ITEMS:
            logging.info(f"最大取得件数({config.MAX_ITEMS}件)に達しました。処理を中断します。")
            break

        detail_link_tag = job_card.find(config.DETAIL_URL_TAG, class_=config.DETAIL_URL_CLASS)
        if not detail_link_tag or not detail_link_tag.has_attr('href'):
            logging.warning(f"[{i+1}/{len(job_cards)}] 詳細ページへのリンクが見つかりませんでした。この求人カードをスキップします。")
            continue
        
        relative_url = detail_link_tag['href']
        detail_url = urljoin(BASE_URL, relative_url)
        logging.info(f"[{i+1}/{len(job_cards)}] 詳細ページ ({detail_url}) の情報を取得中...")

        job_details = get_job_details(detail_url)
        if job_details:
            all_job_details.append(job_details)
        else:
            logging.warning(f"[{i+1}/{len(job_cards)}] 詳細ページ ({detail_url}) から求人情報を取得できませんでした。スキップします。")

    if not all_job_details:
        logging.warning("取得できた求人情報がありませんでした。CSVは作成されません。")
        return

    logging.info(f"合計 {len(all_job_details)} 件の求人情報を取得しました。CSVファイルに保存します。")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    base_filename = f"job_listings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, base_filename)
    logging.info(f"スクレイピング結果を {filepath} に保存しています。")

    fieldnames_set = set()
    for details in all_job_details:
        fieldnames_set.update(details.keys())
    fieldnames = sorted(list(fieldnames_set))
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval="N/A")
            writer.writeheader()
            writer.writerows(all_job_details)
        logging.info(f"--- スクレイピング処理が完了しました。結果は {filepath} に保存されました ---")
    except IOError as e:
        logging.error(f"CSVファイルへの書き込みに失敗しました: {e}")
if __name__ == "__main__":
    main()