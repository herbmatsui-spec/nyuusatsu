"""
Step 53: URL監視結果の単体テスト
- probe_url 関数の各種HTTPステータスコードに対する判定ロジックを検証
- タイムアウト発生時のハンドリングを検証
"""
import asyncio
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from services.url_probe_common import probe_url, ProbeResult


class TestProbeUrl:
    """probe_url 関数の単体テスト"""

    @pytest.mark.asyncio
    async def test_probe_url_success_200(self):
        """正常系: HTTP 200 の場合、到達可能と判定されること"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_url("https://example.com", timeout=5.0)

            assert result.is_reachable is True
            assert result.status_code == 200
            assert result.error is None
            assert result.response_time is not None

    @pytest.mark.asyncio
    async def test_probe_url_success_301(self):
        """正常系: HTTP 301 (リダイレクト) の場合、到達可能と判定されること"""
        mock_response = MagicMock()
        mock_response.status_code = 301

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_url("https://example.com/redirect", timeout=5.0)

            assert result.is_reachable is True
            assert result.status_code == 301

    @pytest.mark.asyncio
    async def test_probe_url_failure_404(self):
        """異常系: HTTP 404 の場合、到達不可能と判定されること"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_url("https://example.com/notfound", timeout=5.0)

            assert result.is_reachable is False
            assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_probe_url_failure_500(self):
        """異常系: HTTP 500 の場合、到達不可能と判定されること"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            result = await probe_url("https://example.com/error", timeout=5.0)

            assert result.is_reachable is False
            assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_probe_url_timeout(self):
        """異常系: タイムアウト発生時、適切にハンドリングされること"""
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):
            result = await probe_url("https://example.com/timeout", timeout=0.1)

            assert result.is_reachable is False
            assert result.error == "Timeout"
            assert result.status_code is None

    @pytest.mark.asyncio
    async def test_probe_url_get_fallback(self):
        """エッジケース: HEADが拒否されGETで成功する場合"""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 405  # Method Not Allowed
        
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, side_effect=httpx.RequestError("Method Not Allowed")):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_get_response):
                result = await probe_url("https://example.com/no-head", timeout=5.0)

                assert result.is_reachable is True
                assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_probe_url_connection_error(self):
        """異常系: 接続エラー発生時、適切にハンドリングされること"""
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, side_effect=httpx.ConnectError("Connection refused")):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("Connection refused")):
                result = await probe_url("https://example.com/down", timeout=5.0)

                assert result.is_reachable is False
                assert "Connection refused" in (result.error or "")
