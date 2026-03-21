"""Model alias resolution for vllmlx."""

from __future__ import annotations

from urllib.parse import urlparse

HF_HOSTS = {"huggingface.co", "www.huggingface.co", "hf.co"}

# Builtin aliases mapping short names to full HuggingFace paths.
BUILTIN_ALIASES: dict[str, str] = {
    # Legacy VLM aliases
    "qwen2-vl-2b": "mlx-community/Qwen2-VL-2B-Instruct-4bit",
    "qwen2-vl-7b": "mlx-community/Qwen2-VL-7B-Instruct-4bit",
    "qwen2.5-vl-3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
    "qwen2.5-vl-7b": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
    "qwen2.5-vl-32b": "mlx-community/Qwen2.5-VL-32B-Instruct-8bit",
    "qwen2.5-vl-72b": "mlx-community/Qwen2.5-VL-72B-Instruct-4bit",
    "pixtral-12b": "mlx-community/pixtral-12b-4bit",
    "llava-qwen-0.5b": "mlx-community/llava-interleave-qwen-0.5b-bf16",
    "llava-qwen-7b": "mlx-community/llava-interleave-qwen-7b-4bit",
    # Ollama-style aliases
    "qwen3:4b": "mlx-community/Qwen3-4B-4bit",
    "qwen3:8b": "mlx-community/Qwen3-8B-4bit",
    "qwen3-vl:4b": "mlx-community/Qwen3-VL-4B-Instruct-4bit",
    "qwen3-vl:8b": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
    "qwen3-embedding:4b": "mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
}


def _extract_hf_repo_from_url(value: str) -> str | None:
    """Extract `namespace/repo` from HuggingFace URLs."""
    candidate = value.strip()
    if not candidate:
        return None

    if "://" not in candidate and candidate.startswith(("huggingface.co/", "hf.co/")):
        candidate = f"https://{candidate}"

    if "://" not in candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.netloc not in HF_HOSTS:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    # Handle optional /models/<namespace>/<repo> URL style.
    if parts[0] == "models":
        parts = parts[1:]

    if len(parts) < 2:
        return None

    return f"{parts[0]}/{parts[1]}"


def normalize_model_name(name: str) -> str:
    """Normalize user input into alias key or HF repo id."""
    stripped = name.strip()
    from_url = _extract_hf_repo_from_url(stripped)
    if from_url:
        return from_url
    return stripped


def resolve_alias(name: str, custom_aliases: dict[str, str] | None = None) -> str:
    """Resolve model alias to full HuggingFace path."""
    normalized = normalize_model_name(name)
    key = normalized.lower()

    if custom_aliases:
        custom_lookup = {alias.lower(): path for alias, path in custom_aliases.items()}
        if key in custom_lookup:
            return custom_lookup[key]

    if key in BUILTIN_ALIASES:
        return BUILTIN_ALIASES[key]

    return normalized
