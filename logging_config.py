"""ロギング設定を初期化するユーティリティ。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional, Tuple


def _coerce_log_level(level_name: Optional[str]) -> Optional[int]:
    """文字列で指定されたログレベルを数値レベルに変換する。"""

    if not level_name:
        return None

    level = getattr(logging, level_name.upper(), None)
    return level if isinstance(level, int) else None


def _select_log_level(
    cli_level: Optional[str],
    env_level: Optional[str],
    default_level: Optional[str],
) -> Tuple[int, str, List[str]]:
    """ログレベルの決定と警告メッセージの収集を行う。"""

    warnings: List[str] = []

    for source, candidate in (
        ("CLI 引数", cli_level),
        ("環境変数 SCRAPING_LOG_LEVEL", env_level),
    ):
        level = _coerce_log_level(candidate)
        if level is not None:
            return level, source, warnings
        if candidate:
            warnings.append(
                f"{source} で指定されたログレベル '{candidate}' は無効です。"
            )

    fallback_source = "config.LOG_LEVEL"
    level = _coerce_log_level(default_level)
    if level is None:
        if default_level:
            warnings.append(
                f"{fallback_source} に無効なログレベル '{default_level}' が設定されています。"
            )
        level = logging.DEBUG
        fallback_source = "デフォルト (DEBUG)"

    return level, fallback_source, warnings


def setup_logging(
    log_level: Optional[str] = None,
    enable_console: bool = True,
    default_level: Optional[str] = None,
) -> None:
    """ロギング設定を構成する。"""

    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"scraping_{timestamp}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    level, source, warnings = _select_log_level(
        cli_level=log_level,
        env_level=os.environ.get("SCRAPING_LOG_LEVEL"),
        default_level=default_level,
    )
    log_format = (
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
    )

    logging.basicConfig(
        level=level,
        format=log_format,
        filename=log_filepath,
        filemode="w",
        encoding="utf-8",
        force=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)

    for warning_message in warnings:
        root_logger.warning(warning_message)

    root_logger.debug(
        "ロギングを初期化しました。レベル=%s, 決定元=%s, 出力ファイル=%s",
        logging.getLevelName(level),
        source,
        log_filepath,
    )

