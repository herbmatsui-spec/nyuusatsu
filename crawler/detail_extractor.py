"""詳細ページ（HTML/PDF）から入札詳細情報を抽出するクラス。

HTMLページおよびPDFファイルから以下の情報を抽出する:
- budget: 予算額
- deadline: 締切日
- qualifications: 参加資格
- deliverables: 成果物/納入物
- announcement_date: 公告日
"""

import re
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BidDetailExtractor:
    """入札詳細ページから情報を抽出するクラス。"""
    
    # 日付パターン（YYYY/MM/DD, YYYY年MM月DD日, YYYY-MM-DD, 和暦 等）
    DATE_PATTERNS = [
        r'\d{4}年\d{1,2}月\d{1,2}日',
        r'\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}',
        r'令和\d{1,2}年\d{1,2}月\d{1,2}日',
        r'平成\d{1,2}年\d{1,2}月\d{1,2}日',
        r'昭和\d{1,2}年\d{1,2}月\d{1,2}日',
        r'[RH]\d{1,2}\.\d{1,2}\.\d{1,2}',
        r'\d{4}\.\d{1,2}\.\d{1,2}',
    ]
    
    # 金額パターン（円, 万円, 億円, 千円 等、カンマ区切り対応）
    AMOUNT_PATTERNS = [
        r'[\d,]+(?:\.\d+)?\s*億円',
        r'[\d,]+(?:\.\d+)?\s*万円',
        r'[\d,]+(?:\.\d+)?\s*千円',
        r'[\d,]+(?:\.\d+)?\s*円',
        r'¥\s*[\d,]+',
        r'(?:金額|予算額|契約金額|見積額|基準価格|予定価格|制限価格)\s*[:：]\s*[\d,]+(?:\.\d+)?\s*(?:円|万円|億円)?',
    ]
    
    # キーワードからフィールドへのマッピング（拡充版）
    KEYWORD_FIELD_MAP = {
        'budget': [
            '予算', '予算額', '金額', '契約金額', '見積額', '基準価格',
            '予定価格', '制限価格', '入札金額', '落札金額', '工事費', '委託費'
        ],
        'deadline': [
            '締切', '締め切り', '期限', '提出期限', '申込期限', '入札期限',
            '開札日', '開札日時', '入札日', '入札日時', '受付期限', '応募期限'
        ],
        'qualifications': [
            '資格', '参加資格', '条件', '要件', '資格要件',
            '入札参加資格', '資格審査', '必要資格', '応募資格', '参加条件'
        ],
        'deliverables': [
            '成果物', '納入物', '納品物', '仕様', '業務内容', '作業内容',
            '工事内容', '委託内容', '調達内容', '購入内容', '仕様書', '設計書'
        ],
        'announcement_date': [
            '公告', '公表', '告示', '公示', '掲載日',
            '公告日', '告示日', '公示日', '掲載開始日', '公表日'
        ],
    }
    
    def __init__(self):
        self.compiled_date_patterns = [re.compile(p) for p in self.DATE_PATTERNS]
        self.compiled_amount_patterns = [re.compile(p) for p in self.AMOUNT_PATTERNS]
    
    def fetch_detail_page(self, url: str, timeout: int = 10) -> Optional[str]:
        """詳細ページのHTMLを取得する。
        
        Args:
            url: 取得対象のURL
            timeout: タイムアウト秒数
            
        Returns:
            HTML文字列、失敗時はNone
        """
        import requests
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, timeout=timeout, headers=headers)
            if response.status_code == 200:
                response.encoding = response.apparent_encoding
                return response.text
            logger.warning(f"Failed to fetch {url}: status {response.status_code}")
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
        return None
    
    def extract_from_html(self, html: str, url: str = "") -> Dict[str, Any]:
        """HTMLから詳細情報を抽出する。
        
        Args:
            html: HTML文字列
            url: ソースURL（ログ用）
            
        Returns:
            抽出されたフィールドの辞書
        """
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        
        result = {}
        
        # 各フィールドを抽出
        result['budget'] = self.extract_budget(text)
        result['deadline'] = self.extract_deadline(text)
        result['qualifications'] = self.extract_qualifications(text)
        result['deliverables'] = self.extract_deliverables(text)
        result['announcement_date'] = self.extract_announcement_date(text)
        
        # テーブル構造からの抽出も試みる
        table_data = self._extract_from_tables(soup)
        for key, value in table_data.items():
            if key not in result or not result[key]:
                result[key] = value
        
        logger.info(f"Extracted from HTML ({url}): {result}")
        return result
    
    def extract_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """PDFファイルから詳細情報を抽出する。
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            抽出されたフィールドの辞書
        """
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            result = {}
            result['budget'] = self.extract_budget(text)
            result['deadline'] = self.extract_deadline(text)
            result['qualifications'] = self.extract_qualifications(text)
            result['deliverables'] = self.extract_deliverables(text)
            result['announcement_date'] = self.extract_announcement_date(text)
            
            logger.info(f"Extracted from PDF ({pdf_path}): {result}")
            return result
        except ImportError:
            logger.warning("pdfplumber not installed, skipping PDF extraction")
            return {}
        except Exception as e:
            logger.warning(f"PDF extraction failed for {pdf_path}: {e}")
            return {}
    
    def extract(self, html: str, url: str = "") -> Dict[str, Any]:
        """HTMLから詳細情報を抽出する（エントリーポイント）。
        
        Args:
            html: HTML文字列
            url: ソースURL
            
        Returns:
            抽出されたフィールドの辞書
        """
        return self.extract_from_html(html, url)
    
    # --- 個別フィールド抽出メソッド ---
    
    def extract_budget(self, text: str) -> Optional[str]:
        """予算額を抽出する。"""
        # キーワード周辺のテキストを探す（より柔軟なパターン）
        for keyword in self.KEYWORD_FIELD_MAP['budget']:
            # キーワードの後に金額があるパターン（コロン、スペース、改行などを許容）
            pattern = rf'{keyword}\s*[:：]?\s*([\d,]+(?:\.\d+)?\s*(?:億円|万円|千円|円))'
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
            
            # キーワードを含む行から金額を探す
            lines = text.split('\n')
            for line in lines:
                if keyword in line:
                    for pattern in self.compiled_amount_patterns:
                        match = pattern.search(line)
                        if match:
                            return match.group(0).strip()
        
        # 金額パターンで最大値を探す（予算らしきもの）
        amounts = []
        for pattern in self.compiled_amount_patterns:
            for match in pattern.finditer(text):
                amounts.append(match.group(0).strip())
        
        if amounts:
            # 最大の金額を返す（億円 > 万円 > 千円 > 円 の順で評価）
            return max(amounts, key=self._parse_amount_value)
        
        return None
    
    def _parse_amount_value(self, amount_str: str) -> float:
        """金額文字列を数値に変換（比較用）。"""
        amount_str = amount_str.replace(',', '').replace('¥', '').strip()
        if '億円' in amount_str:
            return float(amount_str.replace('億円', '')) * 100000000
        elif '万円' in amount_str:
            return float(amount_str.replace('万円', '')) * 10000
        elif '千円' in amount_str:
            return float(amount_str.replace('千円', '')) * 1000
        elif '円' in amount_str:
            return float(amount_str.replace('円', ''))
        return 0
    
    def extract_deadline(self, text: str) -> Optional[str]:
        """締切日を抽出する。"""
        for keyword in self.KEYWORD_FIELD_MAP['deadline']:
            # キーワードの後ろに日付があるパターン（より柔軟なパターン）
            # DATE_PATTERNSの全パターンを試行する
            for date_pat in self.DATE_PATTERNS:
                pattern = rf'{keyword}\s*[:：]?\s*({date_pat})'
                match = re.search(pattern, text)
                if match:
                    return self._normalize_date(match.group(1))
            
            # キーワードを含む行から日付を探す
            lines = text.split('\n')
            for line in lines:
                if keyword in line:
                    for pattern in self.compiled_date_patterns:
                        match = pattern.search(line)
                        if match:
                            return self._normalize_date(match.group(0))
            
            # キーワードの近く（前後50文字）から日付を探す
            pattern = rf'.{{0,50}}{keyword}.{{0,50}}'
            matches = re.findall(pattern, text)
            for match_text in matches:
                for pattern in self.compiled_date_patterns:
                    match = pattern.search(match_text)
                    if match:
                        return self._normalize_date(match.group(0))
        return None
    
    def extract_qualifications(self, text: str) -> Optional[str]:
        """参加資格を抽出する。"""
        for keyword in self.KEYWORD_FIELD_MAP['qualifications']:
            # キーワードを含む段落を抽出（より広い範囲）
            # より広い範囲を広げて抽出（テーブル構造外の記述に対応）
            pattern = rf'({keyword}.*?)(?=\n\n|\Z)'
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
            
            # キーワードを含む行を結合して返す
            lines = text.split('\n')
            relevant_lines = [line.strip() for line in lines if keyword in line]
            if relevant_lines:
                return ' '.join(relevant_lines[:5])  # 最大5行まで
        return None
    
    def extract_deliverables(self, text: str) -> Optional[str]:
        """成果物/納入物を抽出する。"""
        for keyword in self.KEYWORD_FIELD_MAP['deliverables']:
            pattern = rf'(.{{0,200}}{keyword}.{{0,800}})'
            matches = re.findall(pattern, text)
            if matches:
                return max(matches, key=len).strip()
            
            # キーワードを含む行を結合して返す
            lines = text.split('\n')
            relevant_lines = [line.strip() for line in lines if keyword in line]
            if relevant_lines:
                return ' '.join(relevant_lines[:5])
        return None
    
    def extract_announcement_date(self, text: str) -> Optional[str]:
        """公告日を抽出する。"""
        for keyword in self.KEYWORD_FIELD_MAP['announcement_date']:
            pattern = rf'{keyword}\s*[:：]?\s*({self.DATE_PATTERNS[0]})'
            match = re.search(pattern, text)
            if match:
                return self._normalize_date(match.group(1))
            
            lines = text.split('\n')
            for line in lines:
                if keyword in line:
                    for pattern in self.compiled_date_patterns:
                        match = pattern.search(line)
                        if match:
                            return self._normalize_date(match.group(0))
            
            # キーワードの近くから日付を探す
            pattern = rf'.{{0,50}}{keyword}.{{0,50}}'
            matches = re.findall(pattern, text)
            for match_text in matches:
                for pattern in self.compiled_date_patterns:
                    match = pattern.search(match_text)
                    if match:
                        return self._normalize_date(match.group(0))
        return None
    
    def _normalize_date(self, date_str: str) -> str:
        """日付文字列を正規化（YYYY-MM-DD形式）。"""
        # 和暦変換
        date_str = date_str.strip()
        
        # 令和変換（令和X年X月X日, R X.X.X, RXX.XX.XX 等）
        reiwa_match = re.match(r'令和(\d{1,2})年(\d{1,2})月(\d{1,2})日', date_str)
        if reiwa_match:
            year = int(reiwa_match.group(1)) + 2018
            month = int(reiwa_match.group(2))
            day = int(reiwa_match.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
        
        # 令和短縮形（R1.1.1, R01.01.01 等）
        reiwa_short = re.match(r'R(\d{1,2})[.\-](\d{1,2})[.\-](\d{1,2})', date_str)
        if reiwa_short:
            year = int(reiwa_short.group(1)) + 2018
            month = int(reiwa_short.group(2))
            day = int(reiwa_short.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
        
        # 平成変換
        heisei_match = re.match(r'平成(\d{1,2})年(\d{1,2})月(\d{1,2})日', date_str)
        if heisei_match:
            year = int(heisei_match.group(1)) + 1988
            month = int(heisei_match.group(2))
            day = int(heisei_match.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
        
        # 平成短縮形（H31.1.1, H31.01.01 等）
        heisei_short = re.match(r'H(\d{1,2})[.\-](\d{1,2})[.\-](\d{1,2})', date_str)
        if heisei_short:
            year = int(heisei_short.group(1)) + 1988
            month = int(heisei_short.group(2))
            day = int(heisei_short.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
        
        # 昭和変換（念のため）
        showa_match = re.match(r'昭和(\d{1,2})年(\d{1,2})月(\d{1,2})日', date_str)
        if showa_match:
            year = int(showa_match.group(1)) + 1925
            month = int(showa_match.group(2))
            day = int(showa_match.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
        
        # 西暦パターン（YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD 等）
        for sep in ['/', '-', '年', '月', '.']:
            date_str = date_str.replace(sep, '-')
        date_str = date_str.replace('日', '')
        
        parts = date_str.split('-')
        if len(parts) >= 3:
            try:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                if year > 1000:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                pass
        
        return date_str
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """テーブル構造から情報を抽出する。"""
        result = {}
        
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if not th or not td:
                    continue
                
                header = th.get_text(strip=True)
                value = td.get_text(strip=True)
                
                # ヘッダーからフィールドを判定
                for field, keywords in self.KEYWORD_FIELD_MAP.items():
                    if any(kw in header for kw in keywords):
                        if field not in result or not result[field]:
                            result[field] = value
                        break
        
        return result