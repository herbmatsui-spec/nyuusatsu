from __future__ import annotations

from datetime import date, datetime
from typing import List


def generate_ics(milestones: List[dict]) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BidSystem//JP",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for ms in milestones:
        dt = ms.get("date")
        if isinstance(dt, datetime):
            dt = dt.date()
        if dt is None:
            continue
        dt_str = dt.strftime("%Y%m%d")
        uid = f"bid-{ms.get('bid_id', 'unknown')}-{ms.get('type', 'milestone')}@{dt_str}"
        summary = ms.get("type", "入札マイルストーン")
        filename = ms.get("filename", "")
        desc = f"案件: {filename}"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;VALUE=DATE:{dt_str}",
            f"DTEND;VALUE=DATE:{dt_str}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")
