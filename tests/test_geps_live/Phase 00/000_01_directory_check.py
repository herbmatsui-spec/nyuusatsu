# Phase 00: インフラ準備 (3ステップ)

"""
基盤テスト: ディレクトリ構造、基本設定、動作可能性の確認。
"""

import pytest
from pathlib import Path
import os

def test_test_geps_live_directory_exists(test_geps_live_base_dir):
    """Phase 0 ディレクトリが存在することを確認"""
    assert test_geps_live_base_dir.exists()
    assert test_geps_live_base_dir.is_dir()

def test_phase_00_directory_structure(test_geps_live_base_dir, test_geps_live_phases):
    """Phase 00ディレクトリ構造が期待通りであることを確認"""
    
    phases = ['Phase 00', 'Phase 01', 'Phase 02', 'Phase 03', 
              'Phase 04', 'Phase 05', 'Phase 06', 'Phase 07',
              'Phase 08', 'Phase 09', 'Phase 10', 'Phase 11', 'Phase 12']
    
    for phase in phases:
        phase_dir = test_geps_live_base_dir / phase
        assert phase_dir.exists(), f"{phase} ディレクトリが存在しません"
        assert phase_dir.is_dir(), f"{phase} がディレクトリではありません"
        
        # すべてのPhaseには__init__.pyファイルがある
        __init__ = phase_dir / '__init__.py'
        assert __init__.exists(), f"{phase} に __init__.py が見つかりません"
        
        # __init__.pyの内容が単一のデコレータ行であることを確認
        init_content = __init__.read_text().strip()
        assert init_content == "", f"{phase} の __init__.py は空であるべき"

def test_phase_specific_files_exist(test_geps_live_base_dir, test_geps_live_phases):
    """Phase 00のファイルがすべて存在するかどうかを確認"""
    phase_00_dir = test_geps_live_base_dir / "Phase 00"
    
    expected_files = [
        "000_01_directory_check.py",
        "000_02_config_validation.py", 
        "000_03_environment_check.py"
    ]
    
    for file_name in expected_files:
        file_path = phase_00_dir / file_name
        assert file_path.exists(), f"{file_name} ファイルが存在しません"
        
        # Python構文チェック
        import ast
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"{file_name} の構文エラー: {e}")

# Phase 00 の便利なfixture
@pytest.fixture
def test_geps_live_base_dir():
    """ベースの test_geps_live ディレクトリを返す"""
    return Path("tests/test_geps_live")

@pytest.fixture
def test_geps_live_phases(test_geps_live_base_dir):
    """存在するPhaseのリストを返す"""
    return [d.name for d in test_geps_live_base_dir.iterdir() if d.is_dir() and d.name.startswith('Phase ')]

# Phase 00 の便利関数
def normalize_path(path_str):
    """パス文字列を正規化"""
    return str(Path(path_str).resolve())

# 例外クラス
class TestFileError(Exception):
    """テストファイルエラー"""
    pass

# 定数
PHASE_00_TEST_COUNT = 3
PHASE_00_DIR_NAME = "Phase 00"
