import logging
import os
from logging.handlers import RotatingFileHandler


def setup_ocr_logging(log_dir: str = "logs", log_level: int = logging.INFO) -> logging.Logger:
    """OCR用のロギング設定を行う"""
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("ocr")
    logger.setLevel(log_level)

    # ファイルハンドラー
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "ocr.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)

    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # フォーマッター
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
