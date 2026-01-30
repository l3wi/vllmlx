"""Tests for model aliases module."""

import pytest

from vmlx.models.aliases import BUILTIN_ALIASES, resolve_alias


class TestBuiltinAliases:
    """Tests for builtin aliases."""

    def test_builtin_aliases_exist(self):
        """Test that builtin aliases are defined."""
        assert len(BUILTIN_ALIASES) > 0

    def test_qwen2_vl_2b_alias(self):
        """Test qwen2-vl-2b alias is defined."""
        assert "qwen2-vl-2b" in BUILTIN_ALIASES
        assert BUILTIN_ALIASES["qwen2-vl-2b"] == "mlx-community/Qwen2-VL-2B-Instruct-4bit"

    def test_qwen2_vl_7b_alias(self):
        """Test qwen2-vl-7b alias is defined."""
        assert "qwen2-vl-7b" in BUILTIN_ALIASES
        assert BUILTIN_ALIASES["qwen2-vl-7b"] == "mlx-community/Qwen2-VL-7B-Instruct-4bit"

    def test_all_aliases_have_mlx_community_prefix(self):
        """Test all builtin aliases point to mlx-community repos."""
        for alias, path in BUILTIN_ALIASES.items():
            assert path.startswith("mlx-community/"), f"{alias} doesn't start with mlx-community/"


class TestResolveAlias:
    """Tests for resolve_alias function."""

    def test_resolve_builtin_alias(self):
        """Test resolving a builtin alias returns full path."""
        result = resolve_alias("qwen2-vl-2b")
        assert result == "mlx-community/Qwen2-VL-2B-Instruct-4bit"

    def test_resolve_another_builtin(self):
        """Test resolving another builtin alias."""
        result = resolve_alias("pixtral-12b")
        assert result == "mlx-community/pixtral-12b-4bit"

    def test_resolve_custom_alias_overrides_builtin(self):
        """Test custom alias overrides builtin."""
        custom = {"qwen2-vl-2b": "custom-org/custom-model"}
        result = resolve_alias("qwen2-vl-2b", custom_aliases=custom)
        assert result == "custom-org/custom-model"

    def test_resolve_custom_alias_new_name(self):
        """Test custom alias with new name works."""
        custom = {"my-model": "some-org/some-model-4bit"}
        result = resolve_alias("my-model", custom_aliases=custom)
        assert result == "some-org/some-model-4bit"

    def test_resolve_unknown_returns_input(self):
        """Test resolving unknown name returns input unchanged."""
        result = resolve_alias("unknown-model")
        assert result == "unknown-model"

    def test_resolve_full_hf_path_passthrough(self):
        """Test full HF path passes through unchanged."""
        full_path = "mlx-community/Some-Model-4bit"
        result = resolve_alias(full_path)
        assert result == full_path

    def test_resolve_with_empty_custom_aliases(self):
        """Test resolve works with empty custom aliases dict."""
        result = resolve_alias("qwen2-vl-2b", custom_aliases={})
        assert result == "mlx-community/Qwen2-VL-2B-Instruct-4bit"

    def test_resolve_with_none_custom_aliases(self):
        """Test resolve works with None custom aliases."""
        result = resolve_alias("qwen2-vl-2b", custom_aliases=None)
        assert result == "mlx-community/Qwen2-VL-2B-Instruct-4bit"
