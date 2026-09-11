"""品質アラート評価サービス

- `evaluate(metric_name, value)` がしきい値を比較し、'warn', 'alert', 'ok' を返す
- `send_alert(metric_name, value, level)` が Slack と LINE の両方に通知を送信し、
  Redis で重複抑制を行い、QualityAlert を DB に保存する
"""

import os
import logging
from datetime import datetime, date

from database.redis_conn import redis_conn

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLDS_PATH = "config/quality_thresholds.yaml"


def _load_yaml_thresholds(path: str | None = None) -> dict:
    """config/quality_thresholds.yaml からしきい値を読み込む。失敗時は空 dict。"""
    path = path or os.getenv("QUALITY_THRESHOLDS_PATH", _DEFAULT_THRESHOLDS_PATH)
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("metrics", {}) or {}
    except FileNotFoundError:
        logger.debug("Thresholds YAML not found at %s", path)
    except Exception as e:
        logger.warning("Failed to load thresholds YAML: %s", e)
    return {}


def _evaluate_value(metric_name: str, value: float, thresholds: dict) -> tuple[str, float | None]:
    """YAML しきい値に基づいてレベルを判定。しきい値が存在しない場合は ('ok', None)。"""
    cfg = thresholds.get(metric_name)
    if not cfg:
        return "ok", None
    warn = cfg.get("warning")
    critical = cfg.get("critical")
    lower_is_worse = cfg.get("lower_is_worse", False)
    if lower_is_worse:
        if critical is not None and value <= critical:
            return "alert", critical
        if warn is not None and value <= warn:
            return "warn", warn
    else:
        if critical is not None and value >= critical:
            return "alert", critical
        if warn is not None and value >= warn:
            return "warn", warn
    return "ok", None


class QualityAlertService:
    def __init__(self, session, thresholds_path: str | None = None):
        self.session = session
        self._yaml_thresholds = None
        self._thresholds_path = thresholds_path

    @property
    def yaml_thresholds(self) -> dict:
        if self._yaml_thresholds is None:
            self._yaml_thresholds = _load_yaml_thresholds(self._thresholds_path)
        return self._yaml_thresholds

    def _db_threshold(self, metric_name: str) -> float | None:
        """DB の QualityThreshold フォールバック。"""
        try:
            from database.models.quality_threshold import QualityThreshold
            t = self.session.query(QualityThreshold).filter_by(metric_name=metric_name).first()
            return t.alert_at if t else None
        except Exception:
            return None

    def evaluate(self, metric_name: str, value: float) -> str:
        """しきい値を取得し、レベルを判定。存在しない場合は 'ok' を返す。"""
        level, _ = self._evaluate_value(metric_name, value, self.yaml_thresholds)
        if level != "ok":
            return level
        return self._evaluate_db(metric_name, value)

    def _evaluate_db(self, metric_name: str, value: float) -> str:
        """DB QualityThreshold によるフォールバック評価。"""
        from database.models.quality_threshold import QualityThreshold
        threshold = self.session.query(QualityThreshold).filter_by(metric_name=metric_name).first()
        if not threshold:
            return "ok"
        if value >= threshold.alert_at:
            return "alert"
        if value >= threshold.warn_at:
            return "warn"
        return "ok"

    def _get_threshold_value(self, metric_name: str, level: str) -> float:
        """通知レベルに対応するしきい値を取得（YAML 優先）"""
        cfg = self.yaml_thresholds.get(metric_name, {})
        if level == "alert":
            key = "critical" if "critical" in cfg else "alert_at"
            return cfg.get(key, cfg.get("alert_at", 0.0))
        return cfg.get("warning", cfg.get("warn_at", 0.0))

    def _check_redis_dedupe(self, metric_name: str) -> bool:
        """Redis に今日既に通知済みかをチェック。未通知ならキーを設定して True を返す。"""
        if not redis_conn:
            return True
        today = date.today().isoformat()
        key = f"alert_sent:{metric_name}:{today}"
        try:
            ttl = 24 * 3600
            if redis_conn.exists(key):
                return False
            redis_conn.setex(key, ttl, "1")
            return True
        except Exception as e:
            logger.warning("Redis dedup check failed (proceeding): %s", e)
            return True

    def _send_slack_alert(self, message: str) -> bool:
        """Slack に通知。未設定時は失敗しない。"""
        try:
            from notifier import SlackNotificationService
            service = SlackNotificationService()
            if not service.webhook_url:
                logger.info("Slack webhook not configured; skipping.")
                return False
            return bool(service.send(message))
        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False

    def _send_line_alert(self, message: str) -> bool:
        """LINE に通知。未設定時は失敗しない。"""
        try:
            from notifier import LineNotificationService
            service = LineNotificationService()
            if not service.access_token or not service.user_id:
                logger.info("LINE credentials not configured; skipping.")
                return False
            return bool(service.send(message))
        except Exception as e:
            logger.error("LINE notification failed: %s", e)
            return False

    def send_alert(self, metric_name: str, value: float, level: str) -> bool:
        """レベルに応じて通知を送信。 level は 'warn' または 'alert'。
        Redis 重複抑制と DB 保存を行う。"""
        if level not in ("warn", "alert"):
            return False

        if not self._check_redis_dedupe(metric_name):
            logger.info("Alert already sent today for %s; skipping.", metric_name)
            return False

        threshold_val = self._get_threshold_value(metric_name, level)
        level_label = "警告" if level == "warn" else "アラート"
        message = (
            f"⚠️ 【品質{level_label}】\n"
            f"メトリクス: {metric_name}\n"
            f"値: {value}\n"
            f"しきい値 ({level_label}): {threshold_val}\n"
            f"時刻: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        slack_ok = self._send_slack_alert(message)
        line_ok = self._send_line_alert(message)

        try:
            from database.models.quality_alert import QualityAlert
            alert = QualityAlert(
                metric=metric_name,
                level=level,
                value=value,
                threshold=threshold_val,
                sent_at=datetime.utcnow(),
            )
            self.session.add(alert)
            self.session.commit()
        except Exception as e:
            logger.error("Failed to save QualityAlert: %s", e)
            try:
                self.session.rollback()
            except Exception:
                pass

        if not slack_ok and not line_ok:
            logger.warning("Both Slack and LINE notification failed for %s", metric_name)
            return False
        return True

    def get_recent_alerts(self, limit: int = 50, level: str | None = None, metric: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None) -> list:
        """最近のアラート履歴を取得（フィルタ: レベル、メトリクス、期間）。"""
        from database.models.quality_alert import QualityAlert
        query = self.session.query(QualityAlert).order_by(QualityAlert.sent_at.desc())
        if level:
            query = query.filter(QualityAlert.level == level)
        if metric:
            query = query.filter(QualityAlert.metric == metric)
        if start_date:
            query = query.filter(QualityAlert.sent_at >= start_date)
        if end_date:
            query = query.filter(QualityAlert.sent_at <= end_date)
        return query.limit(limit).all()
