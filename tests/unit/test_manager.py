"""Tests for model manager module."""

import sys
from unittest.mock import MagicMock, patch


class TestModelManagerLoadModel:
    """Tests for ModelManager.load_model."""

    def test_load_model_returns_tuple(self):
        """Test load_model returns model, processor, config tuple."""
        mock_model = MagicMock()
        mock_processor = MagicMock()
        mock_config = MagicMock()

        # Create mock modules
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.load = MagicMock(return_value=(mock_model, mock_processor))
        mock_mlx_vlm_utils = MagicMock()
        mock_mlx_vlm_utils.load_config = MagicMock(return_value=mock_config)

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.utils": mock_mlx_vlm_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            model, processor, config = ModelManager.load_model("test-org/test-model")

            assert model is mock_model
            assert processor is mock_processor
            assert config is mock_config

    def test_load_model_calls_with_correct_path(self):
        """Test load_model calls MLX-VLM with correct path."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.load = MagicMock(return_value=(MagicMock(), MagicMock()))
        mock_mlx_vlm_utils = MagicMock()
        mock_mlx_vlm_utils.load_config = MagicMock(return_value=MagicMock())

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.utils": mock_mlx_vlm_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            ModelManager.load_model("mlx-community/Qwen2-VL-7B-Instruct-4bit")

            mock_mlx_vlm.load.assert_called_once_with("mlx-community/Qwen2-VL-7B-Instruct-4bit")
            mock_mlx_vlm_utils.load_config.assert_called_once_with(
                "mlx-community/Qwen2-VL-7B-Instruct-4bit"
            )


class TestModelManagerUnloadModel:
    """Tests for ModelManager.unload_model."""

    def test_unload_model_calls_gc_collect(self):
        """Test unload_model calls gc.collect."""
        mock_mx = MagicMock()
        mock_mx.metal = MagicMock()
        mock_mx.metal.clear_cache = MagicMock()

        with patch.dict(sys.modules, {"mlx": MagicMock(), "mlx.core": mock_mx}):
            with patch("gc.collect") as mock_gc_collect:
                from vmlx.models.manager import ModelManager

                model = MagicMock()
                processor = MagicMock()

                ModelManager.unload_model(model, processor)

                mock_gc_collect.assert_called_once()

    def test_unload_model_handles_missing_clear_cache(self):
        """Test unload_model handles case where clear_cache doesn't exist."""
        mock_mx = MagicMock()
        # Simulate missing clear_cache by making hasattr return False
        del mock_mx.metal.clear_cache

        with patch.dict(sys.modules, {"mlx": MagicMock(), "mlx.core": mock_mx}):
            with patch("gc.collect"):
                from vmlx.models.manager import ModelManager

                model = MagicMock()
                processor = MagicMock()

                # Should not raise even if clear_cache doesn't exist
                ModelManager.unload_model(model, processor)


class TestModelManagerGenerateResponse:
    """Tests for ModelManager.generate_response."""

    def test_generate_response_non_streaming(self):
        """Test generate_response returns string for non-streaming."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.generate = MagicMock(return_value="generated response")
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.prompt_utils": mock_prompt_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            result = ModelManager.generate_response(
                model=MagicMock(),
                processor=MagicMock(),
                config=MagicMock(),
                prompt="test prompt",
                stream=False,
            )

            assert result == "generated response"

    def test_generate_response_with_images(self):
        """Test generate_response includes images in call."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.generate = MagicMock(return_value="response with image")
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.prompt_utils": mock_prompt_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            ModelManager.generate_response(
                model=MagicMock(),
                processor=MagicMock(),
                config=MagicMock(),
                prompt="test prompt",
                images=["image1.jpg", "image2.jpg"],
                stream=False,
            )

            # Check apply_chat_template was called with num_images=2
            mock_prompt_utils.apply_chat_template.assert_called_once()
            call_kwargs = mock_prompt_utils.apply_chat_template.call_args
            # num_images should be in positional args or kwargs
            assert call_kwargs[1].get("num_images") == 2 or call_kwargs[0][3] == 2

    def test_generate_response_passes_max_tokens(self):
        """Test generate_response passes max_tokens to generate."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.generate = MagicMock(return_value="response")
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.prompt_utils": mock_prompt_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            ModelManager.generate_response(
                model=MagicMock(),
                processor=MagicMock(),
                config=MagicMock(),
                prompt="test",
                max_tokens=1024,
                stream=False,
            )

            call_kwargs = mock_mlx_vlm.generate.call_args
            assert call_kwargs[1].get("max_tokens") == 1024

    def test_generate_response_passes_temperature(self):
        """Test generate_response passes temperature to generate."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.generate = MagicMock(return_value="response")
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.prompt_utils": mock_prompt_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            ModelManager.generate_response(
                model=MagicMock(),
                processor=MagicMock(),
                config=MagicMock(),
                prompt="test",
                temperature=0.5,
                stream=False,
            )

            call_kwargs = mock_mlx_vlm.generate.call_args
            assert call_kwargs[1].get("temp") == 0.5


class TestModelManagerGenerateStreaming:
    """Tests for ModelManager.generate_streaming."""

    def test_generate_streaming_yields_tokens(self):
        """Test generate_streaming yields tokens."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.stream_generate = MagicMock(return_value=iter(["Hello", " ", "world"]))
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.prompt_utils": mock_prompt_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            result = list(
                ModelManager.generate_streaming(
                    model=MagicMock(),
                    processor=MagicMock(),
                    config=MagicMock(),
                    prompt="test",
                )
            )

            assert result == ["Hello", " ", "world"]

    def test_generate_streaming_with_images(self):
        """Test generate_streaming includes images."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.stream_generate = MagicMock(return_value=iter(["response"]))
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": mock_mlx_vlm,
                "mlx_vlm.prompt_utils": mock_prompt_utils,
            },
        ):
            from vmlx.models.manager import ModelManager

            list(
                ModelManager.generate_streaming(
                    model=MagicMock(),
                    processor=MagicMock(),
                    config=MagicMock(),
                    prompt="test",
                    images=["image.jpg"],
                )
            )

            # Check that images were passed to stream_generate
            call_args = mock_mlx_vlm.stream_generate.call_args
            # Images should be 4th positional arg
            assert call_args[0][3] == ["image.jpg"]
