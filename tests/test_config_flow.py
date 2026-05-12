"""Tests for config flow source-level regressions."""

from __future__ import annotations

from pathlib import Path
import unittest


class ConfigFlowTest(unittest.TestCase):
    """Test config flow compatibility assumptions."""

    def test_options_flow_does_not_assign_read_only_config_entry(self) -> None:
        """Home Assistant owns OptionsFlow.config_entry as a read-only property."""
        source = Path("custom_components/xplora_kids/config_flow.py").read_text()

        assert "self.config_entry = config_entry" not in source
        assert "self._config_entry = config_entry" in source


if __name__ == "__main__":
    unittest.main()
