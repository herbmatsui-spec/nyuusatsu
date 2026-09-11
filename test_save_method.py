#!/usr/bin/env python3

"""Test the save method functionality""

class MockBidRepository:
    def __init__(self):
        self.saved_items = []

    def save_bid(self, session, bid):
        self.saved_items.append(bid)
        return bid

    def get_session(self):
        class MockSession:
            def add(self, obj):
                pass
            def commit(self):
                pass
            def refresh(self, obj):
                pass
        return MockSession


# Test the save functionality
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    from crawler.config_driven_crawler import ConfigDrivenCrawler

# Create a mock repository
mock_repo = MockBidRepository()

# Create a ConfigDrivenCrawler instance
crawler = ConfigDrivenCrawler("/dummy/config.yaml")

# Test data
test_item = {
