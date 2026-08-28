"""
共通メッセージング設定
──────────────
システム全体で使用するイベントチャンネル名（トピック名）を定義します。
マジックストリングを排除し、型安全な管理を行います。
"""

class EventChannels:
    # クロール関連
    CRAWL_REQUESTED = "event.crawl.requested"
    CRAWL_COMPLETED = "event.crawl.completed"
    CRAWL_FAILED = "event.crawl.failed"

    # PDF/OCR関連
    PDF_DOWNLOADED = "event.pdf.downloaded"
    PDF_DOWNLOAD_FAILED = "event.pdf.download_failed"
    TEXT_EXTRACTED = "event.text.extracted"
    TEXT_EXTRACT_FAILED = "event.text.extract_failed"

    # 分析関連
    ANALYSIS_REQUESTED = "event.analysis.requested"
    ANALYSIS_COMPLETED = "event.analysis.completed"
    ANALYSIS_FAILED = "event.analysis.failed"

    # 通知関連
    NOTIFICATION_REQUESTED = "event.notification.requested"
    NOTIFICATION_SENT = "event.notification.sent"
    NOTIFICATION_FAILED = "event.notification.failed"

    # システム管理
    DEAD_LETTER = "event.system.dead_letter"
    SYSTEM_ALERT = "event.system.alert"

# ハンドラ登録時に使用するチャンネル名のリスト
ALL_CHANNELS = [
    EventChannels.CRAWL_REQUESTED, EventChannels.CRAWL_COMPLETED, EventChannels.CRAWL_FAILED,
    EventChannels.PDF_DOWNLOADED, EventChannels.PDF_DOWNLOAD_FAILED, EventChannels.TEXT_EXTRACTED, EventChannels.TEXT_EXTRACT_FAILED,
    EventChannels.ANALYSIS_REQUESTED, EventChannels.ANALYSIS_COMPLETED, EventChannels.ANALYSIS_FAILED,
    EventChannels.NOTIFICATION_REQUESTED, EventChannels.NOTIFICATION_SENT, EventChannels.NOTIFICATION_FAILED,
    EventChannels.DEAD_LETTER, EventChannels.SYSTEM_ALERT
]
