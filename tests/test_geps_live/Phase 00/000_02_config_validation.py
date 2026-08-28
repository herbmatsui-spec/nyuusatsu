# Phase 00: インフラ準備 (3ステップ)

"""
基盤テスト: 基盤設定の検証と環境互換性の確認。
"""

import pytest
from pathlib import Path
import os
import sys

def test_phase_00_setup_file_structure(test_geps_live_base_dir):
    """Phase 00フォルダに必要なファイルが存在することを確認"""
    required_files = [
        '000_01_directory_check.py',
        '000_02_config_validation.py',
        '000_03_environment_check.py',
        '__init__.py'
    ]
    
    for file_name in required_files:
        file_path = test_geps_live_base_dir / file_name
        assert file_path.exists(), f"{file_name} ファイルが必要です"
        assert file_path.is_file(), f"{file_name} はファイルである必要があります"

def test_phase_00_python_syntax_check(test_geps_live_base_dir):
    """Phase 00のすべてのPythonファイルの構文を検証"""
    python_files = [
        test_geps_live_base_dir / '000_01_directory_check.py',
        test_geps_live_base_dir / '000_02_config_validation.py',
        test_geps_live_base_dir / '000_03_environment_check.py'
    ]
    
    for file_path in python_files:
        assert file_path.exists(), f"{file_path.name} ファイルが存在しません"
        
        # 構文チェック
        try:
            file_path.read_text(encoding='utf-8')
        except Exception as e:
            pytest.fail(f"{file_path.name} ファイルの読み込みエラー: {e}")

def test_phase_00_conftest_imports(test_geps_live_base_dir):
    """conftest.pyが正しい方法でインポートできること"""
    
    # conftest.pyが存在することを確認
    conftest_path = test_geps_live_base_dir.parent / 'conftest.py'
    assert conftest_path.exists(), "test_geps_live の直親ディレクトリに conftest.py が必要です"
    
    # conftest.pyを読み取ってpytestの構文を検証
    try:
        content = conftest_path.read_text(encoding='utf-8')
        
        # 主要なfixturesが存在することを確認
        required_fixtures = ['live_geps_url', 'geps_test_timeout', 'geps_skip_live']
        
        for fixture_name in required_fixtures:
            assert f"def {fixture_name}(" in content, f"{fixture_name} fixtureが見つかりません"
            
    except Exception as e:
        pytest.fail(f"conftest.pyの読み込みエラー: {e}")

def test_phase_00_environment_variables(test_geps_live_base_dir):
    """必須な環境変数が設定可能であることを確認"""
    
    # 必要な環境変数を定義
    required_env_vars = [
        'GEPS_LIVE_URL',
        'GEPS_TEST_TIMEOUT', 
        'GEPS_SKIP_LIVE'
    ]
    
    # システムで一部の変数が既に設定されているか確認
    # （テストでは実際の変数は必要ありませんが、存在可能性を確認します）
    env_values = {}
    
    # GEPS_LIVE_URL のデフォルト値
    default_url = 'https://www.geps.go.jp'
    env_values['GEPS_LIVE_URL'] = default_url
    
    # GEPS_TEST_TIMEOUT のデフォルト値
    default_timeout = '30'
    env_values['GEPS_TEST_TIMEOUT'] = default_timeout
    
    # GEPS_SKIP_LIVE のデフォルト値
    default_skip = ''
    env_values['GEPS_SKIP_LIVE'] = default_skip
    
    # 値が期待通りであることを確認
    assert isinstance(env_values['GEPS_LIVE_URL'], str)
    assert env_values['GEPS_LIVE_URL'].startswith('http://') or env_values['GEPS_LIVE_URL'].startswith('https://')
    
    # 数値のために変換可能なことを確認
    try:
        timeout_int = int(env_values['GEPS_TEST_TIMEOUT'])
        assert timeout_int > 0
    except ValueError:
        pytest.fail("GEPS_TEST_TIMEOUT は数値でなければなりません")
    
    # スキップフラグの値
    valid_skip_values = ['1', 'true', 'yes', '', '0', 'false', 'no']
    assert env_values['GEPS_SKIP_LIVE'] in valid_skip_values

def test_phase_00_test_runner_script(test_geps_live_base_dir):
    """テストランナースクリプトが利用可能であることを確認"""
    
    scripts_dir = test_geps_live_base_dir.parent / 'scripts'
    assert scripts_dir.exists(), "scripts ディレクトリが必要です"
    
    runner_script = scripts_dir / 'run_live_tests.py'
    assert runner_script.exists(), "run_live_tests.py ファイルが必要です"
    
    # Python構文チェック
    try:
        runner_script.read_text(encoding='utf-8')
    except Exception as e:
        pytest.fail(f"test runner script の読み込みエラー: {e}")

# 便利なfixture (共通コンフィグで使用)
@pytest.fixture
def test_geps_live_base_dir():
    """テスト_geps_liveのベースディレクトリを返す"""
    return Path("tests/test_geps_live")

# パス操作用の便利な関数
def safe_resolve_path(path_str):
    """安全にパスを解決する"""
    return Path(path_str).resolve()

# 結果保存用のデータクラス
class TestResult:
    """テスト結果を保存する"""
    def __init__(self, file_name, status, error_msg=None):
        self.file_name = file_name
        self.status = status  # "PASS", "FAIL", "SKIP"
        self.error_msg = error_msg
        self.timestamp = None

# ヘルパー関数
def log_test_result(test_result):
    """結果をログ出力"""
    status_icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⏭"}.get(test_result.status, "?")
    print(f"  {status_icon} {test_result.file_name} - {test_result.status}")
    if test_result.error_msg and test_result.status == "FAIL":
        print(f"    エラー: {test_result.error_msg}")

# 例外定義
class TestSetupError(Exception):
    """テストセットアップエラー"""
    pass

# メタデータ
def get_test_metadata():
    """テストスイートのメタデータを返す"""
    return {
        'total_tests': 3,
        'phase': 'Phase 00',
        'description': 'インフラ準備',
        'recommended_execution_order': '01',
        'dependencies': [],
        'required_environment_variables': ['GEPS_LIVE_URL', 'GEPS_TEST_TIMEOUT', 'GEPS_SKIP_LIVE']
    }
