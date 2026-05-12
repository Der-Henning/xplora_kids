"""Tests for shared helpers."""

from __future__ import annotations

import unittest

from support import load_module


class HelpersTest(unittest.TestCase):
    """Test shared helper functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the helper module."""
        cls.helpers = load_module(
            "xplora_kids_helpers",
            "custom_components/xplora_kids/helpers.py",
        )

    def test_clean_optional_text(self) -> None:
        """Clean optional user-entered strings."""
        assert self.helpers.clean_optional_text("  hello  ") == "hello"
        assert self.helpers.clean_optional_text("+49", strip_plus=True) == "49"
        assert self.helpers.clean_optional_text(" 123 456 ", strip_spaces=True) == "123456"
        assert self.helpers.clean_optional_text("   ") is None
        assert self.helpers.clean_optional_text(None) is None

    def test_normalize_mac(self) -> None:
        """Normalize common MAC address formats."""
        assert self.helpers.normalize_mac("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"
        assert self.helpers.normalize_mac("aa-bb-cc-dd-ee-ff") == "aa:bb:cc:dd:ee:ff"
        assert self.helpers.normalize_mac("aabb.ccdd.eeff") == "aa:bb:cc:dd:ee:ff"
        assert self.helpers.normalize_mac("aabbccddeeff") == "aa:bb:cc:dd:ee:ff"
        assert self.helpers.normalize_mac("not-a-mac") is None

    def test_redacted_hash(self) -> None:
        """Return stable short hashes without exposing the raw value."""
        first = self.helpers.redacted_hash("watch-id")
        assert first == self.helpers.redacted_hash("watch-id")
        assert first != "watch-id"
        assert len(first) == 12
        assert self.helpers.redacted_hash(None) is None


if __name__ == "__main__":
    unittest.main()
