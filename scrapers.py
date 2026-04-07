"""
サイトごとのスクレイピング処理をクラスとして定義するモジュール。
"""
from __future__ import annotations

import abc
from http.cookies import SimpleCookie
from copy import deepcopy
import html
import json
import logging
import math
import os
import re
import time
import random
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
from typing import Dict, List, Optional, Tuple

import utils
import requests
import config
from bs4 import BeautifulSoup, NavigableString, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class BaseScraper(abc.ABC):
    """すべてのスクレイパーの基底クラス。共通処理を定義する。"""

    def __init__(self, site_name: str, site_config: Dict):
        self.site_name = site_name
        self.site_config = site_config
        self.base_url = site_config["BASE_URL"]
        self.logger = logging.getLogger(self.__class__.__name__)
        self.base_headers = config.HEADERS.copy()
        self.base_headers.update(site_config.get("HEADERS", {}))

    def scrape(self, start_page: int, scraped_count: int, max_items: Optional[int]) -> List[Dict[str, str]]:
        """スクレイピングのメインフローを実行する。"""
        all_job_details: List[Dict[str, str]] = []

        total_items, last_page = self._get_pagination_info()
        if total_items is None or last_page is None:
            self.logger.error("総件数または最終ページの取得に失敗しました。処理を終了します。")
            return []

        if start_page > last_page:
            self.logger.warning(f"開始ページ({start_page})が最終ページ({last_page})を超えています。これ以上の新しい求人はありません。")
            return []

        page = start_page
        skip_items = scraped_count % self.site_config.get("ITEMS_PER_PAGE", 30)
        consecutive_page_failures = 0
        max_consecutive_page_failures = 3

        while page <= last_page:
            if max_items is not None and len(all_job_details) >= max_items:
                self.logger.info(f"最大取得件数({max_items}件)に達しました。処理を中断します。")
                break

            list_soup = self._get_soup_for_page(page)
            if not list_soup:
                consecutive_page_failures += 1
                if consecutive_page_failures >= max_consecutive_page_failures:
                    self.logger.warning(
                        "一覧ページの取得失敗が連続したため処理を終了します failures=%d",
                        consecutive_page_failures,
                    )
                    break
                self.logger.warning(
                    "一覧ページの取得に失敗しました。次のページへ進みます page=%d failures=%d/%d",
                    page,
                    consecutive_page_failures,
                    max_consecutive_page_failures,
                )
                page += 1
                continue
            
            consecutive_page_failures = 0

            job_cards = self._find_job_cards(list_soup)
            if not job_cards:
                self.logger.warning(f"ページ {page} で求人カードが見つかりませんでした。")

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

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = self.base_headers.copy()
        if extra:
            headers.update(extra)
        return headers

    def _fetch_soup(self, url: str, extra_headers: Optional[Dict[str, str]] = None) -> Optional[BeautifulSoup]:
        headers = self._build_headers(extra_headers)
        return utils.get_soup(url, headers)

    def _get_soup_for_page(self, page: int) -> Optional[BeautifulSoup]:
        """ページ番号に対応する一覧ページのSoupオブジェクトを返す。"""
        self.logger.info(f"--- {page}ページ目の処理を開始します ---")
        target_url = self._get_page_url(page)

        extra_headers = None
        if page > 1:
            referer_url = self._get_page_url(page - 1)
            extra_headers = {"Referer": referer_url}

        list_soup = self._fetch_soup(target_url, extra_headers)
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
        tag = self.site_config["JOB_CARD_TAG"]
        class_name = self.site_config["JOB_CARD_CLASS"]
        return soup.select(f'{tag}.{class_name}')

    def _process_job_card(self, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        """単一の求人カードを処理して詳細情報を返す。"""
        detail_url_class = self.site_config.get("DETAIL_URL_CLASS")
        find_kwargs = {}
        if detail_url_class:
            find_kwargs['class_'] = detail_url_class

        detail_link_tag = job_card.find(
            self.site_config["DETAIL_URL_TAG"],
            **find_kwargs
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
        list_soup = self._fetch_soup(self.site_config["TARGET_URL"])
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
        soup = self._fetch_soup(detail_url, {"Referer": self.site_config["TARGET_URL"]})
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
        
        base_url = self.site_config["TARGET_URL"]
        
        # URLの解析
        parts = list(urlparse(base_url))
        query = dict(parse_qsl(parts[4]))
        
        # pageパラメータを更新
        query['page'] = page
        
        # 新しいクエリ文字列を生成
        parts[4] = urlencode(query)
        
        # 新しいURLを組み立て
        return urlunparse(parts)
    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        list_soup = self._fetch_soup(self.site_config["TARGET_URL"])
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

        soup_ext = self._fetch_soup(detail_url, {"Referer": self.site_config["TARGET_URL"]})
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


class InfraScraper(BaseScraper):
    """in-fra.jp用のスクレイパー。"""

    def __init__(self, site_name: str, site_config: Dict):
        super().__init__(site_name, site_config)

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        list_soup = self._fetch_soup(self.site_config["TARGET_URL"])
        if not list_soup:
            return None, None

        soup = list_soup

        total_items_text_element = soup.find("span", class_="hit-count")
        if not total_items_text_element:
            self.logger.error("総件数の取得に失敗しました。")
            return None, None

        match = re.search(r'(\d+)', total_items_text_element.text)
        if not match:
            self.logger.error("総件数のテキストから数値の抽出に失敗しました。")
            return None, None

        total_items = int(match.group(1))
        items_per_page = self.site_config.get("ITEMS_PER_PAGE", 50)
        last_page = math.ceil(total_items / items_per_page)
        self.logger.info(f"総求人件数: {total_items}件, 最終ページ: {last_page}")
        return total_items, last_page

    def _get_page_url(self, page: int) -> str:
        if page == 1:
            return self.site_config["TARGET_URL"]
        return f'{self.site_config["TARGET_URL"]}&page={page}'

    def _process_job_card(self, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        job_id = job_card.get('data-id')
        if not job_id:
            self.logger.warning("求人ID(data-id)が見つかりません。")
            return None

        detail_url = f"https://www.in-fra.jp/long-internships/{job_id}"
        job_details = self.get_job_details(detail_url, job_card)
        if job_details:
            job_details.setdefault("求人URL", detail_url)
        return job_details

    def get_job_details(self, detail_url: str, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        soup = self._fetch_soup(detail_url, {"Referer": self.site_config["TARGET_URL"]})
        if not soup:
            self.logger.error(f"詳細ページ ({detail_url}) の取得に失敗しました。")
            return None

        details = {}

        def get_single_line_text(element):
            if not element:
                return 'N/A'
            return element.get_text(separator=', ', strip=True)

        title_elem = soup.find('h1', class_='intern-detail-mv-title-text')
        details['タイトル'] = get_single_line_text(title_elem)

        company_elem = soup.find('h2', class_='intern-detail-desc-name')
        details['会社名'] = get_single_line_text(company_elem)

        task_elem = soup.find('div', class_='intern-detail-task')
        if task_elem and task_elem.find('p'):
            details['このインターンですること'] = get_single_line_text(task_elem.find('p'))

        # 「その他のインターン条件」を取得
        other_conditions_section = soup.find('div', class_='intern-detail-others')
        if other_conditions_section:
            for item in other_conditions_section.find_all('div', class_='intern-detail-others-list'):
                label_elem = item.find('div', class_='intern-detail-others-list-label')
                content_elem = item.find('div', class_='intern-detail-others-list-content')
                if label_elem and content_elem:
                    key = get_single_line_text(label_elem)
                    value = get_single_line_text(content_elem)
                    details[key] = value

        return details


class RenewCareerScraper(BaseScraper):
    """renew-career.com用のスクレイパー。"""

    SECTION_HEADINGS = [
        "仕事概要",
        "入社後の流れ",
        "経験できること",
        "身につくスキル",
        "応募後の流れ",
    ]

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        list_soup = self._fetch_soup(self.site_config["TARGET_URL"])
        if not list_soup:
            return None, None

        total_items_text_element = list_soup.find("p", class_="font-semibold text-sm text-gray-800")
        if not total_items_text_element:
            self.logger.error("総件数の取得に失敗しました。")
            return None, None

        total_items_text = total_items_text_element.text.strip()
        self.logger.info(f"Total items text: {total_items_text}")
        match = re.search(r'(\d{1,3}(,\d{3})*)', total_items_text)
        if not match:
            self.logger.error("総件数のテキストから数値の抽出に失敗しました。")
            return None, None

        total_items = int(match.group(1).replace(',', ''))
        items_per_page = self.site_config.get("ITEMS_PER_PAGE", 20)
        last_page = math.ceil(total_items / items_per_page)
        self.logger.info(f"総求人件数: {total_items}件, 最終ページ: {last_page}")
        return total_items, last_page

    def _get_page_url(self, page: int) -> str:
        """ページ番号に応じた一覧ページのURLを返す。"""
        if page == 1:
            return self.site_config["TARGET_URL"]
        return f'{self.site_config["TARGET_URL"]}&page={page}'


    def _process_job_card(self, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        """単一の求人カードを処理して詳細情報を返す。"""
        detail_link_tag = job_card.find("a")
        if not detail_link_tag or not detail_link_tag.has_attr('href'):
            self.logger.warning("詳細ページへのリンクが見つかりません。")
            return None

        detail_url = detail_link_tag['href']

        job_details = self.get_job_details(detail_url, job_card)
        if job_details:
            job_details.setdefault("求人URL", detail_url)
        return job_details

    def _extract_summary_items(self, soup: BeautifulSoup) -> Dict[str, str]:
        """募集要項セクション内のdl要素を辞書にまとめる。"""
        summary: Dict[str, str] = {}
        heading = soup.find("h2", string=lambda text: text and "募集要項" in text)
        if not heading:
            return summary

        summary_list = heading.find_next("ul")
        if not summary_list:
            return summary

        for li in summary_list.find_all("li"):
            dt = li.find("dt")
            dd = li.find("dd")
            if not dt or not dd:
                continue
            key = dt.get_text(separator=" ", strip=True)
            value = dd.get_text(separator=" ", strip=True)
            if key and value:
                summary[key] = value
        return summary

    def _collect_section_text(self, soup: BeautifulSoup, heading_keyword: str) -> Optional[str]:
        """指定見出し以降のテキストブロックを収集する。"""
        heading = soup.find("h2", string=lambda text: text and heading_keyword in text)
        if not heading:
            return None

        content_parts = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if getattr(sibling, "name", None) == "h2":
                break
            text = sibling.get_text(separator=" ", strip=True)
            if text:
                content_parts.append(text)
        if not content_parts:
            return None
        return "\n".join(content_parts)

    def get_job_details(self, detail_url: str, job_card: BeautifulSoup) -> Optional[Dict[str, str]]:
        """詳細ページから求人情報を抽出する。"""
        details: Dict[str, str] = {}

        def clean_text(text: str) -> str:
            return text.replace('\n', ' ').replace('\r', ' ').strip()

        title_elem = job_card.find("h2")
        if title_elem:
            details["タイトル"] = clean_text(title_elem.get_text(separator=' '))

        company_elem = job_card.find("p", class_="ml-2 text-sm tracking-wide")
        if company_elem:
            details["会社名"] = clean_text(company_elem.get_text(separator=' '))

        # Extracting details from the job card directly
        location_and_job_type_elems = job_card.select("ul.flex.flex-wrap.gap-2 li")
        if len(location_and_job_type_elems) >= 2:
            details["勤務地"] = clean_text(location_and_job_type_elems[0].get_text(separator=' '))
            details["職種"] = clean_text(location_and_job_type_elems[1].get_text(separator=' '))

        # currency_yen, place, train, calendar_today
        items = job_card.select('ul.pb-3.space-y-1 li.flex.items-center.gap-2')
        for item in items:
            icon_elem = item.find('span', class_='material-icons-outlined')
            if icon_elem:
                icon_name = icon_elem.get_text(strip=True)
                text_elem = item.find('p')
                if text_elem:
                    text = clean_text(text_elem.get_text(separator=' '))
                    if 'currency_yen' in icon_name:
                        details['給与'] = text
                    elif 'place' in icon_name:
                        details['勤務地'] = text
                    elif 'train' in icon_name:
                        details['アクセス'] = text
                    elif 'calendar_today' in icon_name:
                        details['勤務時間'] = text

        chip_container = job_card.select_one("ul.flex.flex-wrap.gap-1.md\\:gap-2")
        if chip_container:
            chips = [
                clean_text(chip.get_text(separator=' '))
                for chip in chip_container.find_all("p")
                if chip.get_text(strip=True)
            ]
            if chips:
                details["特徴"] = ", ".join(chips)

        return details


class SokudanScraper(BaseScraper):
    """sokudan.work用のスクレイパー。"""

    _GENERIC_COMPANY_NAMES = {
        "N/A",
        "当社",
        "弊社",
        "自社",
        "私たち",
        "わたしたち",
    }

    def __init__(self, site_name: str, site_config: Dict):
        super().__init__(site_name, site_config)
        self.api_base_url = site_config.get("API_BASE_URL", f"{self.base_url}/api/v2").rstrip("/")
        self.list_api_url = f"{self.api_base_url}/top/projects"
        self.login_url = site_config.get("LOGIN_URL", urljoin(self.base_url, "/login"))
        self.session_cookie_env = site_config.get("SESSION_COOKIE_ENV", "SOKUDAN_SESSION_COOKIE")
        self.email_env = site_config.get("EMAIL_ENV", "SOKUDAN_EMAIL")
        self.password_env = site_config.get("PASSWORD_ENV", "SOKUDAN_PASSWORD")
        self.items_per_page = int(site_config.get("ITEMS_PER_PAGE", 40))
        self.list_api_params = self._build_list_api_params(site_config["TARGET_URL"])

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.auth_session = requests.Session()
        self.auth_session.mount("https://", adapter)
        self.auth_session.mount("http://", adapter)
        self.auth_session.headers.update({
            "User-Agent": self.base_headers.get("user-agent", config.HEADERS.get("user-agent", "Mozilla/5.0")),
        })

        self._auth_checked = False
        self._auth_available = False
        self._authenticated_project_cache: Dict[int, Optional[Dict]] = {}

    def _set_cookie_from_string(self, cookie_string: str) -> bool:
        cookie_string = cookie_string.strip()
        if not cookie_string:
            return False

        hostname = urlparse(self.base_url).hostname or "sokudan.work"
        parsed_cookie = SimpleCookie()
        parsed_cookie.load(cookie_string)

        if parsed_cookie:
            for morsel in parsed_cookie.values():
                self.auth_session.cookies.set(morsel.key, morsel.value, domain=hostname, path="/")
            return True

        if "=" in cookie_string:
            cookie_name, cookie_value = cookie_string.split("=", 1)
        else:
            cookie_name, cookie_value = "_slashub_session", cookie_string

        cookie_name = cookie_name.strip()
        cookie_value = cookie_value.strip()
        if not cookie_name or not cookie_value:
            return False

        self.auth_session.cookies.set(cookie_name, cookie_value, domain=hostname, path="/")
        return True

    def _is_authenticated_session(self) -> bool:
        try:
            response = self.auth_session.get(
                f"{self.api_base_url}/me",
                headers=self._build_headers({
                    "Accept": "application/json, text/plain, */*",
                    "Referer": self.site_config["TARGET_URL"],
                    "X-Requested-With": "XMLHttpRequest",
                }),
                allow_redirects=False,
                timeout=30,
            )
        except requests.RequestException as e:
            self.logger.warning("SOKUDAN の認証状態確認に失敗しました error=%s", e)
            return False

        return response.status_code == 200

    def _login_with_credentials(self, email: str, password: str) -> bool:
        try:
            login_page = self.auth_session.get(
                self.login_url,
                headers=self._build_headers({"Referer": self.login_url}),
                timeout=30,
            )
            login_page.raise_for_status()
        except requests.RequestException as e:
            self.logger.warning("SOKUDAN のログインページ取得に失敗しました error=%s", e)
            return False

        soup = BeautifulSoup(login_page.text, "html.parser")
        login_form = soup.find("form", action=lambda value: value and "/login" in value)
        if not login_form:
            self.logger.warning("SOKUDAN のログインフォームを検出できませんでした。")
            return False

        payload = {}
        for input_tag in login_form.find_all("input"):
            field_name = input_tag.get("name")
            if not field_name:
                continue
            payload[field_name] = input_tag.get("value", "")
        payload["user[email]"] = email
        payload["user[password]"] = password

        login_action = urljoin(self.base_url, login_form.get("action") or "/login")
        try:
            response = self.auth_session.post(
                login_action,
                data=payload,
                headers=self._build_headers({
                    "Origin": self.base_url,
                    "Referer": self.login_url,
                }),
                allow_redirects=True,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.warning("SOKUDAN のログインPOSTに失敗しました error=%s", e)
            return False

        return self._is_authenticated_session()

    def _ensure_authenticated(self) -> bool:
        if self._auth_checked:
            return self._auth_available

        self._auth_checked = True

        session_cookie = os.getenv(self.session_cookie_env, "").strip()
        if session_cookie:
            if self._set_cookie_from_string(session_cookie) and self._is_authenticated_session():
                self._auth_available = True
                self.logger.info("SOKUDAN の認証Cookieを使用して会社名補完を有効化しました。")
                return True
            self.logger.warning("SOKUDAN の認証Cookieが無効なため、フォームログインまたは公開モードへフォールバックします。")

        email = os.getenv(self.email_env, "").strip()
        password = os.getenv(self.password_env, "").strip()
        if email or password:
            if not email or not password:
                self.logger.warning("SOKUDAN のログイン情報が不完全です。%s と %s を両方設定してください。", self.email_env, self.password_env)
                return False
            if self._login_with_credentials(email, password):
                self._auth_available = True
                self.logger.info("SOKUDAN にログインしました。会社名補完を有効化しました。")
                return True
            self.logger.warning("SOKUDAN のログインに失敗したため、公開モードで続行します。")

        return False

    def _fetch_authenticated_project(self, project_id: Optional[int], detail_url: str) -> Optional[Dict]:
        if not project_id:
            return None

        cached = self._authenticated_project_cache.get(project_id)
        if cached is not None or project_id in self._authenticated_project_cache:
            return cached

        if not self._ensure_authenticated():
            self._authenticated_project_cache[project_id] = None
            return None

        api_url = f"{self.api_base_url}/top/projects/{project_id}"
        try:
            response = self.auth_session.get(
                api_url,
                headers=self._build_headers({
                    "Accept": "application/json, text/plain, */*",
                    "Referer": detail_url,
                    "X-Requested-With": "XMLHttpRequest",
                }),
                allow_redirects=False,
                timeout=30,
            )
        except requests.RequestException as e:
            self.logger.warning("SOKUDAN の認証API取得に失敗しました project_id=%s error=%s", project_id, e)
            self._authenticated_project_cache[project_id] = None
            return None

        redirect_location = response.headers.get("location", "")
        if 300 <= response.status_code < 400 and "/login" in redirect_location:
            self.logger.warning("SOKUDAN の認証セッションが失効しました。公開モードへフォールバックします。")
            self._auth_available = False
            self._authenticated_project_cache[project_id] = None
            return None

        if response.status_code != 200:
            self.logger.warning(
                "SOKUDAN の認証APIが失敗しました project_id=%s status=%s",
                project_id,
                response.status_code,
            )
            self._authenticated_project_cache[project_id] = None
            return None

        try:
            project_data = response.json()
        except ValueError as e:
            self.logger.warning("SOKUDAN の認証APIレスポンス解析に失敗しました project_id=%s error=%s", project_id, e)
            self._authenticated_project_cache[project_id] = None
            return None

        if not isinstance(project_data, dict):
            self.logger.warning("SOKUDAN の認証APIレスポンス形式が不正です project_id=%s", project_id)
            self._authenticated_project_cache[project_id] = None
            return None

        self._authenticated_project_cache[project_id] = project_data
        return project_data

    def _merge_project_data(self, public_data: Dict, authenticated_data: Optional[Dict]) -> Dict:
        if not authenticated_data:
            return public_data

        merged = public_data.copy()
        for key, value in authenticated_data.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        return merged

    def _clean_company_name(self, name: Optional[str]) -> str:
        if not name:
            return "N/A"
        cleaned = html.unescape(name).replace("\r", " ").replace("\n", " ").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" |｜-:：")
        return cleaned or "N/A"

    def _is_masked_or_generic_company_name(self, name: Optional[str]) -> bool:
        cleaned = self._clean_company_name(name)
        if cleaned in self._GENERIC_COMPANY_NAMES:
            return True
        placeholder = cleaned.replace("＊", "").replace("*", "").strip()
        return not placeholder

    def _extract_company_name_from_meta(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        if not title or title == "N/A":
            return None

        meta_targets = [
            {"property": "og:description"},
            {"name": "twitter:description"},
            {"name": "description"},
        ]
        for attrs in meta_targets:
            meta_tag = soup.find("meta", attrs=attrs)
            if not meta_tag or not meta_tag.get("content"):
                continue

            content = self._clean_company_name(meta_tag["content"])
            if title not in content:
                continue

            candidate = self._clean_company_name(content.split(title, 1)[0])
            if candidate and not self._is_masked_or_generic_company_name(candidate):
                return candidate

        return None

    def _extract_company_name_from_detail_text(self, corp_detail: str) -> Optional[str]:
        if not corp_detail:
            return None

        first_line = corp_detail.split("。")[0].split("\r\n")[0].split("\n")[0]
        first_line = self._clean_company_name(first_line)
        if not first_line:
            return None

        patterns = [
            r"((?:株式会社|合同会社|有限会社)\s*[^は、。\s]{1,80})",
            r"([^は、。\s]{1,80}(?:株式会社|合同会社|有限会社))",
        ]
        for pattern in patterns:
            match = re.search(pattern, first_line)
            if not match:
                continue
            candidate = self._clean_company_name(match.group(1))
            if candidate and not self._is_masked_or_generic_company_name(candidate):
                return candidate

        return None

    def _resolve_company_name(
        self,
        soup: BeautifulSoup,
        title: str,
        corp_name: Optional[str],
        corp_detail: str,
    ) -> str:
        cleaned_name = self._clean_company_name(corp_name)
        if not self._is_masked_or_generic_company_name(cleaned_name):
            return cleaned_name

        meta_name = self._extract_company_name_from_meta(soup, title)
        if meta_name:
            return meta_name

        inferred_name = self._extract_company_name_from_detail_text(corp_detail)
        if inferred_name:
            return inferred_name

        return cleaned_name

    def _build_list_api_params(self, target_url: str) -> Dict[str, str]:
        params: Dict[str, str] = {}
        for key, value in parse_qsl(urlparse(target_url).query, keep_blank_values=True):
            params[key] = value
        return params

    def _fetch_project_list_page(self, page: int) -> Optional[Dict]:
        params = self.list_api_params.copy()
        params["page"] = str(page)

        try:
            response = self.auth_session.get(
                self.list_api_url,
                params=params,
                headers=self._build_headers({
                    "Accept": "application/json, text/plain, */*",
                    "Referer": self._get_page_url(page),
                    "X-Requested-With": "XMLHttpRequest",
                }),
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error("SOKUDAN の一覧API取得に失敗しました page=%s error=%s", page, e)
            return None

        try:
            data = response.json()
        except ValueError as e:
            self.logger.error("SOKUDAN の一覧APIレスポンス解析に失敗しました page=%s error=%s", page, e)
            return None

        if not isinstance(data, dict):
            self.logger.error("SOKUDAN の一覧APIレスポンス形式が不正です page=%s", page)
            return None

        return data

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        result = self._fetch_project_list_page(1)
        if not result:
            return None, None

        try:
            page_url_list = result.get("pageUrlList", [])
            last_page = 1
            if page_url_list:
                page_numbers = []
                for p in page_url_list:
                    try:
                        page_num = p.get("name")
                        if page_num and str(page_num).isdigit():
                            page_numbers.append(int(page_num))
                    except (ValueError, TypeError):
                        continue
                if page_numbers:
                    last_page = max(page_numbers)

            total_items = result.get("totalCount")
            if total_items:
                last_page = math.ceil(total_items / self.items_per_page)
            else:
                total_items = last_page * self.items_per_page

            self.logger.info(f"最終ページ推測: {last_page}")
            return total_items, last_page
        except Exception as e:
            self.logger.error(f"一覧APIレスポンス処理エラー: {e}")
            return None, None

    def _get_page_url(self, page: int) -> str:
        if page == 1:
            return self.site_config["TARGET_URL"]

        parts = list(urlparse(urljoin(self.base_url, "/top/projects")))
        query = self.list_api_params.copy()
        query["page"] = str(page)
        parts[4] = urlencode(query, doseq=True)
        return urlunparse(parts)

    def scrape(self, start_page: int, scraped_count: int, max_items: Optional[int]) -> List[Dict[str, str]]:
        all_job_details: List[Dict[str, str]] = []

        _, last_page = self._get_pagination_info()
        if last_page is None:
            return []

        page = start_page
        skip_items = scraped_count % self.items_per_page
        while page <= last_page:
            if max_items is not None and len(all_job_details) >= max_items:
                break

            target_url = self._get_page_url(page)
            self.logger.info(f"--- {page}ページ目の処理を開始します ({target_url}) ---")

            result = self._fetch_project_list_page(page)
            if not result:
                break
            project_list = result.get("projectList", [])

            if not project_list:
                self.logger.info("これ以上の求人はありません。")
                break

            for index, project in enumerate(project_list):
                if max_items is not None and len(all_job_details) >= max_items:
                    break
                if index < skip_items:
                    continue
                
                detail_url = urljoin(self.base_url, f"/top/projects/{project['id']}")
                job_details = self.get_job_details(detail_url, project)
                if job_details:
                    all_job_details.append(job_details)
                
                time.sleep(random.uniform(1, 2))

            skip_items = 0
            page += 1
            self.logger.info("ページ処理完了。現在の累計取得件数: %d", len(all_job_details))
            time.sleep(random.uniform(1, 3))

        return all_job_details

    def get_job_details(self, detail_url: str, project_data: Dict) -> Optional[Dict[str, str]]:
        """詳細ページにアクセスして求人情報を深掘り抽出する。"""
        soup = self._fetch_soup(detail_url)
        if not soup:
            return None

        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            return None

        try:
            data = json.loads(script_tag.string)
            page_props = data.get("props", {}).get("pageProps", {})
            detail_data = page_props.get("staticProject", {})
            if not detail_data:
                 detail_data = page_props.get("staticProjectDetail", {}).get("project", {})
            
            if not detail_data:
                self.logger.warning(f"Project data not found in JSON: {detail_url}")
                return None

        except Exception as e:
            self.logger.error(f"Detail JSON error: {e}")
            return None

        # 詳細なデータ抽出
        project_id = detail_data.get("id") or project_data.get("id")
        title = detail_data.get("title", "N/A")
        job_description = detail_data.get("detail", "")
        corp_info = detail_data.get("corporation", {})
        raw_company_name = corp_info.get("name", "N/A")
        corp_detail = corp_info.get("detail", "")

        if self._is_masked_or_generic_company_name(raw_company_name):
            authenticated_project = self._fetch_authenticated_project(project_id, detail_url)
            if authenticated_project:
                detail_data = self._merge_project_data(detail_data, authenticated_project)
                title = detail_data.get("title", title)
                job_description = detail_data.get("detail", job_description)
                corp_info = detail_data.get("corporation", {}) or {}
                raw_company_name = corp_info.get("name", raw_company_name)
                corp_detail = corp_info.get("detail", corp_detail)

        resolved_company_name = self._resolve_company_name(
            soup,
            title,
            raw_company_name,
            corp_detail,
        )

        details: Dict[str, str] = {
            "タイトル": title,
            "会社名": resolved_company_name,
            "求人URL": detail_url,
            "勤務地": detail_data.get("prefecture", {}).get("label", "N/A"),
            "月収下限": detail_data.get("minBudget", {}).get("label", "N/A"),
            "月収上限": detail_data.get("maxBudget", {}).get("label", "N/A"),
            "リモート可否": detail_data.get("remoteType", {}).get("label", "N/A"),
            "稼働日数": detail_data.get("projectAvailableTime", {}).get("label", "N/A"),
            "契約形態": detail_data.get("contractType", "N/A"),
            "副業制限": "制限あり" if detail_data.get("sideJobRestriction") else "制限なし",
            "仕事内容": job_description,
        }
        
        # 電話番号とメールアドレスの抽出 (仕事内容、企業紹介、追記事項から)
        all_text = (job_description or "") + " " + (corp_detail or "")
        postscripts = detail_data.get("postscripts", [])
        for ps in postscripts:
            content = ps.get("content", "")
            if content:
                all_text += " " + content

        # 電話番号 (0x-xxxx-xxxx, 0xx-xxx-xxxx, 0xxx-xx-xxxx など)
        phone_match = re.search(r'\d{2,5}-\d{1,4}-\d{4}', all_text)
        details["電話番号"] = phone_match.group(0) if phone_match else "N/A"

        # メールアドレス
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', all_text)
        details["メールアドレス"] = email_match.group(0) if email_match else "N/A"

        # 特徴タグ
        tags = detail_data.get("tags", [])
        if tags:
            details["特徴"] = ", ".join([t.get("label", "") for t in tags if t.get("label")])
            
        # スキル（必須・歓迎）
        skills = detail_data.get("requiredSkills", [])
        if skills:
            # SOKUDANのデータ構造では必須/歓迎が混在していることが多いため、名前を収集
            details["必須スキル"] = ", ".join([s.get("name", "") for s in skills if s.get("name")])

        # 追記事項（ここに応募資格や人物像が含まれることが多い）
        postscripts = detail_data.get("postscripts", [])
        for ps in postscripts:
            label = ps.get("label", "")
            content = ps.get("content", "")
            if "歓迎" in label:
                details["歓迎スキル"] = content
            elif "人物像" in label:
                details["求める人物像"] = content
            elif "応募後の流れ" in label or "選考" in label:
                details["応募後の流れ"] = content

        return details


class SukiikiScraper(BaseScraper):
    """suki-iki.mynavi.jp 用のAPIベーススクレイパー。"""

    def __init__(self, site_name: str, site_config: Dict):
        super().__init__(site_name, site_config)
        self.api_base_url = site_config["API_BASE_URL"].rstrip("/")
        self.search_path = site_config.get("SEARCH_PATH", "/jobs")
        self.items_per_page = int(site_config.get("ITEMS_PER_PAGE", 20))
        self.search_payload = deepcopy(site_config.get("SEARCH_PAYLOAD", {}))
        self.api_min_interval = float(site_config.get("API_MIN_INTERVAL", 1))
        self.api_max_interval = float(site_config.get("API_MAX_INTERVAL", 2))
        self.search_cache: Dict[int, Dict] = {}
        self.detail_cache: Dict[int, Dict] = {}

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_page_url(self, page: int) -> str:
        if page == 1:
            return self.site_config["TARGET_URL"]

        parts = list(urlparse(self.site_config["TARGET_URL"]))
        query = dict(parse_qsl(parts[4]))
        query["pg"] = str(page)
        parts[4] = urlencode(query)
        return urlunparse(parts)

    def _api_headers(self, is_json_body: bool = False) -> Dict[str, str]:
        headers = self._build_headers({
            "Accept": "application/json, text/plain, */*",
            "Origin": self.base_url,
            "Referer": self.site_config["TARGET_URL"],
        })
        if is_json_body:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        return headers

    def _request_json(self, method: str, path: str, payload: Optional[Dict] = None) -> Optional[Dict]:
        url = path if path.startswith("http") else f"{self.api_base_url}{path}"
        sleep_time = random.uniform(self.api_min_interval, self.api_max_interval)
        self.logger.debug("APIリクエスト前に %.2f 秒待機します url=%s", sleep_time, url)
        time.sleep(sleep_time)

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=self._api_headers(is_json_body=payload is not None),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error("APIリクエストに失敗しました method=%s url=%s error=%s", method.upper(), url, e)
            return None

        try:
            return response.json()
        except ValueError as e:
            self.logger.error("APIレスポンスのJSON解析に失敗しました url=%s error=%s", url, e)
            return None

    def _build_search_payload(self, page: int) -> Dict:
        payload = deepcopy(self.search_payload)
        payload["page"] = page
        payload["pageSize"] = self.items_per_page
        return payload

    def _search_jobs(self, page: int) -> Optional[Dict]:
        if page in self.search_cache:
            return self.search_cache[page]

        data = self._request_json("POST", self.search_path, self._build_search_payload(page))
        if data is not None:
            self.search_cache[page] = data
        return data

    def _fetch_job_detail(self, job_id: Optional[int]) -> Optional[Dict]:
        if not job_id:
            return None
        if job_id in self.detail_cache:
            return self.detail_cache[job_id]

        data = self._request_json("GET", f"/jobs/{job_id}")
        if data is not None:
            self.detail_cache[job_id] = data
        return data

    def _get_pagination_info(self) -> Tuple[Optional[int], Optional[int]]:
        first_page = self._search_jobs(1)
        if not first_page:
            return None, None

        total_items = first_page.get("totalCount")
        if not isinstance(total_items, int):
            self.logger.error("一覧APIレスポンスに totalCount がありません。")
            return None, None

        per_page = first_page.get("perPage") or self.items_per_page
        try:
            per_page = int(per_page)
        except (TypeError, ValueError):
            per_page = self.items_per_page

        last_page = max(1, math.ceil(total_items / per_page))
        self.logger.info("総求人件数: %d件, 最終ページ: %d", total_items, last_page)
        return total_items, last_page

    def _clean_text(self, value: Optional[object]) -> str:
        if value is None:
            return "N/A"
        if isinstance(value, bool):
            return "はい" if value else "いいえ"

        text = html.unescape(str(value))
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
        normalized = "\n".join(line for line in lines if line)
        return normalized or "N/A"

    def _first_non_empty(self, *values):
        for value in values:
            if value is None:
                continue
            if isinstance(value, str):
                cleaned = self._clean_text(value)
                if cleaned != "N/A":
                    return value
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            return value
        return None

    def _join_named_items(self, items: Optional[List[Dict]]) -> str:
        if not items:
            return "N/A"

        names: List[str] = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            name = self._clean_text(item.get("name"))
            if name == "N/A" or name in seen:
                continue
            seen.add(name)
            names.append(name)
        return ", ".join(names) if names else "N/A"

    def _join_text_parts(self, *parts: Optional[object]) -> str:
        values: List[str] = []
        seen = set()
        for part in parts:
            cleaned = self._clean_text(part)
            if cleaned == "N/A" or cleaned in seen:
                continue
            seen.add(cleaned)
            values.append(cleaned)
        return " / ".join(values) if values else "N/A"

    def _build_job_url(self, company_id: Optional[int], job_id: Optional[int]) -> str:
        if not company_id or not job_id:
            return "N/A"
        return urljoin(self.base_url, f"/job/{company_id}/{job_id}/")

    def _map_job_details(
        self,
        detail_url: str,
        job_summary: Dict,
        detail_data: Optional[Dict],
    ) -> Dict[str, str]:
        source = detail_data or {}

        location_prefecture = self._first_non_empty(
            source.get("locationPrefecture"),
            job_summary.get("locationPrefecture"),
        ) or {}
        prefecture_name = "N/A"
        if isinstance(location_prefecture, dict):
            prefecture_name = self._clean_text(location_prefecture.get("name"))

        city = self._clean_text(self._first_non_empty(source.get("locationCity"), job_summary.get("locationCity")))
        address = self._clean_text(self._first_non_empty(source.get("locationAddress"), job_summary.get("locationAddress")))
        area = "".join(part for part in [prefecture_name if prefecture_name != "N/A" else "", city if city != "N/A" else ""])
        if not area:
            area = "N/A"

        period_text = self._join_named_items(self._first_non_empty(source.get("period"), job_summary.get("period")))
        period_extendable = self._first_non_empty(
            source.get("periodExtendable"),
            job_summary.get("periodExtendable"),
        )
        if period_text != "N/A" and period_extendable is True:
            period_text = f"{period_text} (延長可)"

        required_skills = self._join_text_parts(
            self._join_named_items(self._first_non_empty(source.get("requiredSkills"), job_summary.get("requiredSkills"))),
            self._first_non_empty(source.get("requiredSkillText"), job_summary.get("requiredSkillText")),
        )
        recommended_skills = self._join_text_parts(
            self._join_named_items(self._first_non_empty(source.get("recommendedSkills"), job_summary.get("recommendedSkills"))),
            self._first_non_empty(source.get("recommendedSkillText"), job_summary.get("recommendedSkillText")),
        )
        frequency_text = self._join_text_parts(
            self._join_named_items(
                self._first_non_empty(source.get("frequencyOfGoingToOffice"), job_summary.get("frequencyOfGoingToOffice"))
            ),
            source.get("frequencyOfGoingToOfficeText"),
        )

        details: Dict[str, str] = {
            "タイトル": self._clean_text(self._first_non_empty(source.get("title"), job_summary.get("title"))),
            "会社名": self._clean_text(self._first_non_empty(source.get("companyName"), job_summary.get("companyName"))),
            "仕事カテゴリ": self._join_named_items(self._first_non_empty(source.get("jobCategory"), job_summary.get("jobCategory"))),
            "職種詳細": self._join_named_items(self._first_non_empty(source.get("jobType"), job_summary.get("jobType"))),
            "働き方": self._join_named_items(self._first_non_empty(source.get("workStyles"), job_summary.get("workStyles"))),
            "想定報酬": self._clean_text(self._first_non_empty(source.get("unitPrice"), job_summary.get("unitPrice"))),
            "稼働時間": self._clean_text(self._first_non_empty(source.get("workingTime"), job_summary.get("workingTime"))),
            "エリア": area,
            "住所": address,
            "出社頻度": frequency_text,
            "契約期間": period_text,
            "契約形態": self._join_named_items(self._first_non_empty(source.get("contractType"), job_summary.get("contractType"))),
            "特徴": self._join_named_items(self._first_non_empty(source.get("features"), job_summary.get("features"))),
            "必須スキル": required_skills,
            "歓迎スキル": recommended_skills,
            "仕事内容": self._clean_text(
                self._first_non_empty(
                    source.get("requestJobText"),
                    job_summary.get("helpText"),
                    source.get("aboutOperation"),
                    source.get("aboutDeliverable"),
                    source.get("optionText"),
                    job_summary.get("optionText"),
                )
            ),
            "会社紹介": self._clean_text(self._first_non_empty(source.get("aboutUsText"), job_summary.get("aboutUsText"))),
            "公開日": self._clean_text(self._first_non_empty(source.get("publishDate"), job_summary.get("openDate"))),
            "募集終了日": self._clean_text(self._first_non_empty(source.get("publishEndDate"), job_summary.get("closeDate"))),
            "求人URL": detail_url,
        }
        return details

    def scrape(self, start_page: int, scraped_count: int, max_items: Optional[int]) -> List[Dict[str, str]]:
        all_job_details: List[Dict[str, str]] = []

        total_items, last_page = self._get_pagination_info()
        if total_items is None or last_page is None:
            self.logger.error("総件数または最終ページの取得に失敗しました。処理を終了します。")
            return []

        if start_page > last_page:
            self.logger.warning("開始ページ(%d)が最終ページ(%d)を超えています。", start_page, last_page)
            return []

        page = start_page
        skip_items = scraped_count % self.items_per_page
        consecutive_page_failures = 0
        max_consecutive_page_failures = 3

        while page <= last_page:
            if max_items is not None and len(all_job_details) >= max_items:
                self.logger.info("最大取得件数(%d件)に達しました。処理を中断します。", max_items)
                break

            self.logger.info("--- %dページ目の処理を開始します (%s) ---", page, self._get_page_url(page))
            search_result = self._search_jobs(page)
            if not search_result:
                consecutive_page_failures += 1
                if consecutive_page_failures >= max_consecutive_page_failures:
                    self.logger.warning(
                        "一覧APIの取得失敗が連続したため処理を終了します failures=%d",
                        consecutive_page_failures,
                    )
                    break
                self.logger.warning(
                    "一覧APIの取得に失敗しました。次のページへ進みます page=%d failures=%d/%d",
                    page,
                    consecutive_page_failures,
                    max_consecutive_page_failures,
                )
                page += 1
                continue

            consecutive_page_failures = 0
            jobs = search_result.get("jobs", [])
            if not isinstance(jobs, list):
                self.logger.error("一覧APIレスポンスの jobs が不正な形式です page=%d", page)
                break
            if not jobs:
                self.logger.info("これ以上の求人はありません。")
                break

            self.logger.info("ページ %d で求人を %d 件検出しました。", page, len(jobs))

            for index, job_summary in enumerate(jobs):
                if max_items is not None and len(all_job_details) >= max_items:
                    break
                if index < skip_items:
                    continue

                company_id = job_summary.get("companyId")
                job_id = job_summary.get("id")
                detail_url = self._build_job_url(company_id, job_id)
                job_details = self.get_job_details(detail_url, job_summary)
                if job_details:
                    all_job_details.append(job_details)
                else:
                    self.logger.warning("求人情報の取得に失敗しました page=%d index=%d job_id=%s", page, index + 1, job_id)

            skip_items = 0
            page += 1
            self.logger.info("ページ処理完了。現在の累計取得件数: %d", len(all_job_details))

        return all_job_details

    def get_job_details(self, detail_url: str, job_summary: Dict) -> Optional[Dict[str, str]]:
        detail_data = self._fetch_job_detail(job_summary.get("id"))
        if detail_data is None:
            self.logger.warning("詳細APIの取得に失敗したため一覧データのみで補完します url=%s", detail_url)
        return self._map_job_details(detail_url, job_summary, detail_data)
