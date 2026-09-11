import redis
import json
import logging
from typing import Any, Dict, Callable, List
from config_dir import AppConfig

logger = logging.getLogger(__name__)

class RedisSubscriber:
    """
    Redis Pub/Sub を使用したイベント購読基盤。
    イベントタイプ（チャンネル）ごとにハンドラを登録し、
    受信したメッセージを適切なハンドラに振り分ける。
    """

    def __init__( the_self):
        the_self.config = AppConfig()
        redis_host = getattr(the_self.config, "REDIS_HOST", "localhost")
        redis_port = getattr(the_self.config, "REDIS_PORT", 6379)
        
        try:
            the_self.redis_client = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                decode_responses=True
            )
            the_self.pubsub = the_self.redis_client.pubsub()
            the_self.handlers: Dict[str, List[Callable]] = {}
            logger.info(f"RedisSubscriber initialized at {redis_host}:{redis_port}")
        except Exception as e:
            logger.error(f"Failed to initialize RedisSubscriber: {e}")
            raise

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        特定のイベントタイプにハンドラを登録する。
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
            # Redisのチャンネルにも購読登録
            self.pubsub.subscribe(event_type)
            logger.info(f"Subscribed to channel: {event_type}")
        
        self.handlers[event_type].append(handler)
        logger.debug(f"Handler registered for event {event_type}")

    def listen(self) -> None:
        """
        メッセージ待機ループ。受信したメッセージを登録済みハンドラに配送する。
        """
        logger.info("RedisSubscriber listening for events...")
        try:
            for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]
                    
                    try:
                        payload = json.loads(data)
                        self._dispatch(channel, payload)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received on channel {channel}: {data}")
        except Exception as e:
            logger.exception(f"Error in RedisSubscriber listen loop: {e}")
            raise

    def _dispatch(self, channel: str, payload: Dict[str, Any]) -> None:
        """
        受信したイベントを登録されているすべてのハンドラに渡す。
        """
        handlers = self.handlers.get(channel, [])
        if not handlers:
            logger.debug(f"No handlers registered for event type: {channel}")
            return

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.exception(f"Error executing handler for {channel}: {e}")

    def unsubscribe_all(self) -> None:
        """すべてのチャンネルから購読を解除する"""
        self.pubsub.unsubscribe()
        logger.info("Unsubscribed from all channels.")
