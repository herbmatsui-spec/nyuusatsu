from typing import List, Dict, Any


# 団体別URLテンプレート集（実運用では Agency.base_url と組み合わせて使用）
AGENCY_URL_TEMPLATES: List[Dict[str, Any]] = [
    {
        "agency_type": "municipality",
        "templates": [
            "/yotei.html",
            "/index.html?page=forecast",
            "/info/forecast.html",
            "/procurement/plan.html",
            "/shisetsu/yotei.html",
        ],
        "keyword_hints": ["発注見通し", "入札予定"],
    },
    {
        "agency_type": "prefecture",
        "templates": [
            "/bid/forecast/",
            "/contract/plan/",
            "/yotei/index.html",
        ],
        "keyword_hints": ["年度発注見通し", "調達計画"],
    },
]


def get_templates_for_type(agency_type: str) -> List[str]:
    for entry in AGENCY_URL_TEMPLATES:
        if entry["agency_type"] == agency_type:
            return entry["templates"]
    return []


def get_forecast_url_candidates(base_url: str, agency_type: str = "municipality") -> List[str]:
    templates = get_templates_for_type(agency_type)
    return [f"{base_url.rstrip('/')}{t}" for t in templates]
