
from geps_crawler import CrawlerError, BrowserError, ParsingError, DownloadError
import pytest

def test_exception_hierarchy():
    """例外クラスの継承関係テスト"""
    assert issubclass(BrowserError, CrawlerError)
    assert issubclass(ParsingError, CrawlerError)
    assert issubclass(DownloadError, CrawlerError)

def test_exception_message():
    """例外メッセージが正しく設定されるか"""
    err = BrowserError("ブラウザ初期化失敗")
    assert "ブラウザ初期化失敗" in str(err)

def test_browser_error_catchable_as_crawler_error():
    """BrowserErrorをCrawlerErrorとしてキャッチできるか"""
    try:
        raise BrowserError("test")
    except CrawlerError as e:
        assert "test" in str(e)

def test_download_error_catchable_as_base():
    """DownloadErrorを基底Exceptionとしてキャッチできるか"""
    try:
        raise DownloadError("ダウンロード失敗")
    except Exception as e:
        assert "ダウンロード失敗" in str(e)

def test_parsing_error_raises():
    """ParsingErrorがpytest.raisesで検出されるか"""
    with pytest.raises(ParsingError):
        raise ParsingError("HTMLパース失敗")
