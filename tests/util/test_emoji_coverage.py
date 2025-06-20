from palabra_ai.util.emoji import Emoji


class TestEmojiCoverage:
    def test_bool_true(self):
        """Test bool method with True value"""
        assert Emoji.bool(True) == "✅"
