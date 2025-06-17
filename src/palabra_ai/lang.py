from dataclasses import dataclass, field

from palabra_ai.exc import ConfigurationError


@dataclass
class LanguageRegistry:
    by_code: dict[str, "Language"] = field(
        default_factory=dict, repr=False, compare=False
    )
    all_languages: set["Language"] = field(
        default_factory=set, repr=False, compare=False
    )

    def register(self, language: "Language"):
        self.by_code[language.code] = language
        self.all_languages.add(language)

    def get_by_bcp47(self, code: str) -> "Language | None":
        if result := self.by_code.get(code.lower()):
            return result
        raise ConfigurationError(f"Language with BCP47 code '{code}' not found.")

    def get_or_create(self, code: str) -> "Language":
        """Get existing language or create new one dynamically"""
        code_lower = code.lower()
        try:
            return self.get_by_bcp47(code_lower)
        except ConfigurationError:
            # Create new language dynamically
            return Language(code_lower, registry=self)


_default_registry = LanguageRegistry()


@dataclass
class Language:
    code: str
    registry: LanguageRegistry = field(default=None, repr=False, compare=False)
    flag: str = "🌐❓"

    def __post_init__(self):
        self.code = self.code.lower()  # Always store in lowercase
        if self.registry is None:
            self.registry = _default_registry
        self.registry.register(self)

    @property
    def bcp47(self) -> str:
        return self.code

    @classmethod
    def get_by_bcp47(
        cls, code: str, registry: LanguageRegistry | None = None
    ) -> "Language | None":
        if registry is None:
            registry = _default_registry
        return registry.get_by_bcp47(code)

    @classmethod
    def get_or_create(
        cls, code: str, registry: LanguageRegistry | None = None
    ) -> "Language":
        """Get existing language or create new one dynamically"""
        if registry is None:
            registry = _default_registry
        return registry.get_or_create(code)

    def __hash__(self):
        return hash(self.code)

    def __str__(self):
        return self.bcp47

    def __repr__(self):
        return f"{self.flag}{str(self)}"

    def __eq__(self, other):
        if isinstance(other, Language):
            return self.code == other.code
        elif isinstance(other, str):
            # Check if string exists as a language code in registry
            if other.lower() in self.registry.by_code:
                return self.code == other.lower()
            raise TypeError(
                f"Cannot compare Language with unknown language code: {other}"
            )
        else:
            raise TypeError(f"Cannot compare Language with {type(other).__name__}")


AR = Language("ar", flag="🇸🇦")
AR_AE = Language("ar-ae", flag="🇦🇪")
AR_SA = Language("ar-sa", flag="🇸🇦")
AZ = Language("az", flag="🇦🇿")
BG = Language("bg", flag="🇧🇬")
CS = Language("cs", flag="🇨🇿")
DA = Language("da", flag="🇩🇰")
DE = Language("de", flag="🇩🇪")
EL = Language("el", flag="🇬🇷")
EN = Language("en", flag="🇬🇧")
EN_AU = Language("en-au", flag="🇦🇺")
EN_CA = Language("en-ca", flag="🇨🇦")
EN_GB = Language("en-gb", flag="🇬🇧")
EN_US = Language("en-us", flag="🇺🇸")
ES = Language("es", flag="🇪🇸")
ES_MX = Language("es-mx", flag="🇲🇽")
FI = Language("fi", flag="🇫🇮")
FIL = Language("fil", flag="🇵🇭")
FR = Language("fr", flag="🇫🇷")
FR_CA = Language("fr-ca", flag="🇨🇦")
HE = Language("he", flag="🇮🇱")
HI = Language("hi", flag="🇮🇳")
HR = Language("hr", flag="🇭🇷")
HU = Language("hu", flag="🇭🇺")
ID = Language("id", flag="🇮🇩")
IT = Language("it", flag="🇮🇹")
JA = Language("ja", flag="🇯🇵")
KO = Language("ko", flag="🇰🇷")
MS = Language("ms", flag="🇲🇾")
NL = Language("nl", flag="🇳🇱")
NO = Language("no", flag="🇳🇴")
PL = Language("pl", flag="🇵🇱")
PT = Language("pt", flag="🇵🇹")
PT_BR = Language("pt-br", flag="🇧🇷")
RO = Language("ro", flag="🇷🇴")
RU = Language("ru", flag="🇷🇺")
SK = Language("sk", flag="🇸🇰")
SV = Language("sv", flag="🇸🇪")
TA = Language("ta", flag="🇮🇳")
TR = Language("tr", flag="🇹🇷")
UK = Language("uk", flag="🇺🇦")
VN = Language("vn", flag="🇻🇳")
ZH = Language("zh", flag="🇨🇳")
