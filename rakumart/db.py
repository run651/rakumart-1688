
from typing import Iterable, Optional
import os
import json
import datetime as dt

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


SCHEMA_SQL = """
create table if not exists products_clean (
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
    created_at timestamptz not null default now()
);
"""


def init_products_clean_table(*, dsn: Optional[str] = None) -> None:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            # Online schema upgrades to ensure columns exist in any order
            cur.execute("alter table products_clean add column if not exists catch_copy text;")
            cur.execute("alter table products_clean add column if not exists creation_date timestamptz;")


def reset_products_clean_table(*, dsn: Optional[str] = None) -> None:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists products_clean cascade;")
            cur.execute(SCHEMA_SQL)


def save_products_clean_to_db(
    products: Iterable[dict],
    *,
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")

    rows = []
    now = dt.datetime.utcnow()
    for p in products:
        shop = p.get("shopInfo") if isinstance(p.get("shopInfo"), dict) else {}
        title_c = p.get("titleC")
        title_t = p.get("titleT")
        detail_images = p.get("detailImages") if isinstance(p.get("detailImages"), list) else []
        main_img = p.get("imgUrl")
        images = [main_img] + detail_images if main_img else detail_images

        weight = None
        try:
            dims = p.get("dimensions") if isinstance(p.get("dimensions"), dict) else p.get("size")
            if isinstance(dims, dict):
                weight = _to_numeric(dims.get("weight"))
        except Exception:
            weight = None

        rows.append((
            shop.get("shopName"),                 # manufacturer_name
            None,                                  # brand
            str(p.get("goodsId")) if p.get("goodsId") is not None else None,  # product_id
            str(p.get("topCategoryId")) if p.get("topCategoryId") is not None else None,  # main_category
            str(p.get("secondCategoryId")) if p.get("secondCategoryId") is not None else None,  # middle_category
            None,                                  # sub_category
            (title_t or title_c),                  # product_name (prefer Japanese titleT)
            None,                                  # catch_copy (no source in API; placeholder)
            p.get("detailDescription"),           # product_description
            None,                                  # color
            None,                                  # size
            None,                                  # shape
            p.get("shopType"),                    # type
            None,                                  # features
            None,                                  # material_specifications
            None,                                  # packaging_size
            None,                                  # selling_unit
            weight,                                # total_weight_per_unit
            json.dumps(images, ensure_ascii=False) if images else None,  # product_image
            images[0] if len(images) > 0 else None,
            images[1] if len(images) > 1 else None,
            images[2] if len(images) > 2 else None,
            images[3] if len(images) > 3 else None,
            images[4] if len(images) > 4 else None,
            images[5] if len(images) > 5 else None,
            images[6] if len(images) > 6 else None,
            images[7] if len(images) > 7 else None,
            None,                                  # minimum_order_quantity
            int(p.get("monthSold")) if str(p.get("monthSold")).isdigit() else None,  # monthly_sales
            None,                                  # in_stock_quantity
            None,                                  # product_reviews
            _to_numeric(p.get("goodsPrice")),     # wholesale_price
            None,                                  # wholesale_margin
            None,                                  # shipping_cost
            None,                                  # shipping_type
            None,                                  # delivery_time
            None,                                  # country_of_origin
            None,                                  # creation_date (no source; placeholder)
            now,
        ))

    if not rows:
        return 0

    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            if create_table_if_missing:
                cur.execute(SCHEMA_SQL)
            psycopg2.extras.execute_values(
                cur,
                """
                insert into products_clean (
                    manufacturer_name, brand, product_id, main_category, middle_category, sub_category,
                    product_name, catch_copy, product_description, color, size, shape, type, features,
                    material_specifications, packaging_size, selling_unit, total_weight_per_unit,
                    product_image, image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8,
                    minimum_order_quantity, monthly_sales, in_stock_quantity, product_reviews,
                    wholesale_price, wholesale_margin, shipping_cost, shipping_type, delivery_time, country_of_origin,
                    creation_date, created_at
                ) values %s
                """,
                rows,
                template=(
                    "(" 
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
                    ")"
                ),
            )
    return len(rows)


# Backwards-compat for existing CLI imports
def init_products_table(*, dsn: Optional[str] = None) -> None:
    """Legacy name kept for CLI; initializes the clean table."""
    init_products_clean_table(dsn=dsn)


def save_products_to_db(
    products: Iterable[dict],
    *,
    keyword: Optional[str] = None,  # kept for signature compatibility; ignored
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    """Legacy API used by CLI. Writes into products_clean."""
    return save_products_clean_to_db(
        products,
        dsn=dsn,
        create_table_if_missing=create_table_if_missing,
    )


from typing import Iterable, Optional
import os
import json
import datetime as dt

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


SCHEMA_SQL = """
create table if not exists products_clean (
    id bigserial primary key,
    manufacturer_name text,
    brand text,
    product_id text,
    main_category text,
    middle_category text,
    sub_category text,
    product_name text,
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
    created_at timestamptz not null default now()
);
"""


def init_products_clean_table(*, dsn: Optional[str] = None) -> None:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


def reset_products_clean_table(*, dsn: Optional[str] = None) -> None:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists products_clean cascade;")
            cur.execute(SCHEMA_SQL)


def save_products_clean_to_db(
    products: Iterable[dict],
    *,
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")

    rows = []
    now = dt.datetime.utcnow()
    for p in products:
        shop = p.get("shopInfo") if isinstance(p.get("shopInfo"), dict) else {}
        title_c = p.get("titleC")
        title_t = p.get("titleT")
        detail_images = p.get("detailImages") if isinstance(p.get("detailImages"), list) else []
        main_img = p.get("imgUrl")
        images = [main_img] + detail_images if main_img else detail_images

        weight = None
        try:
            dims = p.get("dimensions") if isinstance(p.get("dimensions"), dict) else p.get("size")
            if isinstance(dims, dict):
                weight = _to_numeric(dims.get("weight"))
        except Exception:
            weight = None

        rows.append((
            shop.get("shopName"),                 # manufacturer_name
            None,                                  # brand
            str(p.get("goodsId")) if p.get("goodsId") is not None else None,  # product_id
            str(p.get("topCategoryId")) if p.get("topCategoryId") is not None else None,  # main_category
            str(p.get("secondCategoryId")) if p.get("secondCategoryId") is not None else None,  # middle_category
            None,                                  # sub_category
            (title_t or title_c),                  # product_name (prefer Japanese)
            p.get("detailDescription"),           # product_description
            None,                                  # color
            None,                                  # size
            None,                                  # shape
            p.get("shopType"),                    # type
            None,                                  # features
            None,                                  # material_specifications
            None,                                  # packaging_size
            None,                                  # selling_unit
            weight,                                # total_weight_per_unit
            json.dumps(images, ensure_ascii=False) if images else None,  # product_image
            images[0] if len(images) > 0 else None,
            images[1] if len(images) > 1 else None,
            images[2] if len(images) > 2 else None,
            images[3] if len(images) > 3 else None,
            images[4] if len(images) > 4 else None,
            images[5] if len(images) > 5 else None,
            images[6] if len(images) > 6 else None,
            images[7] if len(images) > 7 else None,
            None,                                  # minimum_order_quantity
            int(p.get("monthSold")) if str(p.get("monthSold")).isdigit() else None,  # monthly_sales
            None,                                  # in_stock_quantity
            None,                                  # product_reviews
            _to_numeric(p.get("goodsPrice")),     # wholesale_price
            None,                                  # wholesale_margin
            None,                                  # shipping_cost
            None,                                  # shipping_type
            None,                                  # delivery_time
            None,                                  # country_of_origin
            now,
        ))

    if not rows:
        return 0

    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            if create_table_if_missing:
                cur.execute(SCHEMA_SQL)
            psycopg2.extras.execute_values(
                cur,
                """
                insert into products_clean (
                    manufacturer_name, brand, product_id, main_category, middle_category, sub_category,
                    product_name, product_description, color, size, shape, type, features,
                    material_specifications, packaging_size, selling_unit, total_weight_per_unit,
                    product_image, image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8,
                    minimum_order_quantity, monthly_sales, in_stock_quantity, product_reviews,
                    wholesale_price, wholesale_margin, shipping_cost, shipping_type, delivery_time, country_of_origin,
                    created_at
                ) values %s
                """,
                rows,
                template=(
                    "(" 
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
                    ")"
                ),
            )
    return len(rows)


from typing import Iterable, Optional
import os
import pathlib
import json
import datetime as dt
# Optional .env loading (no-op if python-dotenv not installed)


try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore
else:
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
    if psycopg2 is None:
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


def init_products_clean_table(*, dsn: Optional[str] = None) -> None:
    """Create the clean table with required columns."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists products_clean (
                    id bigserial primary key,
                    manufacturer_name text,
                    brand text,
                    product_id text,
                    main_category text,
                    middle_category text,
                    sub_category text,
                    product_name text,
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
                    created_at timestamptz not null default now()
                );
                """
            )


def reset_products_clean_table(*, dsn: Optional[str] = None) -> None:
    """Drop products_clean and recreate it."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists products_clean cascade;")
    init_products_clean_table(dsn=dsn_final)


def save_products_clean_to_db(
    products: Iterable[dict],
    *,
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    """Insert rows into products_clean mapping fields best-effort from API items."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")

    rows = []
    now = dt.datetime.utcnow()
    for p in products:
        shop = p.get("shopInfo") if isinstance(p.get("shopInfo"), dict) else {}
        title_c = p.get("titleC")
        title_t = p.get("titleT")

        # Images: prefer list image + detail images
        detail_images = p.get("detailImages") if isinstance(p.get("detailImages"), list) else []
        main_img = p.get("imgUrl")
        images = [main_img] + detail_images if main_img else detail_images

        # Numeric conversions
        weight = None
        try:
            dims = p.get("dimensions") if isinstance(p.get("dimensions"), dict) else p.get("size")
            if isinstance(dims, dict):
                weight = _to_numeric(dims.get("weight"))
        except Exception:
            weight = None

        rows.append((
            shop.get("shopName"),                                   # manufacturer_name
            None,                                                    # brand
            str(p.get("goodsId")) if p.get("goodsId") is not None else None,  # product_id
            str(p.get("topCategoryId")) if p.get("topCategoryId") is not None else None,   # main_category
            str(p.get("secondCategoryId")) if p.get("secondCategoryId") is not None else None,  # middle_category
            None,                                                    # sub_category
            title_t or title_c,                                      # product_name (prefer Japanese)
            p.get("detailDescription"),                             # product_description
            None,                                                    # color
            None,                                                    # size
            None,                                                    # shape
            p.get("shopType"),                                      # type
            None,                                                    # features
            None,                                                    # material_specifications
            None,                                                    # packaging_size
            None,                                                    # selling_unit
            weight,                                                  # total_weight_per_unit
            json.dumps(images, ensure_ascii=False) if images else None,  # product_image (JSON array)
            images[0] if len(images) > 0 else None,
            images[1] if len(images) > 1 else None,
            images[2] if len(images) > 2 else None,
            images[3] if len(images) > 3 else None,
            images[4] if len(images) > 4 else None,
            images[5] if len(images) > 5 else None,
            images[6] if len(images) > 6 else None,
            images[7] if len(images) > 7 else None,
            None,                                                    # minimum_order_quantity
            int(p.get("monthSold")) if str(p.get("monthSold")).isdigit() else None,  # monthly_sales
            None,                                                    # in_stock_quantity
            None,                                                    # product_reviews
            _to_numeric(p.get("goodsPrice")),                       # wholesale_price
            None,                                                    # wholesale_margin
            None,                                                    # shipping_cost
            None,                                                    # shipping_type
            None,                                                    # delivery_time
            None,                                                    # country_of_origin
            now,
        ))

    if not rows:
        return 0

    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            if create_table_if_missing:
                cur.execute(
                    """
                    create table if not exists products_clean (
                        id bigserial primary key,
                        manufacturer_name text,
                        brand text,
                        product_id text,
                        main_category text,
                        middle_category text,
                        sub_category text,
                        product_name text,
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
                        created_at timestamptz not null default now()
                    );
                    """
                )
            psycopg2.extras.execute_values(
                cur,
                """
                insert into products_clean (
                    manufacturer_name, brand, product_id, main_category, middle_category, sub_category,
                    product_name, product_description, color, size, shape, type, features,
                    material_specifications, packaging_size, selling_unit, total_weight_per_unit,
                    product_image, image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8,
                    minimum_order_quantity, monthly_sales, in_stock_quantity, product_reviews,
                    wholesale_price, wholesale_margin, shipping_cost, shipping_type, delivery_time, country_of_origin,
                    created_at
                ) values %s
                """,
                rows,
                template=(
                    "(" 
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
                    ")"
                ),
            )
    return len(rows)


from typing import Iterable, Optional
import os
import pathlib
import json
import datetime as dt
# Optional .env loading (no-op if python-dotenv not installed)


try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore
else:
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
    if psycopg2 is None:
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


def init_products_clean_table(*, dsn: Optional[str] = None) -> None:
    """Create the clean table with the requested columns (id + created_at included)."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists products_clean (
                    id bigserial primary key,
                    manufacturer_name text,
                    brand text,
                    product_id text,
                    main_category text,
                    middle_category text,
                    sub_category text,
                    product_name text,
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
                    created_at timestamptz not null default now()
                );
                """
            )


def reset_products_clean_table(*, dsn: Optional[str] = None) -> None:
    """Drop existing products_clean and recreate it."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists products_clean cascade;")
    init_products_clean_table(dsn=dsn_final)


def save_products_clean_to_db(
    products: Iterable[dict],
    *,
    dsn: Optional[str] = None,
    create_table_if_missing: bool = True,
) -> int:
    """Insert rows into products_clean mapping fields best-effort from the given API payloads."""
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")

    rows = []
    now = dt.datetime.utcnow()
    for p in products:
        shop = p.get("shopInfo") if isinstance(p.get("shopInfo"), dict) else {}
        title_c = p.get("titleC")
        title_t = p.get("titleT")

        # Images: prefer list image + detail images
        detail_images = p.get("detailImages") if isinstance(p.get("detailImages"), list) else []
        main_img = p.get("imgUrl")
        images = [main_img] + detail_images if main_img else detail_images

        # Numeric conversions
        weight = None
        try:
            dims = p.get("dimensions") if isinstance(p.get("dimensions"), dict) else p.get("size")
            if isinstance(dims, dict):
                weight = _to_numeric(dims.get("weight"))
        except Exception:
            weight = None

        rows.append((
            shop.get("shopName"),                                   # manufacturer_name
            None,                                                    # brand
            str(p.get("goodsId")) if p.get("goodsId") is not None else None,  # product_id
            str(p.get("topCategoryId")) if p.get("topCategoryId") is not None else None,   # main_category
            str(p.get("secondCategoryId")) if p.get("secondCategoryId") is not None else None,  # middle_category
            None,                                                    # sub_category
            (title_t or title_c),                                      # product_name (prefer Japanese)
            p.get("detailDescription"),                             # product_description
            None,                                                    # color
            None,                                                    # size
            None,                                                    # shape
            p.get("shopType"),                                      # type
            None,                                                    # features
            None,                                                    # material_specifications
            None,                                                    # packaging_size
            None,                                                    # selling_unit
            weight,                                                  # total_weight_per_unit
            json.dumps(images, ensure_ascii=False) if images else None,  # product_image (JSON array)
            images[0] if len(images) > 0 else None,
            images[1] if len(images) > 1 else None,
            images[2] if len(images) > 2 else None,
            images[3] if len(images) > 3 else None,
            images[4] if len(images) > 4 else None,
            images[5] if len(images) > 5 else None,
            images[6] if len(images) > 6 else None,
            images[7] if len(images) > 7 else None,
            None,                                                    # minimum_order_quantity
            int(p.get("monthSold")) if str(p.get("monthSold")).isdigit() else None,  # monthly_sales
            None,                                                    # in_stock_quantity
            None,                                                    # product_reviews
            _to_numeric(p.get("goodsPrice")),                       # wholesale_price
            None,                                                    # wholesale_margin
            None,                                                    # shipping_cost
            None,                                                    # shipping_type
            None,                                                    # delivery_time
            None,                                                    # country_of_origin
            now,
        ))

    if not rows:
        return 0

    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            if create_table_if_missing:
                cur.execute(
                    """
                    create table if not exists products_clean (
                        id bigserial primary key,
                        manufacturer_name text,
                        brand text,
                        product_id text,
                        main_category text,
                        middle_category text,
                        sub_category text,
                        product_name text,
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
                        created_at timestamptz not null default now()
                    );
                    """
                )
            psycopg2.extras.execute_values(
                cur,
                """
                insert into products_clean (
                    manufacturer_name, brand, product_id, main_category, middle_category, sub_category,
                    product_name, product_description, color, size, shape, type, features,
                    material_specifications, packaging_size, selling_unit, total_weight_per_unit,
                    product_image, image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8,
                    minimum_order_quantity, monthly_sales, in_stock_quantity, product_reviews,
                    wholesale_price, wholesale_margin, shipping_cost, shipping_type, delivery_time, country_of_origin,
                    created_at
                ) values %s
                """,
                rows,
                template=(
                    "(" 
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
                    ")"
                ),
            )
    return len(rows)

