from typing import List


def run_gui(shop_type: str = "1688", timeout: int = 15, detail_limit: int = 5) -> None:
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print(" Tkinter is not available in this Python installation.")
        raise SystemExit(1)

    import webbrowser
    import tempfile

    from .api_search import search_products, get_product_detail
    from .db import save_products_to_db, reset_products_clean_table, fix_products_clean_schema
    from .enrich import enrich_products_with_detail
    from .product_optimizer import update_product_names_in_db, get_products_needing_optimization, ProductNameOptimizer

    root = tk.Tk()
    root.title("1688 商品検索")
    root.geometry("1200x800")

    controls = ttk.Frame(root)
    controls.pack(fill=tk.X, padx=8, pady=8)

    basic_frame = ttk.Frame(controls)
    basic_frame.pack(fill=tk.X, pady=4)

    ttk.Label(basic_frame, text="キーワード:").pack(side=tk.LEFT)
    keyword_var = tk.StringVar(value="laptop")
    keyword_entry = ttk.Entry(basic_frame, textvariable=keyword_var, width=30)
    keyword_entry.pack(side=tk.LEFT, padx=6)

    page_var = tk.IntVar(value=1)
    size_var = tk.IntVar(value=10)
    ttk.Label(basic_frame, text="ページ:").pack(side=tk.LEFT)
    ttk.Entry(basic_frame, textvariable=page_var, width=5).pack(side=tk.LEFT, padx=4)
    ttk.Label(basic_frame, text="サイズ:").pack(side=tk.LEFT)
    ttk.Entry(basic_frame, textvariable=size_var, width=5).pack(side=tk.LEFT, padx=4)

    enrich_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(basic_frame, text="詳細取得", variable=enrich_var).pack(side=tk.LEFT, padx=8)

    filter_frame = ttk.LabelFrame(controls, text="フィルター")
    filter_frame.pack(fill=tk.X, pady=4)

    price_frame = ttk.Frame(filter_frame)
    price_frame.pack(fill=tk.X, pady=2)
    ttk.Label(price_frame, text="価格範囲(RMB):").pack(side=tk.LEFT)
    price_min_var = tk.StringVar()
    price_max_var = tk.StringVar()
    ttk.Entry(price_frame, textvariable=price_min_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(price_frame, text="〜").pack(side=tk.LEFT)
    ttk.Entry(price_frame, textvariable=price_max_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(price_frame, text="RMB").pack(side=tk.LEFT, padx=2)

    jpy_price_frame = ttk.Frame(filter_frame)
    jpy_price_frame.pack(fill=tk.X, pady=2)
    ttk.Label(jpy_price_frame, text="価格範囲(JPY):").pack(side=tk.LEFT)
    jpy_price_min_var = tk.StringVar()
    jpy_price_max_var = tk.StringVar()
    exchange_rate_var = tk.StringVar(value="20.0")
    ttk.Entry(jpy_price_frame, textvariable=jpy_price_min_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(jpy_price_frame, text="〜").pack(side=tk.LEFT)
    ttk.Entry(jpy_price_frame, textvariable=jpy_price_max_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(jpy_price_frame, text="JPY").pack(side=tk.LEFT, padx=2)
    ttk.Label(jpy_price_frame, text="(為替:").pack(side=tk.LEFT, padx=(10,0))
    ttk.Entry(jpy_price_frame, textvariable=exchange_rate_var, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Label(jpy_price_frame, text=")").pack(side=tk.LEFT, padx=2)

    size_frame = ttk.Frame(filter_frame)
    size_frame.pack(fill=tk.X, pady=2)
    ttk.Label(size_frame, text="最大サイズ:").pack(side=tk.LEFT)
    max_length_var = tk.StringVar()
    max_width_var = tk.StringVar()
    max_height_var = tk.StringVar()
    ttk.Label(size_frame, text="長:").pack(side=tk.LEFT, padx=2)
    ttk.Entry(size_frame, textvariable=max_length_var, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Label(size_frame, text="幅:").pack(side=tk.LEFT, padx=2)
    ttk.Entry(size_frame, textvariable=max_width_var, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Label(size_frame, text="高:").pack(side=tk.LEFT, padx=2)
    ttk.Entry(size_frame, textvariable=max_height_var, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Label(size_frame, text="cm").pack(side=tk.LEFT, padx=2)

    weight_frame = ttk.Frame(filter_frame)
    weight_frame.pack(fill=tk.X, pady=2)
    ttk.Label(weight_frame, text="最大重量:").pack(side=tk.LEFT)
    max_weight_var = tk.StringVar()
    ttk.Entry(weight_frame, textvariable=max_weight_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(weight_frame, text="g").pack(side=tk.LEFT, padx=2)

    other_frame = ttk.Frame(filter_frame)
    other_frame.pack(fill=tk.X, pady=2)
    ttk.Label(other_frame, text="最小在庫:").pack(side=tk.LEFT)
    min_inventory_var = tk.StringVar()
    ttk.Entry(other_frame, textvariable=min_inventory_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(other_frame, text="最大配送日数:").pack(side=tk.LEFT, padx=(10,0))
    max_delivery_var = tk.StringVar()
    ttk.Entry(other_frame, textvariable=max_delivery_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(other_frame, text="日").pack(side=tk.LEFT, padx=2)
    ttk.Label(other_frame, text="最大送料:").pack(side=tk.LEFT, padx=(10,0))
    max_shipping_var = tk.StringVar()
    ttk.Entry(other_frame, textvariable=max_shipping_var, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(other_frame, text="RMB").pack(side=tk.LEFT, padx=2)

    strict_mode_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(filter_frame, text="厳密フィルタリング (すべての条件を満たす商品のみ)", variable=strict_mode_var).pack(pady=4)

    def do_search():
        try:
            price_min = price_min_var.get().strip() or None
            price_max = price_max_var.get().strip() or None
            jpy_price_min = float(jpy_price_min_var.get()) if jpy_price_min_var.get().strip() else None
            jpy_price_max = float(jpy_price_max_var.get()) if jpy_price_max_var.get().strip() else None
            exchange_rate = float(exchange_rate_var.get()) if exchange_rate_var.get().strip() else 20.0
            strict_mode = strict_mode_var.get()
            max_length = float(max_length_var.get()) if max_length_var.get().strip() else None
            max_width = float(max_width_var.get()) if max_width_var.get().strip() else None
            max_height = float(max_height_var.get()) if max_height_var.get().strip() else None
            max_weight = float(max_weight_var.get()) if max_weight_var.get().strip() else None
            min_inventory = int(min_inventory_var.get()) if min_inventory_var.get().strip() else None
            max_delivery_days = int(max_delivery_var.get()) if max_delivery_var.get().strip() else None
            max_shipping_fee = float(max_shipping_var.get()) if max_shipping_var.get().strip() else None

            products = search_products(
                keyword_var.get().strip(),
                page=page_var.get(),
                page_size=size_var.get(),
                price_min=price_min,
                price_max=price_max,
                jpy_price_min=jpy_price_min,
                jpy_price_max=jpy_price_max,
                exchange_rate=exchange_rate,
                strict_mode=strict_mode,
                max_length=max_length,
                max_width=max_width,
                max_height=max_height,
                max_weight=max_weight,
                min_inventory=min_inventory,
                max_delivery_days=max_delivery_days,
                max_shipping_fee=max_shipping_fee,
                request_timeout_seconds=timeout,
                shop_type=shop_type,
            )
        except Exception as e:
            messagebox.showerror("エラー", f"検索に失敗しました: {e}")
            return

        if enrich_var.get():
            enrich_products_with_detail(
                products,
                get_detail_fn=lambda **kwargs: get_product_detail(
                    goods_id=kwargs.get("goods_id"),
                    shop_type=kwargs.get("shop_type"),
                    request_timeout_seconds=kwargs.get("request_timeout_seconds"),
                ),
                shop_type=shop_type,
                request_timeout_seconds=timeout,
                limit=0,
            )

        for row in tree.get_children():
            tree.delete(row)
        for item in products:
            shop_info = item.get("shopInfo", {})
            shop_name = shop_info.get("shopName", "") if isinstance(shop_info, dict) else ""
            repurchase_rate = f"{item.get('repurchaseRate', 'N/A')}%"
            trade_score = item.get('tradeScore', 'N/A')
            category = f"{item.get('topCategoryId', 'N/A')}/{item.get('secondCategoryId', 'N/A')}"
            create_date = item.get('createDate', 'N/A')
            if create_date != 'N/A' and len(create_date) > 10:
                create_date = create_date[:10]
            tree.insert("", tk.END, iid=str(item.get("goodsId", "")), values=(
                item.get("goodsId", ""),
                item.get("titleC", ""),
                item.get("titleT", ""),
                item.get("goodsPrice", ""),
                item.get("monthSold", ""),
                shop_name,
                repurchase_rate,
                trade_score,
                category,
                create_date,
            ))

        nonlocal_data.clear()
        for p in products:
            nonlocal_data[str(p.get("goodsId", ""))] = p

        # Auto-save to PostgreSQL after search
        try:
            kw = keyword_var.get().strip() or None
            current = list(nonlocal_data.values())
            saved = save_products_to_db(current, keyword=kw)
            from tkinter import messagebox as _mb
            _mb.showinfo("保存完了", f"PostgreSQL に {saved} 件保存しました。")
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg and "catch_copy" in error_msg:
                # Try to fix the schema and retry
                try:
                    fix_products_clean_schema()
                    saved = save_products_to_db(current, keyword=kw)
                    from tkinter import messagebox as _mb
                    _mb.showinfo("保存完了", f"スキーマを修正してPostgreSQL に {saved} 件保存しました。")
                except Exception as e2:
                    from tkinter import messagebox as _mb
                    _mb.showerror("エラー", f"スキーマ修正後もPostgreSQL への保存に失敗しました: {e2}")
            else:
                from tkinter import messagebox as _mb
                _mb.showerror("エラー", f"PostgreSQL への保存に失敗しました: {e}")

    ttk.Button(controls, text="検索", command=do_search).pack(side=tk.LEFT, padx=6)

    control_frame2 = ttk.Frame(controls)
    control_frame2.pack(fill=tk.X, pady=4)

    ttk.Label(control_frame2, text="フィルター:").pack(side=tk.LEFT)
    filter_var = tk.StringVar()
    filter_entry = ttk.Entry(control_frame2, textvariable=filter_var, width=20)
    filter_entry.pack(side=tk.LEFT, padx=4)

    def apply_filter():
        filter_text = filter_var.get().lower()
        for item in tree.get_children():
            values = tree.item(item)['values']
            search_text = f"{values[1]} {values[2]} {values[5]}".lower()
            if filter_text in search_text or not filter_text:
                tree.reattach(item, "", "end")
            else:
                tree.detach(item)

    ttk.Button(control_frame2, text="フィルター適用", command=apply_filter).pack(side=tk.LEFT, padx=4)
    ttk.Button(control_frame2, text="クリア", command=lambda: [filter_var.set(""), apply_filter()]).pack(side=tk.LEFT, padx=4)

    ttk.Label(control_frame2, text="ソート:").pack(side=tk.LEFT, padx=(20, 4))
    sort_var = tk.StringVar(value="goodsId")
    sort_combo = ttk.Combobox(control_frame2, textvariable=sort_var, width=15, state="readonly")
    sort_combo['values'] = ("goodsId", "titleC", "titleT", "price", "sold", "shopName", "repurchaseRate", "tradeScore", "category", "createDate")
    sort_combo.pack(side=tk.LEFT, padx=4)

    sort_order_var = tk.StringVar(value="asc")
    sort_order_combo = ttk.Combobox(control_frame2, textvariable=sort_order_var, width=8, state="readonly")
    sort_order_combo['values'] = ("asc", "desc")
    sort_order_combo.pack(side=tk.LEFT, padx=4)

    def apply_sort():
        items = []
        for item in tree.get_children():
            values = tree.item(item)['values']
            items.append((item, values))
        sort_col = sort_var.get()
        col_index = cols.index(sort_col) if sort_col in cols else 0
        reverse = sort_order_var.get() == "desc"
        try:
            items.sort(key=lambda x: x[1][col_index], reverse=reverse)
        except Exception:
            items.sort(key=lambda x: str(x[1][col_index]), reverse=reverse)
        for i, (item, values) in enumerate(items):
            tree.move(item, "", i)

    ttk.Button(control_frame2, text="ソート適用", command=apply_sort).pack(side=tk.LEFT, padx=4)

    stats_frame = ttk.LabelFrame(controls, text="統計情報")
    stats_frame.pack(fill=tk.X, pady=4)

    stats_text = tk.Text(stats_frame, height=3, wrap=tk.WORD)
    stats_text.pack(fill=tk.X, padx=4, pady=4)

    def update_stats():
        stats_text.delete(1.0, tk.END)
        visible_items = [item for item in tree.get_children() if tree.exists(item)]
        total_items = len(visible_items)
        if total_items == 0:
            stats_text.insert(tk.END, "表示中のアイテムがありません")
            return
        prices: List[float] = []
        sold_counts: List[int] = []
        categories: dict = {}
        shops: dict = {}
        for item in visible_items:
            values = tree.item(item)['values']
            try:
                price = float(values[3]) if values[3] and values[3] != 'N/A' else 0
                if price > 0:
                    prices.append(price)
            except Exception:
                pass
            try:
                sold = int(values[4]) if values[4] and values[4] != 'N/A' else 0
                sold_counts.append(sold)
            except Exception:
                pass
            category = values[8]
            shop = values[5]
            if category != 'N/A':
                categories[category] = categories.get(category, 0) + 1
            if shop and shop != 'N/A':
                shops[shop] = shops.get(shop, 0) + 1
        stats_info = f"表示中: {total_items} アイテム\n"
        if prices:
            stats_info += f"価格範囲: {min(prices):.2f} - {max(prices):.2f} RMB (平均: {sum(prices)/len(prices):.2f} RMB)\n"
        if sold_counts:
            stats_info += f"販売数範囲: {min(sold_counts)} - {max(sold_counts)} (平均: {sum(sold_counts)/len(sold_counts):.1f})\n"
        if categories:
            top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
            stats_info += f"主要カテゴリ: {', '.join([f'{cat}({count})' for cat, count in top_categories])}\n"
        if shops:
            top_shops = sorted(shops.items(), key=lambda x: x[1], reverse=True)[:3]
            stats_info += f"主要ショップ: {', '.join([f'{shop}({count})' for shop, count in top_shops])}"
        stats_text.insert(tk.END, stats_info)

    def enhanced_do_search():
        do_search()
        update_stats()

    for widget in controls.winfo_children():
        if isinstance(widget, ttk.Button) and widget.cget('text') == '検索':
            widget.configure(command=enhanced_do_search)
            break

    cols = ("goodsId", "titleC", "titleT", "price", "sold", "shopName", "repurchaseRate", "tradeScore", "category", "createDate")
    tree = ttk.Treeview(root, columns=cols, show="headings")
    tree.heading("goodsId", text="商品ID")
    tree.heading("titleC", text="タイトル(中国語)")
    tree.heading("titleT", text="タイトル(日本語)")
    tree.heading("price", text="価格")
    tree.heading("sold", text="月販売数")
    tree.heading("shopName", text="ショップ名")
    tree.heading("repurchaseRate", text="再購入率")
    tree.heading("tradeScore", text="評価")
    tree.heading("category", text="カテゴリ")
    tree.heading("createDate", text="作成日")

    tree.column("goodsId", width=120)
    tree.column("titleC", width=250)
    tree.column("titleT", width=250)
    tree.column("price", width=80)
    tree.column("sold", width=80)
    tree.column("shopName", width=150)
    tree.column("repurchaseRate", width=80)
    tree.column("tradeScore", width=60)
    tree.column("category", width=80)
    tree.column("createDate", width=100)

    v_scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
    h_scrollbar = ttk.Scrollbar(root, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

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

    def show_detailed_info():
        sel = tree.selection()
        if not sel:
            return
        item = nonlocal_data.get(sel[0])
        if not item:
            return
        # Fetch normalized detail if not present
        if not item.get("detailNormalized"):
            try:
                detail = get_product_detail(
                    goods_id=str(item.get("goodsId")),
                    shop_type=shop_type,
                    request_timeout_seconds=timeout,
                    normalize=True,
                )
                if detail:
                    item["detailNormalized"] = detail
                    item["detailImages"] = detail.get("images", [])
                    item["detailDescription"] = detail.get("description", "")
            except Exception as e:
                messagebox.showerror("エラー", f"詳細取得に失敗しました: {e}")
                return

        detail = item.get("detailNormalized") or {}
        win = tk.Toplevel(root)
        win.title(f"詳細: {item.get('goodsId', '')}")
        win.geometry("700x600")
        text = tk.Text(win, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)

        # Compose a readable detailed summary
        text.insert(tk.END, f"fromUrl: {detail.get('fromUrl')}\n")
        text.insert(tk.END, f"fromPlatform: {detail.get('fromPlatform')}\n")
        text.insert(tk.END, f"shopId: {detail.get('shopId')}\n")
        text.insert(tk.END, f"shopName: {detail.get('shopName')}\n")
        text.insert(tk.END, f"goodsId: {detail.get('goodsId')}\n")
        text.insert(tk.END, f"titleC: {detail.get('titleC')}\n")
        text.insert(tk.END, f"titleT: {detail.get('titleT')}\n")
        text.insert(tk.END, f"address: {detail.get('address')}\n\n")

        gi = detail.get("goodsInfo", {}) if isinstance(detail.get("goodsInfo"), dict) else {}
        text.insert(tk.END, "[goodsInfo]\n")
        text.insert(tk.END, f" unit: {gi.get('unit')}\n")
        text.insert(tk.END, f" minOrderQuantity: {gi.get('minOrderQuantity')}\n")
        text.insert(tk.END, f" priceRangesType: {gi.get('priceRangesType')}\n")
        text.insert(tk.END, " priceRanges:\n")
        for pr in gi.get("priceRanges", []) or []:
            text.insert(tk.END, f"  - startQuantity={pr.get('startQuantity')} priceMin={pr.get('priceMin')} priceMax={pr.get('priceMax')}\n")
        text.insert(tk.END, "\n specification:\n")
        for sp in gi.get("specification", []) or []:
            text.insert(tk.END, f"  - {sp.get('keyC')} / {sp.get('keyT')}\n")
            vals = sp.get('valueC', []) or []
            if vals:
                text.insert(tk.END, "    valueC:\n")
                for v in vals:
                    text.insert(tk.END, f"      - {v.get('name')} {v.get('picUrl') or ''}\n")
            vals = sp.get('valueT', []) or []
            if vals:
                text.insert(tk.END, "    valueT:\n")
                for v in vals:
                    text.insert(tk.END, f"      - {v.get('name')} {v.get('picUrl') or ''}\n")
        text.insert(tk.END, "\n goodsInventory:\n")
        for inv in gi.get("goodsInventory", []) or []:
            text.insert(tk.END, f"  - keyC={inv.get('keyC')} keyT={inv.get('keyT')}\n")
            for label in ("valueC", "valueT"):
                entries = inv.get(label, []) or []
                if entries:
                    text.insert(tk.END, f"    {label}:\n")
                    for e in entries:
                        text.insert(tk.END, f"      - startQuantity={e.get('startQuantity')} price={e.get('price')} amountOnSale={e.get('amountOnSale')} skuId={e.get('skuId')} specId={e.get('specId')}\n")

        ttk.Button(win, text="閉じる", command=win.destroy).pack(pady=6)

    ttk.Button(actions, text="画像を開く", command=open_images).pack(side=tk.LEFT)
    ttk.Button(actions, text="説明を開く", command=open_description).pack(side=tk.LEFT, padx=8)
    ttk.Button(actions, text="詳細情報", command=show_detailed_info).pack(side=tk.LEFT, padx=8)

    def save_to_postgres():
        try:
            current_products = list(nonlocal_data.values())
            if not current_products:
                messagebox.showinfo("情報", "保存するデータがありません。先に検索してください。")
                return
            kw = keyword_var.get().strip() or None
            saved = save_products_to_db(current_products, keyword=kw)
            messagebox.showinfo("保存完了", f"PostgreSQL に {saved} 件保存しました。")
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg and "catch_copy" in error_msg:
                # Try to fix the schema and retry
                try:
                    fix_products_clean_schema()
                    saved = save_products_to_db(current_products, keyword=kw)
                    messagebox.showinfo("保存完了", f"スキーマを修正してPostgreSQL に {saved} 件保存しました。")
                except Exception as e2:
                    messagebox.showerror("エラー", f"スキーマ修正後も保存に失敗しました: {e2}")
            else:
                messagebox.showerror("エラー", f"保存に失敗しました: {e}")

    ttk.Button(actions, text="PostgreSQL に保存", command=save_to_postgres).pack(side=tk.LEFT, padx=8)

    def reset_and_use_clean_schema():
        try:
            if messagebox.askyesno("確認", "既存のテーブル(products, products_flat)を削除し、products_clean のみを作成しますか？ この操作は元に戻せません。"):
                reset_products_clean_table()
                messagebox.showinfo("完了", "products_clean を作成しました。以降の保存でクリーン表にも保存されます。")
        except Exception as e:
            messagebox.showerror("エラー", f"初期化に失敗しました: {e}")

    ttk.Button(actions, text="クリーンスキーマ初期化", command=reset_and_use_clean_schema).pack(side=tk.LEFT, padx=8)

    def fix_schema():
        try:
            fix_products_clean_schema()
            messagebox.showinfo("完了", "データベーススキーマを修正しました。")
        except Exception as e:
            messagebox.showerror("エラー", f"スキーマ修正に失敗しました: {e}")

    ttk.Button(actions, text="スキーマ修正", command=fix_schema).pack(side=tk.LEFT, padx=8)

    def optimize_product_names():
        """Optimize product names using OpenAI API"""
        try:
            # Show progress dialog
            progress_window = tk.Toplevel(root)
            progress_window.title("商品名最適化")
            progress_window.geometry("400x200")
            progress_window.transient(root)
            progress_window.grab_set()
            
            # Center the window
            progress_window.update_idletasks()
            x = (progress_window.winfo_screenwidth() // 2) - (400 // 2)
            y = (progress_window.winfo_screenheight() // 2) - (200 // 2)
            progress_window.geometry(f"400x200+{x}+{y}")
            
            tk.Label(progress_window, text="商品名を最適化中...", font=("Arial", 12)).pack(pady=20)
            
            progress_text = tk.Text(progress_window, height=8, width=50)
            progress_text.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
            
            def run_optimization():
                try:
                    progress_text.insert(tk.END, "商品を検索中...\n")
                    progress_window.update()
                    
                    # Get products that need optimization
                    products = get_products_needing_optimization(limit=50)  # Limit to 50 for GUI
                    
                    if not products:
                        progress_text.insert(tk.END, "最適化が必要な商品が見つかりませんでした。\n")
                        progress_window.update()
                        return
                    
                    progress_text.insert(tk.END, f"{len(products)}件の商品が見つかりました。\n")
                    progress_text.insert(tk.END, "OpenAI APIで最適化を開始します...\n")
                    progress_window.update()
                    
                    # Run optimization
                    result = update_product_names_in_db(limit=50)
                    
                    progress_text.insert(tk.END, f"\n最適化完了！\n")
                    progress_text.insert(tk.END, f"処理済み: {result['processed']}件\n")
                    progress_text.insert(tk.END, f"成功: {result['successful']}件\n")
                    progress_text.insert(tk.END, f"失敗: {result['failed']}件\n")
                    
                    if result['errors']:
                        progress_text.insert(tk.END, f"\nエラー:\n")
                        for error in result['errors'][:3]:  # Show first 3 errors
                            progress_text.insert(tk.END, f"- {error}\n")
                    
                    progress_window.update()
                    
                    # Show completion message
                    messagebox.showinfo("完了", f"商品名の最適化が完了しました！\n\n処理済み: {result['processed']}件\n成功: {result['successful']}件\n失敗: {result['failed']}件")
                    
                except Exception as e:
                    progress_text.insert(tk.END, f"エラーが発生しました: {e}\n")
                    progress_window.update()
                    messagebox.showerror("エラー", f"商品名の最適化に失敗しました: {e}")
                finally:
                    # Add close button
                    close_btn = tk.Button(progress_window, text="閉じる", command=progress_window.destroy)
                    close_btn.pack(pady=10)
            
            # Run optimization in a separate thread to avoid blocking GUI
            import threading
            thread = threading.Thread(target=run_optimization)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("エラー", f"商品名最適化の開始に失敗しました: {e}")

    ttk.Button(actions, text="商品名最適化", command=optimize_product_names).pack(side=tk.LEFT, padx=8)

    nonlocal_data: dict = {}

    root.mainloop()


