import pytest
import redis
import json
import time
from typing import Dict, Any
from events.publisher import EventPublisher
from events.redis_publisher import RedisPublisher
from events.redis_subscriber import RedisSubscriber
from events.messaging_config import EventChannels

# Redis接続設定
REDIS_HOST = "localhost"
REDIS_PORT = 6379

@pytest.fixture
def redis_publisher():
    return RedisPublisher(host=REDIS_HOST, port=REDIS_PORT)

@pytest.fixture
def redis_subscriber():
    return RedisSubscriber()

def test_pubsub_flow(redis_publisher, redis_subscriber):
    """
    イベントの発行から受信までのエンドツーエンドフローを検証する。
    """
    # 受信確認用のフラグとデータ
    received_data = {}
    
    def mock_handler(payload: Dict[str, Any]):
        nonlocal received_data
        received_data = payload

    # 1. チャンネルの購読登録
    channel = EventChannels.CRAWL_REQUESTED
    redis_subscriber.subscribe(channel, mock_handler)

    # 2. イベントのパブリッシュ
    test_payload = {
        "trace_id": "test-trace-001",
        "payload": {"agency_id": 123, "prefecture_id": 1}
    }
    redis_publisher.publish(channel, test_payload)

    # 3. 非同期受信待ち (簡易的なポーリング)
    # 本来は listen() はブロッキングするため、別スレッドで回す必要がある
    # このテストでは Redis の pubsub.get_message() 等を用いて同期的に検証する手法を検討
    # ここでは簡略化し、Subscriberの内部ロジックを直接叩くか、
    # 短時間のlistenを想定したモック的な検証を行う
    
    # Subscriberの pubsub.get_message() を直接利用して検証
    message = None
    timeout = 2.0
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        message = redis_subscriber.pubsub.get_message(ignore_subscribe_messages=True)
        if message:
            break
        time.sleep(0.1)

    assert message is not None, "Message was not received from Redis"
    
    # 受信データの検証
    payload = json.loads(message["data"])
    assert payload["trace_id"] == "test-trace-001"
    assert payload["payload"]["agency_id"] == 123

def test_multiple_handlers(redis_publisher, redis_subscriber):
    """
    1つのイベントに対して複数のハンドラが正しく実行されるか検証する。
    """
    results = []
    
    def handler1(p): results.append("h1")
    def handler2(p): results.append("h2")
    
    channel = EventChannels.SYSTEM_ALERT
    redis_subscriber.subscribe(channel, handler1)
    redis_subscriber.subscribe(channel, handler2)
    
    # メッセージ送信
    redis_publisher.publish(channel, {"msg": "test alert"})
    
    # メッセージ取得とディスパッチを手動で実行 (listenループを避けるため)
    message = None
    while not message:
        message = redis_subscriber.pubsub.get_message(ignore_subscribe_messages=True)
        time.sleep(0.1)
    
    redis_subscriber._dispatch(message["channel"], json.loads(message["data"]))
    
    assert "h1" in results
    assert "h2" in results
    assert len(results) == 2
