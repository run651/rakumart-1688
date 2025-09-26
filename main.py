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
        else:
            args = parser.parse_args(["search", *argv])

    if args.command == "search":
        if getattr(args, "verbose", False):
            print(" Using API:", args.api_url or API_URL)
        print(f"🔎 Searching for keyword: '{args.keyword}' (page={args.page}, page_size={args.page_size})")
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
        print(f"🔎 Fetching detail for goodsId={args.goods_id} (shopType={args.shop_type})")
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