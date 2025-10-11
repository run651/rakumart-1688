from typing import Optional, Dict, Any, Tuple
import os

from .config import OPENAI_API_KEY, OPENAI_MODEL

try:
    # Use new OpenAI SDK if available
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


def convert_rmb_to_jpy(rmb_price: float, exchange_rate: float = 20.0) -> float:
    """Convert RMB price to JPY."""
    return rmb_price * exchange_rate


def convert_jpy_to_rmb(jpy_price: float, exchange_rate: float = 20.0) -> float:
    """Convert JPY price to RMB."""
    return jpy_price / exchange_rate


def get_product_price_in_jpy(product: Dict[str, Any], exchange_rate: float = 20.0) -> Optional[float]:
    """Extract and convert product price to JPY. Returns None if unavailable."""
    price_fields = ["goodsPrice", "price", "productPrice", "salePrice", "marketPrice"]
    for field in price_fields:
        price = product.get(field)
        if price is None:
            continue
        try:
            if isinstance(price, str):
                import re
                price_clean = re.sub(r'[^\d.,]', '', price)
                if not price_clean:
                    continue
                price_clean = price_clean.replace(',', '.')
                price_val = float(price_clean)
            else:
                price_val = float(price)
            return convert_rmb_to_jpy(price_val, exchange_rate)
        except (ValueError, TypeError):
            continue
    return None


def _truncate_by_chars(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit]


def generate_marketing_text(original_name: Optional[str]) -> Tuple[str, str]:
    """
    Given an original Japanese product name, generate an improved product name (<=110 chars)
    and a catchphrase (<=70 chars) optimized for sales and SEO.

    Falls back gracefully to the original name and empty catchphrase when OpenAI isn't configured.
    """
    safe_name = (original_name or "").strip()
    if not safe_name:
        return "", ""

    # If SDK or key missing, return original and empty catchphrase
    if OpenAI is None or not OPENAI_API_KEY:
        return _truncate_by_chars(safe_name, 110), ""

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        system_prompt = (
            "あなたは日本のEC向けの商品名最適化アシスタントです。"
            "以下の原題をもとに、検索と購買率を高める日本語の ‘商品名’ と ‘キャッチコピー’ を生成してください。"
            "制約: 商品名は110文字以内、キャッチコピーは70文字以内。余計な説明や引用、ラベルは不要。"
        )
        user_prompt = f"原題: {safe_name}\n商品名とキャッチコピーのみを出力してください。改行で区切ってください。"

        # Use Responses API if available; otherwise try legacy completions/chat
        try:
            resp = client.responses.create(
                model=OPENAI_MODEL,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = resp.output_text
        except Exception:
            # Fallback to chat.completions
            chat = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            text = chat.choices[0].message.content if chat.choices else ""

        # Parse two lines: first -> name, second -> catchphrase
        name_gen = ""
        copy_gen = ""
        for idx, line in enumerate((text or "").splitlines()):
            s = line.strip().strip('"')
            if not s:
                continue
            if not name_gen:
                name_gen = s
                continue
            if not copy_gen:
                copy_gen = s
                break

        if not name_gen:
            name_gen = safe_name
        return _truncate_by_chars(name_gen, 110), _truncate_by_chars(copy_gen, 70)
    except Exception:
        # Fail-closed to original name
        return _truncate_by_chars(safe_name, 110), ""


