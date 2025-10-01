import logging
import random
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

# --- セッションとリトライ設定 ---
session = requests.Session()
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
# --------------------------


def get_soup(url: str):
    """
    指定されたURLからBeautifulSoupオブジェクトを取得する。
    リトライ機能と堅牢なエンコーディング設定を持つセッションを使用する。
    """
    try:
        sleep_time = random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        logging.debug("HTTPリクエスト前に %.2f 秒待機します url=%s", sleep_time, url)
        time.sleep(sleep_time)

        logging.debug("HTTPリクエストを送信します url=%s headers=%s", url, config.HEADERS)
        res = session.get(url, headers=config.HEADERS, timeout=10)
        logging.debug("HTTPレスポンスを受信しました status_code=%s url=%s", res.status_code, url)

        # ステータスコードに基づいてエラーハンドリング
        res.raise_for_status()

        # エンコーディングを自動判別させる
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")
        logging.debug(
            "BeautifulSoupオブジェクトを生成しました url=%s content_length=%d",
            url,
            len(res.text),
        )
        return soup
    except requests.Timeout:
        logging.error("タイムアウトが発生しました url=%s", url)
    except requests.RequestException as e:
        logging.error("ページの取得エラー (%s): %s", url, e)

    logging.debug("URLの取得に失敗したため None を返します url=%s", url)
    return None