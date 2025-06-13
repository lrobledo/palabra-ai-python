class Emoji:
    @classmethod
    def bool(cls, value: bool) -> str:
        return "✅" if value else "❌"
