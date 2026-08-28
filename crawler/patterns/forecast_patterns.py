from typing import List, Dict, Any


FORECAST_URL_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "発注見通し",
        "patterns": [
            "*://*/*発注見通し*",
            "*://*/*発注予見*",
            "*://*/*発注予測*",
        ],
        "keywords": ["発注見通し", "発注予見", "発注予測"],
        "priority": "high",
    },
    {
        "name": "事業計画",
        "patterns": [
            "*://*/*事業計画*",
            "*://*/*事业计画*",
        ],
        "keywords": ["事業計画", "事业计画"],
        "priority": "medium",
    },
    {
        "name": "入札予定",
        "patterns": [
            "*://*/*入札予定*",
            "*://*/*入札予程*",
        ],
        "keywords": ["入札予定", "入札予程"],
        "priority": "high",
    },
    {
        "name": "工事予定",
        "patterns": [
            "*://*/*工事予定*",
            "*://*/*工事計画*",
        ],
        "keywords": ["工事予定", "工事計画"],
        "priority": "medium",
    },
    {
        "name": "調達予定",
        "patterns": [
            "*://*/*調達予定*",
            "*://*/*物品購入*",
        ],
        "keywords": ["調達予定", "物品購入"],
        "priority": "medium",
    },
    {
        "name": "英語 forecast",
        "patterns": [
            "*://*/*forecast*",
            "*://*/*procurement*plan*",
        ],
        "keywords": ["forecast", "procurement plan"],
        "priority": "low",
    },
    {
        "name": "PDF発注見通し",
        "patterns": [
            "*://*/*.pdf*発注*",
            "*://*/*発注*.pdf",
        ],
        "keywords": ["発注", "pdf"],
        "priority": "high",
    },
]


def get_all_patterns() -> List[str]:
    patterns = []
    for group in FORECAST_URL_PATTERNS:
        patterns.extend(group["patterns"])
    return patterns


def get_patterns_by_priority(priority: str) -> List[Dict[str, Any]]:
    return [p for p in FORECAST_URL_PATTERNS if p["priority"] == priority]


def get_pattern_by_name(name: str) -> Dict[str, Any]:
    for group in FORECAST_URL_PATTERNS:
        if group["name"] == name:
            return group
    return None


def get_all_keywords() -> List[str]:
    keywords = []
    for group in FORECAST_URL_PATTERNS:
        keywords.extend(group["keywords"])
    return list(set(keywords))