# Phase 00: インフラ準備 (3ステップ)

"""
基盤テスト: 環境と設定の包括的な検証。
"""

import pytest
from pathlib import Path
import os
import sys

def test_phase_00_project_structure(test_geps_live_base_dir):
    """プロジェクト構造が期待通りであることを確認"""
    
    # 期待される主要ディレクトリ
    expected_items = [
        "Phase 00",
        "Phase 01", 
        "Phase 02",
        "Phase 03",
        "Phase 04",
        "Phase 05",
        "Phase 06",
        "Phase 07",
        "Phase 08",
        "Phase 09",
        "Phase 10",
        "Phase 11",
        "Phase 12",
        "scripts",
        "README.md"
    ]
    
    for item in expected_items:
        item_path = test_geps_live_base_dir / item
        assert item_path.exists(), f"{item} ディレクトリ/ファイルが必要です"
        
        # 各Phaseディレクトリには__init__.pyファイルがある
        if item.startswith("Phase "):
            __init_path = item_path / "__init__.py"
            assert __init_path.exists(), f"{item} に __init__.py が必要です"
            assert __init_path.is_file(), f"{item}/__init__.py はファイルである必要があります"

def test_phase_00_requirements_and_dependencies(test_geps_live_base_dir):
    """必須な要件が満たされていることを確認"""
    
    # tests/test_geps_crawler (モックテスト) ディレクトリが存在することを確認
    original_crawler_tests_path = test_geps_live_base_dir.parent / "test_geps_crawler"
    assert original_crawler_tests_path.exists(), "tests/ 下に test_geps_crawler/ が必要です"
    
    # 元のテストスイートの主要ファイルが存在することを確認
    required_original_files = [
        "conftest.py",
        "test_step_01_crawl_result.py",
        "test_step_16_integration.py"
    ]
    
    for file_name in required_original_files:
        file_path = original_crawler_tests_path / file_name
        assert file_path.exists(), f"必須な元ファイルの {file_name} が見つかりません"
        assert file_path.is_file(), f"{file_name} はファイルである必要があります"

def test_phase_00_python_environment_setup(test_geps_live_base_dir):
    """Python環境が適切に設定されていることを確認"""
    
    # 必要な基本モジュールが利用可能であることを確認
    required_modules = [
        'pytest',
        'pathlib',
        'os',
        'sys'
    ]
    
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            pytest.fail(f"モジュール {module_name} に失敗: {e}")
    
    # テスト用backendとcompatibilityを確認
    assert sys.version_info >= (3, 6), "Python 3.6またはそれ以上が必要です"

def test_phase_00_config_and_settings(test_geps_live_base_dir):
    """共通コンフィグファイルが存在することを確認"""
    
    # 共通の conftest.py が必要
    conftest_path = test_geps_live_base_dir.parent / "conftest.py"
    assert conftest_path.exists(), "test_geps_live の親ディレクトリに conftest.py が必要です"
    
    # conftest.pyを読み取って基本的なpytestの構文を確認
    try:
        conftest_content = conftest_path.read_text(encoding='utf-8')
        
        # 主要な基礎要素が存在することを確認
        required_elements = [
            'import pytest',
            '@pytest.fixture',
            'def test_',  # テスト関数の存在可能性
            'def ',       # デフィニションの存在可能性
        ]
        
        for element in required_elements:
            if element not in conftest_content:
                print(f"WARNING: conftest.py に {element} が見つかりません")
                
    except Exception as e:
        pytest.fail(f"conftest.pyの読み込みに失敗: {e}")

def test_phase_00_test_file_naming_conventions(test_geps_live_base_dir):
    """ Phase 00内のテストファイルが命名規則に従っていることを確認"""
    
    phase_00_dir = test_geps_live_base_dir / "Phase 00"
    python_files = list(phase_00_dir.glob("*.py"))
    
    # 期待されるファイル（__init__.py以外）
    expected_test_files = [
        "000_01_directory_check.py",
        "000_02_config_validation.py",
        "000_03_environment_check.py"
    ]
    
    found_files = [f.name for f in python_files if f.name != "__init__.py"]
    
    # 期待されるファイルが存在することを確認
    for expected_file in expected_test_files:
        assert expected_file in found_files, f"{expected_file} ファイルが見つかりません"
    
    # 命名規則: <0..9>の2桁フェーズ番号 + 3桁ステップ + ファイル名
    for found_file in found_files:
        # 命名規則の検証: 3桁の数字で始まる
        assert found_file[0].isdigit() and found_file[1].isdigit() and found_file[2].isdigit(), \
            f"{found_file} は最初の3文字に数字を持つ必要があります"

def test_phase_00_test_metadata(test_geps_live_base_dir):
    """Phase 0のメタデータが提供されていることを確認"""
    
    # README.mdが存在することを確認
    readme_path = test_geps_live_base_dir.parent / "README.md"
    assert readme_path.exists(), "Phase 0用のREADME.mdが必要です"
    
    # README.mdを読み取ってPhase 00の概要を含むことを確認
    readme_content = readme_path.read_text(encoding='utf-8')
    
    # Phase 0に関連する主要キーワード
    phase_00_keywords = [
        "Phase 00",
        "インフラ準備",
        "ディレクトリ構造"
    ]
    
    # 主要なキーワードがREADMEの一部であることを確認
    for keyword in phase_00_keywords:
        assert keyword in readme_content, f"README.md に {keyword} が見つかりません"

def test_phase_00_infrastructure_cleanup(test_geps_live_base_dir):
    """テスト用インフラストラクチャの一時ファイルを整理"""
    
    # 臨時テストディレクトリが期待通りに作成されていることを確認
    temp_test_dir = test_geps_live_base_dir / "__pycache__"
    if temp_test_dir.exists():
        # 終了時に自動的に削除する
        import shutil
        shutil.rmtree(temp_test_dir)

def test_phase_00_dependency_injection_setup(test_geps_live_base_dir):
    """Phase 00インフラストラクチャのためのfixtureが設定されていることを確認"""
    
    # 主要なPhase 00 fixture:
    #  - test_geps_live_base_dir
    #  - test_geps_live_phases
    
    # fixtureファイルが存在することを確認
    conftest_path = test_geps_live_base_dir.parent / "conftest.py"
    assert conftest_path.exists(), "共通fixture conftest.py が必要です"
    
    # fixtureを読み取って基本的なテストセットアップが含まれていることを確認
    conftest_content = conftest_path.read_text(encoding='utf-8')
    
    # fixtureファイルの主要コンポーネント
    required_fixture_patterns = [
        "test_geps_live_base_dir",
        "test_geps_live_phases",
        "geps_skip_live",
        "live_geps_url",
        "geps_test_timeout"
    ]
    
    # 主要なfixturesが定義されていることを確認
    fixtures_count = 0
    for pattern in required_fixture_patterns:
        if pattern in conftest_content:
            fixtures_count += 1
    
    # 5つ以上の主要フィクスチャが必要
    assert fixtures_count >= 5, f"5つ以上の主要fixturesが必要 ({fixtures_count}個見つかりました)"

# 便利なutility関数
def validate_path(path_str, expected_type="file"):
    """パスのタイプを検証するヘルパー"""
    path = Path(path_str)
    
    if expected_type == "file":
        if not path.is_file():
            raise ValueError(f"{path_str} はファイルである必要があります")
    elif expected_type == "dir":
        if not path.is_dir():
            raise ValueError(f"{path_str} はディレクトリである必要があります")
    
    return path

# 結果キャプチャ用データクラス
class TestFixtureResult:
    """fixtureテストの結果"""
    def __init__(self, test_name, status, error=None):
        self.test_name = test_name
        self.status = status
        self.error = error
        self.timestamp = None

# グローバルテスト結果
class GlobalTestState:
    """グローバルなテスト状態"""
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_skipped = 0
        self.start_time = None
        self.end_time = None

# エラーハンドリング関数
def handle_test_error(test_file, error_msg):
    """テストエラーを処理する"""
    print(f"ERROR in {test_file}: {error_msg}")
    return TestFixtureResult(test_file, "FAIL", error_msg)

# 定数定義
PHASE_00_METADATA = {
    'total_steps': 3,
    'phase_number': 0,
    'phase_description': 'インフラ準備と基盤設定',
    'dependencies': [],
    'required_environment_variables': ['GEPS_LIVE_URL', 'GEPS_TEST_TIMEOUT', 'GEPS_SKIP_LIVE']
}
