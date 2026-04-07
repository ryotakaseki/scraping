import logging
import random
import time
from typing import Optional, Dict

import requests
import tls_client
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin

import config

# --- セッションとリトライ設定 ---
def get_soup(url: str, headers: Optional[Dict[str, str]] = None):
    """
    指定されたURLからBeautifulSoupオブジェクトを取得する。
    リトライ機能と堅牢なエンコーディング設定を持つセッションを使用する。
    """
    try:
        # Use tls_client session
        session = tls_client.Session(
            client_identifier="chrome_112",
            random_tls_extension_order=True
        )

        request_headers = headers if headers is not None else config.HEADERS
        sleep_time = random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        logging.debug("HTTPリクエスト前に %.2f 秒待機します url=%s", sleep_time, url)
        time.sleep(sleep_time)

        current_url = url
        max_redirects = 5

        for redirect_count in range(max_redirects + 1):
            logging.debug("HTTPリクエストを送信します url=%s headers=%s", current_url, request_headers)
            res = session.get(
                current_url,
                headers=request_headers,
                timeout_seconds=30,
                allow_redirects=False,
            )
            logging.debug("HTTPレスポンスを受信しました status_code=%s url=%s", res.status_code, current_url)

            if 300 <= res.status_code < 400:
                location = res.headers.get("Location")
                if not location:
                    logging.error("リダイレクト先が指定されていません URL: %s", current_url)
                    return None

                current_url = urljoin(current_url, location)
                logging.debug(
                    "リダイレクトを検出しました redirect_count=%d next_url=%s",
                    redirect_count + 1,
                    current_url,
                )
                continue

            break
        else:
            logging.error("リダイレクト回数が上限を超えました URL: %s", url)
            return None

        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            logging.debug(
                "BeautifulSoupオブジェクトを生成しました url=%s content_length=%d",
                current_url,
                len(res.text),
            )
            return soup
        
        # Specific HTTP error handling
        if res.status_code == 404:
            logging.error(f"ページが見つかりません (404 Not Found) URL: {current_url}")
        elif res.status_code == 503:
            logging.error(f"サービス利用不可 (503 Service Unavailable) URL: {current_url}")
        elif 400 <= res.status_code < 500:
            logging.error(f"クライアントエラー ({res.status_code}) URL: {current_url}")
        elif 500 <= res.status_code < 600:
            logging.error(f"サーバーエラー ({res.status_code}) URL: {current_url}")
        else:
            logging.error(f"ページの取得エラー (ステータスコード: {res.status_code}) URL: {current_url}")
        return None

    except Exception as e:
        # Log the specific exception type
        logging.error(f"ページの取得中にエラーが発生しました ({url}): {type(e).__name__} - {e}")
        return None
