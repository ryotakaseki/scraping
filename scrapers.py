"""
サイトごとのスクレイピング処理をクラスとして定義するモジュール。
"""
from __future__ import annotations

import abc
import logging
import math
import re
from urllib.parse import urljoin
from typing import Dict, List, Optional, Tuple

import utils
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

            self.logger.info(f"--- {page}ページ目の処理を開始します ---")
            target_url = self._get_page_url(page)
            list_soup = utils.get_soup(target_url)
            if not list_soup:
                self.logger.error(f"{target_url} の取得に失敗。このページをスキップします。")
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

        return all_job_details

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
            class_=self.site_config["DETAIL_URL_CLASS"]
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
                self.logger.warning(f"外部詳細ページの解析に失敗: {e} URL: {detail_url}")
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
