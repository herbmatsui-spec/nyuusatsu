import os
import hashlib
import aiohttp
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from config_dir import AppConfig
from utils.forecast_logger import ForecastLogger


class ForecastDownloader:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.logger = ForecastLogger("Downloader")
        self.temp_dir = Path(self.config.forecast_crawl.forecast_pdf_temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def download_pdf(self, url: str, agency_id: int) -> Optional[Dict[str, Any]]:
        if not url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': self.config.crawler.user_agent
                }
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.config.crawler.pdf_timeout)) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to download PDF", url=url, status=response.status)
                        return None

                    content = await response.read()
                    content_hash = hashlib.sha256(content).hexdigest()

                    filename = f"forecast_{agency_id}_{content_hash[:16]}.pdf"
                    filepath = self.temp_dir / filename

                    with open(filepath, 'wb') as f:
                        f.write(content)

                    return {
                        'url': url,
                        'filename': filename,
                        'filepath': str(filepath),
                        'sha256': content_hash,
                        'file_size': len(content)
                    }

        except asyncio.TimeoutError:
            self.logger.error(f"Download timeout", url=url)
            return None
        except Exception as e:
            self.logger.error(f"Download failed", url=url, error=str(e))
            return None

    async def download_html(self, url: str) -> Optional[str]:
        if not url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': self.config.crawler.user_agent
                }
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.config.crawler.request_timeout)) as response:
                    if response.status != 200:
                        return None

                    content = await response.text()
                    return content

        except Exception as e:
            self.logger.error(f"HTML download failed", url=url, error=str(e))
            return None

    def cleanup_temp_files(self, older_than_hours: int = 24):
        import time
        current_time = time.time()
        cutoff = current_time - (older_than_hours * 3600)

        for filepath in self.temp_dir.glob("*.pdf"):
            if filepath.stat().st_mtime < cutoff:
                try:
                    filepath.unlink()
                    self.logger.info(f"Cleaned up old file", filepath=str(filepath))
                except Exception as e:
                    self.logger.error(f"Cleanup failed", filepath=str(filepath), error=str(e))