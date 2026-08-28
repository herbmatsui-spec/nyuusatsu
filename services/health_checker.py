import os
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from database.session import get_db
from database.models.pipeline_metric import PipelineMetric

logger = logging.getLogger("HealthChecker")

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    message: str = ""
    last_checked: datetime = field(default_factory=datetime.utcnow)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_checked": self.last_checked.isoformat(),
            "details": self.details
        }


class HealthChecker:
    """
    システムの各コンポーネント（Redis、DB、キュー、スケジューラ等）および
    パイプラインアクティビティのヘルス状態をチェックするクラス。
    """
    def __init__(self, queue_alert_threshold: int = 100):
        self.queue_alert_threshold = queue_alert_threshold

    def check_redis(self) -> ComponentHealth:
        """Redis 接続と疎通確認を行う"""
        try:
            import redis
            from database.redis_conn import redis_conn
            redis_conn.ping()
            return ComponentHealth("Redis", HealthStatus.HEALTHY)
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return ComponentHealth("Redis", HealthStatus.UNHEALTHY, message=f"Redis connection failed: {e}")

    def check_queue_depth(self) -> ComponentHealth:
        """RQ キューの滞留件数をチェックする"""
        try:
            from rq import Queue
            from database.redis_conn import redis_conn
            
            queue_names = ["crawl_tasks", "download_tasks", "analysis_tasks", "notification_tasks"]
            details = {}
            max_depth = 0
            
            for name in queue_names:
                q = Queue(name, connection=redis_conn)
                depth = len(q)
                details[name] = {
                    "waiting": depth,
                    "started": q.started_job_registry.count,
                    "failed": q.failed_job_registry.count
                }
                if depth > max_depth:
                    max_depth = depth
                    
            if max_depth > self.queue_alert_threshold:
                return ComponentHealth(
                    "QueueDepth", 
                    HealthStatus.DEGRADED, 
                    message=f"Queue size exceeded threshold ({max_depth} > {self.queue_alert_threshold})",
                    details=details
                )
            return ComponentHealth("QueueDepth", HealthStatus.HEALTHY, details=details)
        except Exception as e:
            logger.error(f"Queue depth health check failed: {e}")
            return ComponentHealth("QueueDepth", HealthStatus.UNHEALTHY, message=f"Failed to fetch queue depth: {e}")

    def check_database(self) -> ComponentHealth:
        """SQLite データベース接続と書き込みテストを行う"""
        try:
            with get_db() as session:
                # 簡易クエリ実行
                session.execute("SELECT 1").first()
                return ComponentHealth("Database", HealthStatus.HEALTHY)
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth("Database", HealthStatus.UNHEALTHY, message=f"Database query failed: {e}")

    def check_scheduler(self) -> ComponentHealth:
        """スケジューラプロセスの動作状況を確認する"""
        try:
            from scheduler import scheduler_manager
            # スケジューラが起動しているか確認
            is_running = scheduler_manager._is_running
            jobs = scheduler_manager.list_jobs()
            details = {"jobs_count": len(jobs), "is_running": is_running}
            
            if not is_running:
                return ComponentHealth("Scheduler", HealthStatus.UNHEALTHY, message="Scheduler is not running", details=details)
            return ComponentHealth("Scheduler", HealthStatus.HEALTHY, details=details)
        except Exception as e:
            logger.error(f"Scheduler health check failed: {e}")
            # scheduler_manager が初期化されていない等の場合
            return ComponentHealth("Scheduler", HealthStatus.DEGRADED, message=f"Scheduler manager not accessible: {e}")

    def check_pipeline_recency(self) -> ComponentHealth:
        """パイプラインが直近で動いているか（ハングや停止がないか）をメトリクスから確認する"""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            with get_db() as session:
                # 直近24時間以内に記録されたクロールまたは解析のメトリクスがあるか
                recent_metric = session.query(PipelineMetric).filter(
                    PipelineMetric.timestamp >= cutoff,
                    PipelineMetric.stage.in_(["crawl", "analysis"])
                ).first()
                
                details = {
                    "recent_metric_found": recent_metric is not None,
                    "last_metric_time": recent_metric.timestamp.isoformat() if recent_metric else None
                }
                
                if not recent_metric:
                    return ComponentHealth(
                        "PipelineRecency",
                        HealthStatus.DEGRADED,
                        message="No pipeline activity recorded in the last 24 hours.",
                        details=details
                    )
                return ComponentHealth("PipelineRecency", HealthStatus.HEALTHY, details=details)
        except Exception as e:
            logger.error(f"Pipeline recency health check failed: {e}")
            return ComponentHealth("PipelineRecency", HealthStatus.DEGRADED, message=f"Failed to check activity: {e}")

    def check_award_data_quality(self) -> ComponentHealth:
        """落札結果DBのデータ品質をチェックする"""
        try:
            from services.award_quality_checker import get_quality_report
            with get_db() as session:
                report = get_quality_report(session)
            issues = 0
            details = {
                "total_awards": report.get("total_awards", 0),
                "missing_award_rate": report.get("missing_award_rate", 0),
                "missing_budget": report.get("missing_budget", 0),
                "missing_winner": report.get("missing_winner", 0),
                "duplicate_source_urls": report.get("duplicate_source_urls", 0),
            }
            issues = (
                report.get("missing_award_rate", 0)
                + report.get("missing_budget", 0)
                + report.get("missing_winner", 0)
                + report.get("duplicate_source_urls", 0)
            )
            if issues > 0:
                return ComponentHealth(
                    "AwardDataQuality",
                    HealthStatus.DEGRADED,
                    message=f"Data quality issues found: {issues}",
                    details=details,
                )
            return ComponentHealth("AwardDataQuality", HealthStatus.HEALTHY, details=details)
        except Exception as e:
            logger.error(f"Award data quality check failed: {e}")
            return ComponentHealth("AwardDataQuality", HealthStatus.UNHEALTHY, message=f"Quality check error: {e}")

    def check_qualification_system(self) -> ComponentHealth:
        """資格システムの健全性をチェックする"""
        try:
            from database.models import QualificationTag, CompanyProfile
            with get_db() as session:
                tag_count = session.query(QualificationTag).count()
                profile_count = session.query(CompanyProfile).count()
            details = {
                "qualification_tags": tag_count,
                "company_profiles": profile_count,
            }
            if tag_count == 0:
                return ComponentHealth(
                    "QualificationSystem",
                    HealthStatus.DEGRADED,
                    message="Qualification tags master is empty",
                    details=details,
                )
            if profile_count == 0:
                return ComponentHealth(
                    "QualificationSystem",
                    HealthStatus.DEGRADED,
                    message="Company profile not registered",
                    details=details,
                )
            return ComponentHealth("QualificationSystem", HealthStatus.HEALTHY, details=details)
        except Exception as e:
            logger.error(f"Qualification system check failed: {e}")
            return ComponentHealth("QualificationSystem", HealthStatus.UNHEALTHY, message=f"Check error: {e}")

    def check_all(self) -> dict:
        """すべてのコンポーネントをチェックし、統合ステータスを返す"""
        checks = [
            self.check_redis(),
            self.check_queue_depth(),
            self.check_database(),
            self.check_scheduler(),
            self.check_pipeline_recency(),
            self.check_award_data_quality(),
            self.check_qualification_system(),
        ]
        
        overall = HealthStatus.HEALTHY
        components = {}
        
        for check in checks:
            components[check.name] = check.to_dict()
            if check.status == HealthStatus.UNHEALTHY:
                overall = HealthStatus.UNHEALTHY
            elif check.status == HealthStatus.DEGRADED and overall != HealthStatus.UNHEALTHY:
                overall = HealthStatus.DEGRADED
                
        return {
            "overall_status": overall.value,
            "timestamp": datetime.utcnow().isoformat(),
            "components": components
        }
