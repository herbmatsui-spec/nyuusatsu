from __future__ import annotations

import re
from typing import List, Optional


class FullTextSearchService:
    def __init__(self):
        self.documents: List[dict] = []

    def index(self, documents: List[dict]):
        self.documents.extend(documents)

    def search(self, query: str, limit: int = 50) -> List[dict]:
        results = []
        pattern = re.compile(query, re.IGNORECASE)
        for doc in self.documents:
            text = doc.get("text", "")
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                snippet = text[start:end]
                results.append({**doc, "snippet": snippet})
            if len(results) >= limit:
                break
        return results
