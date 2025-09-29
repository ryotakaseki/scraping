import logging
import random
import time

import requests
from bs4 import BeautifulSoup

import config


def get_soup(url):
    """指定されたURLからBeautifulSoupオブジェクトを取得する"""
    try:
        sleep_time = random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        logging.debug("HTTPリクエスト前に %.2f 秒待機します url=%s", sleep_time, url)
        time.sleep(sleep_time)

        logging.debug("HTTPリクエストを送信します url=%s headers=%s", url, config.HEADERS)
        res = requests.get(url, headers=config.HEADERS, timeout=10)
        logging.debug("HTTPレスポンスを受信しました status_code=%s url=%s", res.status_code, url)

        # res.encoding = res.apparent_encoding
        res.encoding = 'utf-8'
        res.raise_for_status()

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
