"""Model management for vllmlx."""

import gc
from typing import Any, Generator, Optional, Tuple


class ModelManager:
    """Handles model loading, unloading, and generation via MLX-VLM."""

    @staticmethod
    def load_model(model_path: str) -> Tuple[Any, Any, Any]:
        """Load model, processor, and config from HuggingFace path.

        Args:
            model_path: Full HuggingFace path (e.g., 'mlx-community/Qwen2-VL-7B-Instruct-4bit')

        Returns:
            Tuple of (model, processor, config)
        """
        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        model, processor = load(model_path)
        config = load_config(model_path)
        return model, processor, config

    @staticmethod
    def unload_model(model: Any, processor: Any) -> None:
        """Unload model and free memory.

        Args:
            model: The loaded model to unload
            processor: The processor to unload
        """
        import mlx.core as mx

        del model
        del processor
        gc.collect()
        # Clear MLX metal cache if available
        if hasattr(mx, "metal") and hasattr(mx.metal, "clear_cache"):
            mx.metal.clear_cache()

    @staticmethod
    def generate_response(
        model: Any,
        processor: Any,
        config: Any,
        prompt: str,
        images: Optional[list[str]] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Generator[str, None, None] | str:
        """Generate response from model.

        Args:
            model: The loaded model
            processor: The processor
            config: The model config
            prompt: The text prompt
            images: Optional list of image paths or base64 data URLs
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response

        Returns:
            Generated text (string) or generator for streaming
        """
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted_prompt = apply_chat_template(
            processor,
            config,
            prompt,
            num_images=len(images) if images else 0,
        )

        result = generate(
            model,
            processor,
            formatted_prompt,
            images or [],
            max_tokens=max_tokens,
            temp=temperature,
            verbose=False,
        )

        if stream:
            # For streaming, we need to handle it as an iterator
            # MLX-VLM generate returns a generator when verbose=False
            return result
        else:
            # For non-streaming, consume the full result
            if isinstance(result, str):
                return result
            # If it's a generator, consume it
            full_response = ""
            for token in result:
                full_response += token
            return full_response

    @staticmethod
    def generate_streaming(
        model: Any,
        processor: Any,
        config: Any,
        prompt: str,
        images: Optional[list[str]] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        """Generate response from model with streaming.

        Args:
            model: The loaded model
            processor: The processor
            config: The model config
            prompt: The text prompt
            images: Optional list of image paths or base64 data URLs
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Individual tokens as they are generated
        """
        from mlx_vlm import stream_generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted_prompt = apply_chat_template(
            processor,
            config,
            prompt,
            num_images=len(images) if images else 0,
        )

        for token in stream_generate(
            model,
            processor,
            formatted_prompt,
            images or [],
            max_tokens=max_tokens,
            temp=temperature,
        ):
            yield token
