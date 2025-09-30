import time
import hashlib
import requests
import json
import argparse
import os
from typing import List
import webbrowser
import tempfile

APP_KEY = os.getenv("APP_KEY", "56832_68d09f0d2a2c6")
APP_SECRET = os.getenv("APP_SECRET", "eEtXGkyf9HFIsZ2i!ZOv")

API_URL = os.getenv("API_URL", "https://apiwww.rakumart.com/open/goods/keywordsSearch")
DETAIL_API_URL = os.getenv("DETAIL_API_URL", "https://apiwww.rakumart.com/open/goods/detail")
IMAGE_ID_API_URL = os.getenv("IMAGE_ID_API_URL", "https://apiwww.rakumart.com/open/goods/getImageId")
LOGISTICS_API_URL = os.getenv("LOGISTICS_API_URL", "https://apiwww.rakumart.com/open/currentUsefulLogistics")
TAGS_API_URL = os.getenv("TAGS_API_URL", "https://apiwww.rakumart.com/open/currentUsefulTags")
CREATE_ORDER_API_URL = os.getenv("CREATE_ORDER_API_URL", "https://apiwww.rakumart.com/open/createOrder")
UPDATE_ORDER_STATUS_API_URL = os.getenv("UPDATE_ORDER_STATUS_API_URL", "https://apiwww.rakumart.com/open/updateOrderStatus")
CANCEL_ORDER_API_URL = os.getenv("CANCEL_ORDER_API_URL", "https://apiwww.rakumart.com/open/cancelOrder")
ORDER_LIST_API_URL = os.getenv("ORDER_LIST_API_URL", "https://apiwww.rakumart.com/open/orderList")
ORDER_DETAIL_API_URL = os.getenv("ORDER_DETAIL_API_URL", "https://apiwww.rakumart.com/open/orderDetail")
STOCK_LIST_API_URL = os.getenv("STOCK_LIST_API_URL", "https://apiwww.rakumart.com/open/stockList")
CREATE_PORDER_API_URL = os.getenv("CREATE_PORDER_API_URL", "https://apiwww.rakumart.com/open/createPorder")
UPDATE_PORDER_STATUS_API_URL = os.getenv("UPDATE_PORDER_STATUS_API_URL", "https://apiwww.rakumart.com/open/updatePorderStatus")
CANCEL_PORDER_API_URL = os.getenv("CANCEL_PORDER_API_URL", "https://apiwww.rakumart.com/open/cancelPorder")
PORDER_LIST_API_URL = os.getenv("PORDER_LIST_API_URL", "https://apiwww.rakumart.com/open/porderList")
PORDER_DETAIL_API_URL = os.getenv("PORDER_DETAIL_API_URL", "https://apiwww.rakumart.com/open/porderDetail")
LOGISTICS_TRACK_API_URL = os.getenv("LOGISTICS_TRACK_API_URL", "https://apiwww.rakumart.com/open/logisticsTrack")


def generate_sign(app_key: str, app_secret: str, timestamp: str) -> str:
    """
    Generate MD5 sign = md5(app_key + app_secret + timestamp)
    """
    raw_str = app_key + app_secret + timestamp
    return hashlib.md5(raw_str.encode("utf-8")).hexdigest()


def search_products(
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    shop_type: str = "1688",
    price_min: str | None = None,
    price_max: str | None = None,
    order_key: str | None = None,
    order_value: str | None = None,
    request_timeout_seconds: int = 15,
    app_key: str | None = None,
    app_secret: str | None = None,
    api_url: str | None = None,
) -> List[dict]:
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
    return products


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
    parser = argparse.ArgumentParser(description="Search products and fetch product details via API")
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
    # Detail enrichment controls
    search_parser.add_argument("--with-detail", dest="with_detail", action="store_true", default=True, help="Also fetch detail (images, description) for results [default]")
    search_parser.add_argument("--no-detail", dest="with_detail", action="store_false", help="Do not fetch detail for results")
    search_parser.add_argument("--detail-limit", type=int, default=5, help="Max number of items to enrich with detail (default: 5)")
    search_parser.add_argument("--api-url", type=str, help="Override search API URL")
    search_parser.add_argument("--app-key", type=str, help="Override APP_KEY for this call")
    search_parser.add_argument("--app-secret", type=str, help="Override APP_SECRET for this call")
    search_parser.add_argument("--verbose", action="store_true", help="Print request payload and endpoint")

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

    # GUI subcommand
    gui_parser = subparsers.add_parser("gui", help="Open a simple GUI to search and view details")
    gui_parser.add_argument("--shop-type", type=str, default="1688", help="Shop type (default: 1688)")
    gui_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds (default: 15)")
    gui_parser.add_argument("--detail-limit", type=int, default=5, help="Max items to enrich with detail when listing")

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
            request_timeout_seconds=args.timeout,
            shop_type=getattr(args, "shop_type", "1688"),
            app_key=getattr(args, "app_key", None),
            app_secret=getattr(args, "app_secret", None),
            api_url=getattr(args, "api_url", None),
        )

        # Optionally enrich with detail for first N items
        if getattr(args, "with_detail", True) and products:
            limit = max(0, int(getattr(args, "detail_limit", 0)))
            num_to_enrich = len(products) if limit == 0 else min(limit, len(products))
            for idx in range(num_to_enrich):
                item = products[idx]
                goods_id = str(item.get("goodsId", ""))
                shop_type_val = item.get("shopType", getattr(args, "shop_type", "1688"))
                if not goods_id:
                    continue
                detail = get_product_detail(
                    goods_id=goods_id,
                    shop_type=shop_type_val,
                    request_timeout_seconds=args.timeout,
                    app_key=getattr(args, "app_key", None),
                    app_secret=getattr(args, "app_secret", None),
                    api_url=None,
                )
                if detail:
                    # Attach without overwriting original basic fields
                    item["detailImages"] = detail.get("images", [])
                    item["detailDescription"] = detail.get("description", "")

        print(f" Found {len(products)} products for keyword '{args.keyword}':\n")
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
    elif args.command == "gui":
        try:
            import tkinter as tk
            from tkinter import ttk, messagebox
        except ImportError:
            print(" Tkinter is not available in this Python installation.")
            raise SystemExit(1)

        root = tk.Tk()
        root.title("1688 商品検索")
        root.geometry("1200x800")

        # Top controls
        controls = ttk.Frame(root)
        controls.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(controls, text="キーワード:").pack(side=tk.LEFT)
        keyword_var = tk.StringVar(value="laptop")
        keyword_entry = ttk.Entry(controls, textvariable=keyword_var, width=40)
        keyword_entry.pack(side=tk.LEFT, padx=6)

        page_var = tk.IntVar(value=1)
        size_var = tk.IntVar(value=10)
        ttk.Label(controls, text="ページ:").pack(side=tk.LEFT)
        ttk.Entry(controls, textvariable=page_var, width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(controls, text="サイズ:").pack(side=tk.LEFT)
        ttk.Entry(controls, textvariable=size_var, width=5).pack(side=tk.LEFT, padx=4)

        enrich_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="詳細取得", variable=enrich_var).pack(side=tk.LEFT, padx=8)

        def do_search():
            try:
                products = search_products(
                    keyword_var.get().strip(),
                    page=page_var.get(),
                    page_size=size_var.get(),
                    request_timeout_seconds=args.timeout,
                    shop_type=args.shop_type,
                )
            except Exception as e:
                messagebox.showerror("エラー", f"検索に失敗しました: {e}")
                return

            # Optionally enrich ALL results (not just first N)
            if enrich_var.get():
                for idx, item in enumerate(products):
                    gid = str(item.get("goodsId", ""))
                    if not gid:
                        continue
                    detail = get_product_detail(gid, shop_type=args.shop_type, request_timeout_seconds=args.timeout)
                    if detail:
                        item["detailImages"] = detail.get("images", [])
                        item["detailDescription"] = detail.get("description", "")

            # Populate list
            for row in tree.get_children():
                tree.delete(row)
            for item in products:
                shop_info = item.get("shopInfo", {})
                shop_name = shop_info.get("shopName", "") if isinstance(shop_info, dict) else ""
                tree.insert("", tk.END, iid=str(item.get("goodsId", "")), values=(
                    item.get("goodsId", ""),
                    item.get("titleC", ""),
                    item.get("titleT", ""),
                    item.get("goodsPrice", ""),
                    item.get("monthSold", ""),
                    shop_name,
                ))

            # Store for selection
            nonlocal_data.clear()
            for p in products:
                nonlocal_data[str(p.get("goodsId", ""))] = p

        ttk.Button(controls, text="検索", command=do_search).pack(side=tk.LEFT, padx=6)

        # Results table
        cols = ("goodsId", "titleC", "titleT", "price", "sold", "shopName")
        tree = ttk.Treeview(root, columns=cols, show="headings")
        tree.heading("goodsId", text="商品ID")
        tree.heading("titleC", text="タイトル(中国語)")
        tree.heading("titleT", text="タイトル(日本語)")
        tree.heading("price", text="価格")
        tree.heading("sold", text="月販売数")
        tree.heading("shopName", text="ショップ名")
        tree.column("goodsId", width=120)
        tree.column("titleC", width=300)
        tree.column("titleT", width=300)
        tree.column("price", width=80)
        tree.column("sold", width=100)
        tree.column("shopName", width=200)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Per-row actions
        actions = ttk.Frame(root)
        actions.pack(fill=tk.X, padx=8, pady=8)
        def open_images():
            sel = tree.selection()
            if not sel:
                return
            item = nonlocal_data.get(sel[0])
            if not item:
                return
            for url in item.get("detailImages", []):
                try:
                    webbrowser.open(url)
                except Exception:
                    pass

        def open_description():
            sel = tree.selection()
            if not sel:
                return
            item = nonlocal_data.get(sel[0])
            if not item:
                return
            html = item.get("detailDescription") or "<p>No description</p>"
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as f:
                    f.write(html)
                    path = f.name
                webbrowser.open(path)
            except Exception as e:
                messagebox.showerror("エラー", f"説明の表示に失敗しました: {e}")

        ttk.Button(actions, text="画像を開く", command=open_images).pack(side=tk.LEFT)
        ttk.Button(actions, text="説明を開く", command=open_description).pack(side=tk.LEFT, padx=8)

        # In-memory store
        nonlocal_data = {}

        root.mainloop()