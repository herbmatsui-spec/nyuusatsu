from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawler.utils.domain_collection import (
    DomainCollectionError,
    extract_candidates,
    integrate_candidates,
    read_organizations,
    report_candidates,
    review_candidates,
    write_candidates,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Offline evidenced domain candidates; no network or database access")
    commands = result.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Rank links from a saved UTF-8 HTML file; all candidates remain pending")
    extract.add_argument("--html", type=Path, required=True)
    extract.add_argument("--source-url", required=True)
    extract.add_argument("--organizations", type=Path, required=True)
    extract.add_argument("--category", help="Required for organization CSV without category; exact category for procurement context")
    extract.add_argument("--agency-name", help="Explicit organization context for a saved procurement page")
    extract.add_argument("--fuzzy-threshold", type=float, default=0.8)
    extract.add_argument("--output", type=Path, required=True)
    review = commands.add_parser("review", help="Explicitly approve or reject selected 1-based candidate rows")
    review.add_argument("--input", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    decision = review.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", type=int, nargs="+", metavar="ROW")
    decision.add_argument("--reject", type=int, nargs="+", metavar="ROW")
    review.add_argument("--note")
    integrate = commands.add_parser("integrate", help="Fill empty master fields with approved candidates; reject conflicts")
    integrate.add_argument("--master", type=Path, required=True)
    integrate.add_argument("--candidates", type=Path, nargs="+", required=True)
    integrate.add_argument("--output", type=Path, required=True)
    integrate.add_argument("--category", help="Explicit category if master CSV has no category")
    integrate.add_argument("--in-place", action="store_true", help="Deliberately replace master atomically; output must equal master")
    report = commands.add_parser("report", help="Print JSON summary and numbered candidates; never writes files")
    report.add_argument("--input", type=Path, required=True)
    for command in (extract, review, integrate, report):
        command.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "extract":
            organizations = read_organizations(args.organizations, args.category)
            candidates = extract_candidates(
                args.html, args.source_url, organizations,
                fuzzy_threshold=args.fuzzy_threshold, agency_name=args.agency_name,
                category=args.category,
            )
            write_candidates(args.output, candidates, inputs=(args.html, args.organizations), dry_run=args.dry_run)
            result = {"total": len(candidates), "status": "pending", "dry_run": args.dry_run}
        elif args.command == "review":
            approved = args.approve is not None
            candidates = review_candidates(
                args.input, args.output, args.approve if approved else args.reject,
                "approved" if approved else "rejected", args.note, args.dry_run,
            )
            result = {"total": len(candidates), "selected": len(set(args.approve if approved else args.reject)), "dry_run": args.dry_run}
        elif args.command == "integrate":
            result = integrate_candidates(
                args.master, args.candidates, args.output,
                category=args.category, dry_run=args.dry_run, in_place=args.in_place,
            )
            result["dry_run"] = args.dry_run
        else:
            result = report_candidates(args.input)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (DomainCollectionError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
