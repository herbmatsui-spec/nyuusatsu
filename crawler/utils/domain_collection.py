from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from dataclasses import asdict, dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


CANDIDATE_FIELDS = (
    "agency_name", "category", "base_url", "bid_url_pattern",
    "source_url", "status", "note",
)
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000
MAX_LINKS = 5000
MAX_ORGANIZATIONS = 1000
MAX_COMPARISONS = 100000
BID_WORDS = re.compile(r"入札|調達|契約|procurement|tender|bid|keiyaku|nyusatsu", re.I)


class DomainCollectionError(ValueError):
    pass


def public_url(value: str) -> str:
    if not value or len(value) > 4096 or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        raise DomainCollectionError("Invalid URL characters or length")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").encode("idna").decode("ascii").lower()
        port = parts.port
    except (ValueError, UnicodeError) as exc:
        raise DomainCollectionError("Invalid URL") from exc
    labels = host.split(".")
    reserved = {"localhost", "local", "internal", "lan", "home", "test", "invalid", "example", "onion", "arpa"}
    if (
        parts.scheme not in {"http", "https"}
        or parts.username is not None or parts.password is not None
        or port not in {None, 80, 443}
        or len(host) > 253 or len(labels) < 2
        or labels[-1] in reserved
        or not re.fullmatch(r"[a-z][a-z0-9-]*", labels[-1])
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
    ):
        raise DomainCollectionError("URL must use a public HTTP(S) hostname without credentials")
    authority = host
    if port is not None and port != {"http": 80, "https": 443}[parts.scheme]:
        authority += f":{port}"
    return urlunsplit((parts.scheme, authority, parts.path or "/", parts.query, ""))


@dataclass(frozen=True)
class Candidate:
    agency_name: str
    category: str
    base_url: str
    bid_url_pattern: str
    source_url: str
    status: str = "pending"
    note: str = ""

    def __post_init__(self) -> None:
        for value in asdict(self).values():
            if not isinstance(value, str) or len(value) > 8192 or "\x00" in value:
                raise DomainCollectionError("Invalid candidate field")
        if not self.agency_name.strip() or not self.category.strip():
            raise DomainCollectionError("Candidate requires agency_name and category")
        if self.status not in {"pending", "approved", "rejected"}:
            raise DomainCollectionError("Invalid review status")
        public_url(self.base_url)
        public_url(self.source_url)
        if self.bid_url_pattern:
            public_url(self.bid_url_pattern)


def read_text(path: str | Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise DomainCollectionError("Input must be a regular local file")
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise DomainCollectionError(f"Input exceeds {MAX_BYTES} bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainCollectionError("Input must be UTF-8") from exc
    if "\x00" in text:
        raise DomainCollectionError("NUL characters are not allowed")
    return text


def read_csv(path: str | Path, required: tuple[str, ...]) -> tuple[list[str], list[dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(read_text(path), newline=""), strict=True)
        fields = reader.fieldnames
        if not fields or any(not field or field != field.strip() for field in fields):
            raise DomainCollectionError("Missing or invalid CSV header")
        if len(fields) != len(set(fields)) or not set(required).issubset(fields):
            raise DomainCollectionError("Duplicate or missing CSV columns")
        rows = []
        for row in reader:
            if len(rows) >= MAX_ROWS or None in row or any(value is None for value in row.values()):
                raise DomainCollectionError("Invalid CSV row shape or row limit exceeded")
            rows.append(row)
        return fields, rows
    except csv.Error as exc:
        raise DomainCollectionError(f"Invalid CSV: {exc}") from exc


def read_candidates(path: str | Path) -> list[Candidate]:
    fields, rows = read_csv(path, CANDIDATE_FIELDS)
    if set(fields) != set(CANDIDATE_FIELDS):
        raise DomainCollectionError("Unknown candidate columns")
    return [Candidate(**row) for row in rows]


def same_file(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and left.samefile(right)
    )


def atomic_csv(
    output: str | Path, fields: tuple[str, ...] | list[str], rows: list[dict[str, str]],
    inputs: tuple[Path, ...] = (), dry_run: bool = False,
    replace_input: Path | None = None,
) -> None:
    output = Path(output)
    replacing = replace_input is not None and same_file(output, replace_input)
    if output.is_symlink():
        raise DomainCollectionError("Output cannot be a symlink")
    for source in inputs:
        if same_file(output, source) and not (replacing and source == replace_input):
            raise DomainCollectionError("Output would overwrite an input")
    if output.exists() and not replacing:
        raise DomainCollectionError("Output already exists; choose a new path")
    if not output.parent.is_dir():
        raise DomainCollectionError("Output directory must already exist")
    if len(rows) > MAX_ROWS:
        raise DomainCollectionError("Output row limit exceeded")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue()
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise DomainCollectionError("Output byte limit exceeded")
    if dry_run:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if replacing:
            os.replace(temporary, output)
        else:
            os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_candidates(
    output: str | Path, candidates: list[Candidate],
    inputs: tuple[Path, ...] = (), dry_run: bool = False,
) -> None:
    atomic_csv(output, CANDIDATE_FIELDS, [asdict(candidate) for candidate in candidates], inputs, dry_run)


def read_organizations(path: str | Path, category: str | None = None) -> list[tuple[str, str]]:
    fields, rows = read_csv(path, ("agency_name",))
    if "category" not in fields and not category:
        raise DomainCollectionError("Organization CSV requires category or explicit category")
    organizations = []
    for row in rows:
        row_category = row.get("category", "") or category or ""
        if not row["agency_name"].strip() or not row_category.strip():
            raise DomainCollectionError("Empty organization name or category")
        if category and row_category != category:
            raise DomainCollectionError("Explicit category conflicts with CSV category")
        organizations.append((row["agency_name"], row_category))
    organizations = list(dict.fromkeys(organizations))
    if len(organizations) > MAX_ORGANIZATIONS:
        raise DomainCollectionError("Too many organizations")
    return organizations


def extract_candidates(
    html_path: str | Path, source_url: str, organizations: list[tuple[str, str]],
    fuzzy_threshold: float = 0.8, agency_name: str | None = None,
    category: str | None = None,
) -> list[Candidate]:
    source_url = public_url(source_url)
    if not 0.5 <= fuzzy_threshold <= 1 or len(organizations) > MAX_ORGANIZATIONS:
        raise DomainCollectionError("Invalid fuzzy threshold or organization limit")
    organizations = list(dict.fromkeys(organizations))
    if agency_name is not None and (agency_name, category) not in organizations:
        raise DomainCollectionError("Procurement page requires an exact name and category from organizations")
    soup = BeautifulSoup(read_text(html_path), "html.parser")
    links = soup.find_all("a", href=True, limit=MAX_LINKS + 1)
    if len(links) > MAX_LINKS:
        raise DomainCollectionError("Too many hyperlinks")
    ranked = {}
    comparisons = 0
    for link in links:
        href = str(link["href"])
        if not href or href.startswith("#") or re.search(r"[\s\\\x00-\x1f\x7f]", href):
            continue
        try:
            url = public_url(urljoin(source_url, href))
        except DomainCollectionError:
            continue
        text = link.get_text(" ", strip=True)
        is_bid = bool(BID_WORDS.search(text + " " + urlsplit(url).path))
        if agency_name is not None:
            matches = [(agency_name, category, 1.0, "explicit-page") ] if is_bid else []
        else:
            matches = [(name, cat, 1.0, "exact") for name, cat in organizations if text == name]
            if not matches and text:
                comparisons += len(organizations)
                if comparisons > MAX_COMPARISONS:
                    raise DomainCollectionError("Fuzzy comparison limit exceeded")
                for name, cat in organizations:
                    score = SequenceMatcher(None, text[:512], name[:512]).ratio()
                    if score >= fuzzy_threshold:
                        matches.append((name, cat, score, "suggested-fuzzy"))
        parts = urlsplit(url)
        base_url = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
        for name, cat, score, method in matches:
            candidate = Candidate(
                name, cat, base_url, url if is_bid else "", source_url,
                note=f"match={method}; score={score:.3f}; link={url}; text={text[:512]}",
            )
            key = (name, cat, base_url, candidate.bid_url_pattern)
            rank = (score, int(is_bid), int(parts.hostname.endswith((".go.jp", ".or.jp"))))
            if key not in ranked or rank > ranked[key][0]:
                ranked[key] = (rank, candidate)
    return [item[1] for item in sorted(ranked.values(), key=lambda item: (tuple(-n for n in item[0]), item[1].agency_name, item[1].base_url, item[1].bid_url_pattern))]


def review_candidates(
    input_path: str | Path, output: str | Path, row_numbers: list[int],
    decision: str, note: str | None = None, dry_run: bool = False,
) -> list[Candidate]:
    candidates = read_candidates(input_path)
    if decision not in {"approved", "rejected"}:
        raise DomainCollectionError("Review decision must be approved or rejected")
    if not row_numbers or any(number < 1 or number > len(candidates) for number in row_numbers):
        raise DomainCollectionError("Review requires valid 1-based candidate row numbers")
    selected = set(row_numbers)
    result = [
        replace(item, status=decision, note=item.note + (f"; review={note}" if note else ""))
        if number in selected else item
        for number, item in enumerate(candidates, 1)
    ]
    write_candidates(output, result, inputs=(Path(input_path),), dry_run=dry_run)
    return result


def integrate_candidates(
    master_path: str | Path, candidate_paths: list[str | Path], output: str | Path,
    category: str | None = None, dry_run: bool = False, in_place: bool = False,
) -> dict[str, int]:
    master_path = Path(master_path)
    if not candidate_paths or len(candidate_paths) > 100:
        raise DomainCollectionError("Supply between 1 and 100 candidate CSV files")
    fields, rows = read_csv(master_path, ("agency_name",))
    if "category" not in fields and not category:
        raise DomainCollectionError("Master requires category column or explicit category")
    index = {}
    for row in rows:
        row_category = row.get("category", "") or category or ""
        key = (row["agency_name"], row_category)
        if not key[0].strip() or not key[1].strip():
            raise DomainCollectionError("Master requires nonempty names and categories")
        if category and row_category != category:
            raise DomainCollectionError("Explicit category conflicts with master category")
        if key in index:
            raise DomainCollectionError(f"Duplicate master identity: {key}")
        index[key] = row
    approved: dict[tuple[str, str], dict[str, str]] = {}
    ignored = 0
    approved_count = 0
    total = 0
    for path in candidate_paths:
        candidates = read_candidates(path)
        total += len(candidates)
        if total > MAX_ROWS:
            raise DomainCollectionError("Combined candidate row limit exceeded")
        for item in candidates:
            if item.status != "approved":
                ignored += 1
                continue
            approved_count += 1
            key = (item.agency_name, item.category)
            if key not in index:
                raise DomainCollectionError(f"Approved candidate missing exact master identity: {key}")
            proposed = approved.setdefault(key, {})
            for field in ("base_url", "bid_url_pattern"):
                value = getattr(item, field)
                if not value:
                    continue
                value = public_url(value)
                if field in proposed and proposed[field] != value:
                    raise DomainCollectionError(f"Conflicting approved candidates: {key} {field}")
                existing = index[key].get(field, "")
                if existing and public_url(existing) != value:
                    raise DomainCollectionError(f"Conflict with master: {key} {field}")
                proposed[field] = value
    changed = 0
    for key, proposed in approved.items():
        row = index[key]
        updated = False
        for field, value in proposed.items():
            if not row.get(field, ""):
                if field not in fields:
                    fields.append(field)
                    for existing_row in rows:
                        existing_row[field] = ""
                row[field] = value
                updated = True
        changed += int(updated)
    if in_place and not same_file(Path(output), master_path):
        raise DomainCollectionError("In-place integration requires output to be the master path")
    atomic_csv(
        output, fields, rows,
        inputs=(master_path, *(Path(path) for path in candidate_paths)),
        dry_run=dry_run, replace_input=master_path if in_place else None,
    )
    return {"master_rows": len(rows), "approved": approved_count, "ignored": ignored, "updated": changed}


def report_candidates(input_path: str | Path) -> dict:
    candidates = read_candidates(input_path)
    counts = {status: 0 for status in ("pending", "approved", "rejected")}
    identities = set()
    for item in candidates:
        counts[item.status] += 1
        identities.add((item.agency_name, item.category))
    return {
        "total": len(candidates), "organizations": len(identities), "statuses": counts,
        "candidates": [{"row": number, **asdict(item)} for number, item in enumerate(candidates, 1)],
    }
