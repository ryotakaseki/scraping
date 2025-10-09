"""
サイトごとのスクレイピング処理をクラスとして定義するモジュール。
"""
from __future__ import annotations

import abc
import logging
import math
import re
import time
import random
from urllib.parse import urljoin
from typing import Dict, List, Optional, Tuple

import utils
import requests
from bs4 import BeautifulSoup

class BaseScraper(abc.ABC):
    """すべてのスクレイパーの基底クラス。共通処理を定義する。"""

    def __init__(self, site_name: str, site_config: Dict):
        self.site_name = site_name
        self.site_config = site_config
        self.base_url = site_config["BASE_URL"]
        self.logger = logging.getLogger(self.__class__.__name__)

    def scrape(self, start_page: int, scraped_count: int, max_items: Optional[int]) -> List[Dict[str, str]]:
        """スクレイピングのメインフローを実行する。"""
        all_job_details: List[Dict[str, str]] = []

        total_items, last_page = self._get_pagination_info()
        if total_items is None or last_page is None:
            self.logger.error("総件数または最終ページの取得に失敗しました。処理を終了します。")
            return []

        page = start_page
        skip_items = scraped_count % self.site_config.get("ITEMS_PER_PAGE", 30)

        while page <= last_page:
            if max_items is not None and len(all_job_details) >= max_items:
                self.logger.info(f"最大取得件数({max_items}件)に達しました。処理を中断します。")
                break

            list_soup = self._get_soup_for_page(page)
            if not list_soup:
                page += 1
                continue

            job_cards = self._find_job_cards(list_soup)
            if not job_cards:
                self.logger.warning(f"ページ {page} で求人カードが見つかりませんでした。")
                break

            self.logger.info(f"ページ {page} で求人カードを {len(job_cards)} 件検出しました。")

            for i, job_card in enumerate(job_cards):
                if max_items is not None and len(all_job_details) >= max_items:
                    break
                if i < skip_items:
                    continue

                if "p-ad-item" in job_card.get("class", []):
                    self.logger.debug("広告カードを検出しスキップしました index=%d", i)
                    continue

                job_details = self._process_job_card(job_card)
                if job_details:
                    all_job_details.append(job_details)
                else:
                    self.logger.warning(f"求人情報の取得に失敗しました (カード {i+1})。")

            skip_items = 0
            page += 1
            self.logger.info("ページ処理完了。現在の累計取得件数: %d", len(all_job_details))
            
            # サーバー負荷軽減のための待機
            time.sleep(random.uniform(1, 3))

        return all_job_details

    def _get_soup_for_page(self, page: int) -> Optional[BeautifulSoup]:
        """ページ番号に対応する一覧ページのSoupオブジェクトを返す。"""
        self.logger.info(f"--- {page}ページ目の処理を開始します ---")
        target_url = self._get_page_url(page)
        list_soup = utils.get_soup(target_url)
        if not list_soup:
            self.logger.error(f"{target_url} の取得に失敗。このページをスキップします。")
            return None
        return list_soup

    def _get_page_url(self, page: int) -> str:
        """ページ番号に応じた一覧ページのURLを返す。"""
        if page == 1:
            return self.site_config["TARGET_URL"]
        return f'{self.site_config["TARGET_URL"]}&page={page}'

    @abc.abstractmethod
    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        """総アイテム数と最終ページ番号を取得する。"""
        raise NotImplementedError

    def _find_job_cards(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """一覧ページから求人カードのリストを見つける。"""
        return soup.find_all(
            self.site_config["JOB_CARD_TAG"],
            class_=self.site_config["JOB_CARD_CLASS"]
        )

    def _process_job_card(self, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        """単一の求人カードを処理して詳細情報を返す。"""
        detail_link_tag = job_card.find(
            self.site_config["DETAIL_URL_TAG"],
            class_=self.site_config.get("DETAIL_URL_CLASS")
        )
        if not detail_link_tag or not detail_link_tag.has_attr('href'):
            self.logger.warning("詳細ページへのリンクが見つかりません。")
            return None

        relative_url = detail_link_tag['href']
        detail_url = urljoin(self.base_url, relative_url)

        job_details = self.get_job_details(detail_url, job_card)
        if job_details:
            job_details.setdefault("求人URL", detail_url)
        return job_details

    @abc.abstractmethod
    def get_job_details(self, detail_url: str, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        """詳細ページから求人情報を抽出する。"""
        raise NotImplementedError

    def _parse_dl_tags(self, section_div: BeautifulSoup) -> Dict[str, str]:
        """dlタグ配下の情報を辞書形式に整形する。"""
        details: Dict[str, str] = {}
        if not section_div:
            return details
        for dl in section_div.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt:
                key = dt.text.strip()
                value = " ".join(dd.text.strip().split()) if dd else "N/A"
                details[key] = value
        return details


class InternScraper(BaseScraper):
    """01intern.com用のスクレイパー。"""

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        list_soup = utils.get_soup(self.site_config["TARGET_URL"])
        if not list_soup:
            return None, None

        total_items_text_element = list_soup.find("p", class_="i-recruitment-title")
        if not total_items_text_element:
            self.logger.error("総件数の取得に失敗しました。")
            return None, None

        total_items_text = total_items_text_element.text.strip()
        match = re.search(r'(\d{1,3}(,\d{3})*)', total_items_text)
        if not match:
            self.logger.error("総件数のテキストから数値の抽出に失敗しました。")
            return None, None

        total_items = int(match.group(1).replace(',', ''))
        items_per_page = self.site_config.get("ITEMS_PER_PAGE", 30)
        last_page = math.ceil(total_items / items_per_page)
        self.logger.info(f"総求人件数: {total_items}件, 最終ページ: {last_page}")
        return total_items, last_page

    def get_job_details(self, detail_url: str, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        soup = utils.get_soup(detail_url)
        if not soup:
            self.logger.error(f"詳細ページ ({detail_url}) の取得に失敗しました。")
            return None

        details: Dict[str, str] = {}
        for key, target in self.site_config['EXTRACTION_TARGETS'].items():
            if "tag" in target and "class" in target:
                elem = soup.find(target["tag"], class_=target.get("class"))
                details[key] = elem.get_text(separator=" ", strip=True) if elem else "N/A"
            elif "div_class" in target:
                section_div = soup.find("div", class_=target["div_class"])
                details.update(self._parse_dl_tags(section_div))
        return details


class KyujinboxScraper(BaseScraper):
    """kyujinbox.com用のスクレイパー。"""

    def _get_page_url(self, page: int) -> str:
        if page == 1:
            return self.site_config["TARGET_URL"]
        return f"{self.site_config['TARGET_URL']}?pg={page}"

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        list_soup = utils.get_soup(self.site_config["TARGET_URL"])
        if not list_soup:
            return None, None

        total_items_text_element = list_soup.find("div", class_="p-resultArea_num")
        if not total_items_text_element:
            self.logger.error("総件数の取得に失敗しました。")
            return None, None

        total_items_text = total_items_text_element.text.strip()
        match = re.search(r'(\d{1,3}(,\d{3})*)', total_items_text)
        if not match:
            self.logger.error("総件数のテキストから数値の抽出に失敗しました。")
            return None, None

        total_items = int(match.group(1).replace(',', ''))
        items_per_page = self.site_config.get("ITEMS_PER_PAGE", 30)
        last_page = math.ceil(total_items / items_per_page)
        self.logger.info(f"総求人件数: {total_items}件, 最終ページ: {last_page}")
        return total_items, last_page

    def get_job_details(self, detail_url: str, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        details: Dict[str, str] = {}
        for key, target in self.site_config['EXTRACTION_TARGETS'].items():
            cls = target.get("class")
            elem = job_card.find(target["tag"], class_=cls)
            details[key] = elem.get_text(separator=" ", strip=True) if elem else "N/A"

        source_elem = job_card.find("div", class_="p-result_source")
        if source_elem:
            details["掲載元"] = source_elem.get_text(separator=" ", strip=True)

        soup_ext = utils.get_soup(detail_url)
        if soup_ext:
            try:
                ext_details = self._extract_sections_from_external(
                    soup_ext, self.site_config.get("EXTERNAL_SECTION_RULES")
                )
                details.update(ext_details)
            except Exception as e:
                self.logger.warning(
                    f"外部詳細ページの解析中に予期せぬエラーが発生しました: {type(e).__name__} - {e} URL: {detail_url}"
                )
        return details

    def _extract_sections_from_external(self, soup: BeautifulSoup, rules: Optional[Dict] = None) -> Dict[str, str]:
        result = {}
        targets = rules or {}
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

        for out_key, keywords in targets.items():
            # Find a heading tag that contains one of the keywords
            heading = soup.find(
                lambda tag: tag.name in heading_tags and any(k in tag.get_text(strip=True) for k in keywords)
            )

            if not heading:
                self.logger.debug(f"'{out_key}' に対応する見出しが見つかりませんでした。")
                continue

            # Collect content from subsequent siblings until the next heading
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in heading_tags:
                    break
                # Ensure the sibling has meaningful content
                text = sibling.get_text(separator=" ", strip=True)
                if text:
                    content_parts.append(text)
            
            if content_parts:
                result[out_key] = " ".join(content_parts).strip()
            else:
                self.logger.debug(f"'{out_key}' の見出し配下で内容が見つかりませんでした。")
        return result

class InternshipGuideScraper(BaseScraper):
    """internshipguide.jp用のスクレイパー。"""

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        """総アイテム数と最終ページ番号を取得する。"""
        list_soup = utils.get_soup(self.site_config["TARGET_URL"])
        if not list_soup:
            return None, None

        total_items_text_element = list_soup.find("span", class_="c-breadcrumbs-list__label--current")
        if not total_items_text_element:
            self.logger.error("総件数の取得に失敗しました。")
            return None, None

        total_items_text = total_items_text_element.text.strip()
        match = re.search(r'\((\d[\d,]*)\)', total_items_text)
        if not match:
            self.logger.error("総件数のテキストから数値の抽出に失敗しました。")
            return None, None

        total_items = int(match.group(1).replace(',', ''))
        items_per_page = self.site_config.get("ITEMS_PER_PAGE", 9)
        last_page = math.ceil(total_items / items_per_page)
        self.logger.info(f"総求人件数: {total_items}件, 最終ページ: {last_page}")
        return total_items, last_page

    def _get_soup_for_page(self, page: int) -> Optional[BeautifulSoup]:
        """AJAXリクエストを送信して、ページの内容をSoupとして取得する。"""
        self.logger.info(f"--- {page}ページ目の処理を開始します ---")
        
        payload = {
            "page": page,
            "type": "normal",
            "classId": 1003,
            "sort": 0,
            "targetPrefecture": 13,
            "longterm": 1
        }
        
        try:
            response = requests.post(
                self.site_config["AJAX_URL"], 
                data=payload, 
                headers=self.site_config.get("AJAX_HEADERS"), 
                timeout=15
            )
            response.raise_for_status()
            
            if not response.text.strip():
                self.logger.info(f"ページ {page} のコンテンツが空です。最終ページと判断します。")
                return None
            
            return BeautifulSoup(response.text, 'html.parser')

        except requests.exceptions.RequestException as e:
            self.logger.error(f"AJAXリクエストに失敗しました (ページ {page}): {e}")
            return None

    def get_job_details(self, detail_url: str, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        """詳細ページからすべての項目を抽出し、改行をカンマに変換する。"""
        soup = utils.get_soup(detail_url)
        if not soup:
            self.logger.error(f"詳細ページ ({detail_url}) の取得に失敗しました。")
            return None

        details: Dict[str, str] = {}

        # Helper to extract text, replacing newlines with commas
        def get_text_single_line(selector, attrs=None):
            element = soup.find(selector, attrs=attrs)
            if not element:
                return None
            # Use get_text with a unique separator, then replace that separator
            text = element.get_text(separator='[BR]', strip=True)
            return text.replace('[BR]', ', ')

        # Helper for dd tags, replacing newlines with commas
        def get_dd_text_single_line(dt_text):
            dt_tag = soup.find('dt', string=dt_text)
            if not (dt_tag and dt_tag.find_next_sibling('dd')):
                return None
            
            dd_tag = dt_tag.find_next_sibling('dd')
            # Special handling for URL to not replace <wbr>
            if dt_text == 'URL':
                return dd_tag.get_text(separator='', strip=True)

            text = dd_tag.get_text(separator='[BR]', strip=True)
            return text.replace('[BR]', ', ')

        details['タイトル'] = get_text_single_line('p', attrs={'class': 'notsmartphone c-title'})
        
        timestamp = get_text_single_line('p', attrs={'class': 'page-meta__time-stamp'})
        if timestamp and ':' in timestamp:
            details['最終更新日'] = timestamp.split(':', 1)[1].strip()
        else:
            details['最終更新日'] = timestamp

        details['仕事内容'] = get_text_single_line('p', attrs={'class': 'job-description__detail'})
        details['応募条件'] = get_text_single_line('p', attrs={'class': 'qualification__detail'})
        
        # Extract from definition list
        details['職種'] = get_dd_text_single_line('職種')
        details['給与'] = get_dd_text_single_line('給与')
        details['勤務期間・時間'] = get_dd_text_single_line('勤務期間・時間')
        details['勤務地'] = get_dd_text_single_line('勤務地')
        details['身に付くスキル'] = get_dd_text_single_line('身に付くスキル')
        details['会社名'] = get_dd_text_single_line('会社名')
        details['URL'] = get_dd_text_single_line('URL') # Uses special handling inside the helper
        details['新卒採用（実施予定）'] = get_dd_text_single_line('新卒採用（実施予定）')

        # The company name is also in the h1 tag, which might be more reliable
        if not details.get('会社名'):
             details['会社名'] = get_text_single_line('h1', attrs={'class': 'page-meta__title'})

        # Clean up None values
        for key, value in details.items():
            if value is None:
                details[key] = 'N/A'

        return details