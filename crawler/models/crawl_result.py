from dataclasses import dataclass
from typing import Optional

@dataclass
class CrawlResult:
    title: str
    url: str
    agency_name: str
    publish_date: str = "不明"
    depth: int = 0
    parent_url: str = ""
    is_pdf_link: bool = False
    category: Optional[str] = None
