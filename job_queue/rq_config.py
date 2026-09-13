import redis
from redis import Redis
from rq import Queue, Worker
from config_dir import AppConfig

class RQConfig:
    """
    Redis RQ (RQ) の接続およびキュー設定を管理するクラス。
    """
    def __init__(self):
        self.config = AppConfig()
        self.redis_conn = Redis(
            host=self.config.redis.host,
            port=self.config.redis.port,
            db=self.config.redis.db,
            decode_responses=True
        )

    def get_queue(self, queue_name: str) -> Queue:
        """指定された名前のRQキューを返す"""
        return Queue(queue_name, connection=self.redis_conn)

# グローバル設定インスタンス
rq_config = RQConfig()
