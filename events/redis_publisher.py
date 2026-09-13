import redis
import json
import logging
from typing import Any, Dict
from events.publisher import EventPublisher
from config_dir import AppConfig

logger = logging.getLogger(__name__)

class RedisPublisher(EventPublisher):
    """
    Redis Pub/Sub を使用したイベント発行の実装。
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.config = AppConfig()
        # config.py の設定を優先し、なければ引数を使用
        redis_host = getattr(self.config, "REDIS_HOST", host)
        redis_port = getattr(self.config, "REDIS_PORT", port)
        
        try:
            self.redis_client = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                db=db, 
                decode_responses=True
            )
            # 接続確認
            self.redis_client.ping()
            logger.info(f"Connected to Redis for publishing at {redis_host}:{redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        イベントをRedisのチャンネルにJSON形式でパブリッシュする。
        """
        try:
            message = json.dumps(payload, ensure_ascii=False)
            # event_type をチャンネル名として使用
            receiver_count = self.redis_client.publish(event_type, message)
            logger.debug(f"Published event {event_type} to {receiver_count} subscribers.")
        except Exception as e:
            logger.error(f"Error publishing event {event_type}: {e}")
            # 商用化に向け、ここでは例外を投げずログ出力にとどめる（発行側を止めないため）
            # 必要に応じて再試行キューに回す実装を後で検討
