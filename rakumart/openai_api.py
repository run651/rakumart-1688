from typing import Optional, Tuple

from .config import OPENAI_API_KEY, OPENAI_MODEL

try:
    # Prefer the modern OpenAI SDK if available
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


def _truncate_by_chars(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit]


def generate_marketing_text(original_name: Optional[str]) -> Tuple[str, str]:
    """
    Generate an optimized product name (<=110 chars) and a catchphrase (<=70 chars)
    from the given Japanese product name. Falls back gracefully when OpenAI is not
    configured or available.
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

        # Try Responses API first; fallback to chat.completions
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
            chat = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            text = chat.choices[0].message.content if chat.choices else ""

        name_gen = ""
        copy_gen = ""
        for line in (text or "").splitlines():
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
