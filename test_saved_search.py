#!/usr/bin/env python3
import sys
import json
sys.path.insert(0, '/home/herbmatsui/nyuusatsu')

from database.engine import get_session
from services.saved_search_service import SavedSearchService

def test_saved_search():
    # Get a database session
    db = get_session()
    try:
        service = SavedSearchService(db)
        
        # Use user_id = "1" (string) as would be passed from the UI
        user_id = "1"
        name = "テスト検索"
        criteria = {
            "budget": "1000",
            "qualifications": "資格",
            "deadline": "2026-12-31",
            "organization_name": "東京"
        }
        criteria_json = json.dumps(criteria)
        
        # Create a saved search
        saved_search = service.create(user_id=user_id, name=name, criteria_json=criteria_json)
        print(f"Created saved search: id={saved_search.id}, name={saved_search.name}")
        
        # Retrieve active saved searches for the user
        active_searches = service.get_active_by_user(user_id)
        print(f"Active searches for user {user_id}: {len(active_searches)}")
        for ss in active_searches:
            print(f"  - id={ss.id}, name={ss.name}, criteria={ss.criteria_json}")
        
        # Test matching logic
        from database.repositories.bid_repository import BidRepository
        bid_repo = BidRepository(db)
        bids = bid_repo.list_all(limit=5)
        print(f"Number of bids in DB: {len(bids)}")
        if bids:
            bid = bids[0]
            match = service._matches(bid, criteria)
            print(f"Bid {bid.id} matches criteria: {match}")
            # Also test via match_new_bids with a recent since date
            from datetime import datetime, timedelta
            since = datetime.utcnow() - timedelta(days=1)
            matched = service.match_new_bids(saved_search, since)
            print(f"Matched bids since {since}: {len(matched)}")
        
        # Clean up: delete the saved search we created
        db.delete(saved_search)
        db.commit()
        print("Cleaned up test saved search.")
    finally:
        db.close()

if __name__ == "__main__":
    test_saved_search()