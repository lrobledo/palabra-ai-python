from palabra_ai.util.emoji import Emoji


class TestEmoji:
    def test_bool_false(self):
        assert Emoji.bool(False) == "❌"
