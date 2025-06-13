import pytest

from palabra_ai.lang import Language, LanguageRegistry, EN, ES
from palabra_ai.exc import ConfigurationError


class TestLanguageRegistry:
    def test_register_and_get(self):
        registry = LanguageRegistry()
        lang = Language("test", registry=registry)

        assert registry.get_by_bcp47("test") == lang
        assert lang in registry.all_languages

    def test_get_nonexistent(self):
        registry = LanguageRegistry()

        with pytest.raises(ConfigurationError, match="Language with BCP47 code 'xyz' not found"):
            registry.get_by_bcp47("xyz")

    def test_get_or_create_existing(self):
        registry = LanguageRegistry()
        lang1 = Language("test", registry=registry)
        lang2 = registry.get_or_create("test")

        assert lang1 is lang2

    def test_get_or_create_new(self):
        registry = LanguageRegistry()
        lang = registry.get_or_create("new")

        assert lang.code == "new"
        assert lang in registry.all_languages


class TestLanguage:
    def test_case_insensitive(self):
        lang1 = Language("EN")
        lang2 = Language.get_by_bcp47("en")

        assert lang1 == lang2
        assert lang1.code == "en"

    def test_hash(self):
        lang1 = Language("test")
        lang2 = Language("test")
        lang3 = Language("other")

        assert hash(lang1) == hash(lang2)
        assert hash(lang1) != hash(lang3)

    def test_equality(self):
        assert EN == Language("en")
        assert EN == "en"
        assert ES != EN

        with pytest.raises(TypeError, match="Cannot compare Language with unknown language code"):
            EN == "unknown_code"

        with pytest.raises(TypeError, match="Cannot compare Language with int"):
            EN == 123

    def test_str_repr(self):
        assert str(EN) == "en"
        assert repr(EN) == "🇬🇧en"

    def test_get_or_create_classmethod(self):
        lang = Language.get_or_create("test_new")
        assert lang.code == "test_new"
        assert Language.get_by_bcp47("test_new") == lang
