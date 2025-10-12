"""Rakumart utilities package.

Modules:
- display: printing and analysis of search results
- console: interactive console for search results
"""

from .display import display_all_results_table, display_all_search_result_items
from .console import SearchResultConsole
from .utils import convert_rmb_to_jpy, convert_jpy_to_rmb, get_product_price_in_jpy
from .filters import (
    filter_products_by_size,
    filter_products_by_inventory,
    filter_products_by_delivery,
    filter_products_by_shipping_fee,
    filter_products_by_weight,
    filter_products_by_jpy_price,
    filter_products_by_categories,
    apply_product_filters,
    collect_categories_from_products,
)
from .api_search import (
    search_products,
    get_product_detail,
    get_image_id,
)

__all__ = [
    "display_all_results_table",
    "display_all_search_result_items",
    "SearchResultConsole",
    "convert_rmb_to_jpy",
    "convert_jpy_to_rmb",
    "get_product_price_in_jpy",
    "filter_products_by_size",
    "filter_products_by_inventory",
    "filter_products_by_delivery",
    "filter_products_by_shipping_fee",
    "filter_products_by_weight",
    "filter_products_by_jpy_price",
    "filter_products_by_categories",
    "apply_product_filters",
    "collect_categories_from_products",
    "search_products",
    "get_product_detail",
    "get_image_id",
]


