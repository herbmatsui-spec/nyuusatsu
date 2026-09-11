from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Iterable


TEMPLATE_PATH = Path(__file__).with_name("report_template.md")


def load_json_report(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as report_file:
        return json.load(report_file)


def _test_outcomes(tests: Iterable[dict[str, Any]]) -> dict[str, int]:
    outcomes = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for test in tests:
        outcome = str(test.get("outcome", "")).lower()
        if outcome in outcomes:
            outcomes[outcome] += 1
    return outcomes


def _failure_details(tests: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for test in tests:
        outcome = str(test.get("outcome", "")).lower()
        if outcome not in {"failed", "error"}:
            continue
        longrepr = test.get("longrepr")
        if isinstance(longrepr, dict):
            message = str(longrepr.get("message") or longrepr.get("crash", ""))
            traceback = str(longrepr.get("traceback") or "")
        else:
            message = str(longrepr or "テストが失敗しました")
            traceback = message
        details.append(
            {
                "nodeid": str(test.get("nodeid", "")),
                "message": message.replace("\n", " ").strip(),
                "traceback": traceback.strip(),
            }
        )
    return details


def render_markdown_report(
    report: dict[str, Any],
    *,
    executed_at: datetime | None = None,
    target_municipalities: Iterable[str] | None = None,
    json_report_path: Path | None = None,
) -> str:
    summary = report.get("summary", {})
    tests = report.get("tests", [])
    outcomes = _test_outcomes(tests)
    duration = float(report.get("duration", summary.get("duration", 0.0)) or 0.0)
    timestamp = executed_at or datetime.now(timezone.utc)
    targets = list(target_municipalities or [])
    target_text = ", ".join(targets) if targets else "未指定"
    json_path = f"`{json_report_path}`" if json_report_path else "未保存"
    test_rows = "\n".join(
        f"| {str(test.get('outcome', 'unknown')).replace('|', '\\|')} | "
        f"`{str(test.get('nodeid', '')).replace('|', '\\|')}` | "
        f"{float(test.get('duration', 0.0) or 0.0):.2f} |"
        for test in tests
    ) or "| - | 対象テストなし | 0.00 |"
    details = _failure_details(tests)
    if details:
        error_details = "\n\n".join(
            f"### `{detail['nodeid']}`\n\n"
            f"**メッセージ:** {detail['message']}\n\n"
            f"```text\n{detail['traceback']}\n```"
            for detail in details
        )
    else:
        error_details = "エラーはありません。"

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.substitute(
        executed_at=timestamp.astimezone().isoformat(timespec="seconds"),
        target_municipalities=target_text,
        total=summary.get("total", len(tests)),
        passed=outcomes["passed"],
        failed=outcomes["failed"] + outcomes["error"],
        skipped=outcomes["skipped"],
        duration=f"{duration:.2f}",
        json_report_path=json_path,
        test_rows=test_rows,
        error_details=error_details,
    )


def write_markdown_report(
    json_report_path: Path,
    markdown_report_path: Path,
    *,
    executed_at: datetime | None = None,
    target_municipalities: Iterable[str] | None = None,
) -> dict[str, Any]:
    report = load_json_report(json_report_path)
    markdown_report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_report_path.write_text(
        render_markdown_report(
            report,
            executed_at=executed_at,
            target_municipalities=target_municipalities,
            json_report_path=json_report_path,
        ),
        encoding="utf-8",
    )
    return report
