import codecs
import io
import re
import time
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler
from crawler.utils.date_parser import parse_date_string
from utils.string_normalizer import StringNormalizer
from scripts.validate_crawler_config import load_config, require_valid_config, safe_http_url, validation_result


def origin(url):
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)


def metadata_charset(content):
    if isinstance(content, bytes):
        if content.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return "utf-16"
        content = content[:8192].decode("ascii", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")
    for meta in soup.find_all("meta"):
        charset = meta.get("charset")
        if not charset and str(meta.get("http-equiv", "")).lower() == "content-type":
            match = re.search(r'charset\s*=\s*["\']?([\w-]+)', meta.get("content", ""), re.I)
            charset = match.group(1) if match else None
        if charset:
            try:
                return codecs.lookup(charset).name
            except LookupError:
                pass
    match = re.search(r'<\?xml[^>]*encoding\s*=\s*["\']([\w-]+)', content, re.I)
    if match:
        try:
            return codecs.lookup(match.group(1)).name
        except LookupError:
            pass
    return None


def detect_charset(content):
    declared = metadata_charset(content)
    if declared:
        return declared
    try:
        content.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    response = requests.Response()
    response._content = content
    detected = response.apparent_encoding
    for charset in (detected, "cp932", "euc-jp", "utf-8"):
        if charset:
            try:
                content.decode(charset)
                return codecs.lookup(charset).name
            except (UnicodeDecodeError, LookupError):
                pass
    return "utf-8"


class ConfigDrivenCrawler(BaseCrawler):
    def __init__(self, config_path=None, start_date=None, end_date=None, config=None, **kwargs):
        source = str(config_path) if config_path is not None else "<config>"
        supplied = config if config is not None else self._load_config(config_path)
        require_valid_config(supplied, source, strict=False)
        self.config = deepcopy(supplied)
        self.validation = validation_result(self.config, source, strict=False)
        normalizer = StringNormalizer(self.config.get("agency_name_aliases"))
        if "agency_name" in self.config:
            self.config["agency_name"] = normalizer.normalize(self.config["agency_name"])
        parent = self.config.get("parent_id", "")
        if isinstance(parent, str) and parent.startswith("name:"):
            self.config["parent_id"] = "name:" + normalizer.normalize(parent[5:])
        self.config.setdefault("detail_fields", {})
        settings = self.config.get("crawl_settings", {})
        for key in ("retry", "timeout", "delay", "backoff", "backoff_jitter", "rate_limit"):
            if key in settings:
                kwargs.setdefault(key, settings[key])
        self.max_depth = max(0, int(kwargs.pop("max_depth", settings.get("max_depth", 2))))
        self.user_agent = kwargs.pop("user_agent", settings.get("user_agent", "ConfigDrivenCrawler/1.0"))
        super().__init__(start_date=start_date, end_date=end_date, **kwargs)
        self.list_selector = self.config.get("list_item_selector", self.config.get("list_selector"))
        self.detail_selector = self.config.get("detail_selector")
        self.pagination_selector = self.config.get("pagination_selector")
        self.base_url = self.config.get("base_url", "")
        self.list_url = self.config.get("list_url") or self.config.get("start_url") or self.base_url
        self.page_format = self.config.get("page_format", "html")
        pagination = self.config.get("pagination", {})
        self.pagination_selectors = pagination.get("next_button_selectors", [])
        if isinstance(self.pagination_selectors, str):
            self.pagination_selectors = [self.pagination_selectors]
        if self.pagination_selector:
            self.pagination_selectors = [self.pagination_selector, *self.pagination_selectors]
        self.max_pages = max(0, int(pagination.get("max_pages", 100)))
        dynamic = self.config.get("dynamic_links", {})
        attrs = dynamic if isinstance(dynamic, list) else list(dynamic.values())
        self.dynamic_link_attrs = [attr for attr in attrs if isinstance(attr, str) and re.fullmatch(r"data-[\w-]+", attr)]
        self._current_url = None
        self._last_response_url = None

    def _load_config(self, path):
        return load_config(path)

    def _decode_response(self, response):
        content = response.content
        encoding = self.config.get("encoding", {})
        if isinstance(encoding, str):
            encoding = {"preferred": encoding, "auto_detect": False}
        header = re.search(r'charset\s*=\s*["\']?([\w-]+)', response.headers.get("Content-Type", ""), re.I)
        candidates = []
        if encoding.get("auto_detect", True):
            candidates.extend([header.group(1) if header else None, metadata_charset(content), response.apparent_encoding])
        candidates.extend([encoding.get("preferred"), *encoding.get("fallback_encodings", ["utf-8", "cp932", "euc-jp"])])
        for charset in candidates:
            if charset:
                try:
                    return content.decode(charset)
                except (LookupError, UnicodeDecodeError):
                    pass
        return content.decode("utf-8", errors="replace")

    def fetch(self, url):
        url = safe_http_url(url)
        if not url:
            raise ValueError("Only HTTP(S) URLs are supported")
        self._last_response_url = None
        for attempt in range(max(1, int(self.retry))):
            try:
                current = url
                visited = set()
                for _ in range(6):
                    if current in visited:
                        raise ValueError("Redirect loop")
                    visited.add(current)
                    if self._rate_limiter:
                        self._rate_limiter.throttle_sync(current)
                    if self.delay:
                        time.sleep(self.delay)
                    proxy = self._proxy or self._proxy_manager.get_next_proxy()
                    response = requests.get(current, timeout=self.timeout,
                                            headers={"User-Agent": self.user_agent},
                                            proxies={"http": proxy, "https": proxy} if proxy else None,
                                            allow_redirects=False)
                    try:
                        response.raise_for_status()
                        if 300 <= response.status_code < 400:
                            target = safe_http_url(response.headers.get("Location"), current)
                            if not target or origin(target) != origin(url):
                                raise ValueError("Unsafe or cross-origin redirect")
                            current = target
                            continue
                        self._last_response_url = current
                        if urlsplit(current).path.lower().endswith(".pdf") or "application/pdf" in response.headers.get("Content-Type", "").lower():
                            import pdfplumber
                            with pdfplumber.open(io.BytesIO(response.content)) as document:
                                return "\n".join(page.extract_text() or "" for page in document.pages)
                        return self._decode_response(response)
                    finally:
                        response.close()
                raise ValueError("Redirect limit exceeded")
            except requests.RequestException:
                if attempt + 1 >= max(1, int(self.retry)):
                    raise
                time.sleep(self.backoff * (2 ** attempt))

    def _element_url(self, element, current_url):
        for attr in ("href", *self.dynamic_link_attrs):
            url = safe_http_url(element.get(attr), current_url)
            if url:
                return url
        return None

    def parse_list(self, html, current_url=None):
        current_url = current_url or self._current_url or self.list_url or self.base_url
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(self.list_selector) if self.list_selector else []
        candidates = []
        for element in elements:
            candidates.append(element)
            candidates.extend(element.find_all("a"))
        pdf = self.config.get("pdf_detection", {})
        keywords = pdf.get("text_keywords", [])
        extension = pdf.get("extension_pattern", ".pdf").lower()
        for element in soup.find_all(True):
            url = self._element_url(element, current_url)
            if not url:
                continue
            if any(element.get(attr) for attr in self.dynamic_link_attrs) or (
                pdf and (urlsplit(url).path.lower().endswith(extension)
                         or any(keyword in element.get_text(" ", strip=True) for keyword in keywords))
            ):
                candidates.append(element)
        pagination_elements = {id(element) for selector in self.pagination_selectors
                               for element in soup.select(selector)}
        links = []
        seen = set()
        for element in candidates:
            if id(element) in pagination_elements:
                continue
            url = self._element_url(element, current_url)
            if url and url not in seen:
                links.append(url)
                seen.add(url)
        return links

    def parse_detail(self, html):
        from crawler.parsers.field_normalizer import TRANSFORM_MAP

        soup = BeautifulSoup(html, "html.parser")
        detail_fields = self.config.get("detail_fields", {})
        if not detail_fields:
            detail = soup.select_one(self.detail_selector) if self.detail_selector else None
            return (detail or soup).get_text(separator="\n", strip=True)
        result = {}
        for name, field in detail_fields.items():
            elements = soup.select(field["selector"])
            multiple = field.get("multiple", False)
            if not multiple:
                elements = elements[:1]
            values = []
            for element in elements:
                attr = field.get("attr", "text")
                value = element.get_text(strip=True) if attr == "text" else element.get(attr)
                transform = TRANSFORM_MAP.get(field.get("transform"))
                if transform and value is not None:
                    value = transform(value)
                values.append(value)
            if field.get("required") and (not values or all(value is None or value == "" for value in values)):
                raise ValueError(f"Required field {name} not found in HTML")
            result[name] = values if multiple else (values[0] if values else None)
        return result

    def extract_item_date(self, item):
        if isinstance(item, dict):
            value = item.get("date_text") or item.get("announcement_date") or item.get("deadline")
            if isinstance(value, date):
                return value
            return parse_date_string(str(value)) if value else None
        return None

    def _get_next_page_url(self, html, current_url, visited=None):
        soup = BeautifulSoup(html, "html.parser")
        for selector in self.pagination_selectors:
            for element in soup.select(selector):
                url = self._element_url(element, current_url)
                if url and origin(url) == origin(current_url) and url != current_url and url not in (visited or set()):
                    return url
        return None

    def crawl_range(self, start_url=None, start_date=None, end_date=None):
        original = self.start_date, self.end_date, self._current_url
        self.start_date = start_date if start_date is not None else self.start_date
        self.end_date = end_date if end_date is not None else self.end_date
        try:
            current = safe_http_url(start_url or self.list_url)
            if not current:
                raise ValueError("A supplied HTTP(S) start URL is required")
            first_origin = origin(current)
            visited = set()
            seen_links = set()
            result = []
            page_count = 0
            while current and page_count < self.max_pages and self.max_depth > 0:
                if current in visited or origin(current) != first_origin:
                    break
                visited.add(current)
                self._last_response_url = None
                html = self.fetch(current)
                page_count += 1
                resolved = self._last_response_url or current
                if resolved != current and resolved in visited:
                    break
                current = resolved
                visited.add(current)
                self._current_url = current
                items = self.parse_list(html)
                for item in self._filter_by_date_range(items, self.start_date, self.end_date):
                    if not isinstance(item, str) or item not in seen_links:
                        result.append(item)
                        if isinstance(item, str):
                            seen_links.add(item)
                if self.start_date and self._should_stop_early(items, self.start_date):
                    break
                current = self._get_next_page_url(html, current, visited)
            return result
        finally:
            self.start_date, self.end_date, self._current_url = original

    def crawl(self, start_url=None):
        links = self.crawl_range(start_url)
        if self.max_depth < 2:
            return links
        items = []
        for link in links:
            item = self.parse_detail(self.fetch(link))
            if isinstance(item, dict):
                item.setdefault("source_url", link)
                item.setdefault("agency_name", self.config.get("agency_name", ""))
            items.append(item)
        return self._filter_by_date_range(items, self.start_date, self.end_date)

    def save(self, items, repository):
        upsert = getattr(repository, "upsert_bid", None)
        if callable(upsert):
            for item in items:
                upsert(item)
        elif repository.__class__.__name__ == "AwardResultRepository":
            for item in items:
                repository.create(**item)
        else:
            raise ValueError(f"Unsupported repository type: {repository.__class__.__name__}")
