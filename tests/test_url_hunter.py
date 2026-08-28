import asyncio
import os
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from url_hunter import main_async, save_result, TargetURL
import pytest


@pytest.mark.asyncio
async def test_url_hunter_output(tmp_path):
    os.environ["GEMINI_API_KEY"] = "TEST_KEY"
    target = TargetURL(
        agency_name="Test Agency",
        discovered_url="https://example.com/bid1.pdf",
        confidence_score=90,
        reason="Test reason",
    )
    fake_urls = ["https://example.com/bid1.pdf"]
    fake_page_info = [{"url": fake_urls[0], "title": "Test", "links": [], "pdf_count": 1, "text": "body"}]

    async def fake_search(*args, **kwargs):
        return fake_urls

    async def fake_fetch(*args, **kwargs):
        return fake_page_info[0]

    with patch("url_hunter.search_urls", side_effect=fake_search), \
         patch("url_hunter.fetch_page_info", side_effect=fake_fetch), \
         patch("url_hunter.generate_target_url", return_value=target) as mock_gen, \
         patch("url_hunter.save_result") as mock_save, \
         patch("url_hunter.close_browser", new_callable=AsyncMock):
        await main_async("sample query")
        assert mock_save.called
        saved = mock_save.call_args[0][0]
        assert saved.agency_name == "Test Agency"


if __name__ == "__main__":
    asyncio.run(test_url_hunter_output())
