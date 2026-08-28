import re
from typing import List, Optional

class TextChunker:
    """
    テキストを意味のあるセクションに分割し、LLMへ送る前に最適化するクラス。
    """
    def __init__(self, max_chars: int = 12000, priority_keywords: Optional[List[str]] = None):
        self.max_chars = max_chars
        self.priority_keywords = priority_keywords or [
            "予算", "予定価格", "資格", "等級", "納期", "履行期間", "成果物", "作業内容"
        ]
    
    def split_by_sections(self, text: str) -> List[str]:
        if not text:
            return []
        
        pattern = r'(?:^|\n\s*)(?:第?\d+章|^\d+\.\d*\s|[A-Z]{2,}|[a-z]+:)'
        matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
        
        if not matches:
            return [text]
        
        chunks = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
        
        return chunks if chunks else [text]

    def prepare_for_llm(
        self,
        text: str,
        priority_keywords: Optional[List[str]] = None,
    ) -> str:
        keywords = priority_keywords if priority_keywords is not None else self.priority_keywords
        chunks = self.split_by_sections(text)
        
        if not chunks:
            return text[:self.max_chars]
            
        priority_chunks = []
        other_chunks = []
        
        for chunk in chunks:
            if any(kw in chunk for kw in keywords):
                priority_chunks.append(chunk)
            else:
                other_chunks.append(chunk)
        
        combined = "\n\n".join(priority_chunks + other_chunks)
        
        return combined[:self.max_chars]