from __future__ import annotations

from app.ingestion.crz.links import make_attachment_url, make_detail_url


class TestMakeDetailUrl:
    def test_generates_correct_url(self):
        url = make_detail_url("12345")
        assert url == "https://www.crz.gov.sk/index.php?ID=12345"

    def test_different_id(self):
        url = make_detail_url("99999")
        assert url == "https://www.crz.gov.sk/index.php?ID=99999"


class TestMakeAttachmentUrl:
    def test_generates_correct_url(self):
        url = make_attachment_url("zmluva_12345.pdf")
        assert url == "https://www.crz.gov.sk/data/att/zmluva_12345.pdf"

    def test_none_returns_none(self):
        assert make_attachment_url(None) is None

    def test_empty_string_returns_none(self):
        assert make_attachment_url("") is None
