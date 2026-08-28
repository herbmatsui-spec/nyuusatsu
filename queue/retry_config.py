import logging
from typing import Any, Dict
from rq import Retry

logger = logging.getLogger(__name__)

# RQのリトライ設定を集約して管理する
# 各タスクの特性に合わせてリトライ回数とバックオフ間隔を定義する

# 標準的なリトライ設定: 3回リトライ、指数関数的に待機時間を増加 (4s, 8s, 16s...)
DEFAULT_RETRY = Retry(max=3, interval=[4, 8, 16])

# 重い処理（OCRなど）向けのリトライ設定: 回数を少なめにし、間隔を長く取る
HEAVY_TASK_RETRY = Retry(max=2, interval=[30, 60])

# 外部API依存（LLMなど）のリトライ設定: ネットワークエラーを想定し、回数を多めに設定
API_DEPENDENT_RETRY = Retry(max=5, interval=[2, 4, 8, 16, 32])

# 通知系リトライ設定: 失敗しても影響が小さいため、低頻度でリトライ
NOTIFICATION_RETRY = Retry(max=2, interval=[60, 300])

def get_retry_config(task_type: str = "default") -> Retry:
    """
    タスク種別に応じたリトライ設定を返す
    """
    configs = {
        "default": DEFAULT_RETRY,
        "heavy": HEAVY_TASK_RETRY,
        "api": API_DEPENDENT_RETRY,
        "notification": NOTIFICATION_RETRY
    }
    return configs.get(task_type, DEFAULT_RETRY)
