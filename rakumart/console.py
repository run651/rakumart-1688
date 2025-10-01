from typing import List, Any
from .models import Product
import time
import json
import cmd


class SearchResultConsole(cmd.Cmd):
    """Interactive console for displaying and managing search results."""

    intro = "=== Search Results Console ===\nType 'help' for available commands or 'quit' to exit."
    prompt = "search> "

    def __init__(self, products: List[Product]):
        super().__init__()
        self.products = products
        self.current_page = 0
        self.page_size = 10
        self.filtered_products = products.copy()
        self.sort_key = None
        self.sort_reverse = False

    def do_list(self, args):
        """List products with pagination. Usage: list [page] [size]"""
        try:
            parts = args.split()
            if len(parts) >= 1:
                self.current_page = int(parts[0]) - 1
            if len(parts) >= 2:
                self.page_size = int(parts[1])
        except ValueError:
            print("Invalid page or size. Using defaults.")

        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_products = self.filtered_products[start_idx:end_idx]

        print(f"\n=== Products (Page {self.current_page + 1}, Showing {len(page_products)} items) ===")
        print(f"Total products: {len(self.filtered_products)}")
        print("-" * 80)

        for i, product in enumerate(page_products, start_idx + 1):
            self._display_product_summary(product, i)

    def do_show(self, args):
        """Show detailed information for a specific product. Usage: show <index>"""
        try:
            index = int(args) - 1
            if 0 <= index < len(self.filtered_products):
                product = self.filtered_products[index]
                self._display_product_detail(product, index + 1)
            else:
                print(f"Invalid index. Available range: 1-{len(self.filtered_products)}")
        except ValueError:
            print("Please provide a valid product index.")

    def do_filter(self, args):
        """Filter products by field and value. Usage: filter <field> <value>"""
        if not args:
            print("Usage: filter <field> <value>")
            print("Available fields:", ", ".join(self._get_available_fields()))
            return

        parts = args.split(" ", 1)
        if len(parts) < 2:
            print("Usage: filter <field> <value>")
            return

        field, value = parts
        original_count = len(self.filtered_products)

        self.filtered_products = self.products.copy()
        self.filtered_products = [
            p for p in self.filtered_products
            if str(p.get(field, "")).lower().find(value.lower()) != -1
        ]

        print(f"Filtered by {field}='{value}': {len(self.filtered_products)}/{original_count} products")
        self.current_page = 0

    def do_clear(self, args):
        """Clear all filters and show all products."""
        self.filtered_products = self.products.copy()
        self.current_page = 0
        print(f"Cleared filters. Showing all {len(self.filtered_products)} products.")

    def do_sort(self, args):
        """Sort products by field. Usage: sort <field> [asc|desc]"""
        if not args:
            print("Usage: sort <field> [asc|desc]")
            print("Available fields:", ", ".join(self._get_available_fields()))
            return

        parts = args.split()
        field = parts[0]
        reverse = len(parts) > 1 and parts[1].lower() == "desc"

        try:
            self.filtered_products.sort(
                key=lambda p: self._get_sort_value(p, field),
                reverse=reverse
            )
            direction = "descending" if reverse else "ascending"
            print(f"Sorted by {field} ({direction})")
        except Exception as e:
            print(f"Error sorting: {e}")

    def do_search(self, args):
        """Search within current results. Usage: search <query>"""
        if not args:
            print("Usage: search <query>")
            return

        query = args.lower()
        matches = []
        for i, product in enumerate(self.filtered_products):
            searchable_text = " ".join([
                str(product.get("titleC", "")),
                str(product.get("titleT", "")),
                str(product.get("goodsId", "")),
                str(product.get("shopInfo", {}).get("shopName", ""))
            ]).lower()
            if query in searchable_text:
                matches.append((i, product))

        if matches:
            print(f"Found {len(matches)} matches:")
            for i, (idx, product) in enumerate(matches[:10], 1):
                print(f"{i:2d}. [{idx+1}] {product.get('titleC', 'No title')[:50]}...")
        else:
            print("No matches found.")

    def do_stats(self, args):
        """Show statistics about current results."""
        if not self.filtered_products:
            print("No products to analyze.")
            return

        print(f"\n=== Statistics ===")
        print(f"Total products: {len(self.filtered_products)}")
        prices = [float(p.get("goodsPrice", 0)) for p in self.filtered_products if p.get("goodsPrice")]
        if prices:
            print(f"Price range: {min(prices):.2f} - {max(prices):.2f} RMB")
            print(f"Average price: {sum(prices)/len(prices):.2f} RMB")
        categories = {}
        for p in self.filtered_products:
            cat_id = p.get("topCategoryId")
            if cat_id:
                categories[cat_id] = categories.get(cat_id, 0) + 1
        if categories:
            print(f"Top categories:")
            for cat_id, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  Category {cat_id}: {count} products")

    def do_export(self, args):
        """Export current results to JSON file. Usage: export <filename>"""
        if not args:
            filename = f"search_results_{int(time.time())}.json"
        else:
            filename = args
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.filtered_products, f, ensure_ascii=False, indent=2)
            print(f"Exported {len(self.filtered_products)} products to {filename}")
        except Exception as e:
            print(f"Error exporting: {e}")

    def do_help(self, args):
        """Show available commands."""
        print("\nAvailable commands:")
        print("  list [page] [size]  - List products with pagination")
        print("  show <index>        - Show detailed product information")
        print("  filter <field> <value> - Filter products by field")
        print("  clear               - Clear all filters")
        print("  sort <field> [asc|desc] - Sort products by field")
        print("  search <query>      - Search within current results")
        print("  stats               - Show statistics")
        print("  export [filename]   - Export results to JSON")
        print("  quit                - Exit console")
        print(f"\nCurrent: {len(self.filtered_products)} products, page {self.current_page + 1}")

    def do_quit(self, args):
        """Exit the console."""
        print("Goodbye!")
        return True

    def _display_product_summary(self, product: dict, index: int):
        title = product.get("titleC", "No title")[:50]
        price = product.get("goodsPrice", "N/A")
        sold = product.get("monthSold", 0)
        shop_info = product.get("shopInfo", {})
        shop_name = shop_info.get("shopName", "Unknown")[:30] if isinstance(shop_info, dict) else "Unknown"
        print(f"{index:3d}. {title}...")
        print(f"     Price: {price} RMB | Sold: {sold} | Shop: {shop_name}")
        print()

    def _display_product_detail(self, product: dict, index: int):
        print(f"\n=== Product #{index} Details ===")
        print(f"ID: {product.get('goodsId', 'N/A')}")
        print(f"Chinese Title: {product.get('titleC', 'N/A')}")
        print(f"Japanese Title: {product.get('titleT', 'N/A')}")
        print(f"Price: {product.get('goodsPrice', 'N/A')} RMB")
        print(f"Monthly Sold: {product.get('monthSold', 'N/A')}")
        print(f"Repurchase Rate: {product.get('repurchaseRate', 'N/A')}%")
        print(f"Trade Score: {product.get('tradeScore', 'N/A')}")
        shop_info = product.get("shopInfo", {})
        if isinstance(shop_info, dict):
            print(f"Shop: {shop_info.get('shopName', 'N/A')}")
            print(f"Address: {shop_info.get('address', 'N/A')}")
            print(f"Wangwang: {shop_info.get('wangwang', 'N/A')}")
        print(f"Category: {product.get('topCategoryId', 'N/A')} / {product.get('secondCategoryId', 'N/A')}")
        print(f"Created: {product.get('createDate', 'N/A')}")
        print(f"Modified: {product.get('modifyDate', 'N/A')}")
        detail_images = product.get("detailImages", [])
        if detail_images:
            print(f"Images: {len(detail_images)} available")
            for i, img_url in enumerate(detail_images[:3], 1):
                print(f"  {i}. {img_url}")
            if len(detail_images) > 3:
                print(f"  ... and {len(detail_images) - 3} more")

    def _get_available_fields(self) -> List[str]:
        fields = set()
        for product in self.products:
            fields.update(product.keys())
        return sorted(list(fields))

    def _get_sort_value(self, product: dict, field: str) -> Any:
        value = product.get(field)
        if isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value.lower()
        else:
            return str(value).lower()



