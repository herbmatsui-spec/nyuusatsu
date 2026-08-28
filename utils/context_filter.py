import logging
from utils.log_context import get_log_context

class ContextFilter(logging.Filter):
    """
    スレッドローカル/非同期コンテキスト(contextvars)に保存された
    trace_id や pipeline_stage などのコンテキスト情報を、自動的に
    LogRecord の属性として追加するためのロギングフィルター。
    """
    def filter(self, record):
        ctx = get_log_context()
        
        # 既にrecord側で明示的に指定されていない場合のみ、コンテキストから自動付与する
        if not hasattr(record, "trace_id") or not record.trace_id:
            record.trace_id = ctx.get("trace_id", "")
            
        if not hasattr(record, "pipeline_stage") or not record.pipeline_stage:
            record.pipeline_stage = ctx.get("pipeline_stage", "")
            
        return True
