#!/usr/bin/env python3
"""
本番GEPSクローラーテストランナー

本番GEPSクローラーテストスイートのメイン実行ファイルです。
- 指定されたフェーズまたは全テストを実行
- 報告生成のためにレポートファイルを保存
- 74段階分割されたテストを実行

このファイルはプロジェクト内の tests/test_geps_live から実行することを推奨します。
"""

import argparse
import importlib.util
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
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
    def __init__(self, test_path, phase_range=None, skip_live=False, report_path=None,
                 targets_yaml=None, xdist_workers=None, timeout=None, json_report=True,
                 notify=False):
        self.test_path = Path(test_path)
        self.phase_range = phase_range
        self.skip_live = skip_live
        self.notify = notify or os.getenv("LIVE_TEST_NOTIFY", "").lower() in {"1", "true", "yes"}
        self.started_at = datetime.now(timezone.utc)
        self.timestamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        default_report_dir = Path(os.getenv("LIVE_TEST_REPORT_DIR", "reports/live-tests"))
        self.report_path = Path(report_path) if report_path else default_report_dir / f"live_test_report_{self.timestamp}.md"
        self.json_report_path = self.report_path.with_name(f"{self.report_path.stem}.json")
        self.targets_yaml = Path(targets_yaml) if targets_yaml else self.test_path / "targets.yaml"
        self.xdist_workers = xdist_workers
        self.timeout = timeout
        self.json_report = json_report
        self.target_municipalities = self._load_targets_from_yaml()
        self.logger = logging.getLogger(__name__)

    def _load_targets_from_yaml(self) -> list[str]:
        """targets.yaml から自治体リストを読み込む"""
        if not self.targets_yaml.exists():
            return []
        try:
            import yaml
            with self.targets_yaml.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
            result = []
            for prefecture, cities in data.items():
                if isinstance(cities, list):
                    for city in cities:
                        result.append(f"{prefecture}/{city}")
            return result
        except Exception as e:
            self.logger.warning(f"targets.yaml 読み込みエラー: {e}")
            return []

    def run_tests(self):
        """本番テストを実行"""
        try:
            self._print_header()
            exit_code = self._execute_pytest()
            self._save_report()
            if self.notify:
                self._notify_report(exit_code)
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
        if self.target_municipalities:
            print(f"対象自治体: {len(self.target_municipalities)} 件 (targets.yaml より)")
        if self.xdist_workers:
            print(f"並列ワーカー数: {self.xdist_workers}")
        if self.timeout:
            print(f"タイムアウト: {self.timeout} 秒")
        print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

    def _execute_pytest(self):
        """pytestを実行"""
        env_vars = {}
        if self.skip_live:
            env_vars["GEPS_SKIP_LIVE"] = "true"
        if self.timeout:
            env_vars["GEPS_DEFAULT_TIMEOUT"] = str(self.timeout)
        for key, value in env_vars.items():
            os.environ[key] = value

        self.json_report_path.parent.mkdir(parents=True, exist_ok=True)
        args = [str(self.test_path)]

        if self.phase_range:
            start, end = self.phase_range
            selected_paths = []
            for path in self.test_path.rglob("*.py"):
                if path.name == "conftest.py" or "scripts" in path.parts:
                    continue
                phase_number = self._phase_number(path)
                if phase_number is not None and start <= phase_number <= end:
                    selected_paths.append(str(path))
            if selected_paths:
                args = selected_paths

        args.extend([
            "-v",
            "--no-cov",
            "--tb=short",
            "-o",
            "python_files=*.py",
        ])

        if self.json_report:
            args.extend([
                "--json-report",
                f"--json-report-file={self.json_report_path}",
            ])

        if self.xdist_workers:
            args.extend(["-n", str(self.xdist_workers)])

        if self.timeout:
            # pytest-timeout のデフォルトタイムアウトを環境変数で設定
            os.environ["PYTEST_TIMEOUT"] = str(self.timeout)

        return_code = pytest.main(args)
        return 0 if return_code in (0, True) else 1

    @staticmethod
    def _phase_number(path: Path) -> int | None:
        match = re.match(r"Phase\s*(\d+)", path.parent.name, re.I)
        return int(match.group(1)) if match else None

    def _save_report(self):
        """本番テストの概要を保存"""
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self._generate_report()
        self.logger.info(f"本番テストの概要を {self.report_path} に保存")

    def _generate_report(self):
        """JSON レポートから Markdown サマリを生成する"""
        module_path = Path(__file__).with_name("report_generator.py")
        spec = importlib.util.spec_from_file_location("geps_live_report_generator", module_path)
        report_generator = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = report_generator
        spec.loader.exec_module(report_generator)
        write_markdown_report = report_generator.write_markdown_report

        if not self.json_report_path.exists():
            report = {
                "summary": {
                    "total": _live_test_status["total_tests"],
                    "duration": 0.0,
                },
                "tests": [],
            }
            self.json_report_path.write_text(
                __import__("json").dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        write_markdown_report(
            self.json_report_path,
            self.report_path,
            executed_at=self.started_at,
            target_municipalities=self.target_municipalities,
        )

    def _notify_report(self, exit_code: int):
        from services.alert_manager import send_live_test_report

        results = send_live_test_report(self.report_path, exit_code)
        self.logger.info(f"ライブテストレポート通知結果: {results}")

    def set_status(self, **kwargs):
        """テストランナーの状態を更新"""
        for key, value in kwargs.items():
            _live_test_status[key] = value

# 便利な動作関数

def run_live_tests(test_path, phase_range=None, skip_live=False, report_path=None,
                   targets_yaml=None, xdist_workers=None, timeout=None, json_report=True,
                   notify=False):
    """テストを実行する便利な関数"""
    runner = LiveGepTestsRunner(
        test_path=test_path,
        phase_range=phase_range,
        skip_live=skip_live,
        report_path=report_path,
        targets_yaml=targets_yaml,
        xdist_workers=xdist_workers,
        timeout=timeout,
        json_report=json_report,
        notify=notify
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
  # 全テストを実行（デフォルトパス使用）
  python run_live_tests.py

  # 特定のフェーズのみ実行
  python run_live_tests.py --phase 34-68

  # 本番環境アクセスをスキップ
  python run_live_tests.py --no-live

  # レポートを出力
  python run_live_tests.py --report reports/live_test_report.md

  # targets.yaml を指定
  python run_live_tests.py --targets tests/test_geps_live/targets.yaml

  # 並列実行（xdist）
  python run_live_tests.py --xdist auto

  # タイムアウト設定（秒）
  python run_live_tests.py --timeout 300

  # 組み合わせ例
  python run_live_tests.py --phase 1-10 --xdist 4 --timeout 300 --report report.md
        """
    )

    default_test_path = Path(__file__).parent.parent

    parser.add_argument(
        "--test-path",
        default=str(default_test_path),
        help=f"テストディレクトリのパス (デフォルト: {default_test_path})"
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

    parser.add_argument(
        "--notify",
        action="store_true",
        help="レポートを Slack と LINE に通知する"
    )

    parser.add_argument(
        "--targets",
        help="対象自治体リスト YAML ファイルのパス (デフォルト: test_path/targets.yaml)"
    )

    parser.add_argument(
        "--xdist",
        help="並列実行ワーカー数 (例: auto, 4). pytest-xdist が必要",
        default=None
    )

    parser.add_argument(
        "--timeout",
        type=int,
        help="テスト全体のタイムアウト秒数 (pytest-timeout 使用). デフォルト: 300秒",
        default=None
    )

    parser.add_argument(
        "--no-json-report",
        action="store_true",
        help="JSON レポート出力を無効化"
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

    # xdist ワーカー数を解析
    xdist_workers = None
    if args.xdist:
        if args.xdist.lower() == "auto":
            xdist_workers = "auto"
        else:
            try:
                xdist_workers = int(args.xdist)
            except ValueError:
                print(f"無効なワーカー数: {args.xdist}")
                sys.exit(1)

    # テストを実行
    exit_code = run_live_tests(
        test_path=args.test_path,
        phase_range=phase_range,
        skip_live=args.no_live,
        report_path=args.report,
        targets_yaml=args.targets,
        xdist_workers=xdist_workers,
        timeout=args.timeout,
        json_report=not args.no_json_report,
        notify=args.notify
    )

    sys.exit(exit_code)