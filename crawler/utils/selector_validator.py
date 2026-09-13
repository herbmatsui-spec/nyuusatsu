from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from bs4 import BeautifulSoup


class SelectorValidator:
    REQUIRED_PAGES = {"search_form", "search_results", "detail"}
    REQUIRED_FIELDS = {
        "search_form": {"query", "start_date", "end_date", "submit"},
        "search_results": {"item", "title", "organization", "budget", "deadline"},
        "detail": {"title", "organization", "budget", "deadline"},
    }

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @classmethod
    def from_file(cls, path: str | Path) -> "SelectorValidator":
        with Path(path).open(encoding="utf-8") as config_file:
            return cls(yaml.safe_load(config_file) or {})

    @staticmethod
    def _candidates(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            result = []
            for item in value:
                result.extend(SelectorValidator._candidates(item))
            return result
        return []

    def validate(self) -> dict[str, Any]:
        errors = []
        version = self.config.get("selectors_version")
        if not version:
            errors.append("selectors_version is required")
        pages = self.config.get("pages")
        if not isinstance(pages, dict):
            return {"valid": False, "errors": errors + ["pages must be a mapping"]}

        selector_count = 0
        for page_name in self.REQUIRED_PAGES:
            page = pages.get(page_name)
            if not isinstance(page, dict):
                errors.append(f"missing page: {page_name}")
                continue
            required = self.REQUIRED_FIELDS.get(page_name, set())
            for field in sorted(required):
                candidates = self._candidates(page.get(field))
                if not candidates:
                    errors.append(f"missing selector: {page_name}.{field}")
                    continue
                selector_count += len(candidates)
                for selector in candidates:
                    try:
                        BeautifulSoup("<root></root>", "html.parser").select_one(selector)
                    except Exception as e:
                        errors.append(f"invalid selector {page_name}.{field}: {selector}: {e}")

        return {
            "valid": not errors,
            "selectors_version": version,
            "selector_count": selector_count,
            "errors": errors,
        }

    def validate_html(self, html: str, page_type: str | None = None) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        pages = self.config.get("pages", {})
        selected_pages = [page_type] if page_type else list(self.REQUIRED_PAGES)
        results = {}
        matched = 0
        total = 0
        for page_name in selected_pages:
            page = pages.get(page_name, {})
            page_result = {}
            for field, selectors in page.items():
                candidates = self._candidates(selectors)
                field_matched = 0
                for selector in candidates:
                    total += 1
                    try:
                        count = len(soup.select(selector))
                    except Exception:
                        count = 0
                    if count:
                        field_matched += 1
                        matched += 1
                page_result[field] = {
                    "matched": field_matched > 0,
                    "matches": field_matched,
                    "candidates": len(candidates),
                }
            results[page_name] = page_result
        return {
            "valid": matched > 0,
            "match_rate": (matched / total * 100.0) if total else 0.0,
            "matched": matched,
            "total": total,
            "pages": results,
        }


def validate_selector_config(config: dict[str, Any]) -> dict[str, Any]:
    return SelectorValidator(config).validate()


def validate_html_selectors(html: str, config: dict[str, Any], page_type: str | None = None) -> dict[str, Any]:
    return SelectorValidator(config).validate_html(html, page_type=page_type)
