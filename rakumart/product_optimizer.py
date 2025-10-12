"""
Product Name Optimization Module for Rakumart

This module provides functionality to:
1. Generate optimized product names and catchphrases using OpenAI API
2. Update database records with optimized names
3. Handle batch processing of product names
4. Ensure character limits and quality standards
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time

from .config import OPENAI_API_KEY, OPENAI_MODEL
from .db import _ensure_import, _get_dsn

try:
    from openai import OpenAI, ChatCompletion
except ImportError:
    OpenAI = None
    ChatCompletion = None

logger = logging.getLogger(__name__)


@dataclass
class ProductNameResult:
    """Result of product name optimization"""
    product_id: str
    original_name: str
    optimized_name: str
    catch_copy: str
    success: bool
    error_message: Optional[str] = None


class ProductNameOptimizer:
    """Main class for optimizing product names using OpenAI API"""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or OPENAI_MODEL
        self.client = None
        
        if self.api_key:
            try:
                # Set the API key for the older version
                import openai
                openai.api_key = self.api_key
                self.client = True  # Just mark as available
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            logger.warning("OpenAI not available - API key missing or library not installed")
    
    def _truncate_text(self, text: str, limit: int) -> str:
        """Truncate text to specified character limit"""
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit]
    
    def _is_valid_japanese_text(self, text: str) -> bool:
        """Check if text contains Japanese characters"""
        if not text:
            return False
        
        # Check for Japanese characters (Hiragana, Katakana, Kanji)
        for char in text:
            if '\u3040' <= char <= '\u309F':  # Hiragana
                return True
            if '\u30A0' <= char <= '\u30FF':  # Katakana
                return True
            if '\u4E00' <= char <= '\u9FAF':  # CJK Unified Ideographs
                return True
        return False
    
    def generate_optimized_names(self, original_name: str) -> Tuple[str, str]:
        """
        Generate optimized product name and catchphrase for Rakuten marketplace
        
        Args:
            original_name: Original Japanese product name
            
        Returns:
            Tuple of (optimized_name, catch_copy)
        """
        if not self.client:
            logger.warning("OpenAI client not available, returning original name")
            return self._truncate_text(original_name, 120), ""
        
        if not original_name or not original_name.strip():
            return "", ""
        
        # Validate that input contains Japanese text
        if not self._is_valid_japanese_text(original_name):
            logger.warning(f"Input text doesn't appear to be Japanese: {original_name}")
            return self._truncate_text(original_name, 120), ""
        
        try:
            system_prompt = """あなたは楽天市場向けの商品名最適化の専門家です。

以下の原題をもとに、検索と購買率を高める日本語の商品名とキャッチコピーを生成してください。

【制約】
- 商品名: 120文字以内
- キャッチコピー: 80文字以内
- SEOキーワードを含める
- 購買意欲を高める表現を使用
- 楽天市場のユーザーに響く表現を心がける

【出力形式】
商品名: [最適化された商品名]
キャッチコピー: [魅力的なキャッチコピー]

余計な説明や装飾は不要です。"""

            user_prompt = f"原題: {original_name.strip()}"
            
            # Use the older ChatCompletion API
            import openai
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content if response.choices else ""
            
            # Parse the response
            optimized_name = ""
            catch_copy = ""
            
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('商品名:'):
                    optimized_name = line.replace('商品名:', '').strip()
                elif line.startswith('キャッチコピー:'):
                    catch_copy = line.replace('キャッチコピー:', '').strip()
            
            # Fallback parsing if structured format wasn't used
            if not optimized_name and not catch_copy:
                lines = [line.strip() for line in lines if line.strip()]
                if lines:
                    optimized_name = lines[0]
                    if len(lines) > 1:
                        catch_copy = lines[1]
            
            # Ensure we have valid results
            if not optimized_name:
                optimized_name = original_name
            
            # Truncate to limits
            optimized_name = self._truncate_text(optimized_name, 120)
            catch_copy = self._truncate_text(catch_copy, 80)
            
            logger.info(f"Generated optimized name: {optimized_name[:50]}...")
            return optimized_name, catch_copy
            
        except Exception as e:
            logger.error(f"Error generating optimized names: {e}")
            return self._truncate_text(original_name, 120), ""
    
    def optimize_product(self, product_id: str, original_name: str) -> ProductNameResult:
        """
        Optimize a single product's name
        
        Args:
            product_id: Product ID
            original_name: Original product name
            
        Returns:
            ProductNameResult object
        """
        try:
            optimized_name, catch_copy = self.generate_optimized_names(original_name)
            
            return ProductNameResult(
                product_id=product_id,
                original_name=original_name,
                optimized_name=optimized_name,
                catch_copy=catch_copy,
                success=True
            )
        except Exception as e:
            logger.error(f"Error optimizing product {product_id}: {e}")
            return ProductNameResult(
                product_id=product_id,
                original_name=original_name,
                optimized_name=original_name,
                catch_copy="",
                success=False,
                error_message=str(e)
            )


def update_product_names_in_db(
    product_ids: Optional[List[str]] = None,
    limit: Optional[int] = None,
    dsn: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update product names in the database using OpenAI optimization
    
    Args:
        product_ids: List of specific product IDs to update (if None, updates all)
        limit: Maximum number of products to process
        dsn: Database connection string
        
    Returns:
        Dictionary with processing results
    """
    _ensure_import()
    import psycopg2
    import psycopg2.extras
    
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    
    optimizer = ProductNameOptimizer()
    if not optimizer.client:
        raise RuntimeError("OpenAI API not configured. Set OPENAI_API_KEY environment variable.")
    
    results = {
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "errors": [],
        "updated_products": []
    }
    
    try:
        with psycopg2.connect(dsn_final) as conn:
            with conn.cursor() as cur:
                # Build query to get products
                query = """
                    SELECT product_id, product_name 
                    FROM products_clean 
                    WHERE product_name IS NOT NULL 
                    AND product_name != ''
                """
                params = []
                
                if product_ids:
                    placeholders = ','.join(['%s'] * len(product_ids))
                    query += f" AND product_id IN ({placeholders})"
                    params.extend(product_ids)
                
                query += " ORDER BY created_at DESC"
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cur.execute(query, params)
                products = cur.fetchall()
                
                logger.info(f"Found {len(products)} products to process")
                
                for product_id, original_name in products:
                    try:
                        # Optimize the product name
                        result = optimizer.optimize_product(product_id, original_name)
                        results["processed"] += 1
                        
                        if result.success:
                            # Update the database
                            update_query = """
                                UPDATE products_clean 
                                SET product_name = %s, catch_copy = %s
                                WHERE product_id = %s
                            """
                            cur.execute(update_query, (result.optimized_name, result.catch_copy, product_id))
                            
                            results["successful"] += 1
                            results["updated_products"].append({
                                "product_id": product_id,
                                "original_name": result.original_name,
                                "optimized_name": result.optimized_name,
                                "catch_copy": result.catch_copy
                            })
                            
                            logger.info(f"Updated product {product_id}")
                        else:
                            results["failed"] += 1
                            results["errors"].append(f"Product {product_id}: {result.error_message}")
                        
                        # Small delay to avoid rate limiting
                        time.sleep(0.1)
                        
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"Product {product_id}: {str(e)}")
                        logger.error(f"Error processing product {product_id}: {e}")
                
                conn.commit()
                logger.info(f"Processing complete: {results['successful']} successful, {results['failed']} failed")
                
    except Exception as e:
        logger.error(f"Database error: {e}")
        results["errors"].append(f"Database error: {e}")
    
    return results


def get_products_needing_optimization(
    limit: Optional[int] = None,
    dsn: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get products that need name optimization
    
    Args:
        limit: Maximum number of products to return
        dsn: Database connection string
        
    Returns:
        List of product dictionaries
    """
    _ensure_import()
    import psycopg2
    import psycopg2.extras
    
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured. Set DATABASE_URL or PG* env vars.")
    
    products = []
    
    try:
        with psycopg2.connect(dsn_final) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = """
                    SELECT product_id, product_name, catch_copy, created_at
                    FROM products_clean 
                    WHERE product_name IS NOT NULL 
                    AND product_name != ''
                    ORDER BY created_at DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cur.execute(query)
                products = [dict(row) for row in cur.fetchall()]
                
    except Exception as e:
        logger.error(f"Error getting products: {e}")
    
    return products
