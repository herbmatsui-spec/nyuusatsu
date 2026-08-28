import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import re

class HTMLPatternDetector:
    """
    HTML構造を解析し、入札案件リンクやページネーションのパターンを検出するクラス。
    """
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # 案件リンクによく使われるキーワード（部分一致）
        self.bid_keywords = [
            "入札", "公告", "落札", "結果", "募集", "調達", 
            "tender", "bid", "auction", "procurement"
        ]
        # ページネーションによく使われるキーワード
        self.pagination_keywords = ["次へ", "次ページ", "Next", "＞", ">>", "次へ進む"]

    def detect_bid_link_patterns(self, html: str) -> List[Dict[str, Any]]:
        """
        HTML内のリンクを解析し、入札案件である可能性が高いリンクの共通パターン（CSSセレクタ等）を提案する。
        """
        soup = BeautifulSoup(html, 'html.parser')
        candidates = []
        
        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text(strip=True)
            if any(kw in text for kw in self.bid_keywords):
                # リンクの属性からパターンを抽出（class, idなど）
                pattern = {
                    'text': text,
                    'href': a_tag['href'],
                    'class': a_tag.get('class', []),
                    'id': a_tag.get('id', ''),
                    'parent_class': a_tag.find_parent().get('class', []) if a_tag.find_parent() else [],
                }
                candidates.append(pattern)
        
        return candidates

    def generate_selectors(self, candidates: List[Dict[str, Any]]) -> List[str]:
        """
        検出された候補から、汎用性の高いCSSセレクタを自動生成する。
        """
        selectors = []
        for cand in candidates:
            # 1. IDがある場合は最優先
            if cand['id']:
                selectors.append(f"#{cand['id']}")
                continue
            
            # 2. classがある場合は class 組み合わせを作成
            if cand['class']:
                class_selector = "." + ".".join(cand['class'])
                selectors.append(class_selector)
                
                # 親のclassも組み合わせて精度を上げる
                if cand['parent_class']:
                    parent_selector = "." + ".".join(cand['parent_class'])
                    selectors.append(f"{parent_selector} {class_selector}")
            
            # 3. 特徴的なテキストを含む a タグとしてのセレクタ（擬似的な提案）
            selectors.append(f"a:contains('{cand['text'][:5]}')")
            
        # 重複排除
        return list(set(selectors))

    def analyze_structure(self, html: str) -> Dict[str, Any]:
        """
        ページ全体の構造を分析し、リスト形式のデータがどこに配置されているかを推定する。
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # テーブル構造の検出
        tables = soup.find_all('table')
        table_count = len(tables)
        
        # リスト形式（ul/ol）の検出
        lists = soup.find_all(['ul', 'ol'])
        list_count = len(lists)
        
        # リンク密度の高いエリアを特定
        # (簡易的にタグごとのリンク数をカウント)
        density_map = {}
        for tag in soup.find_all(['div', 'section', 'main']):
            links = tag.find_all('a')
            if len(links) > 5:
                density_map[tag.name] = len(links)

        return {
            'table_count': table_count,
            'list_count': list_count,
            'link_density': density_map,
            'has_pagination': self._has_pagination(html)
        }

    def _has_pagination(self, html: str) -> bool:
        """ページネーションが存在するか判定"""
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text(strip=True)
            if any(kw in text for kw in self.pagination_keywords):
                return True
        return False

    def detect_structure_change(self, old_html: str, new_html: str) -> Dict[str, Any]:
        """
        以前のHTMLと現在のHTMLを比較し、構造的な変更（リンク数の大幅な変動など）を検出する。
        """
        old_soup = BeautifulSoup(old_html, 'html.parser')
        new_soup = BeautifulSoup(new_html, 'html.parser')
        
        old_links = len(old_soup.find_all('a', href=True))
        new_links = len(new_soup.find_all('a', href=True))
        
        # リンク数の変動率を計算
        diff_ratio = 0.0
        if old_links > 0:
            diff_ratio = abs(new_links - old_links) / old_links
            
        # 重要な要素（テーブルやリスト）の数の変化
        old_tables = len(old_soup.find_all('table'))
        new_tables = len(new_soup.find_all('table'))
        
        is_changed = diff_ratio > 0.3 or (old_tables != new_tables)
        
        return {
            'is_changed': is_changed,
            'old_link_count': old_links,
            'new_link_count': new_links,
            'diff_ratio': diff_ratio,
            'table_count_changed': old_tables != new_tables
        }
