"""Models module for vllmlx."""

from vllmlx.models.aliases import BUILTIN_ALIASES, resolve_alias
from vllmlx.models.catalog import CatalogEntry, load_catalog, search_catalog
from vllmlx.models.registry import ModelInfo, delete_model, download_model, list_models

__all__ = [
    "BUILTIN_ALIASES",
    "resolve_alias",
    "CatalogEntry",
    "load_catalog",
    "search_catalog",
    "ModelInfo",
    "list_models",
    "download_model",
    "delete_model",
]
