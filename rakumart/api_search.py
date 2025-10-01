from typing import List, Optional, Dict, Any
import time
import json
import requests
from .sign import md5_sign
from .http import safe_post_json
from .config import APP_KEY, APP_SECRET, API_URL, DETAIL_API_URL, IMAGE_ID_API_URL


def generate_sign(app_key: str, app_secret: str, timestamp: str) -> str:
    # Rakumart open API expects MD5(app_key + app_secret + timestamp)
    return md5_sign(app_key, app_secret, timestamp)


def search_products(
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    shop_type: str = "1688",
    price_min: Optional[str] = None,
    price_max: Optional[str] = None,
    order_key: Optional[str] = None,
    order_value: Optional[str] = None,
    categories: Optional[List[str]] = None,
    subcategories: Optional[List[str]] = None,
    sub_subcategories: Optional[List[str]] = None,
    max_length: Optional[float] = None,
    max_width: Optional[float] = None,
    max_height: Optional[float] = None,
    max_weight: Optional[float] = None,
    jpy_price_min: Optional[float] = None,
    jpy_price_max: Optional[float] = None,
    exchange_rate: float = 20.0,
    strict_mode: bool = False,
    min_inventory: Optional[int] = None,
    max_delivery_days: Optional[int] = None,
    max_shipping_fee: Optional[float] = None,
    request_timeout_seconds: int = 15,
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    api_url: Optional[str] = None,
    apply_filters_fn=None,
) -> List[dict]:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp) if resolved_app_key and resolved_app_secret else ""
    payload: Dict[str, Any] = {
        "app_key": resolved_app_key,
        "timestamp": timestamp,
        "sign": sign,
        "keywords": keyword,
        "shop_type": shop_type,
        "page": str(page),
        "pageSize": str(page_size),
    }
    if price_min is not None:
        payload["price_min"] = str(price_min)
    if price_max is not None:
        payload["price_max"] = str(price_max)
    if order_key is not None:
        payload["order_by[0][key]"] = order_key
    if order_value is not None:
        payload["order_by[0][value]"] = order_value
    if categories is not None:
        for i, category in enumerate(categories):
            payload[f"categories[{i}]"] = str(category)
    if subcategories is not None:
        for i, subcategory in enumerate(subcategories):
            payload[f"subcategories[{i}]"] = str(subcategory)
    if sub_subcategories is not None:
        for i, sub_subcategory in enumerate(sub_subcategories):
            payload[f"sub_subcategories[{i}]"] = str(sub_subcategory)

    if max_length is not None:
        payload["max_length"] = str(max_length)
    if max_width is not None:
        payload["max_width"] = str(max_width)
    if max_height is not None:
        payload["max_height"] = str(max_height)
    if min_inventory is not None:
        payload["min_inventory"] = str(min_inventory)
    if max_delivery_days is not None:
        payload["max_delivery_days"] = str(max_delivery_days)
    if max_shipping_fee is not None:
        payload["max_shipping_fee"] = str(max_shipping_fee)

    data = safe_post_json(resolved_api_url, data=payload, timeout=request_timeout_seconds)
    if data is None:
        return []

    if not data.get("success", False):
        print(" API request failed:", data)
        return []

    try:
        products = data["data"]["result"]["result"]
    except (KeyError, TypeError):
        print(" Unexpected API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return []

    if apply_filters_fn:
        products = apply_filters_fn(
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
            max_shipping_fee=max_shipping_fee,
        )

    return products


def get_product_detail(
    goods_id: str,
    shop_type: str = "1688",
    request_timeout_seconds: int = 15,
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    api_url: Optional[str] = None,
) -> Optional[dict]:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or DETAIL_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp) if resolved_app_key and resolved_app_secret else ""
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "shopType": (None, shop_type),
        "goodsId": (None, str(goods_id)),
    }
    data = safe_post_json(resolved_api_url, files=files, timeout=request_timeout_seconds)
    if data is None:
        return None
    if not data.get("success", False):
        print(" Detail API failed:", data)
        return None
    try:
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected detail API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


def get_image_id(
    image_base64: str,
    request_timeout_seconds: int = 15,
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    api_url: Optional[str] = None,
) -> Optional[dict]:
    timestamp = str(int(time.time()))
    resolved_app_key = app_key or APP_KEY
    resolved_app_secret = app_secret or APP_SECRET
    resolved_api_url = api_url or IMAGE_ID_API_URL
    sign = generate_sign(resolved_app_key, resolved_app_secret, timestamp) if resolved_app_key and resolved_app_secret else ""
    files = {
        "app_key": (None, resolved_app_key),
        "timestamp": (None, timestamp),
        "sign": (None, sign),
        "imageBase64": (None, image_base64),
    }
    data = safe_post_json(resolved_api_url, files=files, timeout=request_timeout_seconds)
    if data is None:
        return None
    if not data.get("success", False):
        print(" Image ID API failed:", data)
        return None
    try:
        return data["data"]
    except (KeyError, TypeError):
        print(" Unexpected image ID API response structure:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None


