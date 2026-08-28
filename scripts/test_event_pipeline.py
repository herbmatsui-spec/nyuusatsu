import time
import logging
from typing import Dict, Any
from events.redis_publisher import RedisPublisher
from events.redis_subscriber import RedisSubscriber
from events.messaging_config import EventChannels
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EventPipelineTest")

def test_event_pipeline():
    """
    Phase 1 の完了確認スクリプト。
    Redis Publisher と Subscriber が正しく動作し、イベントが配送されるかを確認する。
    """
    logger.info("Starting Phase 1 Event Pipeline Verification...")
    
    publisher = RedisPublisher()
    subscriber = RedisSubscriber()
    
    # 受信確認用変数
    received_payloads = []

    def mock_handler(payload: Dict[str, Any]):
        logger.info(f"Successfully received event: {payload}")
        received_payloads.append(payload)

    # 1. テスト用チャンネルの購読
    test_channel = EventChannels.SYSTEM_ALERT
    subscriber.subscribe(test_channel, mock_handler)
    
    # 2. テストイベントの発行
    test_event = {
        "event_id": "test-event-001",
        "trace_id": "trace-phase1-complete",
        "timestamp": "2026-07-10T00:00:00Z",
        "payload": {"status": "Phase 1 Validation", "message": "All components connected!"}
    }
    
    logger.info(f"Publishing test event to {test_channel}...")
    publisher.publish(test_channel, test_event)
    
    # 3. 受信確認 (ポーリング)
    timeout = 5.0
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Subscriberの内部メッセージキューを確認
        msg = subscriber.pubsub.get_message(ignore_subscribe_messages=True)
        if msg:
            payload = json.loads(msg["data"])
            subscriber._dispatch(msg["channel"], payload)
            if payload.get("event_id") == "test-event-001":
                break
        time.sleep(0.2)
    
    if len(received_payloads) > 0:
        logger.info("✅ Phase 1 Event Pipeline Verification PASSED")
    else:
        logger.error("❌ Phase 1 Event Pipeline Verification FAILED: No message received")
        exit(1)

if __name__ == "__main__":
    try:
        test_event_pipeline()
    except Exception as e:
        logger.exception(f"Pipeline test crashed: {e}")
        exit(1)
