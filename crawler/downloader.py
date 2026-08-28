# 改善点1 ステップ3-6: crawler/downloader.py
# PDFファイルを安全にダウンロードし、リトライ機能を持つダウンローダーを実装します。

import urllib.request
import urllib.error
import time
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Downloader")

class Downloader:
    """
    PDFファイルをダウンロードし、ローカルに保存するクラス。
    """
    def __init__(self, timeout: int = 30, max_retries: int = 3, insecure: bool = False):
        self.timeout = timeout
        self.max_retries = max_retries
        self.insecure = insecure
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

    def download_pdf(self, url: str, dest_path: Path) -> bool:
        """
        URLからPDFをダウンロードし、指定したパスに保存する。
        指数バックオフによるリトライ機能を備える。
        """
        import ssl
        logger.info(f"Downloading PDF from {url} to {dest_path}")

        # SSL証明書検証をスキップするコンテキスト
        ssl_context = None
        if self.insecure:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=self.timeout, context=ssl_context) as response:
                    # コンテンツタイプを確認 (簡易的なチェック)
                    content_type = response.info().get_content_type()
                    if 'application/pdf' not in content_type and 'application/octet-stream' not in content_type:
                        logger.warning(f"Unexpected content type {content_type} for URL {url}")
                        # PDFでない場合でも、一旦保存して後段のpdfplumberで検証させる
                    
                    with open(dest_path, 'wb') as f:
                        f.write(response.read())
                
                logger.info(f"Successfully downloaded {url} on attempt {attempt}")
                return True

            except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
                logger.warning(f"Attempt {attempt}/{self.max_retries} failed to download {url}: {e}")
                if attempt < self.max_retries:
                    sleep_time = 2 ** attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Max retries reached. Failed to download {url}")
        
        return False


import hashlib
from pathlib import Path

# crawler.pipeline が期待するインターフェース
#   download(url) -> (success: bool, file_path: str|None, sha256: str|None, error_msg: str|None)
class PDFDownloader:
    """pipeline.download_pdf_task が期待するインターフェースを提供するラッパー。"""

    def __init__(self, timeout: int = 30, max_retries: int = 3, dest_dir: str = "./temp_pdfs", insecure: bool = True):
        self._inner = Downloader(timeout=timeout, max_retries=max_retries, insecure=insecure)
        self.dest_dir = Path(dest_dir)
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha256_of(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def download(self, url: str):
        try:
            # ファイル名をURLから決定（クエリを除去）
            safe_name = url.split("?")[0].rstrip("/").split("/")[-1] or "download.pdf"
            if not safe_name.lower().endswith(".pdf"):
                safe_name += ".pdf"
            dest_path = self.dest_dir / safe_name

            ok = self._inner.download_pdf(url, dest_path)
            if not ok or not dest_path.exists():
                return False, None, None, f"Download failed: {url}"
            sha256 = self._sha256_of(dest_path)
            return True, str(dest_path), sha256, None
        except Exception as e:
            return False, None, None, str(e)
