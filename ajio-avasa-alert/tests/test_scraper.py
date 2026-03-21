"""Unit tests for pure functions in scraper.py."""

import pytest

from scraper import BRAND_CONFIGS, extract_product_code, filter_products, format_product_message, save_to_file


def make_product(**overrides) -> dict:
    base = {
        "name": "AVAASA Kurti",
        "mrp": 999.0,
        "price": 299.0,
        "discount": 70,
        "url": "https://www.ajio.com/p/ABC123",
        "image_url": "https://cdn.ajio.com/img.jpg",
        "image_path": "",
    }
    return {**base, **overrides}


class TestFilterProducts:
    def test_keeps_products_at_threshold(self):
        products = [make_product(discount=70)]
        assert filter_products(products, min_pct=70) == products

    def test_removes_products_below_threshold(self):
        products = [make_product(discount=69)]
        assert filter_products(products, min_pct=70) == []

    def test_keeps_products_above_threshold(self):
        products = [make_product(discount=85)]
        assert filter_products(products, min_pct=70) == products

    def test_empty_list(self):
        assert filter_products([], min_pct=70) == []

    def test_mixed_list(self):
        low = make_product(discount=50)
        high = make_product(discount=80)
        result = filter_products([low, high], min_pct=70)
        assert result == [high]


class TestExtractProductCode:
    def test_extracts_code_from_url(self):
        assert extract_product_code("https://www.ajio.com/p/ABC123") == "ABC123"

    def test_returns_empty_for_no_match(self):
        assert extract_product_code("https://www.ajio.com/search/") == ""

    def test_stops_at_query_string(self):
        code = extract_product_code("https://www.ajio.com/p/XYZ-789?color=red")
        assert code == "XYZ-789"


class TestFormatProductMessage:
    def test_contains_product_name(self):
        p = make_product()
        msg = format_product_message(p, index=1, total=5, min_pct=70)
        assert "AVAASA Kurti" in msg

    def test_contains_discount(self):
        p = make_product(discount=75)
        msg = format_product_message(p, index=1, total=5, min_pct=70)
        assert "75" in msg

    def test_contains_browser_link(self):
        p = make_product()
        msg = format_product_message(p, index=1, total=5, min_pct=70)
        assert "Open in Browser" in msg

    def test_contains_app_link_when_code_present(self):
        p = make_product(url="https://www.ajio.com/p/CODE42")
        msg = format_product_message(p, index=1, total=5, min_pct=70)
        assert "Open in App" in msg

    def test_no_app_link_when_no_code(self):
        p = make_product(url="https://www.ajio.com/search/")
        msg = format_product_message(p, index=1, total=5, min_pct=70)
        assert "Open in App" not in msg


class TestBrandConfigs:
    def test_all_required_brands_present(self):
        for brand in BRAND_CONFIGS.keys():
            assert brand in BRAND_CONFIGS, f"Brand '{brand}' missing from BRAND_CONFIGS"

    def test_expected_brands_included(self):
        for brand in ("avasa", "dnmx", "fig", "rio"):
            assert brand in BRAND_CONFIGS, f"Expected brand '{brand}' not found in BRAND_CONFIGS"

    def test_each_brand_has_text_and_filters(self):
        for brand, cfg in BRAND_CONFIGS.items():
            assert "text" in cfg, f"Brand '{brand}' missing 'text'"
            assert "brand_filters" in cfg, f"Brand '{brand}' missing 'brand_filters'"
            assert isinstance(cfg["brand_filters"], list), f"Brand '{brand}' brand_filters must be a list"
            assert len(cfg["brand_filters"]) >= 1, f"Brand '{brand}' brand_filters must not be empty"

    def test_avasa_has_two_filters(self):
        filters = BRAND_CONFIGS["avasa"]["brand_filters"]
        assert "AVAASA SET" in filters
        assert "AVAASA MIX N' MATCH" in filters

    def test_dnmx_config(self):
        assert BRAND_CONFIGS["dnmx"]["text"] == "dnmx"
        assert "DNMX" in BRAND_CONFIGS["dnmx"]["brand_filters"]

    def test_fig_config(self):
        assert BRAND_CONFIGS["fig"]["text"] == "fig"
        assert "FIG" in BRAND_CONFIGS["fig"]["brand_filters"]

    def test_rio_config(self):
        assert BRAND_CONFIGS["rio"]["text"] == "rio"
        assert "RIO" in BRAND_CONFIGS["rio"]["brand_filters"]


class TestSaveToFile:
    def test_label_appears_in_output(self, tmp_path, monkeypatch):
        import scraper
        monkeypatch.setattr(scraper, "OUTPUT_FILE", tmp_path / "deals.txt")
        products = [make_product()]
        save_to_file(products, min_pct=70, label="AVASA, DNMX, FIG, RIO")
        content = (tmp_path / "deals.txt").read_text(encoding="utf-8")
        assert "AVASA, DNMX, FIG, RIO" in content

    def test_default_label(self, tmp_path, monkeypatch):
        import scraper
        monkeypatch.setattr(scraper, "OUTPUT_FILE", tmp_path / "deals.txt")
        products = [make_product()]
        save_to_file(products, min_pct=70)
        content = (tmp_path / "deals.txt").read_text(encoding="utf-8")
        assert "Avasa" in content
