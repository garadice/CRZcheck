from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.transforms.cleaning import (
    clean_name,
    normalize_ico,
    parse_crz_date,
    parse_crz_datetime,
    parse_int_or_none,
    parse_slovak_price,
)


class TestParseSlovakPrice:
    @pytest.mark.parametrize(
        "input,expected",
        [
            ("1 200,50", Decimal("1200.50")),
            ("50 000", Decimal("50000")),
            ("1 200,50 EUR", Decimal("1200.50")),
            ("5000", Decimal("5000")),
            ("0", Decimal("0")),
            ("-500", Decimal("-500")),
            ("", None),
            ("   ", None),
            ("1\xa0200,50€", Decimal("1200.50")),
            ("1200.50", Decimal("1200.50")),
            (None, None),
            ("1 500,00 EUR", Decimal("1500.00")),
        ],
    )
    def test_price_parsing(self, input, expected):
        result = parse_slovak_price(input)
        assert result == expected


class TestParseCrzDate:
    def test_normal_date(self):
        assert parse_crz_date("2026-05-14") == date(2026, 5, 14)

    def test_zero_date(self):
        assert parse_crz_date("0000-00-00") is None

    def test_none(self):
        assert parse_crz_date(None) is None

    def test_empty(self):
        assert parse_crz_date("") is None

    def test_whitespace(self):
        assert parse_crz_date("  ") is None

    def test_invalid(self):
        assert parse_crz_date("not-a-date") is None


class TestParseCrzDatetime:
    def test_normal_datetime(self):
        assert parse_crz_datetime("2026-05-14 10:30:00") == datetime(2026, 5, 14, 10, 30, 0)

    def test_none(self):
        assert parse_crz_datetime(None) is None

    def test_empty(self):
        assert parse_crz_datetime("") is None


class TestNormalizeIco:
    def test_normal_ico(self):
        assert normalize_ico("12345678") == "12345678"

    def test_short_ico_padded(self):
        assert normalize_ico("1234567") == "01234567"

    def test_ico_with_spaces(self):
        assert normalize_ico(" 123 456 78 ") == "12345678"

    def test_empty(self):
        assert normalize_ico("") is None

    def test_none(self):
        assert normalize_ico(None) is None

    def test_only_spaces(self):
        assert normalize_ico("   ") is None

    def test_with_slashes(self):
        assert normalize_ico("12/345/678") == "12345678"


class TestCleanName:
    def test_normal(self):
        assert clean_name("  Hello   World  ") == "Hello World"

    def test_none(self):
        assert clean_name(None) is None

    def test_empty(self):
        assert clean_name("") is None

    def test_whitespace_only(self):
        assert clean_name("   ") is None


class TestParseIntOrNone:
    def test_normal(self):
        assert parse_int_or_none("42") == 42

    def test_none(self):
        assert parse_int_or_none(None) is None

    def test_invalid(self):
        assert parse_int_or_none("abc") is None

    def test_empty(self):
        assert parse_int_or_none("") is None
