from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import yaml
from bs4 import BeautifulSoup
from lxml import etree

from crawler.registry import PROJECT_ROOT, registry_identity
from utils.string_normalizer import normalize_records

DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {"User-Agent": "AgencyRegistryImporter/1.0"}


@dataclass
class ScrapedAgency:
    municipality_code: str
    name: str
    base_url: str = ""
    bid_url_pattern: str = ""
    bid_system: str = ""
    category: str = "municipality"
    type: str = "municipality"
    region: str = ""
    parser_type: str = "generic"
    parent_id: str = ""
    note: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def identity(self) -> str:
        return registry_identity(self.municipality_code, self.name)

    def __post_init__(self) -> None:
        self.parent_id = (self.parent_id or "").strip()


class RegistryScraper:
    def __init__(self, timeout=DEFAULT_TIMEOUT, headers=None, sources=None):
        self.timeout = timeout
        self.headers = headers or DEFAULT_HEADERS
        self.sources = sources or {}

    @staticmethod
    def _safe_url(value, source_url=""):
        if not isinstance(value, str) or not value.strip():
            return ""
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            return ""
        try:
            url = urljoin(source_url, value)
            parts = urlsplit(url)
            if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password:
                return url
        except ValueError:
            pass
        return ""

    def _fetch(self, path):
        if urlsplit(str(path)).scheme in ("http", "https"):
            return None
        local = Path(path)
        return local.read_bytes() if local.is_file() else None

    @staticmethod
    def _detect_encoding(content):
        if content.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return "utf-16"
        declaration = re.search(br'(?:encoding|charset)\s*=\s*["\']?([\w-]+)', content[:4096], re.I)
        if declaration:
            return declaration.group(1).decode("ascii")
        for encoding in ("utf-8", "cp932", "euc-jp", "iso-2022-jp"):
            try:
                content.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                pass
        return "utf-8"

    def _text(self, content, encoding=None):
        return content.decode(encoding or self._detect_encoding(content)) if isinstance(content, bytes) else content.lstrip("\ufeff")

    def _record(self, row, source_url, source_format, locator, columns=None, category="municipality"):
        aliases = {
            "municipality_code": ("municipality_code", "code", "@code", "団体コード", "全国地方公共団体コード", "市区町村コード"),
            "name": ("name", "agency_name", "@name", "団体名", "市区町村名", "名称"),
            "region": ("region", "prefecture_name", "都道府県名"),
        }
        values = {}
        for key in ScrapedAgency.__dataclass_fields__:
            if key == "extra":
                continue
            keys = ((columns[key],) if columns and key in columns else aliases.get(key, (key,)))
            values[key] = next((str(row[k]).strip() for k in keys if row.get(k) is not None and str(row[k]).strip()), "")
        if not values["name"]:
            return None
        values["category"] = values["category"] or category
        values["type"] = values["type"] or values["category"]
        values["parser_type"] = values["parser_type"] or "generic"
        for key in ("base_url", "bid_url_pattern"):
            values[key] = self._safe_url(values[key], source_url)
        extra = row.get("extra") or {}
        if isinstance(extra, str):
            extra = json.loads(extra)
        extra = dict(extra)
        timestamp_key = (columns or {}).get("updated_at", "updated_at")
        if row.get(timestamp_key) not in (None, ""):
            extra["updated_at"] = row[timestamp_key]
        provenance = list(extra.get("provenance", []))
        provenance.append({"source_url": source_url, "format": source_format, "locator": locator})
        extra.update(provenance=provenance, url_status="unverified")
        return ScrapedAgency(**values, extra=extra)

    def parse_csv(self, content, source_url="", columns=None, encoding=None, category="municipality"):
        reader = csv.DictReader(io.StringIO(self._text(content, encoding).lstrip("\ufeff")))
        records = []
        for index, row in enumerate(reader, 2):
            record = self._record(row, source_url, "csv", f"row:{index}", columns, category)
            if record:
                records.append(record)
        return records

    def parse_xml(self, content, source_url="", columns=None, category="municipality"):
        if isinstance(content, str):
            content = re.sub(r'<\?xml[^>]*\?>', '', content).encode("utf-8")
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        root = etree.fromstring(content, parser)
        if root.getroottree().docinfo.doctype:
            raise ValueError("DTD declarations are not supported")
        records = []

        def walk(node, parent=""):
            if not isinstance(node.tag, str):
                return
            local = etree.QName(node).localname
            if local == "CLASS_OBJ" and node.get("id") not in ("area", "region"):
                return
            row = {etree.QName(k).localname: v for k, v in node.attrib.items()}
            row.update({etree.QName(child).localname: child.text or ""
                        for child in node if isinstance(child.tag, str) and len(child) == 0})
            record = (None if local == "CLASS_OBJ" else
                      self._record(row, source_url, "xml", root.getroottree().getpath(node), columns, category))
            if record:
                record.parent_id = record.parent_id or parent
                records.append(record)
                parent = record.identity
            for child in node:
                walk(child, parent)

        walk(root)
        return records

    def parse_estat(self, content, source_url="", columns=None, encoding=None):
        text = self._text(content, encoding)
        if text.lstrip().startswith("<"):
            return self.parse_xml(text, source_url, columns)
        data = json.loads(text) if isinstance(text, str) else text
        records = []

        def walk(value, locator="$", in_area=False, parent=""):
            if isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{locator}[{index}]", in_area, parent)
            elif isinstance(value, dict):
                if "@id" in value:
                    in_area = value["@id"] in ("area", "region")
                if in_area and "@code" in value and "@name" in value:
                    record = self._record(value, source_url, "estat", locator, columns)
                    record.parent_id = record.parent_id or parent
                    records.append(record)
                    parent = record.identity
                for key, item in value.items():
                    if isinstance(item, (dict, list)):
                        walk(item, f"{locator}.{key}", in_area, parent)

        walk(data)
        return records

    def parse_html_org(self, content, ministry_name, source_url="", encoding=None):
        soup = BeautifulSoup(self._text(content, encoding), "html.parser")
        root = self._record({"name": ministry_name}, source_url, "html", "root", category="ministry")
        records = [root]
        parents = [(0, root.identity)]
        link_parents = {}
        for index, node in enumerate(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "a", "tr"]), 1):
            if node.name == "a" and node.find_parent(["h1", "h2", "h3", "h4", "h5", "h6", "tr"]):
                continue
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            heading = node.name.startswith("h")
            if heading:
                level = int(node.name[1])
                while len(parents) > 1 and parents[-1][0] >= level:
                    parents.pop()
            parent = parents[-1][1]
            link = node if node.name == "a" else node.find("a")
            if node.name == "tr":
                cells = node.find_all("td")
                if not cells:
                    continue
                text = cells[0].get_text(" ", strip=True)
            if registry_identity("", text) == root.identity:
                if heading:
                    parents.append((level, root.identity))
                continue
            if node.name == "a":
                li = node.find_parent("li")
                ancestor = li.find_parent("li") if li else None
                if ancestor:
                    parent = link_parents.get(id(ancestor), parent)
            row = {"name": text, "parent_id": parent,
                   "base_url": link.get("href", "") if link else ""}
            record = self._record(row, source_url, "html", f"element:{index}", category="ministry")
            records.append(record)
            if heading:
                parents.append((level, record.identity))
            elif node.name == "a" and node.find_parent("li"):
                link_parents[id(node.find_parent("li"))] = record.identity
        return records

    def parse_pdf(self, content, source_url="", ministry_name="", columns=None):
        import pdfplumber

        records = []
        if ministry_name:
            records.append(self._record({"name": ministry_name}, source_url, "pdf", "root", category="ministry"))
        with pdfplumber.open(io.BytesIO(content)) as document:
            for number, page in enumerate(document.pages, 1):
                tables = page.extract_tables() or []
                for table_index, table in enumerate(tables, 1):
                    if not table:
                        continue
                    headers = table[0]
                    for row_index, cells in enumerate(table[1:], 2):
                        row = dict(zip(headers, cells))
                        record = self._record(row, source_url, "pdf", f"page:{number}/table:{table_index}/row:{row_index}", columns,
                                              "ministry" if ministry_name else "municipality")
                        if record:
                            record.parent_id = record.parent_id or (records[0].identity if ministry_name else "")
                            records.append(record)
                if not tables and ministry_name:
                    for line_index, line in enumerate((page.extract_text() or "").splitlines(), 1):
                        name = line.strip()
                        if not name or name == ministry_name:
                            continue
                        record = self._record({"name": name, "parent_id": records[0].identity}, source_url, "pdf",
                                              f"page:{number}/line:{line_index}", category="ministry")
                        record.extra["hierarchy_basis"] = "flat text under supplied root; review required"
                        records.append(record)
        return records

    def ingest_source(self, source):
        content = source.get("content")
        if content is None:
            content = self._fetch(source["path"])
        if content is None:
            return []
        url = source.get("source_url", "")
        if url and not self._safe_url(url):
            raise ValueError("source_url must be an HTTP(S) provenance URL")
        fmt = source.get("format") or Path(source.get("path", "")).suffix.lstrip(".").lower()
        options = {key: source[key] for key in ("columns", "encoding") if key in source}
        if fmt == "csv":
            return self.parse_csv(content, url, **options)
        if fmt == "xml":
            return self.parse_xml(self._text(content, options["encoding"]) if "encoding" in options else content,
                                  url, options.get("columns"))
        if fmt in ("estat", "json"):
            return self.parse_estat(content, url, **options)
        if fmt == "html":
            return self.parse_html_org(content, source["ministry_name"], url, options.get("encoding"))
        if fmt == "pdf":
            return self.parse_pdf(content, url, source.get("ministry_name", ""), options.get("columns"))
        raise ValueError(f"Unsupported source format: {fmt}")

    def _load_municipality_codes_from_csv(self, path):
        return self.ingest_source({"path": path, "format": "csv"})

    def _sources_for(self, group):
        sources = self.sources.get(group, [])
        return [sources] if isinstance(sources, dict) else sources

    def scrape_municipality_codes(self):
        sources = self._sources_for("municipalities")
        if not sources:
            path = PROJECT_ROOT / "data/master/municipality_codes.csv"
            sources = [{"path": str(path), "format": "csv"}] if path.exists() else []
        return [record for source in sources for record in self.ingest_source(source)]

    def scrape_estat_master(self):
        return [record for source in self._sources_for("estat") for record in self.ingest_source(source)]

    def scrape_ministry_org_chart(self, ministry_name, org_url):
        for source in self._sources_for("ministry_org_charts"):
            if source.get("ministry_name") == ministry_name and source.get("source_url") == org_url:
                return self.ingest_source(source)
        content = self._fetch(org_url)
        return self.parse_html_org(content, ministry_name, org_url) if content is not None else []

    def _get_ministry_org_urls(self):
        return {source["ministry_name"]: source.get("source_url", "")
                for source in self._sources_for("ministry_org_charts")}

    def deduplicate_and_normalize(self, records, aliases=None, timestamp_field="updated_at"):
        return normalize_records(records, aliases, timestamp_field)

    def to_csv(self, records, output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(ScrapedAgency.__dataclass_fields__))
            writer.writeheader()
            for record in records:
                row = asdict(record)
                row["extra"] = json.dumps(row["extra"], ensure_ascii=False)
                writer.writerow(row)

    def to_yaml(self, records, output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for record in records:
            row = asdict(record)
            note = row.pop("note")
            if note:
                row["extra"]["note"] = note
            data.append(row)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def scrape_all(self, output_dir="data/scraped", include_ministry_charts=True):
        results = {"municipalities": self.scrape_municipality_codes(), "estat": self.scrape_estat_master()}
        if include_ministry_charts:
            results["ministry_org_charts"] = [record for source in self._sources_for("ministry_org_charts")
                                               for record in self.ingest_source(source)]
        for group, records in results.items():
            records = self.deduplicate_and_normalize(records)
            results[group] = records
            self.to_csv(records, str(Path(output_dir) / f"scraped_{group}.csv"))
            self.to_yaml(records, str(Path(output_dir) / f"scraped_{group}.yaml"))
        return results
