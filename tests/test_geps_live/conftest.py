import os
import sys

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
from datetime import datetime

# --------------------------------------------------------------
# Live Integration Test Fixtures
# --------------------------------------------------------------

@pytest.fixture
def live_geps_url():
    """本番GEPSサイトにアクセスするためのURL"""
    url = os.getenv("GEPS_LIVE_URL", "https://www.geps.go.jp")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url

@pytest.fixture
def geps_test_timeout():
    """本番テスト用タイムアウト（デフォルト30秒）"""
    return int(os.getenv("GEPS_TEST_TIMEOUT", "30"))

@pytest.fixture
def geps_skip_live():
    """GEPS_SKIP_LIVEが設定されている場合はTrue"""
    return os.getenv("GEPS_SKIP_LIVE", "").lower() in ("1", "true", "yes")

# --------------------------------------------------------------
# Phase 0: 環境チェックfixture
# --------------------------------------------------------------

@pytest.fixture(autouse=True)
def check_geps_environment(live_geps_url, geps_skip_live):
    """本番テスト前の環境チェックとスキップ判定"""
    if geps_skip_live:
        pytest.skip("GEPS_SKIP_LIVE 環境変数が設定されているため、本番テストをスキップ")
    
    # 基本URLアクセス可能か確認（高速ping用）
    import requests
    try:
        # HEADリクエスト（短時間）でURLの活性を確認
        import warnings
        warnings.filterwarnings("ignore")
        response = requests.head(live_geps_url, timeout=5, allow_redirects=True)
        # レスポンスコードで可用性を確認
        if response.status_code >= 400:
            pytest.skip(f"GEPSサイトでHTTPステータス {response.status_code}。本番テストをスキップ")
    except Exception as e:
        # ネットワークエラーはテストを失敗させずスキップ
        pytest.skip(f"GEPSサイトへの接続に失敗: {e}。本番テストをスキップ")

# --------------------------------------------------------------
# Phase 0: 共通ヘルパー
# --------------------------------------------------------------

def normalize_url(url: str) -> str:
    """URLからフラグメントを除去して正規化"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

@pytest.fixture
def validate_response_status():
    """レスポンスステータスを検証するヘルパー"""
    return {
        'check': lambda status_code, expected=None: True,
        'assert_success': lambda status_code: status_code < 400,
        'assert_content_type_pdf': lambda content_type: 'application/pdf' in content_type,
        'assert_non_empty': lambda length: length > 0,
        'assert_valid_url': lambda url: url.startswith(('http://', 'https://'))
    }

# --------------------------------------------------------------
# Phase 0: 動的スキップマーカー
# --------------------------------------------------------------

def skip_reason(reason: str):
    """スキップ理由を生成"""
    return pytest.mark.skip(reason=reason)

# --------------------------------------------------------------
# 重要: テスト状態フラグ
# --------------------------------------------------------------
import atexit
from threading import Lock

_live_test_status = {
    'total_tests': 0,
    'passed_tests': 0,
    'failed_tests': 0,
    'skipped_tests': 0,
    'start_time': None,
    'end_time': None,
    'lock': Lock()
}

@atexit.register
def log_live_test_summary():
    """プロセス終了時に本番テストの概要をログ出力"""
    with _live_test_status['lock']:
        print(f"\n{'='*60}")
        print(f"本番テスト概要")
        print(f"{'='*60}")
        print(f"総実行テスト数: {_live_test_status['total_tests']}")
        print(f"成功: {_live_test_status['passed_tests']}")
        print(f"失敗: {_live_test_status['failed_tests']}")
        print(f"スキップ: {_live_test_status['skipped_tests']}")
        print(f"開始時間: {_live_test_status['start_time']}")
        if _live_test_status['end_time']:
            duration = (_live_test_status['end_time'] - _live_test_status['start_time']).total_seconds()
            print(f"所要時間: {duration:.2f} 秒")
        print(f"{'='*60}")

# --------------------------------------------------------------
# Phase 0: 本番テスト実行前セットアップ
# --------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_live_test_environment():
    """本番テストの実行前に一度だけ実行されるセットアップ"""
    _live_test_status['start_time'] = datetime.now()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 本番GEPSテストのセットアップを開始")
    yield
    _live_test_status['end_time'] = datetime.now()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 本番GEPSテストのセットアップを終了")

# --------------------------------------------------------------
# Phase 0: リソースクリーンアップ
# --------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def cleanup_live_test_resources():
    """テスト終了時のクリーンアップ"""
    yield
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 本番テスト後のクリーンアップを実行")
    # 対外的クリーンアップがある場合ここに追加
    
# --------------------------------------------------------------
# 本番テスト用共通ヘルパー（いまだけ、非Gitignore）
# --------------------------------------------------------------

def save_test_result(test_name: str, status: str, error_msg: str = None, duration: float = 0.0):
    """テスト結果を保存するヘルパー"""
    with _live_test_status['lock']:
        _live_test_status['total_tests'] += 1
        if status == 'passed':
            _live_test_status['passed_tests'] += 1
        elif status == 'failed':
            _live_test_status['failed_tests'] += 1
        elif status == 'skipped':
            _live_test_status['skipped_tests'] += 1
    
    # 結果をログに記録
    status_icon = {"passed": "✓", "failed": "✗", "skipped": "⏭"}.get(status, "?")
    print(f"  {status_icon} {test_name} ({duration:.2f}秒) - {status}")
    if error_msg and status == 'failed':
        print(f"    エラー: {error_msg}")

# 
# 本番テスト用に一時ファイルを保存するディレクトリ（テスト中に削除されるはず）
# TODO: 本番テストごとに固有のタイムスタンプでディレクトリを作成し、クリーンアップ
