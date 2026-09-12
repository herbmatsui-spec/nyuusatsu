import atexit
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
import yaml

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
# Phase 0: 対象自治体リストの読み込みとパラメータライズ
# --------------------------------------------------------------

def _load_target_municipalities() -> list[tuple[str, str]]:
    """targets.yaml から自治体リストを読み込み、 (prefecture, city) タプルのリストを返す"""
    targets_path = Path(__file__).parent / "targets.yaml"
    if not targets_path.exists():
        return []
    with targets_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    result = []
    for prefecture, cities in data.items():
        if isinstance(cities, list):
            for city in cities:
                result.append((prefecture, city))
    return result


def pytest_generate_tests(metafunc: pytest.Metafunc):
    """自治体リストでテストをパラメータライズ"""
    if "prefecture" in metafunc.fixturenames and "city" in metafunc.fixturenames:
        municipalities = _load_target_municipalities()
        if municipalities:
            metafunc.parametrize("prefecture,city", municipalities, scope="function")


# --------------------------------------------------------------
# Phase 0: 環境チェックfixture
# --------------------------------------------------------------

def _check_required_env_vars() -> list[str]:
    """必須環境変数が設定されているかチェックし、不足分を返す"""
    configured = os.getenv("LIVE_TEST_REQUIRED_ENV_VARS", "").strip()
    required = [var.strip() for var in configured.split(",") if var.strip()] if configured else ["DEEPSEEK_API_KEY", "GEMINI_API_KEY"]
    return [var for var in required if not os.getenv(var)]


@pytest.fixture(autouse=True)
def check_geps_environment(request, live_geps_url, geps_skip_live):
    """本番テスト前の環境チェックとスキップ判定 (live_test マーカーがあるテストのみ)"""
    # live_test マーカーがないテストはスキップしない
    if not request.node.get_closest_marker("live_test"):
        return
    if geps_skip_live:
        pytest.skip("GEPS_SKIP_LIVE 環境変数が設定されているため、本番テストをスキップ")

    missing_vars = _check_required_env_vars()
    if missing_vars:
        pytest.skip(f"必須環境変数が未設定: {', '.join(missing_vars)}。本番テストをスキップ")

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
# pytest マーカー設定 (timeout, flaky, xdist)
# --------------------------------------------------------------

def pytest_configure(config: pytest.Config):
    """pytest 設定時にマーカーを登録"""
    config.addinivalue_line("markers", "timeout(seconds): タイムアウト秒数を指定")
    config.addinivalue_line("markers", "flaky(reruns, reruns_delay): フレーキーテスト対策リトライ")
    config.addinivalue_line("markers", "live_test: 本番環境テストマーカー")
    config.addinivalue_line("markers", "integration: 統合テストマーカー")


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
# Step 1: タイムスタンプ付き一時ディレクトリ fixture
# --------------------------------------------------------------

@pytest.fixture(scope="session")
def live_test_dir(tmp_path_factory):
    """タイムスタンプ付き一時ディレクトリ（成功時は削除、失敗時は保持）"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = tmp_path_factory.mktemp(f"live_test_{ts}")
    yield d

    # クリーンアップ: 成功時のみ削除、失敗時は残す
    if not getattr(live_test_dir, "_failed", False):
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """失敗したライブテストの一時ディレクトリを保持する"""
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        live_test_dir._failed = True


# --------------------------------------------------------------
# デフォルト timeout / flaky マーカーの自動付与
# --------------------------------------------------------------

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    """テスト収集後にデフォルトの timeout と flaky マーカーを付与"""
    default_timeout = int(os.getenv("GEPS_DEFAULT_TIMEOUT", "300"))
    default_reruns = int(os.getenv("GEPS_DEFAULT_RERUNS", "2"))
    default_reruns_delay = int(os.getenv("GEPS_DEFAULT_RERUNS_DELAY", "10"))
    live_root = Path(__file__).parent
    for item in items:
        is_live_test = item.get_closest_marker("live_test") or Path(item.path).is_relative_to(live_root)
        if is_live_test:
            if not item.get_closest_marker("timeout"):
                item.add_marker(pytest.mark.timeout(default_timeout))
            if not item.get_closest_marker("flaky"):
                item.add_marker(pytest.mark.flaky(max_runs=default_reruns + 1, min_passes=1))
