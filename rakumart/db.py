from __future__ import annotations

from typing import Iterable, Optional
import os
import json
import datetime as dt

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


def _ensure_import():
    if psycopg2 is None:
        raise RuntimeError(f"psycopg2 not available: {_import_error}")


def init_products_table(*, dsn: Optional[str] = None) -> None:
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists products (
                    id bigserial primary key,
                    goods_id text,
                    keyword text,
                    raw jsonb not null,
                    created_at timestamptz not null default now(),
                    unique (goods_id, keyword)
                );
                """
            )


def save_products_to_db(
    products: Iterable[dict],
    *,
    keyword: Optional[str] = None,
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
        goods_id = str(p.get("goodsId", "")) or None
        rows.append((goods_id, keyword, json.dumps(p, ensure_ascii=False), now))
    if not rows:
        return 0

    with psycopg2.connect(dsn_final) as conn:
        with conn.cursor() as cur:
            if create_table_if_missing:
                cur.execute(
                    """
                    create table if not exists products (
                        id bigserial primary key,
                        goods_id text,
                        keyword text,
                        raw jsonb not null,
                        created_at timestamptz not null default now(),
                        unique (goods_id, keyword)
                    );
                    """
                )
            psycopg2.extras.execute_values(
                cur,
                """
                insert into products (goods_id, keyword, raw, created_at)
                values %s
                on conflict (goods_id, keyword) do update set
                  raw = excluded.raw,
                  created_at = excluded.created_at
                """,
                rows,
                template="(%s, %s, %s::jsonb, %s)",
            )
    return len(rows)


