"""URL Validator - checks URL accessibility via HEAD/GET requests."""

import logging
import requests
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of URL validation."""
    url: str
    is_valid: bool
    status_code: Optional[int]
    error: Optional[str] = None
    redirect_url: Optional[str] = None


class UrlValidator:
    """URL Validator class for sync script compatibility."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def validate(self, url: str) -> ValidationResult:
        """Validate a URL."""
        return validate_url(url, timeout=self.timeout)


def validate_url(
    url: str,
    timeout: int = 10,
    method: str = "HEAD",
    allow_redirects: bool = True,
) -> ValidationResult:
    """Validate a single URL by making an HTTP request.
    
    Args:
        url: URL to validate
        timeout: Request timeout in seconds
        method: HTTP method ("HEAD" or "GET")
        allow_redirects: Whether to follow redirects
    
    Returns:
        ValidationResult with validation status
    """
    try:
        response = requests.request(
            method=method,
            url=url,
            timeout=timeout,
            allow_redirects=allow_redirects,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NyuusatsuBot/1.0)"},
        )
        
        is_valid = 200 <= response.status_code < 400
        redirect_url = response.url if response.url != url else None
        
        return ValidationResult(
            url=url,
            is_valid=is_valid,
            status_code=response.status_code,
            redirect_url=redirect_url,
            error=None if is_valid else f"HTTP {response.status_code}",
        )
    
    except requests.exceptions.Timeout:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            error=f"Timeout after {timeout}s",
        )
    except requests.exceptions.ConnectionError:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            error="Connection error",
        )
    except requests.exceptions.RequestException as e:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            error=str(e),
        )


def validate_base_url(base_url: str, timeout: int = 10) -> ValidationResult:
    """Validate a base URL (typically the main site)."""
    return validate_url(base_url, timeout=timeout, method="GET")


def validate_bid_url(bid_url: str, timeout: int = 10) -> ValidationResult:
    """Validate a bid/search URL."""
    return validate_url(bid_url, timeout=timeout, method="HEAD")


def validate_registry_entry(entry) -> dict:
    """Validate both base_url and bid_url_pattern for a registry entry."""
    base_result = validate_base_url(entry.base_url)
    bid_result = validate_bid_url(entry.bid_url_pattern)
    
    return {
        "municipality_code": entry.municipality_code,
        "name": entry.name,
        "base_url": base_result,
        "bid_url_pattern": bid_result,
        "both_valid": base_result.is_valid and bid_result.is_valid,
    }