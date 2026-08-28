import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database.models.agency import Agency
from database.models.agency_category import AgencyCategory
from crawler.models.crawl_result import CrawlResult

logger = logging.getLogger(__name__)

class GEPSMappingService:
    """
    GEPSから抽出された結果を標準化されたAgencyモデルにマッピングし、DBに保存するサービス。
    """
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_category(self, category_name: str) -> AgencyCategory:
        """カテゴリ名からカテゴリIDを取得、なければ作成する"""
        category = self.session.query(AgencyCategory).filter_by(name=category_name).first()
        if not category:
            logger.info(f"Creating new category: {category_name}")
            category = AgencyCategory(name=category_name)
            self.session.add(category)
            self.session.flush()
        return category

    def map_crawl_result_to_agency(self, result: CrawlResult) -> Agency:
        """
        CrawlResultをAgencyモデルに変換して保存する。
        GEPSの場合、categoryは'国'として扱う。
        """
        agency_name = result.agency_name or "GEPS"
        
        # 既存の機関があるか確認
        agency = self.session.query(Agency).filter_by(name=agency_name).first()
        
        if not agency:
            logger.info(f"Creating new agency for GEPS: {agency_name}")
            # '国'カテゴリを取得
            national_category = self.get_or_create_category("国")
            
            agency = Agency(
                name=agency_name,
                type="ministry",
                region="全国",
                base_url="https://www.geps.go.jp",
                category_id=national_category.id,
                priority_level="高"
            )
            self.session.add(agency)
            self.session.flush()
        
        return agency

    def process_geps_results(self, results: List[CrawlResult]):
        """
        GEPSの結果リストを処理し、機関をDBに登録する。
        """
        processed_count = 0
        for result in results:
            try:
                agency = self.map_crawl_result_to_agency(result)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error mapping result {result.url}: {e}")
        
        self.session.commit()
        logger.info(f"Successfully processed {processed_count} GEPS results into agencies.")
        return processed_count
