"""Model alias resolution for vmlx."""

# Builtin aliases mapping short names to full HuggingFace paths
BUILTIN_ALIASES: dict[str, str] = {
    "qwen2-vl-2b": "mlx-community/Qwen2-VL-2B-Instruct-4bit",
    "qwen2-vl-7b": "mlx-community/Qwen2-VL-7B-Instruct-4bit",
    "qwen2.5-vl-3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
    "qwen2.5-vl-7b": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
    "qwen2.5-vl-32b": "mlx-community/Qwen2.5-VL-32B-Instruct-8bit",
    "qwen2.5-vl-72b": "mlx-community/Qwen2.5-VL-72B-Instruct-4bit",
    "pixtral-12b": "mlx-community/pixtral-12b-4bit",
    "llava-qwen-0.5b": "mlx-community/llava-interleave-qwen-0.5b-bf16",
    "llava-qwen-7b": "mlx-community/llava-interleave-qwen-7b-4bit",
}


def resolve_alias(name: str, custom_aliases: dict[str, str] | None = None) -> str:
    """Resolve model alias to full HuggingFace path.

    Args:
        name: Model name (alias or full HF path)
        custom_aliases: Optional dict of custom aliases that override builtins

    Returns:
        Full HuggingFace path (e.g., 'mlx-community/Qwen2-VL-7B-Instruct-4bit')
    """
    # Custom aliases override builtins
    if custom_aliases and name in custom_aliases:
        return custom_aliases[name]

    # Check builtin aliases
    if name in BUILTIN_ALIASES:
        return BUILTIN_ALIASES[name]

    # Assume it's already a full path
    return name
