from __future__ import annotations

from pathlib import Path

from app.ingestion.crz.parser import compute_schema_fingerprint, parse_xml

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "xml"
SAMPLE_XML = FIXTURE_DIR / "sample.xml"


class TestParseXml:
    def test_parses_all_five_contracts(self):
        result = parse_xml(SAMPLE_XML)
        assert len(result.contracts) == 5

    def test_contract_ids(self):
        result = parse_xml(SAMPLE_XML)
        ids = [c.crz_contract_id for c in result.contracts]
        assert ids == ["12345", "12346", "12347", "12348", "12349"]

    def test_normal_contract_with_all_fields(self):
        result = parse_xml(SAMPLE_XML)
        c = result.contracts[0]
        assert c.title == "Test Contract 1"
        assert c.buyer_name == "Ministerstvo financií SR"
        assert c.supplier_name == "ABC Company s.r.o."
        assert c.supplier_ico == "12345678"
        assert c.supplier_address == "Bratislava"
        assert c.buyer_ico == "98765432"
        assert c.buyer_address == "Bratislava"
        assert c.subject == "Test predmet"
        assert c.effective_date == "2026-01-15"
        assert c.valid_until == "2027-01-15"
        assert c.price_contract == "50 000"
        assert c.price_total == "50 000"
        assert c.publication_date == "2026-05-14 10:30:00"
        assert c.contract_type == "1"
        assert c.contract_kind == "1"
        assert c.department == "100"

    def test_contract_with_one_attachment(self):
        result = parse_xml(SAMPLE_XML)
        c = result.contracts[0]
        assert len(c.attachments) == 1
        att = c.attachments[0]
        assert att.attachment_id == "att001"
        assert att.attachment_name == "Zmluva.pdf"
        assert att.scan_filename == "zmluva_12345.pdf"
        assert att.text_filename == "zmluva_12345.txt"
        assert att.scan_size_bytes == 102400
        assert att.text_size_bytes == 20480

    def test_zero_price_no_supplier_ico(self):
        result = parse_xml(SAMPLE_XML)
        c = result.contracts[1]
        assert c.price_contract == "0"
        assert c.price_total == "0"
        assert c.supplier_ico is None
        assert c.supplier_name is None
        assert c.supplier_address is None
        assert len(c.attachments) == 0

    def test_multiple_attachments(self):
        result = parse_xml(SAMPLE_XML)
        c = result.contracts[2]
        assert len(c.attachments) == 3
        assert c.attachments[0].attachment_id == "att010"
        assert c.attachments[1].attachment_id == "att011"
        assert c.attachments[2].attachment_id == "att012"
        assert c.attachments[2].text_filename == "priloha2_12347.txt"
        assert c.attachments[2].text_size_bytes == 10240
        assert c.attachments[1].text_filename is None
        assert c.attachments[1].text_size_bytes is None

    def test_minimal_contract_empty_fields(self):
        result = parse_xml(SAMPLE_XML)
        c = result.contracts[3]
        assert c.crz_contract_id == "12348"
        assert c.title is None
        assert c.buyer_name is None
        assert c.attachments == []

    def test_slovak_price_format(self):
        result = parse_xml(SAMPLE_XML)
        c = result.contracts[4]
        assert c.price_contract == "1 200,50 EUR"
        assert c.price_total == "1 500,00 EUR"

    def test_datum_from_root_applied_to_all(self):
        result = parse_xml(SAMPLE_XML)
        for c in result.contracts:
            assert c.contract_date == "2026-05-14"

    def test_export_date_from_root(self):
        result = parse_xml(SAMPLE_XML)
        assert result.export_date == "2026-05-14"

    def test_unmapped_fields_stored(self):
        result = parse_xml(SAMPLE_XML)
        c0 = result.contracts[0]
        assert "poznamka" in c0.unmapped_fields
        assert c0.unmapped_fields["poznamka"] == "Test note"
        assert "stav" in c0.unmapped_fields
        assert c0.unmapped_fields["stav"] == "1"

        c2 = result.contracts[2]
        assert "popis" in c2.unmapped_fields
        assert c2.unmapped_fields["popis"] == "Complex procurement"

        c4 = result.contracts[4]
        assert "internapozn" in c4.unmapped_fields
        assert "uvo" in c4.unmapped_fields

    def test_schema_fingerprint_present(self):
        result = parse_xml(SAMPLE_XML)
        assert result.schema_fingerprint is not None
        assert result.schema_fingerprint.contract_count == 5
        assert len(result.schema_fingerprint.element_names) > 0
        assert result.schema_fingerprint.fingerprint != ""

    def test_schema_fingerprint_stable(self):
        r1 = parse_xml(SAMPLE_XML)
        r2 = parse_xml(SAMPLE_XML)
        assert r1.schema_fingerprint is not None
        assert r2.schema_fingerprint is not None
        assert r1.schema_fingerprint.fingerprint == r2.schema_fingerprint.fingerprint

    def test_schema_fingerprint_differs_for_different_structure(self):
        r1 = parse_xml(SAMPLE_XML)
        different_xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<zmluvy datum="2026-01-01"><zmluva>'
            "<ID>99999</ID><nazov>Different</nazov>"
            "<newfield>value</newfield>"
            "</zmluva></zmluvy>"
        )
        r2 = parse_xml(different_xml)
        assert r1.schema_fingerprint is not None
        assert r2.schema_fingerprint is not None
        assert r1.schema_fingerprint.fingerprint != r2.schema_fingerprint.fingerprint

    def test_zero_contract_xml(self):
        xml = '<?xml version="1.0" encoding="utf-8"?><zmluvy datum="2026-01-01"></zmluvy>'
        result = parse_xml(xml)
        assert len(result.contracts) == 0
        assert result.export_date == "2026-01-01"

    def test_parse_from_bytes(self):
        raw = SAMPLE_XML.read_bytes()
        result = parse_xml(raw)
        assert len(result.contracts) == 5

    def test_parse_from_string(self):
        xml_str = SAMPLE_XML.read_text(encoding="utf-8")
        result = parse_xml(xml_str)
        assert len(result.contracts) == 5

    def test_utf8_bom_handled(self):
        raw = SAMPLE_XML.read_bytes()
        bom_raw = b"\xef\xbb\xbf" + raw
        result = parse_xml(bom_raw)
        assert len(result.contracts) == 5


class TestComputeSchemaFingerprint:
    def test_deterministic(self):
        names = ["ID", "nazov", "zs1"]
        fp1 = compute_schema_fingerprint(names)
        fp2 = compute_schema_fingerprint(names)
        assert fp1 == fp2

    def test_order_independent(self):
        fp1 = compute_schema_fingerprint(["ID", "nazov", "zs1"])
        fp2 = compute_schema_fingerprint(["zs1", "ID", "nazov"])
        assert fp1 == fp2

    def test_different_names_different_fingerprint(self):
        fp1 = compute_schema_fingerprint(["ID", "nazov"])
        fp2 = compute_schema_fingerprint(["ID", "zs1"])
        assert fp1 != fp2
