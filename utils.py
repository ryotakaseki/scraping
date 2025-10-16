import logging
import random
import time
from typing import Optional, Dict

import requests
import tls_client
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

        logging.debug("HTTPリクエストを送信します url=%s headers=%s", url, request_headers)
        res = session.get(url, headers=request_headers)
        logging.debug("HTTPレスポンスを受信しました status_code=%s url=%s", res.status_code, url)



        # ステータスコードに基づいてエラーハンドリング
        if res.status_code != 200:
            logging.error(f"ページの取得エラー ({url}): status_code={res.status_code}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        logging.debug(
            "BeautifulSoupオブジェクトを生成しました url=%s content_length=%d",
            url,
            len(res.text),
        )
        return soup
    except Exception as e:
        logging.error("ページの取得エラー (%s): %s", url, e)

    logging.debug("URLの取得に失敗したため None を返します url=%s", url)
    return None
