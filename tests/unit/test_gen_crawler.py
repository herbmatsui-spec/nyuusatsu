"""Tests for scripts/gen_crawler.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml
from scripts.gen_crawler import (
    detect_charset,
    detect_charset_from_html,
    generate_config_dict,
    render_config_yaml,
    safe_name,
    class_name,
    AGENCY_TYPE_DEFAULTS,
    PAGINATION_SELECTORS,
    PDF_LINK_KEYWORDS,
    generate_from_registry,
)


def test_detect_charset_utf8():
    """UTF-8バイトデータの検出。"""
    assert detect_charset("テスト".encode("utf-8")) == "utf-8"


def test_detect_charset_shift_jis():
    """Shift_JISバイトデータの検出。"""
    result = detect_charset("テスト".encode("shift_jis"))
    assert result in ("shift_jis", "cp932")


def test_detect_charset_euc_jp():
    text = "テストデータテストデータ"
    content = text.encode("euc_jp")
    assert content.decode(detect_charset(content)) == text


def test_detect_charset_from_html_meta():
    """HTML metaタグから文字コード検出。"""
    html = '<html><head><meta charset="shift_jis"></head></html>'
    assert detect_charset_from_html(html) == "shift_jis"


def test_detect_charset_from_html_http_equiv():
    """HTML http-equiv metaから文字コード検出。"""
    html = '<html><head><META http-equiv="Content-Type" content="text/html; charset=euc-jp"></head></html>'
    assert detect_charset_from_html(html) == "euc_jp"


def test_detect_charset_from_html_default():
    """メタタグがない場合はUTF-8を返す。"""
    assert detect_charset_from_html("<html></html>") == "utf-8"


def test_agency_type_defaults():
    """すべての機関タイプのデフォルト設定が存在すること。"""
    for t in ["ministry", "prefecture", "municipality", "quasi", "default"]:
        assert t in AGENCY_TYPE_DEFAULTS
        defaults = AGENCY_TYPE_DEFAULTS[t]
        assert "delay" in defaults
        assert "retry" in defaults
        assert "timeout" in defaults
        assert "max_depth" in defaults


def test_ministry_has_higher_delay():
    """省庁は自治体より高い遅延・リトライ設定を持つこと。"""
    assert AGENCY_TYPE_DEFAULTS["ministry"]["delay"] > AGENCY_TYPE_DEFAULTS["municipality"]["delay"]
    assert AGENCY_TYPE_DEFAULTS["ministry"]["retry"] >= AGENCY_TYPE_DEFAULTS["municipality"]["retry"]


def test_pagination_selectors_not_empty():
    """ページネーションセレクタリストが空でないこと。"""
    assert len(PAGINATION_SELECTORS) >= 5


def test_pdf_link_keywords_not_empty():
    """PDFリンクキーワードリストが空でないこと。"""
    assert len(PDF_LINK_KEYWORDS) >= 5
    assert "入札" in PDF_LINK_KEYWORDS


def test_safe_name():
    """機関名から安全なファイル名を生成すること。"""
    assert safe_name("示例市") == "示例市"
    assert safe_name("札幌市") == "札幌市"
    assert safe_name("test agency") == "test_agency"
    assert safe_name("test-agency!") == "test_agency"


def test_class_name():
    """機関名からクラス名を生成すること。"""
    assert class_name("示例市") == "示例市Fetcher"
    assert class_name("test agency") == "testagencyFetcher"


def test_generate_config_dict_basic():
    """基本的な設定辞書が生成できること。"""
    cfg = generate_config_dict("テスト市", "https://example.com/")
    assert cfg["agency_name"] == "テスト市"
    assert cfg["base_url"] == "https://example.com/"
    assert cfg["agency_type"] == "default"
    assert "pagination" in cfg
    assert "pdf_detection" in cfg
    assert "dynamic_links" in cfg
    assert "encoding" in cfg
    assert "crawl_settings" in cfg
    assert "detail_fields" in cfg


def test_generate_config_dict_agency_type():
    """agency_typeに応じた設定が適用されること。"""
    cfg = generate_config_dict("国土交通省", "https://www.mlit.go.jp/", agency_type="ministry")
    assert cfg["agency_type"] == "ministry"
    assert cfg["crawl_settings"]["delay"] == AGENCY_TYPE_DEFAULTS["ministry"]["delay"]
    assert cfg["crawl_settings"]["retry"] == AGENCY_TYPE_DEFAULTS["ministry"]["retry"]
    assert cfg["crawl_settings"]["max_depth"] == AGENCY_TYPE_DEFAULTS["ministry"]["max_depth"]


def test_generate_config_dict_custom_selectors():
    """カスタムセレクタが設定できること。"""
    cfg = generate_config_dict(
        "テスト市",
        "https://example.com/",
        list_item_selector="table.bid-list a",
        detail_selector=".bid-detail",
    )
    assert cfg["list_item_selector"] == "table.bid-list a"
    assert cfg["detail_selector"] == ".bid-detail"


def test_generate_config_dict_pagination():
    """ページネーション設定が含まれること。"""
    cfg = generate_config_dict("テスト市", "https://example.com/", pagination_selectors=["a.custom-next"])
    assert "pagination" in cfg
    assert cfg["pagination"]["next_button_selectors"] == ["a.custom-next"]
    assert cfg["pagination"]["max_pages"] == 100


def test_generate_config_dict_pdf_detection():
    """PDF検出設定が含まれること。"""
    cfg = generate_config_dict("テスト市", "https://example.com/")
    assert cfg["pdf_detection"]["extension_pattern"] == ".pdf"
    assert len(cfg["pdf_detection"]["text_keywords"]) >= 5


def test_generate_config_dict_encoding():
    """エンコーディング設定が含まれること。"""
    cfg = generate_config_dict("テスト市", "https://example.com/")
    assert cfg["encoding"]["auto_detect"] is True
    assert "utf-8" in cfg["encoding"]["fallback_encodings"]
    assert "shift_jis" in cfg["encoding"]["fallback_encodings"]
    assert "euc-jp" in cfg["encoding"]["fallback_encodings"]


def test_render_config_yaml_valid():
    """YAML出力が有効であること。"""
    cfg = generate_config_dict("テスト市", "https://example.com/")
    yaml_str = render_config_yaml(cfg)
    parsed = yaml.safe_load(yaml_str)
    assert parsed["agency_name"] == "テスト市"
    assert parsed["pagination"]["next_button_selectors"] == PAGINATION_SELECTORS


def test_generate_from_registry_dry_run(tmp_path, monkeypatch, capsys):
    from crawler.registry import RegistryRecord
    from scripts.list_registered_agencies import REGISTRY_FACTORIES

    records = [RegistryRecord(str(index), f"機関{index}", "", f"https://official.example/{index}")
               for index in range(6)]
    monkeypatch.setattr(REGISTRY_FACTORIES["ministry"], "all_records", lambda self: records)
    results = generate_from_registry(
        output_dir=str(tmp_path / "gen"),
        registry_type="ministry",
        dry_run=True,
    )
    assert results == []
    assert capsys.readouterr().out.count("agency_name:") == 6
    assert not (tmp_path / "gen").exists()


def test_generate_from_registry_actual(tmp_path, monkeypatch):
    from crawler.registry import RegistryRecord
    from scripts.list_registered_agencies import REGISTRY_FACTORIES

    records = [RegistryRecord("1", "親省", "https://official.example/", "https://official.example/bids", type="ministry"),
               RegistryRecord("2", "子局", "https://official.example/child", parent_id="code:1"),
               RegistryRecord("3", "仮URL", "", "https://search.geps.go.jp/search?q=x")]
    monkeypatch.setattr(REGISTRY_FACTORIES["ministry"], "all_records", lambda self: records)
    output_dir = tmp_path / "gen"
    results = generate_from_registry(str(output_dir), "ministry")
    assert len(results) == 1
    config = yaml.safe_load(Path(results[0]).read_text())
    assert config["list_url"] == "https://official.example/bids"
    assert config["url_status"] == "unverified"
    assert config["municipality_code"] == "1"


def test_generate_from_registry_invalid_type():
    """無効なレジストリタイプでエラーが発生すること。"""
    try:
        generate_from_registry(registry_type="invalid_type")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_generated_fetcher_executes_as_data_only(tmp_path, monkeypatch):
    from scripts.gen_crawler import render_fetcher_py
    from crawler.config_driven_crawler import ConfigDrivenCrawler

    name = '123\"\nraise RuntimeError("injected")\n'
    config = generate_config_dict(name, "https://official.example/bids?x='quoted'",
                                  list_item_selector="a.notice", detail_fields={"title": {"selector": "h1"}})
    source = render_fetcher_py(config)
    namespace = {}
    exec(compile(source, "generated_fetcher.py", "exec"), namespace)
    fetcher = namespace[class_name(name)](delay=0)
    assert isinstance(fetcher, ConfigDrivenCrawler)
    assert fetcher.config == config
    monkeypatch.setattr(fetcher, "fetch", lambda url: '<a class="notice" href="/detail">案件</a>'
                        if url == config["list_url"] else '<h1>公告</h1>')
    assert fetcher.crawl() == [{"title": "公告", "source_url": "https://official.example/detail",
                                "agency_name": config["agency_name"]}]
    assert config["agency_name"] == '123" raise RuntimeError("injected")'
    assert config["list_url"] == config["base_url"]
    assert "list.html" not in source


def test_yaml_quotes_untrusted_strings():
    name = 'name:\n  parser: malicious'
    config = generate_config_dict(name, "https://official.example/bids")
    assert yaml.safe_load(render_config_yaml(config)) == config


def test_cli_writes_functional_files_to_output_dir(tmp_path, monkeypatch):
    from scripts.gen_crawler import main

    monkeypatch.setattr(sys, "argv", ["gen_crawler.py", "--name", "123 city", "--url",
                                     "https://official.example/bids", "--output-dir", str(tmp_path)])
    main()
    config = yaml.safe_load((tmp_path / "123_city_crawler.yaml").read_text())
    assert config["list_url"] == "https://official.example/bids"
    namespace = {}
    exec(compile((tmp_path / "123_city_fetcher.py").read_text(), "fetcher.py", "exec"), namespace)
    assert namespace[class_name("123 city")]().config == config


def test_registry_normalization_dedup_and_region_filenames(tmp_path, monkeypatch):
    from copy import deepcopy
    from crawler.registry import RegistryRecord
    from scripts.list_registered_agencies import REGISTRY_FACTORIES
    from utils.string_normalizer import normalize_records

    records = [RegistryRecord("01", "旧親", "", "https://official.example/root", region="北"),
               RegistryRecord("02", " 子 ", "", "https://official.example/new", region="北",
                              parent_id="name:旧親", extra={"updated_at": "2026-09-17"}),
               RegistryRecord("02", "子", "", "https://official.example/old", region="北",
                              parent_id="code:01", extra={"updated_at": "2026-09-16"})]
    records.extend(RegistryRecord("", "中央町", "", "https://official.example/town", region=region)
                   for region in ("北", "南", "東"))
    before = deepcopy(records)
    aliases = {"旧親": "新親"}
    monkeypatch.setattr(REGISTRY_FACTORIES["ministry"], "all_records", lambda self: records)
    paths = generate_from_registry(tmp_path, "ministry", aliases=aliases)
    assert len(paths) == len(set(paths)) == 5
    configs = [yaml.safe_load(Path(path).read_text(encoding="utf-8")) for path in paths]
    expected = normalize_records(records, aliases)
    assert [(row["agency_name"], row["parent_id"]) for row in configs] == [(row.name, row.parent_id) for row in expected]
    assert configs[1]["list_url"] == "https://official.example/new"
    assert all(config["url_status"] == "unverified" for config in configs)
    assert records == before
