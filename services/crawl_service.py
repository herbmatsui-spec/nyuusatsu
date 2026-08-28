from typing import List, Optional
from sqlalchemy.orm import Session
from database.models.crawl import CrawlHistory, CrawledUrl, SystemSetting
from datetime import datetime

class CrawlService:
    def __init__(self, session: Session):
        self.session = session

    def record_crawl_history(self, url_count: int, new_count: int, status: str, error_message: Optional[str] = None):
        history = CrawlHistory(
            crawl_time=datetime.utcnow(),
            url_count=url_count,
            new_count=new_count,
            status=status,
            error_message=error_message
        )
        self.session.add(history)
        self.session.commit()

    def get_crawl_history(self, limit: int = 50) -> List[CrawlHistory]:
        return self.session.query(CrawlHistory).order_by(CrawlHistory.crawl_time.desc()).limit(limit).all()

    def set_setting(self, key: str, value: str):
        setting = self.session.query(SystemSetting).filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = SystemSetting(key=key, value=value)
            self.session.add(setting)
        self.session.commit()

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        setting = self.session.query(SystemSetting).filter_by(key=key).first()
        return setting.value if setting else default
