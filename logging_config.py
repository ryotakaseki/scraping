import logging
import os
from datetime import datetime
from typing import Optional


def _resolve_log_level(log_level: Optional[str]) -> int:
    """渡されたログレベル文字列を logging モジュール用の数値に変換する。"""
    if not log_level:
        return logging.DEBUG

    level = getattr(logging, log_level.upper(), None)
    if isinstance(level, int):
        return level

    logging.getLogger(__name__).warning(
        "無効なログレベル '%s' が指定されました。DEBUG レベルを使用します。",
        log_level,
    )
    return logging.DEBUG


def setup_logging(log_level: Optional[str] = None, enable_console: bool = True) -> None:
    """ログ設定を行う関数."""

    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"scraping_{timestamp}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    level = _resolve_log_level(log_level or os.environ.get("SCRAPING_LOG_LEVEL"))
    log_format = (
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
    )

    logging.basicConfig(
        level=level,
        format=log_format,
        filename=log_filepath,
        filemode="w",
        encoding="utf-8",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)

    root_logger.debug(
        "ロギングを初期化しました。レベル=%s, 出力ファイル=%s",
        logging.getLevelName(level),
        log_filepath,
    )
