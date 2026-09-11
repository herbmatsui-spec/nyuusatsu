#!/usr/bin/env python3
"""Mock repository for testing"""

class MockBidRepository:
    def __init__(self):
        self.saved_items = []
    
    def save_bid(self, session, bid):
        """Mock save_bid method that records the bid"""
        self.saved_items.append(bid)
        print(f"Saved bid: {bid}")
        return bid
    
    def get_session(self):
        """Mock session getter"""
        class MockSession:
            def add(self, obj):
                pass
            def commit(self):
                pass
            def refresh(self, obj):
                pass
        return MockSession()

# Test the save functionality
if __name__ == "__main__":
    from crawler.config_driven_crawler import ConfigDrivenCrawler
    
    # Create a mock repository
    mock_repo = MockBidRepository()
    
    # Create a ConfigDrivenCrawler instance (with dummy config)
    crawler = ConfigDrivenCrawler("/dummy/config.yaml")
    
    # Test data
    test_item = {
        "field1": 1234567,  # Already processed by normalize_amount
        "field2": "2026-08-27",  # Already processed by normalize_date
        "field3": "平成元年",  # Already processed by normalize_whitespace
    }
    
    print("Testing crawler.save method...")
    try:
        # This should work now
        crawler.save([test_item], repository=mock_repo)
        print("✅ Save method executed successfully")
        print("Saved items:", len(mock_repo.saved_items))
        if mock_repo.saved_items:
            print("First saved item:", mock_repo.saved_items[0])
    except Exception as e:
        print("❌ Error in save method:", e)
        import traceback
        traceback.print_exc()
"
