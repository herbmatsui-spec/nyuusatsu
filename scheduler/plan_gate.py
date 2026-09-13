"""プランゲート - 機能制限とプランベースアクセス制御 (Step 44)。"""

from enum import Enum
from typing import Optional
from functools import wraps
from fastapi import HTTPException, Request

from scheduler.auth_decorator import get_current_user, ENABLE_AUTH


class PlanTier(str, Enum):
    """サブスクリプションプラン階層。"""
    FREE = "free"
    STANDARD = "standard"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Feature(str, Enum):
    """制御対象機能。"""
    # スケジューラ機能
    SCHEDULER_START = "scheduler_start"
    SCHEDULER_STOP = "scheduler_stop"
    SCHEDULER_JOB_LIST = "scheduler_job_list"
    SCHEDULER_JOB_ADD = "scheduler_job_add"
    SCHEDULER_JOB_REMOVE = "scheduler_job_remove"
    SCHEDULER_SYNC = "scheduler_sync"
    
    # クロール機能
    CRAWL_MANUAL = "crawl_manual"
    CRAWL_SCHEDULED = "crawl_scheduled"
    CRAWL_FORECAST = "crawl_forecast"
    CRAWL_AWARD = "crawl_award"
    
    # バックフィル
    BACKFILL_RUN = "backfill_run"
    BACKFILL_RETRY = "backfill_retry"
    BACKFILL_SCHEDULE = "backfill_schedule"
    
    # メトリクス・アラート
    METRICS_COLLECT = "metrics_collect"
    METRICS_VIEW = "metrics_view"
    ALERT_EVALUATE = "alert_evaluate"
    ALERT_CONFIG = "alert_config"
    
    # ヘルスチェック・DLQ
    HEALTH_CHECK = "health_check"
    DLQ_VIEW = "dlq_view"
    DLQ_RETRY = "dlq_retry"


# プラン別機能マトリックス
PLAN_FEATURES = {
    PlanTier.FREE: {
        Feature.SCHEDULER_JOB_LIST,
        Feature.METRICS_VIEW,
        Feature.HEALTH_CHECK,
        Feature.DLQ_VIEW,
    },
    PlanTier.STANDARD: {
        Feature.SCHEDULER_START,
        Feature.SCHEDULER_STOP,
        Feature.SCHEDULER_JOB_LIST,
        Feature.SCHEDULER_JOB_ADD,
        Feature.SCHEDULER_JOB_REMOVE,
        Feature.SCHEDULER_SYNC,
        Feature.CRAWL_MANUAL,
        Feature.CRAWL_SCHEDULED,
        Feature.METRICS_COLLECT,
        Feature.METRICS_VIEW,
        Feature.ALERT_EVALUATE,
        Feature.HEALTH_CHECK,
        Feature.DLQ_VIEW,
        Feature.DLQ_RETRY,
    },
    PlanTier.PRO: {
        Feature.SCHEDULER_START,
        Feature.SCHEDULER_STOP,
        Feature.SCHEDULER_JOB_LIST,
        Feature.SCHEDULER_JOB_ADD,
        Feature.SCHEDULER_JOB_REMOVE,
        Feature.SCHEDULER_SYNC,
        Feature.CRAWL_MANUAL,
        Feature.CRAWL_SCHEDULED,
        Feature.CRAWL_FORECAST,
        Feature.CRAWL_AWARD,
        Feature.BACKFILL_RUN,
        Feature.BACKFILL_RETRY,
        Feature.BACKFILL_SCHEDULE,
        Feature.METRICS_COLLECT,
        Feature.METRICS_VIEW,
        Feature.ALERT_EVALUATE,
        Feature.ALERT_CONFIG,
        Feature.HEALTH_CHECK,
        Feature.DLQ_VIEW,
        Feature.DLQ_RETRY,
    },
    PlanTier.ENTERPRISE: set(Feature),  # 全機能
}


class PlanGate:
    """プランベースの機能アクセス制御。"""
    
    def __init__(self, current_plan: PlanTier = PlanTier.FREE):
        self.current_plan = current_plan
        self.allowed_features = PLAN_FEATURES.get(current_plan, set())
    
    def can_access(self, feature: Feature) -> bool:
        """機能へのアクセス可否を判定。"""
        return feature in self.allowed_features
    
    def require_feature(self, feature: Feature) -> None:
        """機能アクセスを要求、不可なら例外。"""
        if not self.can_access(feature):
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature.value}' requires plan upgrade. "
                       f"Current: {self.current_plan.value}, Required: {self._min_plan_for_feature(feature).value}"
            )
    
    def _min_plan_for_feature(self, feature: Feature) -> PlanTier:
        """機能を利用するために必要な最小プランを取得。"""
        for tier in [PlanTier.FREE, PlanTier.STANDARD, PlanTier.PRO, PlanTier.ENTERPRISE]:
            if feature in PLAN_FEATURES.get(tier, set()):
                return tier
        return PlanTier.ENTERPRISE
    
    def get_available_features(self) -> set[Feature]:
        """利用可能な機能セットを取得。"""
        return self.allowed_features.copy()
    
    def get_upgrade_info(self, feature: Feature) -> dict:
        """機能利用のためのアップグレード情報を取得。"""
        min_plan = self._min_plan_for_feature(feature)
        return {
            "feature": feature.value,
            "current_plan": self.current_plan.value,
            "required_plan": min_plan.value,
            "available_in": [t.value for t in PlanTier if feature in PLAN_FEATURES.get(t, set())],
        }


# グローバルインスタンス（実行時にプラン設定で初期化）
_plan_gate: Optional[PlanGate] = None


def init_plan_gate(plan: PlanTier) -> PlanGate:
    """プランゲートを初期化。"""
    global _plan_gate
    _plan_gate = PlanGate(plan)
    return _plan_gate


def get_plan_gate() -> Optional[PlanGate]:
    """初期化済みのプランゲートを取得。"""
    return _plan_gate


def require_feature(feature: Feature):
    """FastAPIデコレータ: 機能アクセス制限。"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not ENABLE_AUTH:
                return await func(request, *args, **kwargs)
            
            plan_gate = get_plan_gate()
            if plan_gate is None:
                # 初期化されていない場合はデフォルトFREEとして扱う
                plan_gate = PlanGate(PlanTier.FREE)
            
            plan_gate.require_feature(feature)
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_user_plan(request: Request) -> PlanTier:
    """リクエストからユーザーのプランを取得（将来拡張: JWTから取得等）。"""
    # ヘッダーからプラン取得（開発用）
    plan_header = request.headers.get("X-User-Plan")
    if plan_header:
        try:
            return PlanTier(plan_header.lower())
        except ValueError:
            pass
    
    # デフォルトはFREE
    return PlanTier.FREE


def get_user_plan_gate(request: Request) -> PlanGate:
    """リクエストからユーザーのプランゲートを取得。"""
    plan = get_user_plan(request)
    return PlanGate(plan)