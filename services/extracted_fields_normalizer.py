import ast
import json
import logging
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from utils.budget_parser import parse_budget
from utils.date_parser import parse_date

logger = logging.getLogger(__name__)

_MISSING = {"", "none", "null", "n/a", "unknown", "不明", "記載なし", "未記載", "未取得", "未定", "-", "―"}
_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:億円|万円|千円|円)?"
_EXCLUSIVE = r"(?:税抜(?:き)?|税別|消費税(?:及び地方消費税)?を含まない|非課税|不課税)"
_INCLUSIVE = r"(?:税込(?:み)?|内税|消費税(?:及び地方消費税)?を含む)"
_DATE = r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{4}年\d{1,2}月\d{1,2}日|(?:令和|平成|昭和)(?:元|\d{1,2})年\d{1,2}月\d{1,2}日|[RHSrhs]\d{1,2}\.\d{1,2}\.\d{1,2})"
_DATE_TOKEN = rf"({_DATE})(?:\s*\([月火水木金土日](?:曜日)?\))?"
_DATE_LABEL = r"(?:(?:納期(?:限)?|納入期限|納品期限|履行期限|履行期間|契約期間|完了期限|delivery_deadline)\s*[:：]?\s*)?"


def normalize_text(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = unicodedata.normalize("NFKC", value).strip()
        if text.lower() in _MISSING:
            logger.warning("%s is missing; storing NULL", field)
            return None
        if text.startswith(("[", "{")):
            try:
                decoded = json.loads(text)
            except (ValueError, TypeError):
                try:
                    decoded = ast.literal_eval(text)
                except (ValueError, SyntaxError, TypeError, RecursionError):
                    logger.warning("Unsupported %s serialization; storing NULL", field)
                    return None
            return normalize_text(decoded, field)
        return text
    if isinstance(value, (list, tuple)):
        if any(item is not None and not isinstance(item, str) for item in value):
            logger.warning("Unsupported %s list; storing NULL", field)
            return None
        items = [normalize_text(item, field) for item in value]
        return "\n".join(dict.fromkeys(item for item in items if item)) or None
    logger.warning("Unsupported %s type; storing NULL", field)
    return None


def normalize_budget(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        logger.warning("Unsupported budget boolean; storing NULL")
        return None
    text: Optional[str]
    if isinstance(value, (int, float, Decimal)):
        text = str(value)
    else:
        text = normalize_text(value, "budget_amount")
    if text is None:
        return None
    text = unicodedata.normalize("NFKC", text)
    amount = None
    if re.search(_INCLUSIVE, text):
        candidates = []
        for clause in re.split(r"[、;\n]|,(?!\d{3}(?:\D|$))", text):
            suffix = re.fullmatch(rf"\s*({_AMOUNT})\s*\(\s*{_EXCLUSIVE}\s*\)\s*", clause)
            prefix = re.fullmatch(rf"\s*{_EXCLUSIVE}\s*[:：]?\s*({_AMOUNT})\s*", clause)
            candidate = suffix or prefix
            if candidate:
                candidates.append(candidate.group(1))
        if len(candidates) == 1:
            amount = candidates[0]
    else:
        match = re.fullmatch(
            rf"\s*(?:(?:予算(?:額)?|予定価格|上限(?:額)?|金額)\s*[:：]?\s*)?"
            rf"(?:{_EXCLUSIVE}\s*[:：]?\s*)?({_AMOUNT})"
            rf"\s*(?:\(?\s*{_EXCLUSIVE}\s*\)?)?\s*", text
        )
        if match:
            amount = match.group(1)
    if amount is not None:
        compact = re.sub(r"[\s,]", "", amount)
        match = re.fullmatch(r"(\d+(?:\.\d+)?)(億円|万円|千円|円)?", compact)
        if match:
            try:
                multiplier = {"億円": 100_000_000, "万円": 10_000, "千円": 1_000}.get(match.group(2), 1)
                exact = Decimal(match.group(1)) * multiplier
                parsed = parse_budget(compact)
                if exact == exact.to_integral_value() and 0 <= exact <= 2**63 - 1:
                    if parsed == int(exact):
                        return parsed
            except (InvalidOperation, ValueError, OverflowError):
                pass
    logger.warning("Unsupported or ambiguous budget_amount; storing NULL")
    return None


def _parse_explicit_date(value: str) -> Optional[date]:
    era = re.fullmatch(r"(令和|平成|昭和)(元|\d+)年(\d+)月(\d+)日", value)
    short = re.fullmatch(r"([RHSrhs])(\d+)\.(\d+)\.(\d+)", value)
    match = era or short
    if match:
        offsets = {"令和": 2018, "平成": 1988, "昭和": 1925, "R": 2018, "H": 1988, "S": 1925}
        year = 1 if match.group(2) == "元" else int(match.group(2))
        if year < 1:
            return None
        value = f"{offsets[match.group(1).upper()] + year:04d}-{int(match.group(3)):02d}-{int(match.group(4)):02d}"
    parts = re.fullmatch(r"(\d{4})(?:年|[-/])(\d{1,2})(?:月|[-/])(\d{1,2})日?", value)
    if not parts:
        return None
    try:
        validated = date(*(int(part) for part in parts.groups()))
    except ValueError:
        return None
    if match:
        limits = {
            2018: (date(2019, 5, 1), date.max),
            1988: (date(1989, 1, 8), date(2019, 4, 30)),
            1925: (date(1926, 12, 25), date(1989, 1, 7)),
        }
        lower, upper = limits[offsets[match.group(1).upper()]]
        if not lower <= validated <= upper:
            return None
    return parse_date(validated.isoformat())


def normalize_delivery_deadline(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_text(value, "delivery_deadline")
    if text is None:
        return None
    single = re.fullmatch(rf"{_DATE_LABEL}{_DATE_TOKEN}\s*(?:まで|限り)?", text)
    if single and not re.match(r"(?:履行期間|契約期間)", text):
        parsed = _parse_explicit_date(single.group(1))
        if parsed:
            return parsed
    period = re.fullmatch(
        rf"{_DATE_LABEL}(?:{_DATE_TOKEN}|(契約(?:締結日?|日)|契約締結の日|着手日))"
        rf"\s*(?:から|[~〜～]|\s[-–—]\s)\s*{_DATE_TOKEN}\s*(?:まで|限り)?", text
    )
    if period:
        start = _parse_explicit_date(period.group(1)) if period.group(1) else None
        end = _parse_explicit_date(period.group(3))
        if end and (period.group(2) or (start and start <= end)):
            return end
    logger.warning("Unsupported or ambiguous delivery_deadline; storing NULL")
    return None


def normalize_extracted_fields(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict) or data.get("success") is False or data.get("error") or data.get("status") in ("failed", "error"):
        logger.warning("Extraction failed or returned unsupported data; storing NULL fields")
        data = {}
    budget_value = data.get("budget", data.get("budget_amount"))
    budget = str(budget_value) if isinstance(budget_value, (int, float, Decimal)) and not isinstance(budget_value, bool) else normalize_text(budget_value, "budget")
    deadline_value = data.get("deadline")
    deadline = deadline_value.isoformat() if isinstance(deadline_value, date) else normalize_text(deadline_value, "deadline")
    return {
        "budget": budget,
        "budget_amount": normalize_budget(budget_value),
        "qualifications": normalize_text(data.get("qualifications"), "qualifications"),
        "deadline": deadline,
        "delivery_deadline": normalize_delivery_deadline(data.get("delivery_deadline", deadline_value)),
        "deliverables": normalize_text(data.get("deliverables"), "deliverables"),
    }
