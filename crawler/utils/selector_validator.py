"""
Selector validation utility for GEPS selectors.
"""
from typing import List, Tuple, Dict, Any
from pathlib import Path
from bs4 import BeautifulSoup
import yaml


class SelectorValidator:
    """セレクタ設定の妥当性を検証するクラス。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @classmethod
    def from_file(cls, path: Path) -> "SelectorValidator":
        """YAMLファイルからバリデータを作成する。"""
        with path.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
        return cls(config)

    def validate(self) -> Dict[str, Any]:
        """全セレクタを検証する。"""
        results = {
            "valid": True,
            "selector_count": 0,
            "errors": [],
            "warnings": [],
        }
        
        pages = self.config.get("pages", {})
        for page_type, fields in pages.items():
            for field_name, selectors in fields.items():
                candidates = self._flatten(selectors)
                results["selector_count"] += len(candidates)
                
                for selector in candidates:
                    # 基本的な構文チェック
                    if not self._is_valid_selector_syntax(selector):
                        results["valid"] = False
                        results["errors"].append(f"Invalid selector syntax: {selector}")
        
        return results

    def validate_against_html(self, html: str) -> Dict[str, Any]:
        """実際のHTMLに対してセレクタを検証する。"""
        results = {
            "valid": True,
            "matches": [],
            "errors": [],
        }
        
        pages = self.config.get("pages", {})
        for page_type, fields in pages.items():
            for field_name, selectors in fields.items():
                candidates = self._flatten(selectors)
                
                for selector in candidates:
                    is_valid, count = validate_selector(html, selector)
                    results["matches"].append({
                        "page_type": page_type,
                        "field": field_name,
                        "selector": selector,
                        "is_valid": is_valid,
                        "match_count": count,
                    })
                    if not is_valid:
                        results["warnings"].append(
                            f"Selector '{selector}' ({page_type}.{field_name}) matched 0 elements"
                        )
        
        return results

    def _flatten(self, value: Any) -> List[str]:
        """セレクタ値を平坦化して候補リストを返す。"""
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            out: List[str] = []
            for item in value:
                out.extend(self._flatten(item))
            return out
        return []

    def _is_valid_selector_syntax(self, selector: str) -> bool:
        """基本的なCSSセレクタ構文チェック。"""
        try:
            # 空文字列や明らかに無効なものを除外
            if not selector or selector.strip() == "":
                return False
            # 簡易的な構文チェック: 開き括弧と閉じ括弧のバランス
            if selector.count("[") != selector.count("]"):
                return False
            if selector.count("(") != selector.count(")"):
                return False
            # BeautifulSoupでパースしてみる
            BeautifulSoup("", "html.parser").select(selector)
            return True
        except Exception:
            return False


def validate_selector(html: str, selector: str) -> Tuple[bool, int]:
    """
    Validate a CSS selector against HTML.
    
    Args:
        html: HTML string to validate against
        selector: CSS selector string
        
    Returns:
        Tuple of (is_valid, match_count) where is_valid is True if selector matches at least one element
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        matches = soup.select(selector)
        return len(matches) > 0, len(matches)
    except Exception:
        # If selector syntax is invalid, return False
        return False, 0


def validate_selectors(html: str, selectors: List[str]) -> List[Tuple[str, bool, int]]:
    """
    Validate a list of selectors against HTML.
    
    Args:
        html: HTML string to validate against
        selectors: List of CSS selector strings
        
    Returns:
        List of tuples (selector, is_valid, match_count)
    """
    results = []
    for selector in selectors:
        is_valid, count = validate_selector(html, selector)
        results.append((selector, is_valid, count))
    return results


def find_first_valid_selector(html: str, selectors: List[str]) -> Tuple[str, int]:
    """
    Find the first valid selector from a list (ordered by priority).
    
    Args:
        html: HTML string to validate against
        selectors: List of CSS selector strings in priority order
        
    Returns:
        Tuple of (first_valid_selector, match_count) or ("", 0) if none valid
    """
    for selector in selectors:
        is_valid, count = validate_selector(html, selector)
        if is_valid:
            return selector, count
    return "", 0