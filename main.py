"メインのスクレイピング処理を定義するモジュール。"

from __future__ import annotations

import argparse
import csv
import logging
import os
import time
from typing import Dict, List, Optional, Set, Tuple, Type

import config
import logging_config
from scrapers import BaseScraper, InternScraper, KyujinboxScraper, InfraScraper, RenewCareerScraper, SokudanScraper, SukiikiScraper

# サイト名とスクレイパークラスのマッピング
SCRAPER_CLASSES: Dict[str, Type[BaseScraper]] = {
    "01intern": InternScraper,
    "kyujinbox": KyujinboxScraper,
    "infra": InfraScraper,
    "kyujinbox_sales": KyujinboxScraper,
    "renew-career": RenewCareerScraper,
    "sokudan": SokudanScraper,
    "sukiiki": SukiikiScraper,
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

def _is_valid_fieldname(name: Optional[str]) -> bool:
    """CSVの列名として扱う値かを判定する。"""
    if not name:
        return False
    stripped = name.strip()
    if not stripped or stripped.upper() == "N/A":
        return False
    if "://" in stripped:
        return False
    return True


def _normalize_row(row: Dict[str, str], fieldnames: List[str]) -> Dict[str, str]:
    """指定した列名に沿って行データを整形し、改行をスペースに置換する。"""
    normalized = {}
    for field in fieldnames:
        val = row.get(field, "N/A")
        if isinstance(val, str):
            # 改行をスペースに置き換え
            val = val.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        normalized[field] = val
    return normalized


def _load_resume_state(site: str, items_per_page: int) -> Tuple[int, int]:
    """既存の出力ファイルから再開位置を計算する。"""
    output_dir = "output"
    candidates = [
        (os.path.join(output_dir, f"{site}_job_listings.tsv"), "\t", "TSV"),
        (os.path.join(output_dir, f"{site}_job_listings.csv"), ",", "CSV"),
    ]

    for resume_file, delimiter, file_label in candidates:
        if not os.path.exists(resume_file):
            continue

        logging.info("再開モード: 既存の%sファイルを使用します path=%s", file_label, resume_file)
        try:
            with open(resume_file, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                if not reader.fieldnames:
                    logging.info("%sファイルにヘッダーがないため、最初から開始します。", file_label)
                    return 1, 0

                scraped_count = 0
                for row in reader:
                    if not row:
                        continue
                    if any((value or "").strip() for value in row.values()):
                        scraped_count += 1
        except (csv.Error, UnicodeDecodeError) as e:
            logging.error(
                "%sファイル %s の読み込みエラー: %s。ファイルが破損している可能性があるため、処理を中断します。",
                file_label,
                resume_file,
                e,
            )
            raise
        except Exception as e:
            logging.error(
                "再開処理中に予期せぬエラーが発生しました file=%s error=%s",
                resume_file,
                e,
            )
            raise

        if scraped_count <= 0:
            logging.info("有効なデータが見つからなかったため、最初から開始します。")
            return 1, 0

        if items_per_page <= 0:
            logging.warning(
                "ITEMS_PER_PAGE が不正なため再開開始ページを計算できません。1ページ目から続行します count=%d",
                scraped_count,
            )
            return 1, scraped_count

        start_page = (scraped_count // items_per_page) + 1
        logging.info("取得済み件数 %d 件を検出しました。%d ページ目から再開します。", scraped_count, start_page)
        return start_page, scraped_count

    logging.info("再開できるTSV/CSVファイルが見つかりませんでした。最初から開始します。")
    return 1, 0


def save_to_csv(site: str, all_job_details: List[Dict[str, str]], required_fields: List[str], field_order: Optional[List[str]] = None) -> None:
    """スクレイピング結果をTSVファイルに保存する。"""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{site}_job_listings.tsv")

    file_exists = os.path.exists(filepath)
    if not all_job_details and not file_exists:
        logging.warning("取得できた求人情報がありませんでした。TSVは更新されません。")
        return

    valid_existing_rows: List[Dict[str, str]] = []
    field_candidates: Set[str] = set()

    if file_exists:
        try:
            with open(filepath, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    if not row:
                        continue
                    sanitized = {k: v for k, v in row.items() if _is_valid_fieldname(k)}
                    if not sanitized:
                        continue
                    field_candidates.update(sanitized.keys())
                    url_val = sanitized.get("求人URL", "")
                    if url_val.startswith("http"):
                        valid_existing_rows.append(sanitized)
                    else:
                        logging.debug("URLが欠落している既存行を破棄しました row=%s", sanitized)
        except Exception as e:
            logging.error("既存TSVの読み込みに失敗したため、既存データは無視されます: %s", e)

    new_rows: List[Dict[str, str]] = []
    for details in all_job_details:
        sanitized = {k: v for k, v in details.items() if _is_valid_fieldname(k)}
        if not sanitized:
            continue
        field_candidates.update(sanitized.keys())
        new_rows.append(sanitized)

    if not new_rows and not valid_existing_rows:
        logging.warning("出力対象となる有効なデータが存在しませんでした。TSVは更新されません。")
        return

    preferred_order: List[str] = []
    if field_order:
        preferred_order.extend(field_order)
    elif required_fields:
        preferred_order.extend(required_fields)

    # 重複排除しつつ order を確定
    seen = set()
    final_fieldnames: List[str] = []
    for field in preferred_order:
        if _is_valid_fieldname(field) and field not in seen:
            seen.add(field)
            final_fieldnames.append(field)

    additional_fields = sorted(
        field for field in field_candidates
        if field not in seen and _is_valid_fieldname(field)
    )
    final_fieldnames.extend(additional_fields)

    if not final_fieldnames:
        fallback_fields = []
        fallback_seen = set()
        for row in valid_existing_rows:
            for key in row.keys():
                if _is_valid_fieldname(key) and key not in fallback_seen:
                    fallback_seen.add(key)
                    fallback_fields.append(key)
        if not fallback_fields:
            logging.error("確定できるTSVの列名がありません。処理を中断します。")
            return
        final_fieldnames = fallback_fields

    merged_rows = [
        _normalize_row(row, final_fieldnames)
        for row in (valid_existing_rows + new_rows)
    ]

    deduped_rows: List[Dict[str, str]] = []
    row_index_by_key: Dict[str, int] = {}
    fallback_index_by_key: Dict[tuple, int] = {}

    def _build_key(row: Dict[str, str]) -> Optional[str]:
        """求人URLを識別子として使用できる場合はその値を返す。"""
        url_value = row.get("求人URL", "")
        if not url_value:
            return None
        trimmed = url_value.strip()
        if not trimmed or trimmed.upper() == "N/A":
            return None
        return trimmed

    for row in merged_rows:
        url_key = _build_key(row)
        if url_key:
            existing_index = row_index_by_key.get(url_key)
            if existing_index is not None:
                deduped_rows[existing_index] = row
            else:
                row_index_by_key[url_key] = len(deduped_rows)
                deduped_rows.append(row)
            continue

        # 求人URLが存在しない場合は列全体の値で判定する
        row_tuple = tuple(row.get(field, "N/A") for field in final_fieldnames)
        existing_index = fallback_index_by_key.get(row_tuple)
        if existing_index is not None:
            deduped_rows[existing_index] = row
        else:
            fallback_index_by_key[row_tuple] = len(deduped_rows)
            deduped_rows.append(row)

    duplicates_removed = len(merged_rows) - len(deduped_rows)
    if duplicates_removed > 0:
        logging.info("重複データを %d 件削除しました。", duplicates_removed)

    try:
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=final_fieldnames, restval="N/A", delimiter='\t')
            writer.writeheader()
            writer.writerows(deduped_rows)
        logging.info(f"--- TSV {filepath} を更新しました。合計 {len(deduped_rows)} 件のデータ。 ---")
    except IOError as e:
        logging.error(f"TSVファイルへの書き込みに失敗しました: {e}")

def main(
    site: str,
    start_page: int = 1,
    resume: bool = False,
    log_level: Optional[str] = None,
    limit: Optional[int] = None,
) -> None:
    """求人情報をスクレイピングしてTSVに出力する。"""
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
        try:
            start_page, scraped_count = _load_resume_state(
                site,
                scraper.site_config.get("ITEMS_PER_PAGE", 30),
            )
        except Exception:
            return

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
            "処理を再開します。outputフォルダ内の既存のTSVファイル\n"
            "(旧CSVファイルがある場合はそちらも対象) から\n"
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
