import asyncio
import httpx
import logging
from typing import Tuple, Optional, List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from database.repositories import get_active_agency_urls

# ロギング設定
logger = logging.getLogger("url_probe")

@dataclass
class ProbeResult:
    url: str
    is_reachable: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    response_time: Optional[float] = None

async def probe_url(url: str, timeout: float = 10.0) -> ProbeResult:
    """
    指定されたURLにHTTPリクエストを送り、到達可能かを確認する。
    HEADリクエストを優先し、不可の場合はGETで試行する。
    """
    start_time = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            # 効率のためまずは HEAD リクエストを試行
            try:
                response = await client.head(url, timeout=timeout)
                status_code = response.status_code
            except httpx.RequestError:
                # HEADが拒否されるサイトが多いため GET でリトライ
                response = await client.get(url, timeout=timeout)
                status_code = response.status_code
            
            response_time = asyncio.get_event_loop().time() - start_time
            
            # 2xx, 3xx は到達可能と判定
            return ProbeResult(
                url=url,
                is_reachable=200 <= status_code < 400,
                status_code=status_code,
                response_time=response_time
            )
    except httpx.TimeoutException:
        return ProbeResult(url=url, is_reachable=False, error="Timeout", response_time=asyncio.get_event_loop().time() - start_time)
    except Exception as e:
        return ProbeResult(url=url, is_reachable=False, error=str(e), response_time=asyncio.get_event_loop().time() - start_time)

async def probe_all_urls(session: Session, timeout: float = 10.0, concurrency: int = 5) -> List[ProbeResult]:
    """
    DBから取得した全有効URLに対して並列にプローブを実行する。
    """
    agency_urls = get_active_agency_urls(session)
    if not agency_urls:
        logger.info("No active agency URLs found in database.")
        return []

    logger.info(f"Starting probe for {len(agency_urls)} URLs with concurrency={concurrency}")
    
    semaphore = asyncio.Semaphore(concurrency)

    async def sem_probe(url):
        async with semaphore:
            return await probe_url(url, timeout=timeout)

    tasks = [sem_probe(url) for _, url in agency_urls]
    results = await asyncio.gather(*tasks)
    
    return results
