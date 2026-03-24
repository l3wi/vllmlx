"""Model alias resolution for vllmlx."""

from __future__ import annotations

from urllib.parse import urlparse

from vllmlx.models.catalog import build_alias_index, load_catalog_cached

HF_HOSTS = {"huggingface.co", "www.huggingface.co", "hf.co"}

# Builtin aliases mapping short names to full HuggingFace paths.
BUILTIN_ALIASES: dict[str, str] = build_alias_index(load_catalog_cached())


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
