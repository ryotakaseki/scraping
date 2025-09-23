import logging
import random
import time
import requests
from bs4 import BeautifulSoup
import config

def get_soup(url):
    """
    指定されたURLからBeautifulSoupオブジェクトを取得する
    """
    try:
        sleep_time = random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        logging.info(f"{sleep_time:.2f}秒待機します...")
        time.sleep(sleep_time)
        
        res = requests.get(url, headers=config.HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        res.raise_for_status()
        return BeautifulSoup(res.text, "html.parser")
    except requests.RequestException as e:
        logging.error(f"ページの取得エラー ({url}): {e}")
        return None