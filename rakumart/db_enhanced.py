from typing import Iterable, Optional, Dict, Any, Set, List
import os
import json
import datetime as dt
from .openai_api import generate_marketing_text

# Optional .env loading
try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore
else:  # pragma: no cover
    try:
        load_dotenv()
    except Exception:
        pass

try:
    import psycopg2
    import psycopg2.extras
except Exception as exc:  # pragma: no cover
    psycopg2 = None  # type: ignore
    _import_error = exc
else:
    _import_error = None


def _get_dsn() -> Optional[str]:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("PGHOST")
    if not host:
        return None
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    dbname = os.getenv("PGDATABASE")
    port = os.getenv("PGPORT", "5432")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def _ensure_import() -> None:
    if psycopg2 is None:  # pragma: no cover
        raise RuntimeError(f"psycopg2 not available: {_import_error}")


def _to_numeric(value):
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value)
        import re
        s = re.sub(r"[^0-9.\-]", "", s)
        return float(s) if s else None
    except Exception:
        return None


def _sanitize_column_name(name: str) -> str:
    """Convert attribute name to valid PostgreSQL column name."""
    import re
    # Remove/replace invalid characters
    name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
    # Ensure it starts with letter or underscore
    if name and name[0].isdigit():
        name = f"attr_{name}"
    # Ensure it's not empty
    if not name:
        name = "unknown_attribute"
    return name.lower()


def _extract_attributes_from_detail(detail: Dict[str, Any]) -> Dict[str, str]:
    """Extract attributes from normalized product detail."""
    attrs = {}
    goods_info = detail.get("goodsInfo", {}) if isinstance(detail.get("goodsInfo"), dict) else {}
    
    # Extract from specification
    specs = goods_info.get("specification", []) or []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        key_t = spec.get("keyT") or spec.get("keyC")
        if not key_t:
            continue
        
        # Get values (prefer Japanese, fallback to Chinese)
        values = spec.get("valueT") or spec.get("valueC") or []
        if isinstance(values, list) and values:
            # Join multiple values with comma
            value_names = [v.get("name", "") for v in values if isinstance(v, dict) and v.get("name")]
            if value_names:
                attrs[key_t] = ", ".join(value_names)
    
    # Extract from detail section
    detail_rows = goods_info.get("detail", []) or []
    for row in detail_rows:
        if isinstance(row, dict):
            key_t = row.get("keyT") or row.get("keyC")
            value_t = row.get("valueT") or row.get("valueC")
            if key_t and value_t:
                attrs[key_t] = str(value_t)
    
    return attrs


def _ensure_attribute_columns(dsn: str, attributes: Set[str]) -> None:
    """Ensure all attribute columns exist in the table."""
    if not attributes:
        return
    
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            for attr in attributes:
                col_name = _sanitize_column_name(attr)
                try:
                    cur.execute(f"alter table products_enhanced add column if not exists \"{col_name}\" text;")
                except Exception as e:
                    print(f"Warning: Could not add column {col_name}: {e}")


# Base schema with core columns
BASE_SCHEMA_SQL = """
create table if not exists products_enhanced (
    id bigserial primary key,
    manufacturer_name text,
    brand text,
    product_id text,
    main_category text,
    middle_category text,
    sub_category text,
    product_name text,
    catch_copy text,
    product_description text,
    color text,
    size text,
    shape text,
    type text,
    features text,
    material_specifications text,
    packaging_size text,
    selling_unit text,
    total_weight_per_unit numeric,
    product_image jsonb,
    image_1 text,
    image_2 text,
    image_3 text,
    image_4 text,
    image_5 text,
    image_6 text,
    image_7 text,
    image_8 text,
    minimum_order_quantity int,
    monthly_sales int,
    in_stock_quantity int,
    product_reviews jsonb,
    wholesale_price numeric,
    wholesale_margin numeric,
    shipping_cost numeric,
    shipping_type text,
    delivery_time text,
    country_of_origin text,
    creation_date timestamptz,
    created_at timestamptz not null default now(),
    -- Enhanced fields
    from_url text,
    from_platform text,
    shop_id text,
    shop_name text,
    goods_id text,
    title_c text,
    title_t text,
    video_url text,
    address text,
    -- Price range info
    price_min numeric,
    price_max numeric,
    price_ranges_type text,
    price_ranges jsonb,
    -- Inventory info
    inventory_data jsonb,
    -- Raw detail for reference
    raw_detail jsonb
);
"""


def init_products_enhanced_table(*, dsn: Optional[str] = None) -> None:
    """Create the enhanced table with core columns."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute(BASE_SCHEMA_SQL)


def reset_products_enhanced_table(*, dsn: Optional[str] = None) -> None:
    """Drop and recreate the enhanced table."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists products_enhanced cascade;")
    init_products_enhanced_table(dsn=dsn_final)


def save_products_enhanced_to_db(
    products: Iterable[dict],
    *,
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    """Save products with enhanced detail and separate attribute columns."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")

    if create_table_if_missing:
        init_products_enhanced_table(dsn=dsn_final)

    # Collect all unique attributes across all products
    all_attributes: Set[str] = set()
    processed_products = []
    
    for p in products:
        # Extract basic info
        shop = p.get("shopInfo") if isinstance(p.get("shopInfo"), dict) else {}
        title_c = p.get("titleC")
        title_t = p.get("titleT")
        
        # Images
        detail_images = p.get("detailImages") if isinstance(p.get("detailImages"), list) else []
        main_img = p.get("imgUrl")
        images = [main_img] + detail_images if main_img else detail_images
        
        # Weight
        weight = None
        try:
            dims = p.get("dimensions") if isinstance(p.get("dimensions"), dict) else p.get("size")
            if isinstance(dims, dict):
                weight = _to_numeric(dims.get("weight"))
        except Exception:
            weight = None

        # Generate SEO text
        gen_name, gen_copy = generate_marketing_text(title_t or title_c)
        
        # Extract attributes from detail if available
        attributes = {}
        price_ranges = None
        inventory_data = None
        raw_detail = None
        
        # Check if this product has detailed info
        if "goodsInfo" in p or "fromUrl" in p:
            # This looks like normalized detail data
            raw_detail = p
            attributes = _extract_attributes_from_detail(p)
            all_attributes.update(attributes.keys())
            
            goods_info = p.get("goodsInfo", {}) if isinstance(p.get("goodsInfo"), dict) else {}
            price_ranges = goods_info.get("priceRanges")
            inventory_data = goods_info.get("goodsInventory")
        
        processed_products.append({
            "basic": {
                "manufacturer_name": shop.get("shopName"),
                "brand": None,
                "product_id": str(p.get("goodsId")) if p.get("goodsId") is not None else None,
                "main_category": str(p.get("topCategoryId")) if p.get("topCategoryId") is not None else None,
                "middle_category": str(p.get("secondCategoryId")) if p.get("secondCategoryId") is not None else None,
                "sub_category": None,
                "product_name": gen_name,
                "catch_copy": gen_copy,
                "product_description": p.get("detailDescription"),
                "color": None,  # Will be filled from attributes
                "size": None,   # Will be filled from attributes
                "shape": None,
                "type": p.get("shopType"),
                "features": None,
                "material_specifications": None,
                "packaging_size": None,
                "selling_unit": None,
                "total_weight_per_unit": weight,
                "product_image": json.dumps(images, ensure_ascii=False) if images else None,
                "image_1": images[0] if len(images) > 0 else None,
                "image_2": images[1] if len(images) > 1 else None,
                "image_3": images[2] if len(images) > 2 else None,
                "image_4": images[3] if len(images) > 3 else None,
                "image_5": images[4] if len(images) > 4 else None,
                "image_6": images[5] if len(images) > 5 else None,
                "image_7": images[6] if len(images) > 6 else None,
                "image_8": images[7] if len(images) > 7 else None,
                "minimum_order_quantity": None,
                "monthly_sales": int(p.get("monthSold")) if str(p.get("monthSold")).isdigit() else None,
                "in_stock_quantity": None,
                "product_reviews": None,
                "wholesale_price": _to_numeric(p.get("goodsPrice")),
                "wholesale_margin": None,
                "shipping_cost": None,
                "shipping_type": None,
                "delivery_time": None,
                "country_of_origin": None,
                "creation_date": None,
                "from_url": p.get("fromUrl"),
                "from_platform": p.get("fromPlatform"),
                "shop_id": str(p.get("shopId")) if p.get("shopId") is not None else None,
                "shop_name": p.get("shopName"),
                "goods_id": str(p.get("goodsId")) if p.get("goodsId") is not None else None,
                "title_c": p.get("titleC"),
                "title_t": p.get("titleT"),
                "video_url": p.get("video"),
                "address": p.get("address"),
                "price_min": None,
                "price_max": None,
                "price_ranges_type": None,
                "price_ranges": json.dumps(price_ranges, ensure_ascii=False) if price_ranges else None,
                "inventory_data": json.dumps(inventory_data, ensure_ascii=False) if inventory_data else None,
                "raw_detail": json.dumps(raw_detail, ensure_ascii=False) if raw_detail else None,
            },
            "attributes": attributes
        })

    # Ensure all attribute columns exist
    _ensure_attribute_columns(dsn_final, all_attributes)

    if not processed_products:
        return 0

    # Build dynamic insert query
    base_columns = [
        "manufacturer_name", "brand", "product_id", "main_category", "middle_category", "sub_category",
        "product_name", "catch_copy", "product_description", "color", "size", "shape", "type", "features",
        "material_specifications", "packaging_size", "selling_unit", "total_weight_per_unit",
        "product_image", "image_1", "image_2", "image_3", "image_4", "image_5", "image_6", "image_7", "image_8",
        "minimum_order_quantity", "monthly_sales", "in_stock_quantity", "product_reviews",
        "wholesale_price", "wholesale_margin", "shipping_cost", "shipping_type", "delivery_time", "country_of_origin",
        "creation_date", "from_url", "from_platform", "shop_id", "shop_name", "goods_id", "title_c", "title_t",
        "video_url", "address", "price_min", "price_max", "price_ranges_type", "price_ranges", "inventory_data", "raw_detail"
    ]
    
    # Add attribute columns
    attr_columns = [_sanitize_column_name(attr) for attr in sorted(all_attributes)]
    all_columns = base_columns + attr_columns
    
    # Build values template
    base_placeholders = ["%s"] * len(base_columns)
    attr_placeholders = ["%s"] * len(attr_columns)
    all_placeholders = base_placeholders + attr_placeholders
    
    # Prepare rows
    rows = []
    now = dt.datetime.utcnow()
    
    for product_data in processed_products:
        basic = product_data["basic"]
        attributes = product_data["attributes"]
        
        # Base values
        row_values = [
            basic["manufacturer_name"], basic["brand"], basic["product_id"], basic["main_category"], 
            basic["middle_category"], basic["sub_category"], basic["product_name"], basic["catch_copy"],
            basic["product_description"], basic["color"], basic["size"], basic["shape"], basic["type"],
            basic["features"], basic["material_specifications"], basic["packaging_size"], basic["selling_unit"],
            basic["total_weight_per_unit"], basic["product_image"], basic["image_1"], basic["image_2"],
            basic["image_3"], basic["image_4"], basic["image_5"], basic["image_6"], basic["image_7"], basic["image_8"],
            basic["minimum_order_quantity"], basic["monthly_sales"], basic["in_stock_quantity"], basic["product_reviews"],
            basic["wholesale_price"], basic["wholesale_margin"], basic["shipping_cost"], basic["shipping_type"],
            basic["delivery_time"], basic["country_of_origin"], basic["creation_date"], basic["from_url"],
            basic["from_platform"], basic["shop_id"], basic["shop_name"], basic["goods_id"], basic["title_c"],
            basic["title_t"], basic["video_url"], basic["address"], basic["price_min"], basic["price_max"],
            basic["price_ranges_type"], basic["price_ranges"], basic["inventory_data"], basic["raw_detail"]
        ]
        
        # Add attribute values in the same order as columns
        for attr_col in attr_columns:
            attr_name = None
            for orig_attr in attributes:
                if _sanitize_column_name(orig_attr) == attr_col:
                    attr_name = orig_attr
                    break
            row_values.append(attributes.get(attr_name) if attr_name else None)
        
        rows.append(tuple(row_values))

    # Execute insert
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            columns_str = ", ".join(f'"{col}"' for col in all_columns)
            placeholders_str = ", ".join(all_placeholders)
            
            insert_sql = f"""
                insert into products_enhanced ({columns_str}) 
                values ({placeholders_str})
            """
            
            psycopg2.extras.execute_values(
                cur,
                insert_sql,
                rows,
                template=f"({', '.join(all_placeholders)})"
            )
    
    return len(rows)


# Backwards compatibility
def save_products_to_db(
    products: Iterable[dict],
    *,
    keyword: Optional[str] = None,  # ignored
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    """Legacy API - saves to enhanced table."""
    return save_products_enhanced_to_db(
        products,
        dsn=dsn,
        create_table_if_missing=create_table_if_missing,
    )


def init_products_table(*, dsn: Optional[str] = None) -> None:
    """Legacy API - initializes enhanced table."""
    init_products_enhanced_table(dsn=dsn)

