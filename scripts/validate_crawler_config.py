from __future__ import annotations

import argparse
import codecs
import math
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

if __name__ == "__main__":
    sys.dont_write_bytecode = True

import soupsieve
import yaml


TOP_LEVEL_KEYS = {
    "agency_name", "agency_type", "agency_name_aliases", "municipality_code", "parent_id",
    "base_url", "list_url", "start_url", "list_item_selector", "list_selector",
    "title_selector", "detail_selector", "pagination_selector", "pagination",
    "pdf_detection", "dynamic_links", "encoding", "crawl_settings", "detail_fields",
    "parser", "page_format", "url_status", "registry_source", "enabled", "approved",
    "robots_allowed", "extraction_verified",
}
SETTING_RANGES = {
    "max_pages": (1, 10000, True), "retry": (1, 10, True),
    "timeout": (0.001, 300, False), "delay": (0, 3600, False),
    "max_depth": (0, 20, True), "backoff": (0, 300, False),
    "backoff_jitter": (0, 300, False), "rate_limit": (0, 3600, False),
}
TRANSFORMS = {
    "normalize_amount", "normalize_date", "normalize_whitespace",
    "normalize_fullwidth_to_halfwidth",
}


class ConfigValidationError(ValueError):
    pass


def safe_http_url(value, base_url=""):
    if not isinstance(value, str) or not value or value.startswith("#"):
        return None
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    if "\\" in value or any(ord(char) < 32 or ord(char) == 127 for char in unquote(value)):
        return None
    try:
        url = urldefrag(urljoin(base_url, value))[0]
        parts = urlsplit(url)
        host = parts.hostname
        if parts.scheme not in ("http", "https") or not host or parts.username is not None or parts.password is not None:
            return None
        if any(char in host for char in "%{}\\") or "{" in url or "}" in url:
            return None
        if ":" not in host:
            labels = host.rstrip(".").encode("idna").decode("ascii").split(".")
            if any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels):
                return None
        if parts.port == 0:
            return None
        return url
    except (ValueError, UnicodeError):
        return None


def validate_config(config, path="<config>", strict=True):
    errors = []

    def error(field, reason):
        errors.append(f"{path}: {field}: {reason}")

    def mapping(value, field, allowed=None):
        if not isinstance(value, dict):
            error(field, "must be a mapping")
            return False
        for key in value:
            if not isinstance(key, str) or (allowed is not None and key not in allowed):
                error(f"{field}.{key}" if field != "$" else str(key), "unknown key")
        return True

    def text(value, field):
        if not isinstance(value, str) or not value.strip():
            error(field, "must be a nonempty string")
            return False
        return True

    def selector(value, field):
        if text(value, field):
            try:
                soupsieve.compile(value)
            except (soupsieve.SelectorSyntaxError, NotImplementedError, ValueError) as exc:
                error(field, f"invalid CSS selector: {exc}")

    def boolean(value, field):
        if type(value) is not bool:
            error(field, "must be a boolean")

    def number(value, field, key):
        lower, upper, integer = SETTING_RANGES[key]
        if (type(value) not in (int, float) or (integer and type(value) is not int)
                or not lower <= value <= upper or not math.isfinite(value)):
            kind = "integer" if integer else "finite number"
            error(field, f"must be a {kind} in [{lower}, {upper}]")

    def sequence(value, field, check):
        if not isinstance(value, list):
            error(field, "must be a list")
            return
        for index, item in enumerate(value):
            check(item, f"{field}[{index}]")

    def charset(value, field):
        if text(value, field):
            try:
                b"".decode(value)
                codecs.lookup(value)
            except (LookupError, ValueError, TypeError):
                error(field, "must name a supported text encoding")

    def attribute(value, field, dynamic=False):
        pattern = r"data-[A-Za-z0-9_-]+" if dynamic else r"[A-Za-z_:][A-Za-z0-9_.:-]*"
        if text(value, field) and not re.fullmatch(pattern, value):
            error(field, "invalid data attribute" if dynamic else "invalid attribute name")

    if not mapping(config, "$", TOP_LEVEL_KEYS):
        return errors
    if strict and not any(key in config for key in ("start_url", "list_url", "base_url")):
        error("start_url/list_url/base_url", "one HTTP(S) URL is required")
    for key in ("start_url", "list_url", "base_url"):
        if key in config and not safe_http_url(config[key]):
            error(key, "must be an absolute HTTP(S) URL without credentials, whitespace or unsafe characters")
    if strict and not any(key in config for key in ("list_item_selector", "list_selector")):
        error("list_item_selector/list_selector", "a nonempty CSS selector is required")
    for key in ("list_item_selector", "list_selector", "detail_selector", "title_selector", "pagination_selector"):
        if key in config:
            selector(config[key], key)
    for key in ("agency_name", "agency_type", "registry_source"):
        if key in config:
            text(config[key], key)
    for key in ("municipality_code", "parent_id"):
        if key in config and not isinstance(config[key], str):
            error(key, "must be a string")
    for key in ("enabled", "approved", "robots_allowed", "extraction_verified"):
        if key in config:
            boolean(config[key], key)
    for key in ("parser", "page_format"):
        if key in config and config[key] not in ("html", "pdf"):
            error(key, "must be html or pdf")
    if "url_status" in config and config["url_status"] not in ("unverified", "verified", "invalid", "missing", "unreachable"):
        error("url_status", "unknown URL status")
    if "agency_name_aliases" in config:
        aliases = config["agency_name_aliases"]
        if mapping(aliases, "agency_name_aliases"):
            for key, value in aliases.items():
                text(key, "agency_name_aliases key")
                text(value, f"agency_name_aliases.{key}")
    if "pagination" in config:
        pagination = config["pagination"]
        if mapping(pagination, "pagination", {"next_button_selectors", "max_pages"}):
            if "max_pages" in pagination:
                number(pagination["max_pages"], "pagination.max_pages", "max_pages")
            if "next_button_selectors" in pagination:
                selectors = pagination["next_button_selectors"]
                if isinstance(selectors, str):
                    selector(selectors, "pagination.next_button_selectors")
                else:
                    sequence(selectors, "pagination.next_button_selectors", selector)
    if "crawl_settings" in config:
        settings = config["crawl_settings"]
        allowed = (set(SETTING_RANGES) - {"max_pages"}) | {"user_agent"}
        if mapping(settings, "crawl_settings", allowed):
            for key, value in settings.items():
                if key in allowed - {"user_agent"}:
                    number(value, f"crawl_settings.{key}", key)
                elif key == "user_agent" and text(value, "crawl_settings.user_agent"):
                    if any(ord(char) < 32 or ord(char) == 127 for char in value):
                        error("crawl_settings.user_agent", "must not contain control characters")
    if "encoding" in config:
        encoding = config["encoding"]
        if isinstance(encoding, str):
            charset(encoding, "encoding")
        elif mapping(encoding, "encoding", {"preferred", "auto_detect", "fallback_encodings"}):
            if "preferred" in encoding:
                charset(encoding["preferred"], "encoding.preferred")
            if "auto_detect" in encoding:
                boolean(encoding["auto_detect"], "encoding.auto_detect")
            if "fallback_encodings" in encoding:
                sequence(encoding["fallback_encodings"], "encoding.fallback_encodings", charset)
    if "dynamic_links" in config:
        dynamic = config["dynamic_links"]
        if isinstance(dynamic, list):
            sequence(dynamic, "dynamic_links", lambda value, field: attribute(value, field, True))
        elif mapping(dynamic, "dynamic_links", {"data_url_attribute", "data_href_attribute"}):
            for key, value in dynamic.items():
                attribute(value, f"dynamic_links.{key}", True)
    if "pdf_detection" in config:
        pdf = config["pdf_detection"]
        if mapping(pdf, "pdf_detection", {"extension_pattern", "text_keywords"}):
            if "extension_pattern" in pdf:
                value = pdf["extension_pattern"]
                if text(value, "pdf_detection.extension_pattern") and not re.fullmatch(r"\.[A-Za-z0-9]+", value):
                    error("pdf_detection.extension_pattern", "must be a literal file extension")
            if "text_keywords" in pdf:
                sequence(pdf["text_keywords"], "pdf_detection.text_keywords", text)
    if "detail_fields" in config:
        fields = config["detail_fields"]
        if mapping(fields, "detail_fields"):
            for name, field in fields.items():
                prefix = f"detail_fields.{name}"
                text(name, "detail_fields key")
                if not mapping(field, prefix, {"selector", "attr", "transform", "required", "multiple"}):
                    continue
                selector(field.get("selector"), f"{prefix}.selector")
                if "attr" in field:
                    attribute(field["attr"], f"{prefix}.attr")
                if "transform" in field and (not isinstance(field["transform"], str) or field["transform"] not in TRANSFORMS):
                    error(f"{prefix}.transform", "unknown transform")
                for key in ("required", "multiple"):
                    if key in field:
                        boolean(field[key], f"{prefix}.{key}")
    return errors


def require_valid_config(config, path="<config>", strict=True):
    errors = validate_config(config, path, strict=strict)
    if errors:
        raise ConfigValidationError("\n".join(errors))
    return config


def validation_result(config, path="<config>", strict=True):
    errors = validate_config(config, path, strict=strict)
    execution_errors = []
    for key in ("enabled", "approved", "robots_allowed", "extraction_verified"):
        if not isinstance(config, dict) or config.get(key) is not True:
            execution_errors.append(f"{path}: {key}: not confirmed; syntax validation does not authorize execution")
    return {"syntax_valid": not errors, "errors": errors,
            "execution_eligible": not errors and not execution_errors,
            "execution_errors": execution_errors}


def load_config(path):
    if path is None:
        raise ConfigValidationError("<config>: path: a config file is required")
    path = Path(path)
    try:
        content = path.read_text(encoding="utf-8")
        root = yaml.compose(content, Loader=yaml.SafeLoader)
        visited = set()

        def check_keys(node, field):
            if node is None or id(node) in visited:
                return
            visited.add(id(node))
            if isinstance(node, yaml.MappingNode):
                seen = set()
                for key, value in node.value:
                    if not isinstance(key, yaml.ScalarNode):
                        raise ConfigValidationError(f"{path}: {field}: mapping keys must be strings")
                    identity = (key.tag, key.value)
                    if identity in seen:
                        raise ConfigValidationError(f"{path}: {field}.{key.value}: duplicate key at line {key.start_mark.line + 1}")
                    seen.add(identity)
                    check_keys(value, f"{field}.{key.value}")
            elif isinstance(node, yaml.SequenceNode):
                for index, value in enumerate(node.value):
                    check_keys(value, f"{field}[{index}]")

        check_keys(root, "$")
        config = yaml.safe_load(content)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError) as exc:
        raise ConfigValidationError(f"{path}: YAML: {exc}") from exc
    return require_valid_config(config, str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate local crawler configuration syntax without executing crawlers")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    paths = []
    errors = []
    for path in args.paths:
        if path.is_dir():
            found = sorted(set(path.rglob("*.yaml")) | set(path.rglob("*.yml")))
            if not found:
                errors.append(f"{path}: no YAML configuration files found")
            paths.extend(found)
        else:
            paths.append(path)
    for path in dict.fromkeys(paths):
        try:
            config = load_config(path)
            result = validation_result(config, str(path))
            state = "eligible" if result["execution_eligible"] else "not authorized"
            print(f"{path}: syntax valid; execution {state}")
            for reason in result["execution_errors"]:
                print(reason)
        except ConfigValidationError as exc:
            errors.append(str(exc))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
