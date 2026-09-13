"""URLバリデーター。

HEADリクエストを試し、405/403等で失敗した場合は軽量GETでフォールバックして
URLの到達可否を判定する。タイムアウトを短めに設定し、失敗はスキップ可能にする。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}


@dataclass
class ValidationResult:
    url: str
    is_valid: bool
    status_code: Optional[int]
    content_type: Optional[str]
    error: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.is_valid


class UrlValidator:
    """URL到達可否をHEAD→GETフォールバックで検証する。"""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        headers: Optional[dict] = None,
        verify: bool = True,
    ) -> None:
        self.timeout = timeout
        self.headers = headers or DEFAULT_HEADERS
        self.verify = verify

    def validate(self, url: str, method: str = "head") -> ValidationResult:
        if not url:
            return ValidationResult(url=url, is_valid=False, status_code=None, content_type=None, error="empty url")

        if method.lower() != "get":
            try:
                resp = requests.head(
                    url, timeout=self.timeout, headers=self.headers, allow_redirects=True, verify=self.verify
                )
                if resp.status_code < 400:
                    return ValidationResult(
                        url=url, is_valid=True, status_code=resp.status_code,
                        content_type=resp.headers.get("Content-Type"),
                    )
                if resp.status_code not in (403, 405, 400, 404):
                    return ValidationResult(
                        url=url, is_valid=False, status_code=resp.status_code,
                        content_type=resp.headers.get("Content-Type"), error=f"HEAD {resp.status_code}",
                    )
            except requests.RequestException as e:
                logger.debug("HEAD failed for %s: %s", url, e)

        return self._validate_get(url)

    def _validate_get(self, url: str) -> ValidationResult:
        try:
            resp = requests.get(
                url, timeout=self.timeout, headers=self.headers, allow_redirects=True, verify=self.verify
            )
            is_valid = resp.status_code < 400
            if not is_valid:
                logger.debug("GET %s -> %d", url, resp.status_code)
            return ValidationResult(
                url=url, is_valid=is_valid, status_code=resp.status_code,
                content_type=resp.headers.get("Content-Type"),
                error=None if is_valid else f"GET {resp.status_code}",
            )
        except requests.RequestException as e:
            return ValidationResult(url=url, is_valid=False, status_code=None, content_type=None, error=str(e))


def validate_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Optional[str]]:
    """便利関数: (is_valid, error_message)。"""
    result = UrlValidator(timeout=timeout).validate(url)
    return result.is_valid, result.error
