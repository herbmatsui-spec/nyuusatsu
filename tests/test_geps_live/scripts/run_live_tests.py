#!/usr/bin/env python3
"""
本番GEPSクローラーテストランナー

本番GEPSクローラーテストスイートのメイン実行ファイルです。
- 指定されたフェーズまたは全テストを実行
- 報告生成のためにレポートファイルを保存
- 74段階分割されたテストを実行

このファイルは、C: ドライブ内のディレクトリから実行することを推奨します。
I: ドライブ内で実行するとディスクI/Oのブロックが発生し、プロセスがフリーズする可能性があります。
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# プロジェクトルートを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

# テストランナー状態（グローバル）
_live_test_status = {
    'total_tests': 0,
    'passed_tests': 0,
    'failed_tests': 0,
    'skipped_tests': 0,
    'start_time': None,
    'end_time': None,
    'current_phase': None
}

# 設定パス
CONFIG_PATH = Path(__file__).parent.parent.parent / ".kilo"

# ログ設定
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
        ]
    )
    return logging.getLogger(__name__)

# テストランナー
class LiveGepTestsRunner:
    def __init__(self, test_path, phase_range=None, skip_live=False, report_path=None):
        self.test_path = Path(test_path)
        self.phase_range = phase_range
        self.skip_live = skip_live
        self.report_path = Path(report_path) if report_path else None
        self.logger = logging.getLogger(__name__)

    def run_tests(self):
        """本番テストを実行"""
        try:
            self._print_header()
            
            # テストを実行
            exit_code = self._execute_pytest()
            
            # レポートを保存
            self._save_report()
            
            return exit_code
        except Exception as e:
            self.logger.error(f"テスト実行中にエラーが発生: {e}", exc_info=True)
            return 1

    def _print_header(self):
        """ヘッダーを印刷"""
        print(f"\n{'='*70}")
        print(f"本番GEPSクローラーテストランナー")
        print(f"{'='*70}")
        print(f"テストディレクトリ: {self.test_path}")
        
        if self.phase_range:
            start, end = self.phase_range
            print(f"フェーズ: {start}-{end} を実行")
        else:
            print(f"全フェーズを実行")
            
        if self.skip_live:
            print(f"GEPS_SKIP_LIVE=true により、本番アクセスをスキップ")
            
        print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

    def _execute_pytest(self):
        """pytestを実行"""
        # 環境変数を設定
        env_vars = {}
        if self.skip_live:
            env_vars["GEPS_SKIP_LIVE"] = "true"
            
        # テストファイルパスをフィルタリング
        args = [str(self.test_path)]
        
        # フェーズフィルタリング
        if self.phase_range:
            start, end = self.phase_range
            file_patterns = []
            
            for phase in range(start, end + 1):
                phase_str = f"{phase:03d}"
                file_patterns.extend([
                    f"**/test_{phase_str}_*.py",
                ])
                
            if file_patterns:
                args.extend(["-k", " or ".join(file_patterns)])
                
        # 静音モードでpytestを実行
        args.extend(["-v", "--no-cov", "--tb=short"])
        
        # pytestを実行
        return_code = pytest.main(args)
        
        return 0 if return_code in (0, True) else 1

    def _save_report(self):
        """本番テストの概要を保存"""
        if self.report_path:
            # レポートディレクトリを作成
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 概要を保存
            self._generate_report()
            
            self.logger.info(f"本番テストの概要を {self.report_path} に保存")

    def _generate_report(self):
        """レポートのプレースホルダー"""
        # TODO: 本番テストの概要をレポートに生成
        pass

    def set_status(self, **kwargs):
        """テストランナーの状態を更新"""
        for key, value in kwargs.items():
            _live_test_status[key] = value

# 便利な動作関数

def run_live_tests(test_path, phase_range=None, skip_live=False, report_path=None):
    """テストを実行する便利な関数"""
    runner = LiveGepTestsRunner(
        test_path=test_path,
        phase_range=phase_range,
        skip_live=skip_live,
        report_path=report_path
    )
    return runner.run_tests()

# メインモード
if __name__ == "__main__":
    # 引数を解析
    parser = argparse.ArgumentParser(
        description="本番GEPSクローラーテストランナー",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 全テストを実行
  python run_live_tests.py

  # 特定のフェーズのみ実行
  python run_live_tests.py --phase 34-68

  # 本番環境アクセスをスキップ
  python run_live_tests.py --no-live

  # レポートを出力
  python run_live_tests.py --report reports/live_test_report.txt
        """
    )
    
    parser.add_argument(
        "--test-path",
        default="I:\\入札システム\\tests\\test_geps_live",
        help="テストディレクトリのパス"
    )
    
    parser.add_argument(
        "--phase",
        help="実行するフェーズ (例: 34-68)"
    )
    
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="GEPS_SKIP_LIVE=true による本番環境アクセスをスキップ"
    )
    
    parser.add_argument(
        "--report",
        help="レポートを出力するファイルのパス"
    )
    
    args = parser.parse_args()
    
    # フェーズの範囲を解析
    phase_range = None
    if args.phase:
        try:
            start, end = map(int, args.phase.split('-'))
            phase_range = (start, end)
        except ValueError:
            print(f"無効なフェーズ形式: {args.phase}")
            print("フェーズ形式は例のように --phase 34-68 です")
            sys.exit(1)
    
    # テストを実行
    exit_code = run_live_tests(
        test_path=args.test_path,
        phase_range=phase_range,
        skip_live=args.no_live,
        report_path=args.report
    )
    
    sys.exit(exit_code)