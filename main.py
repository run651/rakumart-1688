import time
import hashlib
import requests
import json
import argparse
import os
from typing import List, Dict, Any
import webbrowser
import tempfile
import cmd
import shutil
from rakumart.display import display_all_results_table, display_all_search_result_items
from rakumart.console import SearchResultConsole
from rakumart.filters import apply_product_filters, collect_categories_from_products
from rakumart.utils import convert_rmb_to_jpy, convert_jpy_to_rmb, get_product_price_in_jpy
from rakumart.api_search import search_products, get_product_detail, get_image_id
from rakumart.orders import (
    create_order,
    update_order_status,
    cancel_order,
    get_order_list,
    get_order_detail,
    get_stock_list,
    create_porder,
    update_porder_status,
    cancel_porder,
    get_porder_list,
    get_porder_detail,
    get_logistics_track,
)
from rakumart.config import (
    APP_KEY,
    APP_SECRET,
    API_URL,
    DETAIL_API_URL,
    IMAGE_ID_API_URL,
    LOGISTICS_API_URL,
    TAGS_API_URL,
    CREATE_ORDER_API_URL,
    UPDATE_ORDER_STATUS_API_URL,
    CANCEL_ORDER_API_URL,
    ORDER_LIST_API_URL,
    ORDER_DETAIL_API_URL,
    STOCK_LIST_API_URL,
    CREATE_PORDER_API_URL,
    UPDATE_PORDER_STATUS_API_URL,
    CANCEL_PORDER_API_URL,
    PORDER_LIST_API_URL,
    PORDER_DETAIL_API_URL,
    LOGISTICS_TRACK_API_URL,
)
from rakumart.enrich import enrich_products_with_detail

# API constants moved to rakumart.config


def generate_sign(app_key: str, app_secret: str, timestamp: str) -> str:
    """
    Generate MD5 sign = md5(app_key + app_secret + timestamp)
    """
    raw_str = app_key + app_secret + timestamp
    return hashlib.md5(raw_str.encode("utf-8")).hexdigest()


def convert_rmb_to_jpy(rmb_price: float, exchange_rate: float = 20.0) -> float:
    """
    Convert RMB price to Japanese Yen.
    Default exchange rate: 1 RMB = 20 JPY (approximate)
    """
    return rmb_price * exchange_rate


def convert_jpy_to_rmb(jpy_price: float, exchange_rate: float = 20.0) -> float:
    """
    Convert Japanese Yen price to RMB.
    Default exchange rate: 1 RMB = 20 JPY (approximate)
    """
    return jpy_price / exchange_rate


def get_product_price_in_jpy(product: dict, exchange_rate: float = 20.0) -> float | None:
    """
    Extract and convert product price to Japanese Yen.
    Returns None if price cannot be determined.
    """
    # Try various price fields
    price_fields = ["goodsPrice", "price", "productPrice", "salePrice", "marketPrice"]
    
    for field in price_fields:
        price = product.get(field)
        if price is not None:
            try:
                # Handle string prices (remove currency symbols, commas, etc.)
                if isinstance(price, str):
                    import re
                    # Remove currency symbols and extract numeric value
                    price_clean = re.sub(r'[^\d.,]', '', price)
                    if price_clean:
                        # Handle comma as decimal separator
                        price_clean = price_clean.replace(',', '.')
                        price_val = float(price_clean)
                    else:
                        continue
                else:
                    price_val = float(price)
                
                # Convert RMB to JPY
                return convert_rmb_to_jpy(price_val, exchange_rate)
            except (ValueError, TypeError):
                continue
    
    return None


def filter_products_by_size(products: List[dict], max_length: float | None = None, 
                          max_width: float | None = None, max_height: float | None = None,
                          strict_mode: bool = False) -> List[dict]:
    """
    Filter products by size constraints (length, width, height).
    In strict mode, products without size information are excluded.
    In non-strict mode, products without size information are included by default.
    """
    if not any([max_length, max_width, max_height]):
        return products
    
    filtered = []
    for product in products:
        # Get product dimensions from various possible fields
        dimensions = product.get("dimensions", {})
        if not dimensions:
            # Try alternative field names
            dimensions = product.get("size", {}) or product.get("specs", {})
        
        # Check each dimension constraint
        length = dimensions.get("length") or dimensions.get("l") or dimensions.get("长")
        width = dimensions.get("width") or dimensions.get("w") or dimensions.get("宽")
        height = dimensions.get("height") or dimensions.get("h") or dimensions.get("高")
        
        # Convert to float if possible
        try:
            length_val = float(length) if length else None
            width_val = float(width) if width else None
            height_val = float(height) if height else None
        except (ValueError, TypeError):
            # If conversion fails, include the product only in non-strict mode
            if not strict_mode:
                filtered.append(product)
            continue
        
        # In strict mode, exclude products missing required dimension info
        if strict_mode:
            if max_length and length_val is None:
                continue
            if max_width and width_val is None:
                continue
            if max_height and height_val is None:
                continue
        else:
            # In non-strict mode, include products without dimension info
            if not any([length_val, width_val, height_val]):
                filtered.append(product)
                continue
        
        # Check constraints
        if max_length and length_val and length_val > max_length:
            continue
        if max_width and width_val and width_val > max_width:
            continue
        if max_height and height_val and height_val > max_height:
            continue
            
        filtered.append(product)
    
    return filtered


def filter_products_by_inventory(products: List[dict], min_inventory: int, strict_mode: bool = False) -> List[dict]:
    """
    Filter products by minimum inventory level.
    In strict mode, products without inventory information are excluded.
    In non-strict mode, products without inventory information are included by default.
    """
    if min_inventory is None:
        return products
    
    filtered = []
    for product in products:
        # Get inventory from various possible fields
        inventory = product.get("inventory") or product.get("stock") or product.get("quantity")
        
        # If no inventory info, handle based on strict mode
        if inventory is None:
            if not strict_mode:
                filtered.append(product)
            continue
            
        try:
            inventory_val = int(inventory)
            if inventory_val >= min_inventory:
                filtered.append(product)
        except (ValueError, TypeError):
            # If conversion fails, include the product only in non-strict mode
            if not strict_mode:
                filtered.append(product)
    
    return filtered


def filter_products_by_delivery(products: List[dict], max_delivery_days: int, strict_mode: bool = False) -> List[dict]:
    """
    Filter products by maximum delivery days to Japan.
    In strict mode, products without delivery information are excluded.
    In non-strict mode, products without delivery information are included by default.
    """
    if max_delivery_days is None:
        return products
    
    filtered = []
    for product in products:
        # Get delivery info from various possible fields
        delivery = product.get("delivery_days") or product.get("shipping_days") or product.get("delivery_time")
        
        # If no delivery info, handle based on strict mode
        if delivery is None:
            if not strict_mode:
                filtered.append(product)
            continue
            
        try:
            # Handle different delivery time formats
            if isinstance(delivery, str):
                # Extract numbers from strings like "3-5 days", "7 days", etc.
                import re
                numbers = re.findall(r'\d+', delivery)
                if numbers:
                    delivery_val = int(numbers[0])  # Use first number found
                else:
                    delivery_val = None
            else:
                delivery_val = int(delivery)
                
            if delivery_val is None or delivery_val <= max_delivery_days:
                filtered.append(product)
        except (ValueError, TypeError):
            # If conversion fails, include the product only in non-strict mode
            if not strict_mode:
                filtered.append(product)
    
    return filtered


def filter_products_by_shipping_fee(products: List[dict], max_shipping_fee: float, strict_mode: bool = False) -> List[dict]:
    """
    Filter products by maximum shipping fee to Japan.
    In strict mode, products without shipping fee information are excluded.
    In non-strict mode, products without shipping fee information are included by default.
    """
    if max_shipping_fee is None:
        return products
    
    filtered = []
    for product in products:
        # Get shipping fee from various possible fields
        shipping_fee = product.get("shipping_fee") or product.get("shipping_cost") or product.get("delivery_fee")
        
        # If no shipping fee info, handle based on strict mode
        if shipping_fee is None:
            if not strict_mode:
                filtered.append(product)
            continue
            
        try:
            shipping_fee_val = float(shipping_fee)
            if shipping_fee_val <= max_shipping_fee:
                filtered.append(product)
        except (ValueError, TypeError):
            # If conversion fails, include the product only in non-strict mode
            if not strict_mode:
                filtered.append(product)
    
    return filtered


def filter_products_by_weight(products: List[dict], max_weight: float, strict_mode: bool = False) -> List[dict]:
    """
    Filter products by maximum weight.
    In strict mode, products without weight information are excluded.
    In non-strict mode, products without weight information are included by default.
    """
    if max_weight is None:
        return products
    
    filtered = []
    for product in products:
        # Get weight from various possible fields
        weight = product.get("weight") or product.get("product_weight") or product.get("net_weight") or product.get("gross_weight")
        
        # If no weight info, handle based on strict mode
        if weight is None:
            if not strict_mode:
                filtered.append(product)
            continue
            
        try:
            # Handle different weight formats and units
            if isinstance(weight, str):
                # Extract numeric value from strings like "500g", "1.2kg", "2.5 lbs", etc.
                import re
                # Remove common weight units and extract number
                weight_clean = re.sub(r'[^\d.,]', '', weight)
                if weight_clean:
                    # Handle comma as decimal separator
                    weight_clean = weight_clean.replace(',', '.')
                    weight_val = float(weight_clean)
                    
                    # Convert to grams if needed (assuming kg if no unit specified and value > 10)
                    if 'kg' in weight.lower() or (weight_val > 10 and 'g' not in weight.lower()):
                        weight_val = weight_val * 1000  # Convert kg to grams
                    elif 'lb' in weight.lower() or 'pound' in weight.lower():
                        weight_val = weight_val * 453.592  # Convert pounds to grams
                else:
                    weight_val = None
            else:
                weight_val = float(weight)
                
            if weight_val is None or weight_val <= max_weight:
                filtered.append(product)
        except (ValueError, TypeError):
            # If conversion fails, include the product only in non-strict mode
            if not strict_mode:
                filtered.append(product)
    
    return filtered


def filter_products_by_jpy_price(products: List[dict], jpy_price_min: float | None = None, 
                                jpy_price_max: float | None = None, exchange_rate: float = 20.0,
                                strict_mode: bool = False) -> List[dict]:
    """
    Filter products by Japanese Yen price range.
    In strict mode, products without price information are excluded.
    In non-strict mode, products without price information are included by default.
    """
    if not any([jpy_price_min, jpy_price_max]):
        return products
    
    filtered = []
    for product in products:
        # Get price in JPY
        jpy_price = get_product_price_in_jpy(product, exchange_rate)
        
        # If no price info, handle based on strict mode
        if jpy_price is None:
            if not strict_mode:
                filtered.append(product)
            continue
        
        # Check price constraints
        if jpy_price_min and jpy_price < jpy_price_min:
            continue
        if jpy_price_max and jpy_price > jpy_price_max:
            continue
            
        filtered.append(product)
    
    return filtered


def apply_product_filters(products: List[dict], categories: List[str] | None = None,
                         subcategories: List[str] | None = None, sub_subcategories: List[str] | None = None,
                         max_length: float | None = None, max_width: float | None = None, max_height: float | None = None,
                         min_inventory: int | None = None, max_delivery_days: int | None = None,
                         max_shipping_fee: float | None = None, max_weight: float | None = None,
                         jpy_price_min: float | None = None, jpy_price_max: float | None = None,
                         exchange_rate: float = 20.0, strict_mode: bool = False) -> List[dict]:
    """
    Apply all product filters to the given list of products.
    In strict mode, only products meeting ALL criteria are returned.
    """
    filtered_products = products
    
    # Apply category filters first
    filtered_products = filter_products_by_categories(
        filtered_products, categories, subcategories, sub_subcategories
    )
    
    # Apply JPY price filters
    filtered_products = filter_products_by_jpy_price(
        filtered_products, jpy_price_min, jpy_price_max, exchange_rate, strict_mode
    )
    
    # Apply size filters
    filtered_products = filter_products_by_size(
        filtered_products, max_length, max_width, max_height, strict_mode
    )
    
    # Apply weight filter
    filtered_products = filter_products_by_weight(
        filtered_products, max_weight, strict_mode
    )
    
    # Apply inventory filter
    filtered_products = filter_products_by_inventory(
        filtered_products, min_inventory, strict_mode
    )
    
    # Apply delivery filter
    filtered_products = filter_products_by_delivery(
        filtered_products, max_delivery_days, strict_mode
    )
    
    # Apply shipping fee filter
    filtered_products = filter_products_by_shipping_fee(
        filtered_products, max_shipping_fee, strict_mode
    )
    
    return filtered_products


def get_available_categories(products: List[dict]) -> dict:
    """
    Extract available categories, subcategories, and sub-subcategories from a list of products.
    Returns a dictionary with 'categories', 'subcategories', and 'sub_subcategories' lists.
    """
    categories = set()
    subcategories = set()
    sub_subcategories = set()
    
    for product in products:
        # Extract category information from various possible fields
        category_info = product.get("category") or product.get("categoryInfo") or {}
        
        if isinstance(category_info, dict):
            # Main category
            main_cat = category_info.get("category") or category_info.get("mainCategory") or category_info.get("一级类目")
            if main_cat:
                categories.add(main_cat)
            
            # Subcategory
            sub_cat = category_info.get("subcategory") or category_info.get("subCategory") or category_info.get("二级类目")
            if sub_cat:
                subcategories.add(sub_cat)
            
            # Sub-subcategory
            sub_sub_cat = category_info.get("subSubcategory") or category_info.get("sub_subcategory") or category_info.get("三级类目")
            if sub_sub_cat:
                sub_subcategories.add(sub_sub_cat)
        elif isinstance(category_info, str):
            # If it's a string, treat it as the main category
            categories.add(category_info)
    
    return {
        "categories": sorted(list(categories)),
        "subcategories": sorted(list(subcategories)),
        "sub_subcategories": sorted(list(sub_subcategories))
    }


def filter_products_by_categories(products: List[dict], categories: List[str] | None = None,
                                 subcategories: List[str] | None = None,
                                 sub_subcategories: List[str] | None = None) -> List[dict]:
    """
    Filter products by category, subcategory, and sub-subcategory.
    Products without category information are included by default.
    """
    if not any([categories, subcategories, sub_subcategories]):
        return products
    
    filtered = []
    for product in products:
        # Get category information
        category_info = product.get("category") or product.get("categoryInfo") or {}
        
        if not category_info:
            # If no category info, include the product
            filtered.append(product)
            continue
        
        # Check category filters
        if categories:
            main_cat = category_info.get("category") or category_info.get("mainCategory") or category_info.get("一级类目")
            if not main_cat or main_cat not in categories:
                continue
        
        if subcategories:
            sub_cat = category_info.get("subcategory") or category_info.get("subCategory") or category_info.get("二级类目")
            if not sub_cat or sub_cat not in subcategories:
                continue
        
        if sub_subcategories:
            sub_sub_cat = category_info.get("subSubcategory") or category_info.get("sub_subcategory") or category_info.get("三级类目")
            if not sub_sub_cat or sub_sub_cat not in sub_subcategories:
                continue
        
        filtered.append(product)
    
    return filtered


# moved to rakumart.api_search.search_products
def search_products(
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    shop_type: str = "1688",
    price_min: str | None = None,
    price_max: str | None = None,
    order_key: str | None = None,
    order_value: str | None = None,
    # Category filtering - Multi-select support for hierarchical categories
    categories: List[str] | None = None,
    subcategories: List[str] | None = None,
    sub_subcategories: List[str] | None = None,
    # Size filtering - Maximum values for length, width, height (in cm)
    max_length: float | None = None,
    max_width: float | None = None,
    max_height: float | None = None,
    # Weight filtering - Maximum weight (in grams)
    max_weight: float | None = None,
    # Japanese Yen price filtering - Price range in JPY
    jpy_price_min: float | None = None,
    jpy_price_max: float | None = None,
    # Exchange rate for RMB to JPY conversion (default: 1 RMB = 20 JPY)
    exchange_rate: float = 20.0,
    # Strict filtering mode - Only return products meeting ALL criteria
    strict_mode: bool = False,
    # Inventory filtering - Minimum inventory level required
    min_inventory: int | None = None,
    # Delivery filtering - Maximum delivery days to Japan
    max_delivery_days: int | None = None,
    # Shipping fee filtering - Maximum shipping fee to Japan (in RMB)
    max_shipping_fee: float | None = None,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> List[dict]:
    """
    Enhanced product search with comprehensive filtering capabilities.
    
    Features implemented:
    1. Multi-category filtering (categories, subcategories, sub-subcategories)
    2. Price range filtering (min/max values in RMB)
    3. Japanese Yen price filtering (min/max values in JPY with automatic conversion)
    4. Size filtering (maximum length, width, height)
    5. Weight filtering (maximum weight in grams)
    6. Inventory filtering (minimum inventory level)
    7. Delivery date filtering (maximum delivery days to Japan)
    8. Shipping fee filtering (maximum shipping fee to Japan)
    9. Strict filtering mode (only return products meeting ALL criteria)
    
    The function applies both API-level filters (for supported features) and
    client-side filters (for features not supported by the API).
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    payload = {
        "app_key": resolved_app_key,
        "timestamp": timestamp,
        "sign": sign,
        "keywords": keyword,
        "shop_type": shop_type,
        "page": str(page),
        "pageSize": str(page_size)
    }

    # Optional filters and sorting
    if price_min is not None:
        payload["price_min"] = str(price_min)
    if price_max is not None:
        payload["price_max"] = str(price_max)
    if order_key is not None:
        payload["order_by[0][key]"] = order_key
    if order_value is not None:
        payload["order_by[0][value]"] = order_value
    
    # Category filtering
    if categories is not None:
        for i, category in enumerate(categories):
            payload[f"categories[{i}]"] = str(category)
    if subcategories is not None:
        for i, subcategory in enumerate(subcategories):
            payload[f"subcategories[{i}]"] = str(subcategory)
    if sub_subcategories is not None:
        for i, sub_subcategory in enumerate(sub_subcategories):
            payload[f"sub_subcategories[{i}]"] = str(sub_subcategory)
    
    # Size filtering
    if max_length is not None:
        payload["max_length"] = str(max_length)
    if max_width is not None:
        payload["max_width"] = str(max_width)
    if max_height is not None:
        payload["max_height"] = str(max_height)
    
    # Inventory filtering
    if min_inventory is not None:
        payload["min_inventory"] = str(min_inventory)
    
    # Delivery filtering
    if max_delivery_days is not None:
        payload["max_delivery_days"] = str(max_delivery_days)
    
    # Shipping fee filtering
    if max_shipping_fee is not None:
        payload["max_shipping_fee"] = str(max_shipping_fee)

    # 4) Send POST request
    try:
        response = requests.post(resolved_api_url, data=payload, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to API timed out after {request_timeout_seconds}s")
        return []
    except requests.RequestException as exc:
        print(f" Network error while calling API: {exc}")
        return []

    # 5) Parse response JSON
    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from API response")
        return []

    if not data.get("success", False):
        # Provide a clearer hint when credentials are invalid
        msg = data.get("msg") or data
        if data.get("code") == 10001:
            print(" API request failed: app_key invalid or not recognized. Check APP_KEY/APP_SECRET and API_URL.")
        print(" API request failed:", data)
        return []

    total = None
    try:
        # Common structure for this API
        products = data["data"]["result"]["result"]
        total = data["data"]["result"].get("total")
    except (KeyError, TypeError):
        print(" Unexpected API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return []

    if total is not None:
        print(f" API reported total: {total}")
    
    # Apply client-side filters for features not supported by the API
    products = apply_product_filters(
        products,
        categories=categories,
        subcategories=subcategories,
        sub_subcategories=sub_subcategories,
        max_length=max_length,
        max_width=max_width,
        max_height=max_height,
        max_weight=max_weight,
        jpy_price_min=jpy_price_min,
        jpy_price_max=jpy_price_max,
        exchange_rate=exchange_rate,
        strict_mode=strict_mode,
        min_inventory=min_inventory,
        max_delivery_days=max_delivery_days,
        max_shipping_fee=max_shipping_fee
    )
    
    return products


# moved to rakumart.api_search.get_product_detail
def get_product_detail(
    goods_id: str,
    shop_type: str = "1688",
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Fetch product detail by goodsId.

    Matches detail API that expects fields: app_key, timestamp, sign, shopType, goodsId.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or DETAIL_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    # Send as multipart/form-data per API doc. Use (None, value) so requests builds multipart parts without filenames.
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "shopType": (None, shop_type),
        "goodsId": (None, str(goods_id)),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to detail API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling detail API: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from detail API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Detail API failed: app_key invalid or not recognized. Check credentials and DETAIL_API_URL.")
        print(" Detail API failed:", data)
        return None

    try:
        # Detail payload usually under data
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected detail API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


# moved to rakumart.api_search.get_image_id
def get_image_id(
    image_base64: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Get image ID by uploading base64 encoded image.

    Matches getImageId API that expects fields: app_key, timestamp, sign, imageBase64.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or IMAGE_ID_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    # Send as multipart/form-data per API doc. Use (None, value) so requests builds multipart parts without filenames.
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "imageBase64": (None, image_base64),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to image ID API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling image ID API: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from image ID API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Image ID API failed: app_key invalid or not recognized. Check credentials and IMAGE_ID_API_URL.")
        print(" Image ID API failed:", data)
        return None

    try:
        # Image ID payload usually under data
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected image ID API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


# moved to rakumart.console.SearchResultConsole


def get_current_useful_logistics(
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Get current useful logistics information.

    Matches currentUsefulLogistics API that expects fields: app_key, timestamp, sign.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or LOGISTICS_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    # Send as multipart/form-data per API doc. Use (None, value) so requests builds multipart parts without filenames.
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to logistics API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling logistics API: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from logistics API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Logistics API failed: app_key invalid or not recognized. Check credentials and LOGISTICS_API_URL.")
        print(" Logistics API failed:", data)
        return None

    try:
        # Logistics payload usually under data
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected logistics API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


def get_current_useful_tags(
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Get current useful tags information.

    Matches currentUsefulTags API that expects fields: app_key, timestamp, sign.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or TAGS_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    # Send as multipart/form-data per API doc. Use (None, value) so requests builds multipart parts without filenames.
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to tags API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling tags API: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from tags API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Tags API failed: app_key invalid or not recognized. Check credentials and TAGS_API_URL.")
        print(" Tags API failed:", data)
        return None

    try:
        # Tags payload usually under data
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected tags API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


def create_order(
    purchase_order: str,
    status: str,
    goods: List[dict],
    logistics_id: str | None = None,
    remark: str | None = None,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Create an order with multiple products.

    Args:
        purchase_order: Customer's original order number
        status: Order Status (10-Provisional Order, 20-Official Order)
        goods: List of product dictionaries with the following structure:
            {
                "link": "https://...",  # Product link (required)
                "pic": "https://...",  # Product image (optional)
                "price": "9.99",  # Price in RMB (required)
                "num": "2",  # Quantity (required)
                "remark": "Test Order",  # Product remarks (optional)
                "props": [{"key": "Colour", "value": "Red"}],  # Product attributes (optional)
                "option": [{"name": "Detailed Inspection", "num": "1"}],  # Option services (optional)
                "fba": "4232342",  # FBA code (optional)
                "asin": "543254",  # Product code (optional)
                "tags": [{"type": "ZOZO", "no": "R3111111-B01", "goods_no": "7654376543"}]  # Tags (optional)
            }
        logistics_id: Customer's desired logistics mode (optional)
        remark: Order remarks (optional)
        request_timeout_seconds: HTTP timeout
        app_key: Override APP_KEY
        app_secret: Override APP_SECRET
        api_url: Override API URL

    Returns:
        Order creation response data or None if failed
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or CREATE_ORDER_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    
    # Build the multipart form data
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "purchase_order": (None, purchase_order),
        "status": (None, status),
    }
    
    # Add optional fields
    if logistics_id is not None:
        files["logistics_id"] = (None, logistics_id)
    if remark is not None:
        files["remark"] = (None, remark)
    
    # Add goods data
    for i, good in enumerate(goods):
        prefix = f"goods[{i}]"
        
        # Required fields
        files[f"{prefix}[link]"] = (None, good["link"])
        files[f"{prefix}[price]"] = (None, str(good["price"]))
        files[f"{prefix}[num]"] = (None, str(good["num"]))
        
        # Optional fields
        if "pic" in good:
            files[f"{prefix}[pic]"] = (None, good["pic"])
        if "remark" in good:
            files[f"{prefix}[remark]"] = (None, good["remark"])
        if "fba" in good:
            files[f"{prefix}[fba]"] = (None, good["fba"])
        if "asin" in good:
            files[f"{prefix}[asin]"] = (None, good["asin"])
        
        # Product attributes (props)
        if "props" in good:
            for j, prop in enumerate(good["props"]):
                files[f"{prefix}[props][{j}][key]"] = (None, prop["key"])
                files[f"{prefix}[props][{j}][value]"] = (None, prop["value"])
        
        # Option services
        if "option" in good:
            for j, opt in enumerate(good["option"]):
                files[f"{prefix}[option][{j}][name]"] = (None, opt["name"])
                files[f"{prefix}[option][{j}][num]"] = (None, str(opt["num"]))
        
        # Tags
        if "tags" in good:
            for j, tag in enumerate(good["tags"]):
                files[f"{prefix}[tags][{j}][type]"] = (None, tag["type"])
                files[f"{prefix}[tags][{j}][no]"] = (None, tag["no"])
                if "goods_no" in tag:
                    files[f"{prefix}[tags][{j}][goods_no]"] = (None, tag["goods_no"])

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to create order API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling create order API: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from create order API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Create order API failed: app_key invalid or not recognized. Check credentials and CREATE_ORDER_API_URL.")
        print(" Create order API failed:", data)
        return None

    try:
        # Order creation payload usually under data
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected create order API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


def update_order_status(
    order_sn: str,
    status: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Update an order status.

    Matches updateOrderStatus API that expects fields: app_key, timestamp, sign, order_sn, status.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or UPDATE_ORDER_STATUS_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)

    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "order_sn": (None, order_sn),
        "status": (None, status),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to update order status API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling update order status API: {exc}")
        return None


def cancel_order(
    order_sn: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Cancel an order.

    Matches cancelOrder API that expects fields: app_key, timestamp, sign, order_sn.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or CANCEL_ORDER_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)

    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "order_sn": (None, order_sn),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to cancel order API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling cancel order API: {exc}")
        return None

def get_order_list(
    page: int = 1,
    page_size: int = 10,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Fetch paginated order list.

    Matches orderList API that expects fields: app_key, timestamp, sign, page, pageSize.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or ORDER_LIST_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)

    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "page": (None, str(page)),
        "pageSize": (None, str(page_size)),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to order list API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling order list API: {exc}")
        return None

def get_order_detail(
    order_sn: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Fetch order detail by order_sn.

    Matches orderDetail API that expects fields: app_key, timestamp, sign, order_sn.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or ORDER_DETAIL_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)

    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "order_sn": (None, order_sn),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to order detail API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling order detail API: {exc}")
        return None

def get_stock_list(
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Fetch stock list information.

    Matches stockList API that expects fields: app_key, timestamp, sign.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or STOCK_LIST_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)

    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
    }

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to stock list API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling stock list API: {exc}")
        return None

def create_porder(
    status: str,
    logistics_id: str,
    porder_detail: List[dict],
    client_remark: str | None = None,
    receiver_address: dict | None = None,
    importer_address: dict | None = None,
    porder_file: List[dict] | None = None,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    """Create a delivery order (Porder).

    porder_detail: list of items with keys order_sn (required), sorting, num (required), client_remark, porder_detail_tag (list of {type,no,goods_no,text_line_one,text_line_two}).
    receiver_address/importer_address: dicts with specified keys in API doc.
    porder_file: list of {name, file} where file is a path to upload.
    """
    timestamp = str(int(time.time()))

    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or CREATE_PORDER_API_URL

    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)

    files: dict = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "status": (None, status),
        "logistics_id": (None, logistics_id),
    }

    if client_remark:
        files["client_remark"] = (None, client_remark)

    # porder_detail items
    for i, item in enumerate(porder_detail):
        prefix = f"porder_detail[{i}]"
        files[f"{prefix}[order_sn]"] = (None, item["order_sn"])
        if "sorting" in item:
            files[f"{prefix}[sorting]"] = (None, str(item["sorting"]))
        files[f"{prefix}[num]"] = (None, str(item["num"]))
        if "client_remark" in item:
            files[f"{prefix}[client_remark]"] = (None, item["client_remark"])

        if "porder_detail_tag" in item:
            for j, tag in enumerate(item["porder_detail_tag"]):
                tprefix = f"{prefix}[porder_detail_tag][{j}]"
                if "type" in tag:
                    files[f"{tprefix}["]
                # Fill all possible keys if present
                for key in ["type", "no", "goods_no", "text_line_one", "text_line_two"]:
                    if key in tag:
                        files[f"{tprefix}[{key}]"] = (None, str(tag[key]))

    # Receiver address
    if isinstance(receiver_address, dict):
        for key, value in receiver_address.items():
            files[f"receiver_address[{key}]"] = (None, str(value))

    # Importer address
    if isinstance(importer_address, dict):
        for key, value in importer_address.items():
            files[f"importer_address[{key}]"] = (None, str(value))

    # Files
    if porder_file:
        for i, pf in enumerate(porder_file):
            fprefix = f"porder_file[{i}]"
            if "name" in pf:
                files[f"{fprefix}[name]"] = (None, pf["name"])
            if "file" in pf and pf["file"]:
                try:
                    files[f"{fprefix}[file]"] = (os.path.basename(pf["file"]), open(pf["file"], "rb"))
                except Exception:
                    # fallback: send as path string if cannot open
                    files[f"{fprefix}[file]"] = (None, pf["file"])

    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to create porder API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling create porder API: {exc}")
        return None
    finally:
        # close any opened file handles
        for key, val in list(files.items()):
            if isinstance(val, tuple) and len(val) == 2 and hasattr(val[1], "close"):
                try:
                    val[1].close()
                except Exception:
                    pass

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from create porder API response")
        return None

def update_porder_status(
    porder_sn: str,
    status: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or UPDATE_PORDER_STATUS_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "porder_sn": (None, porder_sn),
        "status": (None, status),
    }
    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to update porder status API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling update porder status API: {exc}")
        return None
    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from update porder status API response")
        return None
    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Update porder status API failed: app_key invalid or not recognized.")
        print(" Update porder status API failed:", data)
        return None
    return data.get("data", {})

def cancel_porder(
    porder_sn: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or CANCEL_PORDER_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "porder_sn": (None, porder_sn),
    }
    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to cancel porder API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling cancel porder API: {exc}")
        return None
    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from cancel porder API response")
        return None
    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Cancel porder API failed: app_key invalid or not recognized.")
        print(" Cancel porder API failed:", data)
        return None
    return data

def get_porder_list(
    page: int = 1,
    page_size: int = 10,
    porder_sn: str | None = None,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or PORDER_LIST_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "page": (None, str(page)),
        "pageSize": (None, str(page_size)),
    }
    if porder_sn:
        files["porder_sn"] = (None, porder_sn)
    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to porder list API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling porder list API: {exc}")
        return None
    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from porder list API response")
        return None
    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Porder list API failed: app_key invalid or not recognized.")
        print(" Porder list API failed:", data)
        return None
    return data.get("data")

def get_porder_detail(
    porder_sn: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or PORDER_DETAIL_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "porder_sn": (None, porder_sn),
    }
    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to porder detail API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling porder detail API: {exc}")
        return None
    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from porder detail API response")
        return None
    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Porder detail API failed: app_key invalid or not recognized.")
        print(" Porder detail API failed:", data)
        return None
    return data.get("data")

def get_logistics_track(
    express_no: str,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> dict | None:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or LOGISTICS_TRACK_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp)
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "express_no": (None, express_no),
    }
    try:
        response = requests.post(resolved_api_url, files=files, timeout=request_timeout_seconds)
        response.raise_for_status()
    except requests.Timeout:
        print(f" Request to logistics track API timed out after {request_timeout_seconds}s")
        return None
    except requests.RequestException as exc:
        print(f" Network error while calling logistics track API: {exc}")
        return None
    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from logistics track API response")
        return None
    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Logistics track API failed: app_key invalid or not recognized.")
        print(" Logistics track API failed:", data)
        return None
    return data.get("data")

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Create porder API failed: app_key invalid or not recognized. Check credentials and CREATE_PORDER_API_URL.")
        print(" Create porder API failed:", data)
        return None

    try:
        return data
    except (KeyError, TypeError):
        print(" Unexpected create porder API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from stock list API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Stock list API failed: app_key invalid or not recognized. Check credentials and STOCK_LIST_API_URL.")
        print(" Stock list API failed:", data)
        return None

    try:
        return data
    except (KeyError, TypeError):
        print(" Unexpected stock list API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from order detail API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Order detail API failed: app_key invalid or not recognized. Check credentials and ORDER_DETAIL_API_URL.")
        print(" Order detail API failed:", data)
        return None

    try:
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected order detail API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from order list API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Order list API failed: app_key invalid or not recognized. Check credentials and ORDER_LIST_API_URL.")
        print(" Order list API failed:", data)
        return None

    try:
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected order list API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from cancel order API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Cancel order API failed: app_key invalid or not recognized. Check credentials and CANCEL_ORDER_API_URL.")
        print(" Cancel order API failed:", data)
        return None

    try:
        return data
    except (KeyError, TypeError):
        print(" Unexpected cancel order API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    try:
        data = response.json()
    except ValueError:
        print(" Failed to parse JSON from update order status API response")
        return None

    if not data.get("success", False):
        if data.get("code") == 10001:
            print(" Update order status API failed: app_key invalid or not recognized. Check credentials and UPDATE_ORDER_STATUS_API_URL.")
        print(" Update order status API failed:", data)
        return None

    try:
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected update order status API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

if __name__ == "__main__":
    # Delegate to modular CLI
    from rakumart.cli import run as cli_run
    exit(cli_run())
    subparsers = parser.add_subparsers(dest="command", required=False)

    # Search subcommand (default behavior if no command given)
    search_parser = subparsers.add_parser("search", help="Search products by keyword")
    search_parser.add_argument("keyword", nargs="?", default="laptop", help="Keyword to search (default: laptop)")
    search_parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    search_parser.add_argument("--page-size", type=int, default=10, help="Page size (default: 10)")
    search_parser.add_argument("--price-min", type=str, help="Minimum price filter (sent as price_min)")
    search_parser.add_argument("--price-max", type=str, help="Maximum price filter (sent as price_max)")
    search_parser.add_argument("--order-key", type=str, help="Sort field (sent as order_by[0][key])")
    search_parser.add_argument("--order-value", type=str, choices=["asc", "desc"], help="Sort direction (sent as order_by[0][value])")
    search_parser.add_argument("--shop-type", type=str, default="1688", help="Shop type (default: 1688)")
    search_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    
    # Category filtering
    search_parser.add_argument("--categories", nargs="*", help="Filter by categories (multi-select)")
    search_parser.add_argument("--subcategories", nargs="*", help="Filter by subcategories (multi-select)")
    search_parser.add_argument("--sub-subcategories", nargs="*", help="Filter by sub-subcategories (multi-select)")
    
    # Size filtering
    search_parser.add_argument("--max-length", type=float, help="Maximum length (cm)")
    search_parser.add_argument("--max-width", type=float, help="Maximum width (cm)")
    search_parser.add_argument("--max-height", type=float, help="Maximum height (cm)")
    
    # Weight filtering
    search_parser.add_argument("--max-weight", type=float, help="Maximum weight (grams)")
    
    # Japanese Yen price filtering
    search_parser.add_argument("--jpy-price-min", type=float, help="Minimum price in Japanese Yen")
    search_parser.add_argument("--jpy-price-max", type=float, help="Maximum price in Japanese Yen")
    search_parser.add_argument("--exchange-rate", type=float, default=20.0, help="RMB to JPY exchange rate (default: 20.0)")
    
    # Strict filtering mode
    search_parser.add_argument("--strict", action="store_true", help="Strict mode: only return products meeting ALL criteria")
    
    # Inventory filtering
    search_parser.add_argument("--min-inventory", type=int, help="Minimum inventory level")
    
    # Delivery filtering
    search_parser.add_argument("--max-delivery-days", type=int, help="Maximum delivery days to Japan")
    
    # Shipping fee filtering
    search_parser.add_argument("--max-shipping-fee", type=float, help="Maximum shipping fee to Japan (RMB)")
    
    # Detail enrichment controls
    search_parser.add_argument("--with-detail", dest="with_detail", action="store_true", default=True, help="Also fetch detail (images, description) for results [default]")
    search_parser.add_argument("--no-detail", dest="with_detail", action="store_false", help="Do not fetch detail for results")
    search_parser.add_argument("--detail-limit", type=int, default=5, help="Max number of items to enrich with detail (default: 5)")
    search_parser.add_argument("--api-url", type=str, help="Override search API URL")
    search_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    search_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    search_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    search_parser.add_argument("--show-all-fields", action="store_true", help="Display all available fields in search results")
    search_parser.add_argument("--show-empty-fields", action="store_true", help="Include empty fields in field analysis")
    search_parser.add_argument("--display-all", action="store_true", help="Display all results in a formatted table like GUI")

    # Detail subcommand
    detail_parser = subparsers.add_parser("detail", help="Get product detail by goodsId")
    detail_parser.add_argument("--goods-id", required=True, help="goodsId to fetch detail for")
    detail_parser.add_argument("--shop-type", type=str, default="1688", help="Product type: 1688/taobao")
    detail_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    detail_parser.add_argument("--detail-api-url", type=str, help="Override detail API URL")
    detail_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    detail_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    detail_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    detail_parser.add_argument("--description-only", action="store_true", help="Print only the HTML description")
    detail_parser.add_argument("--images-only", action="store_true", help="Print only the image URLs array")
    detail_parser.add_argument("--images-and-description", action="store_true", help="Print both images and description together")

    # Image ID subcommand
    image_parser = subparsers.add_parser("image", help="Get image ID by uploading base64 encoded image")
    image_parser.add_argument("--image-base64", required=True, help="Base64 encoded image data")
    image_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    image_parser.add_argument("--image-api-url", type=str, help="Override image ID API URL")
    image_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    image_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    image_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    image_parser.add_argument("--image-id-only", action="store_true", help="Print only the image ID")
    image_parser.add_argument("--link-only", action="store_true", help="Print only the search link")

    # Logistics subcommand
    logistics_parser = subparsers.add_parser("logistics", help="Get current useful logistics information")
    logistics_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    logistics_parser.add_argument("--logistics-api-url", type=str, help="Override logistics API URL")
    logistics_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    logistics_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    logistics_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    logistics_parser.add_argument("--names-only", action="store_true", help="Print only logistics names")
    logistics_parser.add_argument("--ids-only", action="store_true", help="Print only logistics IDs")

    # Tags subcommand
    tags_parser = subparsers.add_parser("tags", help="Get current useful tags information")
    tags_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    tags_parser.add_argument("--tags-api-url", type=str, help="Override tags API URL")
    tags_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    tags_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    tags_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    tags_parser.add_argument("--types-only", action="store_true", help="Print only tag types")
    tags_parser.add_argument("--translations-only", action="store_true", help="Print only Japanese translations")

    # Create Order subcommand
    order_parser = subparsers.add_parser("order", help="Create an order with multiple products")
    order_parser.add_argument("--purchase-order", required=True, help="Customer's original order number")
    order_parser.add_argument("--status", required=True, choices=["10", "20"], help="Order Status: 10-Provisional Order, 20-Official Order")
    order_parser.add_argument("--goods", required=True, help="JSON string containing goods data array")
    order_parser.add_argument("--logistics-id", type=str, help="Customer's desired logistics mode")
    order_parser.add_argument("--remark", type=str, help="Order remarks")
    order_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    order_parser.add_argument("--order-api-url", type=str, help="Override create order API URL")
    order_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    order_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    order_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    order_parser.add_argument("--order-sn-only", action="store_true", help="Print only the order number")
    order_parser.add_argument("--status-only", action="store_true", help="Print only the order status")

    # Update Order Status subcommand
    update_parser = subparsers.add_parser("update-status", help="Update order status")
    update_parser.add_argument("--order-sn", required=True, help="rakumart system order number")
    update_parser.add_argument("--status", required=True, choices=["10", "20"], help="New status: 10-Provisional, 20-Official")
    update_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    update_parser.add_argument("--update-api-url", type=str, help="Override update order status API URL")
    update_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    update_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    update_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    update_parser.add_argument("--order-sn-only", action="store_true", help="Print only the order number from response")

    # Cancel Order subcommand
    cancel_parser = subparsers.add_parser("cancel", help="Cancel an order")
    cancel_parser.add_argument("--order-sn", required=True, help="rakumart system order number")
    cancel_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    cancel_parser.add_argument("--cancel-api-url", type=str, help="Override cancel order API URL")
    cancel_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    cancel_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    cancel_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    cancel_parser.add_argument("--raw", action="store_true", help="Print raw API response as JSON")

    # Order List subcommand
    order_list_parser = subparsers.add_parser("orders", help="Fetch paginated order list")
    order_list_parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    order_list_parser.add_argument("--page-size", type=int, default=10, help="Items per page (default: 10)")
    order_list_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    order_list_parser.add_argument("--orders-api-url", type=str, help="Override order list API URL")
    order_list_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    order_list_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    order_list_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    order_list_parser.add_argument("--summary", action="store_true", help="Print only a summary table of orders")

    # Order Detail subcommand
    order_detail_parser = subparsers.add_parser("order-detail", help="Fetch order detail by order_sn")
    order_detail_parser.add_argument("--order-sn", required=True, help="rakumart system order number")
    order_detail_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    order_detail_parser.add_argument("--order-detail-api-url", type=str, help="Override order detail API URL")
    order_detail_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    order_detail_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    order_detail_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    order_detail_parser.add_argument("--items-only", action="store_true", help="Print only order_detail items array")

    # Stock List subcommand
    stock_list_parser = subparsers.add_parser("stock", help="Fetch stock list")
    stock_list_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    stock_list_parser.add_argument("--stock-api-url", type=str, help="Override stock list API URL")
    stock_list_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    stock_list_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    stock_list_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    stock_list_parser.add_argument("--raw", action="store_true", help="Print raw API response as JSON")

    # Create Porder subcommand
    porder_parser = subparsers.add_parser("porder", help="Create a delivery order (Porder)")
    porder_parser.add_argument("--status", required=True, choices=["10", "20"], help="Porder status: 10-Provisional, 20-Official")
    porder_parser.add_argument("--logistics-id", required=True, help="Logistics ID")
    porder_parser.add_argument("--porder-detail", required=True, help="JSON array for porder_detail list")
    porder_parser.add_argument("--client-remark", type=str, help="Client remark for the whole porder")
    porder_parser.add_argument("--receiver-address", type=str, help="JSON object for receiver_address")
    porder_parser.add_argument("--importer-address", type=str, help="JSON object for importer_address")
    porder_parser.add_argument("--porder-file", type=str, help="JSON array for porder_file list")
    porder_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    porder_parser.add_argument("--porder-api-url", type=str, help="Override create porder API URL")
    porder_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    porder_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    porder_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    porder_parser.add_argument("--porder-sn-only", action="store_true", help="Print only the porder_sn from response")

    # Update Porder Status subcommand
    upd_porder_parser = subparsers.add_parser("porder-update-status", help="Update porder status")
    upd_porder_parser.add_argument("--porder-sn", required=True, help="rakumart system porder number")
    upd_porder_parser.add_argument("--status", required=True, choices=["10", "20"], help="Porder status: 10-Provisional, 20-Official")
    upd_porder_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    upd_porder_parser.add_argument("--porder-update-api-url", type=str, help="Override update porder status API URL")
    upd_porder_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    upd_porder_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    upd_porder_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")

    # Cancel Porder subcommand
    cancel_porder_parser = subparsers.add_parser("porder-cancel", help="Cancel a porder")
    cancel_porder_parser.add_argument("--porder-sn", required=True, help="rakumart system porder number")
    cancel_porder_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    cancel_porder_parser.add_argument("--porder-cancel-api-url", type=str, help="Override cancel porder API URL")
    cancel_porder_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    cancel_porder_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    cancel_porder_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")

    # Porder List subcommand
    porder_list_parser = subparsers.add_parser("porders", help="Fetch porder list")
    porder_list_parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    porder_list_parser.add_argument("--page-size", type=int, default=10, help="Items per page (default: 10)")
    porder_list_parser.add_argument("--porder-sn", type=str, help="Filter by porder_sn")
    porder_list_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    porder_list_parser.add_argument("--porders-api-url", type=str, help="Override porder list API URL")
    porder_list_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    porder_list_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    porder_list_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    porder_list_parser.add_argument("--summary", action="store_true", help="Print only a summary table of porders")

    # Porder Detail subcommand
    porder_detail_parser = subparsers.add_parser("porder-detail", help="Fetch porder detail by porder_sn")
    porder_detail_parser.add_argument("--porder-sn", required=True, help="rakumart system porder number")
    porder_detail_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    porder_detail_parser.add_argument("--porder-detail-api-url", type=str, help="Override porder detail API URL")
    porder_detail_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    porder_detail_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    porder_detail_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    porder_detail_parser.add_argument("--items-only", action="store_true", help="Print only porder_detail items array")

    # Logistics Track subcommand
    ltrack_parser = subparsers.add_parser("ltrack", help="Fetch international logistics tracking by express number")
    ltrack_parser.add_argument("--express-no", required=True, help="International logistics number")
    ltrack_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    ltrack_parser.add_argument("--ltrack-api-url", type=str, help="Override logistics track API URL")
    ltrack_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    ltrack_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    ltrack_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")
    ltrack_parser.add_argument("--timeline-only", action="store_true", help="Print only time/address timeline entries")

    # Categories subcommand
    categories_parser = subparsers.add_parser("categories", help="Get available categories from search results")
    categories_parser.add_argument("keyword", nargs="?", default="laptop", help="Keyword to search (default: laptop)")
    categories_parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    categories_parser.add_argument("--page-size", type=int, default=50, help="Page size (default: 50)")
    categories_parser.add_argument("--shop-type", type=str, default="1688", help="Shop type (default: 1688)")
    categories_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    categories_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    categories_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    categories_parser.add_argument("--api-url", type=str, help="Override search API URL")

    # GUI subcommand
    gui_parser = subparsers.add_parser("gui", help="Open a simple GUI to search and view details")
    gui_parser.add_argument("--shop-type", type=str, default="1688", help="Shop type (default: 1688)")
    gui_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    gui_parser.add_argument("--detail-limit", type=int, default=5, help="Max items to enrich with detail when listing")

    # Console subcommand
    console_parser = subparsers.add_parser("console", help="Interactive console for search results")
    console_parser.add_argument("keyword", nargs="?", default="laptop", help="Keyword to search (default: laptop)")
    console_parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    console_parser.add_argument("--page-size", type=int, default=20, help="Page size (default: 20)")
    console_parser.add_argument("--shop-type", type=str, default="1688", help="Shop type (default: 1688)")
    console_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    console_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    console_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    console_parser.add_argument("--api-url", type=str, help="Override search API URL")
    console_parser.add_argument("--with-detail", dest="with_detail", action="store_true", default=True, help="Also fetch detail for results [default]")
    console_parser.add_argument("--no-detail", dest="with_detail", action="store_false", help="Do not fetch detail for results")
    console_parser.add_argument("--detail-limit", type=int, default=10, help="Max number of items to enrich with detail (default: 10)")

    # Parse first
    args = parser.parse_args()

    # Robust fallback: if no command, decide based on argv contents, then reparse
    if getattr(args, "command", None) is None:
        argv = os.sys.argv[1:]
        if any(tok == "detail" or tok.startswith("--goods-id") for tok in argv):
            args = parser.parse_args(["detail", *argv])
        elif any(tok == "image" or tok.startswith("--image-base64") for tok in argv):
            args = parser.parse_args(["image", *argv])
        elif any(tok == "logistics" for tok in argv):
            args = parser.parse_args(["logistics", *argv])
        elif any(tok == "tags" for tok in argv):
            args = parser.parse_args(["tags", *argv])
        elif any(tok == "order" or tok.startswith("--purchase-order") for tok in argv):
            args = parser.parse_args(["order", *argv])
        elif any(tok == "update-status" or tok.startswith("--order-sn") for tok in argv):
            args = parser.parse_args(["update-status", *argv])
        elif any(tok == "cancel" or tok.startswith("--order-sn") for tok in argv):
            args = parser.parse_args(["cancel", *argv])
        elif any(tok == "orders" or tok.startswith("--page") for tok in argv):
            args = parser.parse_args(["orders", *argv])
        elif any(tok == "order-detail" or tok.startswith("--order-sn") for tok in argv):
            args = parser.parse_args(["order-detail", *argv])
        elif any(tok == "stock" for tok in argv):
            args = parser.parse_args(["stock", *argv])
        elif any(tok == "porder" or tok.startswith("--porder-detail") for tok in argv):
            args = parser.parse_args(["porder", *argv])
        elif any(tok == "porder-update-status" or tok.startswith("--porder-sn") and "porder-update-status" in argv for tok in argv):
            args = parser.parse_args(["porder-update-status", *argv])
        elif any(tok == "porder-cancel" or tok.startswith("--porder-sn") and "porder-cancel" in argv for tok in argv):
            args = parser.parse_args(["porder-cancel", *argv])
        elif any(tok == "porders" or tok.startswith("--page") for tok in argv):
            args = parser.parse_args(["porders", *argv])
        elif any(tok == "porder-detail" or tok.startswith("--porder-sn") for tok in argv):
            args = parser.parse_args(["porder-detail", *argv])
        elif any(tok == "ltrack" or tok.startswith("--express-no") for tok in argv):
            args = parser.parse_args(["ltrack", *argv])
        elif any(tok == "categories" for tok in argv):
            args = parser.parse_args(["categories", *argv])
        else:
            args = parser.parse_args(["search", *argv])

    if args.command == "search":
        if getattr(args, "verbose", False):
            print(" Using API:", args.api_url or API_URL)
        print(f"Searching for keyword: '{args.keyword}' (page={args.page}, page_size={args.page_size})")
        products = search_products(
            args.keyword,
            page=args.page,
            page_size=args.page_size,
            price_min=getattr(args, "price_min", None),
            price_max=getattr(args, "price_max", None),
            order_key=getattr(args, "order_key", None),
            order_value=getattr(args, "order_value", None),
            # Category filtering
            categories=getattr(args, "categories", None),
            subcategories=getattr(args, "subcategories", None),
            sub_subcategories=getattr(args, "sub_subcategories", None),
            # Size filtering
            max_length=getattr(args, "max_length", None),
            max_width=getattr(args, "max_width", None),
            max_height=getattr(args, "max_height", None),
            # Weight filtering
            max_weight=getattr(args, "max_weight", None),
            # Japanese Yen price filtering
            jpy_price_min=getattr(args, "jpy_price_min", None),
            jpy_price_max=getattr(args, "jpy_price_max", None),
            exchange_rate=getattr(args, "exchange_rate", 20.0),
            # Strict filtering mode
            strict_mode=getattr(args, "strict", False),
            # Inventory filtering
            min_inventory=getattr(args, "min_inventory", None),
            # Delivery filtering
            max_delivery_days=getattr(args, "max_delivery_days", None),
            # Shipping fee filtering
            max_shipping_fee=getattr(args, "max_shipping_fee", None),
            request_timeout_seconds=args.timeout,
            shop_type=getattr(args, "shop_type", "1688"),
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "api_url", None),
        )

        # Optionally enrich with detail for first N items
        if getattr(args, "with_detail", True) and products:
            limit = max(0, int(getattr(args, "detail_limit", 0)))
            enrich_products_with_detail(
                products,
                get_detail_fn=lambda **kwargs: get_product_detail(
                    goods_id=kwargs.get("goods_id"),
                    shop_type=kwargs.get("shop_type"),
                    request_timeout_seconds=kwargs.get("request_timeout_seconds"),
                    app_key=getattr(args, "app_key", None),
                    app_secret=getattr(args, "app_secret", None),
                    api_url=None,
                ),
                shop_type=getattr(args, "shop_type", "1688"),
                request_timeout_seconds=args.timeout,
                limit=limit,
                )

        print(f" Found {len(products)} products for keyword '{args.keyword}':\n")
        
        # Show all fields analysis if requested
        if getattr(args, "show_all_fields", False):
            display_all_search_result_items(products, show_empty=getattr(args, "show_empty_fields", False))
        elif getattr(args, "display_all", False):
            # Display all results in formatted table
            display_all_results_table(products)
        else:
            # Default behavior - show individual products
            for p in products:
                print(json.dumps(p, ensure_ascii=False, indent=2))
    elif args.command == "detail":
        if getattr(args, "verbose", False):
            print(" Using API:", args.detail_api_url or DETAIL_API_URL)
        print(f"Fetching detail for goodsId={args.goods_id} (shopType={args.shop_type})")
        detail = get_product_detail(
            goods_id=args.goods_id,
            shop_type=args.shop_type,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "detail_api_url", None),
        )
        if detail is None:
            print(" No detail returned.")
        else:
            if getattr(args, "images_and_description", False):
                out = {
                    "images": detail.get("images", []),
                    "description": detail.get("description", ""),
                }
                print(json.dumps(out, ensure_ascii=False, indent=2))
            elif getattr(args, "description_only", False):
                print(detail.get("description", ""))
            elif getattr(args, "images_only", False):
                print(json.dumps(detail.get("images", []), ensure_ascii=False, indent=2))
            else:
                print(json.dumps(detail, ensure_ascii=False, indent=2))
    elif args.command == "image":
        if getattr(args, "verbose", False):
            print(" Using API:", args.image_api_url or IMAGE_ID_API_URL)
        print(f"Getting image ID for base64 image data (length: {len(args.image_base64)} chars)")
        result = get_image_id(
            image_base64=args.image_base64,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "image_api_url", None),
        )
        if result is None:
            print(" No image ID returned.")
        else:
            if getattr(args, "image_id_only", False):
                print(result.get("imageId", ""))
            elif getattr(args, "link_only", False):
                print(result.get("link", ""))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "order":
        if getattr(args, "verbose", False):
            print(" Using API:", args.order_api_url or CREATE_ORDER_API_URL)
        
        # Parse goods JSON
        try:
            goods_data = json.loads(args.goods)
        except json.JSONDecodeError as e:
            print(f" Failed to parse goods JSON: {e}")
            exit(1)
        
        print(f"Creating order: {args.purchase_order} (status: {args.status})")
        result = create_order(
            purchase_order=args.purchase_order,
            status=args.status,
            goods=goods_data,
            logistics_id=getattr(args, "logistics_id", None),
            remark=getattr(args, "remark", None),
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "order_api_url", None),
        )
        if result is None:
            print(" No order created.")
        else:
            if getattr(args, "order_sn_only", False):
                print(result.get("order_sn", ""))
            elif getattr(args, "status_only", False):
                print(result.get("status", ""))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "update-status":
        if getattr(args, "verbose", False):
            print(" Using API:", args.update_api_url or UPDATE_ORDER_STATUS_API_URL)
        print(f"Updating order status: order_sn={args.order_sn}, status={args.status}")
        result = update_order_status(
            order_sn=args.order_sn,
            status=args.status,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "update_api_url", None),
        )
        if result is None:
            print(" No response data returned.")
        else:
            if getattr(args, "order_sn_only", False):
                print(result.get("order_sn", ""))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "cancel":
        if getattr(args, "verbose", False):
            print(" Using API:", args.cancel_api_url or CANCEL_ORDER_API_URL)
        print(f"Cancelling order: order_sn={args.order_sn}")
        result = cancel_order(
            order_sn=args.order_sn,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "cancel_api_url", None),
        )
        if result is None:
            print(" No response data returned.")
        else:
            if getattr(args, "raw", False):
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "orders":
        if getattr(args, "verbose", False):
            print(" Using API:", args.orders_api_url or ORDER_LIST_API_URL)
        print(f"Fetching orders: page={args.page}, page_size={args.page_size}")
        data_obj = get_order_list(
            page=args.page,
            page_size=args.page_size,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "orders_api_url", None),
        )
        if data_obj is None:
            print(" No data returned.")
        else:
            if getattr(args, "summary", False):
                try:
                    rows = data_obj.get("data", [])
                    for row in rows:
                        print(json.dumps({
                            "order_sn": row.get("order_sn"),
                            "status": row.get("status"),
                            "status_name": row.get("status_name"),
                            "goods_count": row.get("goods_count"),
                            "created_at": row.get("created_at"),
                        }, ensure_ascii=False))
                except Exception:
                    print(json.dumps(data_obj, ensure_ascii=False, indent=2))
            
    elif args.command == "order-detail":
        if getattr(args, "verbose", False):
            print(" Using API:", args.order_detail_api_url or ORDER_DETAIL_API_URL)
        print(f"Fetching order detail: order_sn={args.order_sn}")
        data_obj = get_order_detail(
            order_sn=args.order_sn,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "order_detail_api_url", None),
        )
        if data_obj is None:
            print(" No data returned.")
        else:
            if getattr(args, "items_only", False):
                try:
                    print(json.dumps(data_obj.get("order_detail", []), ensure_ascii=False, indent=2))
                except Exception:
                    print(json.dumps(data_obj, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(data_obj, ensure_ascii=False, indent=2))
    elif args.command == "stock":
        if getattr(args, "verbose", False):
            print(" Using API:", args.stock_api_url or STOCK_LIST_API_URL)
        print("Fetching stock list")
        data_obj = get_stock_list(
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "stock_api_url", None),
        )
        if data_obj is None:
            print(" No data returned.")
        else:
            if getattr(args, "raw", False):
                print(json.dumps(data_obj, ensure_ascii=False, indent=2))
    elif args.command == "porder":
        if getattr(args, "verbose", False):
            print(" Using API:", args.porder_api_url or CREATE_PORDER_API_URL)
        # Parse JSON inputs
        try:
            porder_detail = json.loads(args.porder_detail)
        except json.JSONDecodeError as e:
            print(f" Failed to parse porder_detail JSON: {e}")
            exit(1)
        receiver_address_obj = None
        importer_address_obj = None
        porder_file_list = None
        if getattr(args, "receiver_address", None):
            try:
                receiver_address_obj = json.loads(args.receiver_address)
            except json.JSONDecodeError as e:
                print(f" Failed to parse receiver_address JSON: {e}")
                exit(1)
        if getattr(args, "importer_address", None):
            try:
                importer_address_obj = json.loads(args.importer_address)
            except json.JSONDecodeError as e:
                print(f" Failed to parse importer_address JSON: {e}")
                exit(1)
        if getattr(args, "porder_file", None):
            try:
                porder_file_list = json.loads(args.porder_file)
            except json.JSONDecodeError as e:
                print(f" Failed to parse porder_file JSON: {e}")
                exit(1)

        print(f"Creating porder (status={args.status}, logistics_id={args.logistics_id})")
        result = create_porder(
            status=args.status,
            logistics_id=args.logistics_id,
            porder_detail=porder_detail,
            client_remark=getattr(args, "client_remark", None),
            receiver_address=receiver_address_obj,
            importer_address=importer_address_obj,
            porder_file=porder_file_list,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "porder_api_url", None),
        )
        if result is None:
            print(" No response data returned.")
        else:
            if getattr(args, "porder_sn_only", False):
                data = result.get("data") if isinstance(result, dict) else None
                print((data or {}).get("porder_sn", ""))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "porder-update-status":
        if getattr(args, "verbose", False):
            print(" Using API:", args.porder_update_api_url or UPDATE_PORDER_STATUS_API_URL)
        print(f"Updating porder status: porder_sn={args.porder_sn}, status={args.status}")
        result = update_porder_status(
            porder_sn=args.porder_sn,
            status=args.status,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "porder_update_api_url", None),
        )
        if result is None:
            print(" No response data returned.")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "porder-cancel":
        if getattr(args, "verbose", False):
            print(" Using API:", args.porder_cancel_api_url or CANCEL_PORDER_API_URL)
        print(f"Cancelling porder: porder_sn={args.porder_sn}")
        result = cancel_porder(
            porder_sn=args.porder_sn,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "porder_cancel_api_url", None),
        )
        if result is None:
            print(" No response data returned.")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "porders":
        if getattr(args, "verbose", False):
            print(" Using API:", args.porders_api_url or PORDER_LIST_API_URL)
        print(f"Fetching porders: page={args.page}, page_size={args.page_size}, porder_sn={getattr(args, 'porder_sn', None)}")
        data_obj = get_porder_list(
            page=args.page,
            page_size=args.page_size,
            porder_sn=getattr(args, "porder_sn", None),
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "porders_api_url", None),
        )
        if data_obj is None:
            print(" No data returned.")
        else:
            if getattr(args, "summary", False):
                try:
                    rows = data_obj.get("data", [])
                    for row in rows:
                        print(json.dumps({
                            "porder_sn": row.get("porder_sn"),
                            "status": row.get("status"),
                            "status_name": row.get("status_name"),
                            "created_at": row.get("created_at"),
                        }, ensure_ascii=False))
                except Exception:
                    print(json.dumps(data_obj, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(data_obj, ensure_ascii=False, indent=2))
    elif args.command == "porder-detail":
        if getattr(args, "verbose", False):
            print(" Using API:", args.porder_detail_api_url or PORDER_DETAIL_API_URL)
        print(f"Fetching porder detail: porder_sn={args.porder_sn}")
        data_obj = get_porder_detail(
            porder_sn=args.porder_sn,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "porder_detail_api_url", None),
        )
        if data_obj is None:
            print(" No data returned.")
        else:
            if getattr(args, "items_only", False):
                try:
                    print(json.dumps(data_obj.get("porder_detail", []), ensure_ascii=False, indent=2))
                except Exception:
                    print(json.dumps(data_obj, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(data_obj, ensure_ascii=False, indent=2))
    elif args.command == "ltrack":
        if getattr(args, "verbose", False):
            print(" Using API:", args.ltrack_api_url or LOGISTICS_TRACK_API_URL)
        print(f"Fetching logistics track: express_no={args.express_no}")
        data_obj = get_logistics_track(
            express_no=args.express_no,
            request_timeout_seconds=args.timeout,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "ltrack_api_url", None),
        )
        if data_obj is None:
            print(" No data returned.")
        else:
            if getattr(args, "timeline_only", False):
                try:
                    for node in data_obj.get("address_data", []):
                        print(json.dumps({"time": node.get("time"), "address": node.get("address")}, ensure_ascii=False))
                except Exception:
                    print(json.dumps(data_obj, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(data_obj, ensure_ascii=False, indent=2))
    elif args.command == "categories":
        print(f"Getting available categories for keyword: '{args.keyword}' (page={args.page}, page_size={args.page_size})")
        products = search_products(
            args.keyword,
            page=args.page,
            page_size=args.page_size,
            request_timeout_seconds=args.timeout,
            shop_type=args.shop_type,
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "api_url", None),
        )
        
        if not products:
            print(" No products found.")
        else:
            categories_info = get_available_categories(products)
            print(f" Found {len(products)} products with the following categories:")
            print("\nCategories:")
            for cat in categories_info["categories"]:
                print(f"  - {cat}")
            print("\nSubcategories:")
            for subcat in categories_info["subcategories"]:
                print(f"  - {subcat}")
            print("\nSub-subcategories:")
            for sub_subcat in categories_info["sub_subcategories"]:
                print(f"  - {sub_subcat}")
    elif args.command == "gui":
        from rakumart.gui import run_gui
        run_gui(shop_type=getattr(args, "shop_type", "1688"), timeout=args.timeout, detail_limit=getattr(args, "detail_limit", 5))
    elif args.command == "console":
        print(f"Searching for keyword: '{args.keyword}' (page={args.page}, page_size={args.page_size})")
        products = search_products(
            args.keyword,
            page=args.page,
            page_size=args.page_size,
            request_timeout_seconds=args.timeout,
            shop_type=getattr(args, "shop_type", "1688"),
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "api_url", None),
        )

        # Optionally enrich with detail for first N items
        if getattr(args, "with_detail", True) and products:
            limit = max(0, int(getattr(args, "detail_limit", 0)))
            enrich_products_with_detail(
                products,
                get_detail_fn=lambda **kwargs: get_product_detail(
                    goods_id=kwargs.get("goods_id"),
                    shop_type=kwargs.get("shop_type"),
                    request_timeout_seconds=kwargs.get("request_timeout_seconds"),
                    app_key=getattr(args, "app_key", None),
                    app_secret=getattr(args, "app_secret", None),
                    api_url=None,
                ),
                shop_type=getattr(args, "shop_type", "1688"),
                request_timeout_seconds=args.timeout,
                limit=limit,
                )

        if not products:
            print("No products found.")
            exit(0)
        print(f"Found {len(products)} products. Starting interactive console...")
        console = SearchResultConsole(products)
        console.cmdloop()