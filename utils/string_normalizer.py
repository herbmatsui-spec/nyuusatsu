from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


def normalize_whitespace(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Names must be strings")
    return " ".join(unicodedata.normalize("NFKC", value).split())


class StringNormalizer:
    def __init__(self, aliases=None):
        if aliases is not None and not isinstance(aliases, Mapping):
            raise TypeError("Aliases must be a mapping")
        direct = {}
        for source, target in (aliases or {}).items():
            source, target = normalize_whitespace(source), normalize_whitespace(target)
            if not source or not target:
                raise ValueError("Alias names must not be empty")
            if source in direct and direct[source] != target:
                raise ValueError(f"Conflicting aliases for {source!r}")
            direct[source] = target
        self._aliases = {}
        for source in direct:
            current = source
            visited = set()
            while current in direct and direct[current] != current:
                if current in visited:
                    raise ValueError(f"Cyclic alias: {source!r}")
                visited.add(current)
                current = direct[current]
            self._aliases[source] = current

    def normalize(self, value: str) -> str:
        value = normalize_whitespace(value)
        return self._aliases.get(value, value)

    def normalize_records(self, records, timestamp_field="updated_at"):
        originals = list(records)
        rows = []
        for record in originals:
            row = asdict(record) if is_dataclass(record) else deepcopy(dict(record))
            row["name"] = self.normalize(row["name"])
            if not row["name"]:
                raise ValueError("Agency name must not be empty")
            code = row.get("municipality_code", "")
            if code is not None and not isinstance(code, str):
                raise TypeError("Municipality codes must be strings")
            row["region"] = self.normalize(row.get("region") or "")
            reference = row.get("parent_id") or ""
            if not isinstance(reference, str):
                raise TypeError("Parent references must be strings")
            reference = reference.strip()
            if reference.startswith("name:"):
                reference = "name:" + self.normalize(reference[5:])
            row["parent_id"] = reference
            rows.append(row)

        names, codes = {}, {}
        for index, row in enumerate(rows):
            names.setdefault(row["name"], []).append(index)
            code = (row.get("municipality_code") or "").strip()
            if code:
                codes.setdefault(code, []).append(index)

        signatures, parents, visiting = {}, {}, set()

        def signature(index):
            if index in signatures:
                return signatures[index]
            if index in visiting:
                raise ValueError(f"Cyclic parent: {rows[index]['name']!r}")
            visiting.add(index)
            row = rows[index]
            reference = row["parent_id"]
            if reference.startswith("code:"):
                candidates = codes.get(reference[5:], [])
            elif reference.startswith("name:"):
                candidates = names.get(reference[5:], [])
            else:
                candidates = list(set(codes.get(reference, []) + names.get(self.normalize(reference), [])))
            if candidates:
                targets = {signature(candidate) for candidate in candidates}
                if len(targets) != 1:
                    raise ValueError(f"Ambiguous parent: {reference!r}")
                parent = next(iter(targets))
                target = rows[candidates[0]]
                code = (target.get("municipality_code") or "").strip()
                parents[index] = f"code:{code}" if code else f"name:{target['name']}"
            else:
                if reference and not reference.startswith(("code:", "name:")):
                    reference = self.normalize(reference)
                parents[index] = reference
                parent = ("external", reference)
            result = (row["name"], parent, row["region"], row.get("category") or "",
                      (row.get("municipality_code") or "").strip())
            signatures[index] = result
            visiting.remove(index)
            return result

        for index in range(len(rows)):
            signature(index)
        for code, indexes in codes.items():
            if len({signatures[index] for index in indexes}) != 1:
                raise ValueError(f"Conflicting records for code: {code!r}")
        scopes = {}
        for key in signatures.values():
            scopes.setdefault(key[:-1], set()).add(key[-1])
        for scope, values in scopes.items():
            if "" in values and len(values) > 1:
                raise ValueError(f"Ambiguous conflicting codes for {scope[0]!r}")

        selected = {}
        for index, row in enumerate(rows):
            timestamp = row.get(timestamp_field)
            if timestamp in (None, ""):
                timestamp = (row.get("extra") or {}).get(timestamp_field)
            rank = self._timestamp(timestamp)
            key = signatures[index]
            if key not in selected or rank >= selected[key][0]:
                selected[key] = rank, index
        result = []
        for _, index in selected.values():
            row = rows[index]
            updates = {"name": row["name"], "region": row["region"], "parent_id": parents[index]}
            original = originals[index]
            if is_dataclass(original):
                result.append(replace(deepcopy(original), **updates))
            else:
                row.update(updates)
                result.append(row)
        return result

    @staticmethod
    def _timestamp(value):
        if value in (None, ""):
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(f"Invalid timestamp: {value!r}") from error
        if not isinstance(value, datetime):
            raise ValueError(f"Invalid timestamp: {value!r}")
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def normalize(value: str, aliases=None) -> str:
    return StringNormalizer(aliases).normalize(value)


def normalize_records(records, aliases=None, timestamp_field="updated_at"):
    return StringNormalizer(aliases).normalize_records(records, timestamp_field)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Normalize agency records from local JSON or stdin")
    parser.add_argument("input", nargs="?", default="-")
    parser.add_argument("--aliases", type=Path)
    parser.add_argument("--timestamp-field", default="updated_at")
    args = parser.parse_args(argv)
    aliases = json.loads(args.aliases.read_text(encoding="utf-8")) if args.aliases else None
    records = json.load(sys.stdin) if args.input == "-" else json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        parser.error("Input must be a JSON array of records")
    print(json.dumps(normalize_records(records, aliases, args.timestamp_field), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
