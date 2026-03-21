"""Tests for model aliases module."""

from vllmlx.models.aliases import BUILTIN_ALIASES, normalize_model_name, resolve_alias


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
        """Test most builtin aliases point to mlx-community repos."""
        for alias, path in BUILTIN_ALIASES.items():
            assert (
                path.startswith("mlx-community/") or path.startswith("Qwen/")
            ), f"{alias} doesn't start with a supported org prefix"


class TestResolveAlias:
    """Tests for resolve_alias function."""

    def test_resolve_builtin_alias(self):
        """Test resolving a builtin alias returns full path."""
        result = resolve_alias("qwen2-vl-2b")
        assert result == "mlx-community/Qwen2-VL-2B-Instruct-4bit"

    def test_resolve_ollama_style_alias(self):
        """Test resolving ollama-style aliases."""
        assert resolve_alias("qwen3:8b") == "mlx-community/Qwen3-8B-4bit"
        assert resolve_alias("qwen3:4b") == "mlx-community/Qwen3-4B-4bit"
        assert resolve_alias("qwen3-vl:8b") == "mlx-community/Qwen3-VL-8B-Instruct-4bit"
        assert resolve_alias("qwen3-embedding:4b") == "mlx-community/Qwen3-Embedding-4B-4bit-DWQ"

    def test_resolve_alias_case_insensitive(self):
        """Test alias lookup is case-insensitive."""
        assert resolve_alias("QWEN3:8B") == "mlx-community/Qwen3-8B-4bit"

    def test_resolve_another_builtin(self):
        """Test resolving another builtin alias."""
        result = resolve_alias("pixtral-12b")
        assert result == "mlx-community/pixtral-12b-4bit"

    def test_resolve_custom_alias_overrides_builtin(self):
        """Test custom alias overrides builtin."""
        custom = {"QWEN2-VL-2B": "custom-org/custom-model"}
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

    def test_resolve_hf_url_to_repo_id(self):
        """Test HuggingFace URL normalizes to repo id."""
        result = resolve_alias("https://huggingface.co/Qwen/Qwen3-Embedding-4B")
        assert result == "Qwen/Qwen3-Embedding-4B"


class TestNormalizeModelName:
    """Tests for input normalization."""

    def test_normalize_hf_short_url(self):
        assert normalize_model_name("hf.co/Qwen/Qwen3-Embedding-4B") == "Qwen/Qwen3-Embedding-4B"

    def test_normalize_hf_models_url(self):
        value = "https://huggingface.co/models/mlx-community/Qwen3-8B-4bit"
        assert normalize_model_name(value) == "mlx-community/Qwen3-8B-4bit"

    def test_normalize_non_url_unchanged(self):
        assert normalize_model_name("qwen3:8b") == "qwen3:8b"

    def test_resolve_with_empty_custom_aliases(self):
        """Test resolve works with empty custom aliases dict."""
        result = resolve_alias("qwen2-vl-2b", custom_aliases={})
        assert result == "mlx-community/Qwen2-VL-2B-Instruct-4bit"

    def test_resolve_with_none_custom_aliases(self):
        """Test resolve works with None custom aliases."""
        result = resolve_alias("qwen2-vl-2b", custom_aliases=None)
        assert result == "mlx-community/Qwen2-VL-2B-Instruct-4bit"
