"""クローラー基底クラスの基本テスト"""
def test_import():
    """インポートできるかテスト"""
    from crawler.base_crawler import BaseCrawler
    assert BaseCrawler is not None