import logging
import random
import time
from typing import Dict, Optional
from urllib.parse import urlparse

import tls_client
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


def _determine_sec_fetch_site(target_host: str, referer: Optional[str]) -> str:
    if not referer:
        return "none"

    referer_host = urlparse(referer).netloc
    if referer_host == target_host:
        return "same-origin"
    return "cross-site"


def build_chrome_like_headers(
    url: str,
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Chromeブラウザからのアクセスを模したヘッダーを生成する。"""

    overrides = dict(overrides or {})
    target_host = urlparse(url).netloc
    sec_fetch_site = _determine_sec_fetch_site(target_host, overrides.get("Referer") or overrides.get("referer"))

    profile = random.choice(config.CHROME_HEADER_PROFILES)

    headers: Dict[str, str] = {
        **config.BASE_HEADERS,
        "authority": target_host,
        "host": target_host,
        "sec-ch-ua": profile["sec_ch_ua"],
        "sec-ch-ua-mobile": profile.get("sec_ch_ua_mobile", "?0"),
        "sec-ch-ua-platform": profile["sec_ch_ua_platform"],
        "sec-fetch-site": sec_fetch_site,
        "user-agent": profile["user_agent"],
    }

    headers.update(overrides)
    return headers


# --- セッションとリトライ設定 ---
def get_soup(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[BeautifulSoup]:
    """指定されたURLからBeautifulSoupオブジェクトを取得する。"""

    try:
        session = tls_client.Session(
            client_identifier="chrome_112",
            random_tls_extension_order=True,
        )

        request_headers = build_chrome_like_headers(url, headers)
        sleep_time = random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        logger.debug("HTTPリクエスト前に %.2f 秒待機します url=%s", sleep_time, url)
        time.sleep(sleep_time)

        logger.debug("HTTPリクエストを送信します url=%s headers=%s", url, request_headers)
        response = session.get(url, headers=request_headers)
        logger.debug(
            "HTTPレスポンスを受信しました status_code=%s url=%s", response.status_code, url
        )

        if response.status_code != 200:
            logger.error(
                "ページの取得エラー (%s): status_code=%s", url, response.status_code
            )
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        logger.debug(
            "BeautifulSoupオブジェクトを生成しました url=%s content_length=%d",
            url,
            len(response.text),
        )
        return soup
    except Exception as exc:  # noqa: BLE001 - 広範囲のエラーをログに残すため
        logger.error("ページの取得エラー (%s): %s", url, exc)

    logger.debug("URLの取得に失敗したため None を返します url=%s", url)
    return None
