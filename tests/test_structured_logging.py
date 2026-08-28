import json
import logging
from utils.structured_formatter import StructuredFormatter
from utils.log_context import new_trace_id, set_pipeline_stage, get_log_context, clear_context
from utils.context_filter import ContextFilter

def test_structured_formatter():
    formatter = StructuredFormatter()
    
    # ログレコードの疑似オブジェクトを作成
    class Record:
        def __init__(self):
            self.created = 1770000000.0
            self.levelname = "INFO"
            self.name = "test_logger"
            self.msg = "Hello API key: api_key=123456789abc"
            self.module = "test_mod"
            self.funcName = "test_func"
            self.lineno = 42
            self.exc_info = None
            
        def getMessage(self):
            return self.msg
            
    record = Record()
    output = formatter.format(record)
    data = json.loads(output)
    
    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    # レダクション（マスク処理）が効いていることの確認
    assert "123456789abc" not in data["message"]
    assert "***" in data["message"]
    assert "timestamp" in data

def test_log_context_and_filter():
    clear_context()
    logger = logging.getLogger("test_context")
    logger.setLevel(logging.INFO)
    
    # ハンドラとフィルターの用意
    class MockHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
            
        def emit(self, record):
            self.records.append(record)
            
    handler = MockHandler()
    ctx_filter = ContextFilter()
    handler.addFilter(ctx_filter)
    logger.addHandler(handler)
    
    # コンテキスト設定前
    logger.info("Before context")
    assert handler.records[-1].trace_id == ""
    assert handler.records[-1].pipeline_stage == ""
    
    # コンテキスト設定後
    tid = new_trace_id()
    set_pipeline_stage("crawl")
    logger.info("After context")
    
    assert handler.records[-1].trace_id == tid
    assert handler.records[-1].pipeline_stage == "crawl"
    
    clear_context()
