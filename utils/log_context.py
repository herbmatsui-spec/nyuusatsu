import contextvars
import uuid

# コンテキスト変数の定義
_trace_id = contextvars.ContextVar('trace_id', default='')
_pipeline_stage = contextvars.ContextVar('pipeline_stage', default='')

def new_trace_id() -> str:
    """新しい一意のトレースIDを生成し、コンテキストに設定する"""
    tid = uuid.uuid4().hex[:12]
    _trace_id.set(tid)
    return tid

def set_trace_id(trace_id: str):
    """既存のトレースIDをコンテキストに設定する"""
    _trace_id.set(trace_id)

def set_pipeline_stage(stage: str):
    """現在のパイプラインステージ（例: crawl, download, analysis など）をコンテキストに設定する"""
    _pipeline_stage.set(stage)

def clear_context():
    """コンテキスト変数をクリアする"""
    _trace_id.set('')
    _pipeline_stage.set('')

def get_log_context() -> dict:
    """現在のログコンテキスト情報を取得する"""
    return {
        "trace_id": _trace_id.get(''),
        "pipeline_stage": _pipeline_stage.get(''),
    }
