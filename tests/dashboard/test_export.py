from __future__ import annotations

from types import SimpleNamespace

from app.dashboard.components.export import contracts_to_dataframe, export_dataframe


def make_contract(**kwargs):
    defaults = {
        "crz_contract_id": "12345",
        "title": "Test Contract",
        "buyer_name": "Ministerstvo testov SR",
        "buyer_ico": "99999999",
        "supplier_name": "TestCo s.r.o.",
        "supplier_ico": "88888888",
        "price_total": 50000,
        "contract_date": "2026-05-14",
        "publication_date": "2026-05-15",
        "crz_detail_url": "https://www.crz.gov.sk/detail/12345",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_flag(name="Chýba cena", flag_code="NO_PRICE", severity="medium", reason="Price is zero"):
    return {"flag_code": flag_code, "name": name, "severity": severity, "reason": reason}


def _make_item(contract_kwargs=None, flags=None, flag_count=None, compound_severity="low"):
    c = make_contract(**(contract_kwargs or {}))
    fl = flags if flags is not None else [make_flag()]
    fc = flag_count if flag_count is not None else len(fl)
    return {
        "contract": c,
        "flags": fl,
        "flag_count": fc,
        "compound_severity": compound_severity,
    }


EXPECTED_COLUMNS = [
    "ID zmluvy",
    "Názov",
    "Obstarávateľ",
    "IČO obstarávateľa",
    "Dodávateľ",
    "IČO dodávateľa",
    "Cena celková",
    "Dátum zmluvy",
    "Zverejnené",
    "Počet oznamov",
    "Závažnosť",
    "Oznamy",
    "Odkaz CRZ",
]


class TestContractsToDataframe:
    def test_normal_contract_values(self):
        item = _make_item()
        df = contracts_to_dataframe([item])
        assert len(df) == 1
        row = df.iloc[0]
        assert row["ID zmluvy"] == "12345"
        assert row["Názov"] == "Test Contract"
        assert row["Obstarávateľ"] == "Ministerstvo testov SR"
        assert row["IČO obstarávateľa"] == "99999999"
        assert row["Dodávateľ"] == "TestCo s.r.o."
        assert row["IČO dodávateľa"] == "88888888"
        assert row["Cena celková"] == "50000"
        assert row["Dátum zmluvy"] == "2026-05-14"
        assert row["Zverejnené"] == "2026-05-15"
        assert row["Odkaz CRZ"] == "https://www.crz.gov.sk/detail/12345"

    def test_natural_person_masking(self):
        item = _make_item(
            contract_kwargs={"supplier_name": "Ján Novák", "supplier_ico": ""},
        )
        df = contracts_to_dataframe([item])
        row = df.iloc[0]
        assert row["Dodávateľ"] == "[fyzická osoba]"
        assert row["IČO dodávateľa"] == ""

    def test_none_fields_become_empty_string(self):
        item = _make_item(
            contract_kwargs={
                "title": None,
                "buyer_name": None,
                "buyer_ico": None,
                "supplier_name": None,
                "supplier_ico": None,
                "contract_date": None,
                "publication_date": None,
                "crz_detail_url": None,
            },
        )
        df = contracts_to_dataframe([item])
        row = df.iloc[0]
        assert row["Názov"] == ""
        assert row["Obstarávateľ"] == ""
        assert row["IČO obstarávateľa"] == ""
        assert row["Dátum zmluvy"] == ""
        assert row["Zverejnené"] == ""
        assert row["Odkaz CRZ"] == ""

    def test_multiple_flags_comma_separated(self):
        flags = [
            make_flag(name="Chýba cena"),
            make_flag(name="Opakovaný dodávateľ", flag_code="REPEAT_SUPPLIER"),
        ]
        item = _make_item(flags=flags, flag_count=2)
        df = contracts_to_dataframe([item])
        assert df.iloc[0]["Oznamy"] == "Chýba cena, Opakovaný dodávateľ"

    def test_empty_list_returns_empty_dataframe(self):
        df = contracts_to_dataframe([])
        assert len(df) == 0
        assert list(df.columns) == []

    def test_none_price_total_becomes_empty_string(self):
        item = _make_item(contract_kwargs={"price_total": None})
        df = contracts_to_dataframe([item])
        assert df.iloc[0]["Cena celková"] == ""

    def test_compound_severity_in_dataframe(self):
        item = _make_item(compound_severity="high")
        df = contracts_to_dataframe([item])
        assert df.iloc[0]["Závažnosť"] == "high"

    def test_expected_column_names(self):
        item = _make_item()
        df = contracts_to_dataframe([item])
        assert list(df.columns) == EXPECTED_COLUMNS

    def test_two_contracts_two_rows(self):
        items = [
            _make_item(contract_kwargs={"crz_contract_id": "A001"}),
            _make_item(contract_kwargs={"crz_contract_id": "A002"}),
        ]
        df = contracts_to_dataframe(items)
        assert len(df) == 2
        assert df.iloc[0]["ID zmluvy"] == "A001"
        assert df.iloc[1]["ID zmluvy"] == "A002"


class TestExportDataframe:
    """Tests for export_dataframe() — CSV export with disclaimer header."""

    def test_csv_contains_disclaimer_header(self):
        """export_dataframe should produce CSV with Slovak disclaimer header."""
        from unittest.mock import patch

        import pandas as pd

        df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})

        with patch("app.dashboard.components.export.st") as mock_st:
            export_dataframe(df, "test_export")

            mock_st.download_button.assert_called_once()
            call_kwargs = mock_st.download_button.call_args[1]
            csv_data = call_kwargs["data"]

            assert "# CRZ Risk & Quality Monitor" in csv_data
            assert "# Upozornenie:" in csv_data
            assert "# Označenia nie sú dôkazom" in csv_data
            assert "# Exportované:" in csv_data

    def test_csv_contains_dataframe_content(self):
        """CSV data should include actual DataFrame values."""
        from unittest.mock import patch

        import pandas as pd

        df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [90, 85]})

        with patch("app.dashboard.components.export.st") as mock_st:
            export_dataframe(df, "scores")

            call_kwargs = mock_st.download_button.call_args[1]
            csv_data = call_kwargs["data"]
            assert "Alice" in csv_data
            assert "Bob" in csv_data
            assert "Score" in csv_data

    def test_filename_format_includes_timestamp(self):
        """Download filename should include base name and timestamp."""
        import re
        from unittest.mock import patch

        import pandas as pd

        df = pd.DataFrame({"x": [1]})

        with patch("app.dashboard.components.export.st") as mock_st:
            export_dataframe(df, "my_export")

            call_kwargs = mock_st.download_button.call_args[1]
            filename = call_kwargs["file_name"]
            assert filename.startswith("my_export_")
            assert filename.endswith(".csv")
            assert re.match(r"my_export_\d{8}_\d{6}\.csv", filename)

    def test_download_button_label_and_mime(self):
        """download_button should use the correct label and MIME type."""
        from unittest.mock import patch

        import pandas as pd

        df = pd.DataFrame({"x": [1]})

        with patch("app.dashboard.components.export.st") as mock_st:
            export_dataframe(df, "test")

            call_kwargs = mock_st.download_button.call_args[1]
            assert call_kwargs["label"] == "📥 Stiahnuť CSV"
            assert call_kwargs["mime"] == "text/csv"

    def test_csv_separator_and_no_index(self):
        """CSV should not include DataFrame index column."""
        from unittest.mock import patch

        import pandas as pd

        df = pd.DataFrame({"A": [10]}, index=[42])

        with patch("app.dashboard.components.export.st") as mock_st:
            export_dataframe(df, "idx_test")

            call_kwargs = mock_st.download_button.call_args[1]
            csv_data = call_kwargs["data"]
            lines = csv_data.strip().split("\n")
            header_line = [line for line in lines if not line.startswith("#")][0]
            assert "42" not in header_line
            assert "A" in header_line
