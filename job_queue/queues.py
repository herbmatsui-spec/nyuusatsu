from queue.rq_config import rq_config
from rq import Queue

class Queues:
    """
    システム全体で使用するRQキューの定義。
    役割ごとにキューを分けることで、ワーカーのリソース割り当てを最適化し、
    特定タスクの滞留が他へ影響するのを防ぐ。
    """
    # クロール系 (I/O負荷が高い)
    CRAWL = "queue:crawl"
    
    # PDF/OCR系 (CPU負荷が高く、時間がかかる)
    PDF_PROCESS = "queue:pdf_process"
    
    # 分析・LLM系 (外部API待ちが発生する)
    ANALYSIS = "queue:analysis"
    
    # 通知系 (軽量だが外部連携がある)
    NOTIFICATION = "queue:notification"

# キューインスタンスへのアクセス用ヘルパー
def get_queue(name: str) -> Queue:
    """
    名前を指定してRQキューインスタンスを取得する。
    """
    return rq_config.get_queue(name)

# よく使われるキューのショートカット
crawl_queue = get_queue(Queues.CRAWL)
pdf_queue = get_queue(Queues.PDF_PROCESS)
analysis_queue = get_queue(Queues.ANALYSIS)
notification_queue = get_queue(Queues.NOTIFICATION)
