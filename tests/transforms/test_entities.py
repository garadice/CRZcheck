from __future__ import annotations

from app.transforms.entities import is_probable_natural_person, normalize_entity_name


class TestIsProbableNaturalPerson:
    def test_no_ico_no_suffix_is_natural_person(self):
        assert is_probable_natural_person("Ján Novák", None) is True

    def test_no_ico_empty_string(self):
        assert is_probable_natural_person("Ján Novák", "") is True

    def test_no_ico_zero_string(self):
        assert is_probable_natural_person("Ján Novák", "0") is True

    def test_has_ico_not_natural_person(self):
        assert is_probable_natural_person("Ján Novák", "12345678") is False

    def test_has_ico_with_spaces(self):
        assert is_probable_natural_person("Ján Novák", " 12345678 ") is False

    def test_no_ico_with_sro_suffix(self):
        assert is_probable_natural_person("ABC s.r.o.", None) is False

    def test_no_ico_with_as_suffix(self):
        assert is_probable_natural_person("XYZ a.s.", None) is False

    def test_no_ico_with_vos_suffix(self):
        assert is_probable_natural_person("DEF v.o.s.", None) is False

    def test_no_ico_with_ks_suffix(self):
        assert is_probable_natural_person("GHI k.s.", None) is False

    def test_no_ico_with_sp_suffix(self):
        assert is_probable_natural_person("Ján Novák š.p.", None) is False

    def test_no_ico_with_oz_suffix(self):
        assert is_probable_natural_person("Občianske združenie o.z.", None) is False

    def test_no_ico_with_prispevkova(self):
        assert is_probable_natural_person("Nemocnica príspevková organizácia", None) is False

    def test_no_ico_with_rozpockova(self):
        assert is_probable_natural_person("Úrad rozpočtová organizácia", None) is False

    def test_no_ico_with_nadacia(self):
        assert is_probable_natural_person("Nadácia blahoslaveného", None) is False

    def test_no_ico_with_no_suffix(self):
        assert is_probable_natural_person("Ivan Hrozny", None) is True

    def test_empty_name(self):
        assert is_probable_natural_person("", None) is False

    def test_none_name(self):
        assert is_probable_natural_person(None, None) is False

    def test_whitespace_name(self):
        assert is_probable_natural_person("   ", None) is False

    def test_both_none(self):
        assert is_probable_natural_person(None, None) is False

    def test_case_insensitive_suffix(self):
        assert is_probable_natural_person("ABC S.R.O.", None) is False


class TestNormalizeEntityName:
    def test_normal_name(self):
        assert normalize_entity_name("Ministerstvo Financií SR") == "ministerstvo financií sr"

    def test_extra_spaces(self):
        assert normalize_entity_name("  ABC   Company  ") == "abc company"

    def test_none(self):
        assert normalize_entity_name(None) is None

    def test_empty(self):
        assert normalize_entity_name("") is None

    def test_whitespace_only(self):
        assert normalize_entity_name("   ") is None

    def test_already_normalized(self):
        assert normalize_entity_name("abc company") == "abc company"
