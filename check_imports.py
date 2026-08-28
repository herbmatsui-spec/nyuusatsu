import sys
print("Python version:", sys.version)

try:
    from database.engine import get_session
    print("✓ database.engine imported")
except Exception as e:
    print("✗ database.engine import error:", e)

try:
    from database.repositories import BidRepository
    print("✓ database.repositories imported")
except Exception as e:
    print("✗ database.repositories import error:", e)

try:
    from geps_crawler import GEPSCrawler
    print("✓ geps_crawler imported")
except Exception as e:
    print("✗ geps_crawler import error:", e)

try:
    from config import AppConfig
    print("✓ config imported")
except Exception as e:
    print("✗ config import error:", e)

try:
    from services.bid_service import BidService
    print("✓ services.bid_service imported")
except Exception as e:
    print("✗ services.bid_service import error:", e)

try:
    from services.analysis_service import AnalysisService
    print("✓ services.analysis_service imported")
except Exception as e:
    print("✗ services.analysis_service import error:", e)
