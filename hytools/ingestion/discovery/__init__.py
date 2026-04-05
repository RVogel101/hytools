"""Discovery: catalog search (WorldCat), book inventory, author extraction and research."""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "BookAuthor": ("book_inventory", "BookAuthor"),
    "BookEdition": ("book_inventory", "BookEdition"),
    "BookInventoryEntry": ("book_inventory", "BookInventoryEntry"),
    "BookInventoryManager": ("book_inventory", "BookInventoryManager"),
    "BookInventorySummary": ("book_inventory", "BookInventorySummary"),
    "ContentType": ("book_inventory", "ContentType"),
    "CoverageStatus": ("book_inventory", "CoverageStatus"),
    "LanguageVariant": ("book_inventory", "LanguageVariant"),
    "AuthorProfile": ("author_research", "AuthorProfile"),
    "AuthorProfileManager": ("author_research", "AuthorProfileManager"),
    "FALLBACK_ARMENIAN_BOOKS": ("worldcat_searcher", "FALLBACK_ARMENIAN_BOOKS"),
    "WorldCatError": ("worldcat_searcher", "WorldCatError"),
    "WorldCatSearcher": ("worldcat_searcher", "WorldCatSearcher"),
    "AuthorExtractor": ("author_extraction", "AuthorExtractor"),
    "extract_authors_from_corpus": ("author_extraction", "extract_authors_from_corpus"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
