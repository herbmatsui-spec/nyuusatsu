import logging
import sys


def get_forecast_logger(name: str = "Forecast") -> logging.Logger:
    logger = logging.getLogger(f"forecast.{name}")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


class ForecastLogger:
    def __init__(self, name: str = "Forecast"):
        self.logger = get_forecast_logger(name)

    def info(self, message: str, **kwargs):
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} {extra_info}".strip() if extra_info else message
        self.logger.info(full_message)

    def warning(self, message: str, **kwargs):
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} {extra_info}".strip() if extra_info else message
        self.logger.warning(full_message)

    def error(self, message: str, **kwargs):
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} {extra_info}".strip() if extra_info else message
        self.logger.error(full_message)

    def debug(self, message: str, **kwargs):
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} {extra_info}".strip() if extra_info else message
        self.logger.debug(full_message)