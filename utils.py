import logging
import random
import time

import requests
from bs4 import BeautifulSoup
from typing import Optional

import config


def get_soup(url: str) -> Optional[BeautifulSoup]:
    """指定されたURLから ``BeautifulSoup`` オブジェクトを取得する。"""

    try:
        sleep_time = random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        logging.debug("URL %s の取得前に %.2f 秒スリープします。", url, sleep_time)
        time.sleep(sleep_time)

        logging.debug("URL %s に対して HTTP リクエストを送信します。", url)
        res = requests.get(url, headers=config.HEADERS, timeout=10)
        logging.debug(
            "URL %s からステータスコード %s を受信しました。", url, res.status_code
        )

        res.encoding = "utf-8"
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        logging.debug("URL %s の解析に成功しました。", url)
        return soup
    except requests.RequestException as e:
        logging.error("ページの取得エラー (%s): %s", url, e)
        return None

