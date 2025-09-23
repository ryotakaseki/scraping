import logging
import os
from datetime import datetime

def setup_logging():
    """
    ログ設定を行う関数
    """
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"scraping_{timestamp}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=log_filepath,
        filemode="w",
        encoding="utf-8"
    )

    # コンソールにもログを出力したい場合は、以下のハンドラを追加
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.INFO)
    # formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    # console_handler.setFormatter(formatter)
    # logging.getLogger().addHandler(console_handler)
