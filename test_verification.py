"""
Bid System Verification Script
=========================
Verify the system's ability to collect, save, summarize, and report bid information.
"""
import os
import sys
import json
import logging
import traceback
from datetime import datetime

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('verification_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_1_database_connection():
    """Test 1: Database connection"""
    logger.info("Test 1: Database Connection")
    
    try:
        from database.engine import get_session
        from database.repositories.bid_repository import BidRepository
        
        with get_session() as db:
            repo = BidRepository(db)
            count = repo.count_all()
            logger.info(f"Database connection successful: Total bids = {count}")
            
            bids = repo.list_all()
            if bids:
                logger.info(f"Sample data retrieved: {len(bids)} items")
            else:
                logger.info("Database is empty.")
        return True
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        logger.error(traceback.format_exc())
        return False


def test_2_crawler_capability():
    """Test 2: Crawler capability"""
    logger.info("Test 2: Crawler Capability")
    
    try:
        from geps_crawler import GEPSCrawler, CrawlerConfig
        
        config = CrawlerConfig()
        crawler = GEPSCrawler(config)
        
        logger.info(f"GEPS Crawler initialized")
        return True
    except Exception as e:
        logger.error(f"Crawler initialization error: {e}")
        logger.error(traceback.format_exc())
        return False


def test_3_llm_service():
    """Test 3: LLM Analysis Service"""
    logger.info("Test 3: LLM Analysis Service")
    
    try:
        from config import AppConfig
        config = AppConfig()
        
        deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
        gemini_key = os.environ.get('GEMINI_API_KEY')
        
        logger.info(f"Configuration loaded")
        logger.info(f"  DeepSeek API key: {'Set' if deepseek_key else 'Not set'}")
        logger.info(f"  Gemini API key: {'Set' if gemini_key else 'Not set'}")
        
        return True
    except Exception as e:
        logger.error(f"LLM service error: {e}")
        logger.error(traceback.format_exc())
        return False


def test_4_bid_service():
    """Test 4: Bid Service (Save/Retrieve)"""
    logger.info("Test 4: Bid Service")
    
    try:
        from database.engine import get_session
        from database.repositories.bid_repository import BidRepository
        from services.bid_service import BidService
        
        with get_session() as db:
            repo = BidRepository(db)
            bid_service = BidService(repo)
            
            all_bids = bid_service.get_all_bids()
            logger.info(f"BidService initialized: {len(all_bids)} bids")
        return True
    except Exception as e:
        logger.error(f"BidService error: {e}")
        logger.error(traceback.format_exc())
        return False


def test_5_analysis_service():
    """Test 5: Analysis/Summary Service"""
    logger.info("Test 5: Analysis/Summary Service")
    
    try:
        from database.engine import get_session
        from services.analysis_service import AnalysisService
        
        with get_session() as db:
            analysis_service = AnalysisService(db)
            overview = analysis_service.get_overview()
            logger.info(f"AnalysisService initialized: Total bids={overview.get('total_bids', 0)}")
        return True
    except Exception as e:
        logger.error(f"AnalysisService error: {e}")
        logger.error(traceback.format_exc())
        return False


def test_6_dashboard():
    """Test 6: Dashboard functionality"""
    logger.info("Test 6: Dashboard Functionality")
    
    try:
        from services.market_intel_service import MarketIntelService
        intel_service = MarketIntelService()
        logger.info(f"MarketIntelService initialized")
        return True
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        logger.error(traceback.format_exc())
        return False


def test_7_local_government_crawler():
    """Test 7: Local Government Crawler"""
    logger.info("Test 7: Local Government Crawler")
    
    from config import AppConfig
    config = AppConfig()
    
    logger.info(f"Target URL: {config.crawler.target_url}")
    
    if "geps.go.jp" in config.crawler.target_url:
        logger.warning("Current crawler is GEPS-specific.")
        logger.warning("Local government (e.g., Uwajima City) support is missing.")
        return False
    else:
        return True


def main():
    """Main verification"""
    logger.info("Bid System Verification Test")
    
    results = {}
    tests = [
        ("Database Connection", test_1_database_connection),
        ("Crawler Capability", test_2_crawler_capability),
        ("LLM Analysis Service", test_3_llm_service),
        ("Bid Service", test_4_bid_service),
        ("Analysis/Summary Service", test_5_analysis_service),
        ("Dashboard", test_6_dashboard),
        ("Local Government Support", test_7_local_government_crawler),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            logger.error(f"{name} test error: {e}")
            logger.error(traceback.format_exc())
            results[name] = False
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    logger.info(f"\nSummary: {passed}/{total} tests passed")
    
    if results.get("Local Government Support") == False:
        logger.info("\nConclusion: Local government (Uwajima City) support is missing.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
