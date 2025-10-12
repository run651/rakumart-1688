"""
Image processing module for Rakumart 1688 scraper.

This module provides functionality to:
1. Detect Chinese text in images using Google Vision API
2. Translate Chinese text to Japanese using AWS Translate API
3. Replace Chinese text with Japanese text in images
4. Detect and blur faces in images
5. Detect and remove logos/stamps from images
6. Process images from PostgreSQL database

Requirements:
- Google Cloud Vision API credentials
- AWS Translate API credentials
- PIL/Pillow for image manipulation
- requests for HTTP operations
"""

import os
import json
import base64
import io
import logging
import hashlib
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import requests
    from google.cloud import vision
    import boto3
    from botocore.exceptions import ClientError
except ImportError as e:
    print(f"Missing required dependencies: {e}")
    print("Please install: pip install pillow requests google-cloud-vision boto3")
    raise

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TextDetection:
    """Represents detected text in an image."""
    text: str
    confidence: float
    bounding_box: List[Dict[str, float]]  # [{"x": 0.1, "y": 0.2}, ...]
    language: str = "zh"  # Default to Chinese

@dataclass
class FaceDetection:
    """Represents detected face in an image."""
    confidence: float
    bounding_box: List[Dict[str, float]]  # [{"x": 0.1, "y": 0.2}, ...]

@dataclass
class LogoDetection:
    """Represents detected logo/stamp in an image."""
    confidence: float
    bounding_box: List[Dict[str, float]]  # [{"x": 0.1, "y": 0.2}, ...]
    description: str = ""

class ImageProcessor:
    """Main class for processing images with Google Vision API and AWS Translate."""
    
    def __init__(self):
        """Initialize the image processor with API clients."""
        self.vision_client = None
        self.translate_client = None
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize Google Vision and AWS Translate clients."""
        try:
            # Initialize Google Vision API client
            # Credentials should be set via GOOGLE_APPLICATION_CREDENTIALS env var
            # or service account key file
            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Vision API client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Vision API: {e}")
            logger.error("Please set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            
        try:
            # Initialize AWS Translate client
            # Credentials should be set via AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
            # or AWS profile
            self.translate_client = boto3.client(
                'translate',
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            logger.info("AWS Translate API client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AWS Translate API: {e}")
            logger.error("Please set AWS credentials")
    
    def detect_text(self, image_bytes: bytes) -> List[TextDetection]:
        """
        Detect text in image using Google Vision API.
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            List of TextDetection objects
        """
        if not self.vision_client:
            logger.error("Google Vision API client not initialized")
            return []
            
        try:
            image = vision.Image(content=image_bytes)
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if response.error.message:
                logger.error(f"Google Vision API error: {response.error.message}")
                return []
                
            detections = []
            for text in texts[1:]:  # Skip first element (full text)
                # Convert bounding box to normalized coordinates
                vertices = text.bounding_poly.vertices
                bounding_box = [
                    {"x": vertex.x / image.width if hasattr(image, 'width') else vertex.x,
                     "y": vertex.y / image.height if hasattr(image, 'height') else vertex.y}
                    for vertex in vertices
                ]
                
                detections.append(TextDetection(
                    text=text.description,
                    confidence=0.9,  # Google Vision doesn't provide confidence for text detection
                    bounding_box=bounding_box,
                    language="zh"  # Assume Chinese for now
                ))
                
            logger.info(f"Detected {len(detections)} text regions")
            return detections
            
        except Exception as e:
            logger.error(f"Error detecting text: {e}")
            return []
    
    def detect_faces(self, image_bytes: bytes) -> List[FaceDetection]:
        """
        Detect faces in image using Google Vision API.
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            List of FaceDetection objects
        """
        if not self.vision_client:
            logger.error("Google Vision API client not initialized")
            return []
            
        try:
            image = vision.Image(content=image_bytes)
            response = self.vision_client.face_detection(image=image)
            faces = response.face_annotations
            
            if response.error.message:
                logger.error(f"Google Vision API error: {response.error.message}")
                return []
                
            detections = []
            for face in faces:
                # Convert bounding box to normalized coordinates
                vertices = face.bounding_poly.vertices
                bounding_box = [
                    {"x": vertex.x / image.width if hasattr(image, 'width') else vertex.x,
                     "y": vertex.y / image.height if hasattr(image, 'height') else vertex.y}
                    for vertex in vertices
                ]
                
                detections.append(FaceDetection(
                    confidence=face.detection_confidence,
                    bounding_box=bounding_box
                ))
                
            logger.info(f"Detected {len(detections)} faces")
            return detections
            
        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []
    
    def detect_logos(self, image_bytes: bytes) -> List[LogoDetection]:
        """
        Detect logos/stamps in image using Google Vision API.
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            List of LogoDetection objects
        """
        if not self.vision_client:
            logger.error("Google Vision API client not initialized")
            return []
            
        try:
            image = vision.Image(content=image_bytes)
            response = self.vision_client.logo_detection(image=image)
            logos = response.logo_annotations
            
            if response.error.message:
                logger.error(f"Google Vision API error: {response.error.message}")
                return []
                
            detections = []
            for logo in logos:
                # Convert bounding box to normalized coordinates
                vertices = logo.bounding_poly.vertices
                bounding_box = [
                    {"x": vertex.x / image.width if hasattr(image, 'width') else vertex.x,
                     "y": vertex.y / image.height if hasattr(image, 'height') else vertex.y}
                    for vertex in vertices
                ]
                
                detections.append(LogoDetection(
                    confidence=logo.score,
                    bounding_box=bounding_box,
                    description=logo.description
                ))
                
            logger.info(f"Detected {len(detections)} logos")
            return detections
            
        except Exception as e:
            logger.error(f"Error detecting logos: {e}")
            return []
    
    def translate_text(self, text: str, source_lang: str = "zh", target_lang: str = "ja") -> str:
        """
        Translate text using AWS Translate API.
        
        Args:
            text: Text to translate
            source_lang: Source language code (default: zh for Chinese)
            target_lang: Target language code (default: ja for Japanese)
            
        Returns:
            Translated text
        """
        if not self.translate_client:
            logger.error("AWS Translate API client not initialized")
            return text
            
        try:
            response = self.translate_client.translate_text(
                Text=text,
                SourceLanguageCode=source_lang,
                TargetLanguageCode=target_lang
            )
            
            translated_text = response['TranslatedText']
            logger.info(f"Translated: '{text}' -> '{translated_text}'")
            return translated_text
            
        except ClientError as e:
            logger.error(f"AWS Translate API error: {e}")
            return text
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return text
    
    def blur_faces(self, image: Image.Image, face_detections: List[FaceDetection]) -> Image.Image:
        """
        Blur faces in the image.
        
        Args:
            image: PIL Image object
            face_detections: List of face detections
            
        Returns:
            PIL Image with blurred faces
        """
        if not face_detections:
            return image
            
        # Create a copy to avoid modifying the original
        blurred_image = image.copy()
        draw = ImageDraw.Draw(blurred_image)
        
        for face in face_detections:
            # Convert normalized coordinates to pixel coordinates
            width, height = image.size
            vertices = face.bounding_box
            
            # Calculate bounding box in pixels
            x_coords = [int(v["x"] * width) for v in vertices]
            y_coords = [int(v["y"] * height) for v in vertices]
            
            left = min(x_coords)
            top = min(y_coords)
            right = max(x_coords)
            bottom = max(y_coords)
            
            # Add some padding
            padding = 10
            left = max(0, left - padding)
            top = max(0, top - padding)
            right = min(width, right + padding)
            bottom = min(height, bottom + padding)
            
            # Extract face region and blur it
            face_region = image.crop((left, top, right, bottom))
            blurred_face = face_region.filter(ImageFilter.GaussianBlur(radius=15))
            
            # Paste blurred face back
            blurred_image.paste(blurred_face, (left, top))
            
        logger.info(f"Blurred {len(face_detections)} faces")
        return blurred_image
    
    def remove_logos(self, image: Image.Image, logo_detections: List[LogoDetection]) -> Image.Image:
        """
        Remove logos/stamps from the image by inpainting.
        
        Args:
            image: PIL Image object
            logo_detections: List of logo detections
            
        Returns:
            PIL Image with logos removed
        """
        if not logo_detections:
            return image
            
        # Create a copy to avoid modifying the original
        cleaned_image = image.copy()
        
        for logo in logo_detections:
            # Convert normalized coordinates to pixel coordinates
            width, height = image.size
            vertices = logo.bounding_box
            
            # Calculate bounding box in pixels
            x_coords = [int(v["x"] * width) for v in vertices]
            y_coords = [int(v["y"] * height) for v in vertices]
            
            left = min(x_coords)
            top = min(y_coords)
            right = max(x_coords)
            bottom = max(y_coords)
            
            # Add some padding
            padding = 5
            left = max(0, left - padding)
            top = max(0, top - padding)
            right = min(width, right + padding)
            bottom = min(height, bottom + padding)
            
            # Simple inpainting: fill with average color of surrounding area
            # Get surrounding pixels for color estimation
            sample_left = max(0, left - 20)
            sample_top = max(0, top - 20)
            sample_right = min(width, right + 20)
            sample_bottom = min(height, bottom + 20)
            
            sample_region = image.crop((sample_left, sample_top, sample_right, sample_bottom))
            avg_color = self._get_average_color(sample_region)
            
            # Fill logo area with average color
            draw = ImageDraw.Draw(cleaned_image)
            draw.rectangle([left, top, right, bottom], fill=avg_color)
            
        logger.info(f"Removed {len(logo_detections)} logos")
        return cleaned_image
    
    def _get_average_color(self, image: Image.Image) -> Tuple[int, int, int]:
        """Get average color of an image region."""
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Get pixel data
        pixels = list(image.getdata())
        
        # Calculate average
        r_sum = g_sum = b_sum = 0
        for r, g, b in pixels:
            r_sum += r
            g_sum += g
            b_sum += b
            
        count = len(pixels)
        if count == 0:
            return (128, 128, 128)  # Default gray
            
        return (r_sum // count, g_sum // count, b_sum // count)
    
    def replace_text_with_japanese(self, image: Image.Image, text_detections: List[TextDetection]) -> Image.Image:
        """
        Replace Chinese text with Japanese translations in the image.
        
        Args:
            image: PIL Image object
            text_detections: List of text detections
            
        Returns:
            PIL Image with Japanese text
        """
        if not text_detections:
            return image
            
        # Create a copy to avoid modifying the original
        modified_image = image.copy()
        draw = ImageDraw.Draw(modified_image)
        
        # Try to load a Japanese font
        try:
            # Try to use a system font that supports Japanese
            font_size = 20
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        for detection in text_detections:
            # Translate Chinese text to Japanese
            japanese_text = self.translate_text(detection.text, "zh", "ja")
            
            # Convert normalized coordinates to pixel coordinates
            width, height = image.size
            vertices = detection.bounding_box
            
            # Calculate bounding box in pixels
            x_coords = [int(v["x"] * width) for v in vertices]
            y_coords = [int(v["y"] * height) for v in vertices]
            
            left = min(x_coords)
            top = min(y_coords)
            right = max(x_coords)
            bottom = max(y_coords)
            
            # Fill original text area with white background
            draw.rectangle([left, top, right, bottom], fill="white")
            
            # Draw Japanese text
            try:
                # Calculate text position (center of bounding box)
                text_x = (left + right) // 2
                text_y = (top + bottom) // 2
                
                # Draw text
                draw.text((text_x, text_y), japanese_text, fill="black", font=font, anchor="mm")
            except Exception as e:
                logger.error(f"Error drawing Japanese text: {e}")
                
        logger.info(f"Replaced {len(text_detections)} text regions with Japanese")
        return modified_image
    
    def save_processed_image(self, processed_bytes: bytes, original_url: str, output_dir: str = "processed_images") -> Optional[str]:
        """
        Save processed image to local storage.
        
        Args:
            processed_bytes: Processed image data as bytes
            original_url: Original image URL for naming
            output_dir: Directory to save processed images
            
        Returns:
            Path to saved file, or None if saving failed
        """
        try:
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename from URL
            parsed_url = urllib.parse.urlparse(original_url)
            filename = os.path.basename(parsed_url.path)
            
            # If no filename or extension, create one
            if not filename or '.' not in filename:
                # Create hash from URL for unique naming
                url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
                filename = f"processed_{url_hash}.jpg"
            else:
                # Add processed prefix to existing filename
                name, ext = os.path.splitext(filename)
                filename = f"processed_{name}{ext}"
            
            # Ensure .jpg extension
            if not filename.lower().endswith(('.jpg', '.jpeg')):
                filename = f"{os.path.splitext(filename)[0]}.jpg"
            
            # Full path to save file
            file_path = output_path / filename
            
            # Save the processed image
            with open(file_path, 'wb') as f:
                f.write(processed_bytes)
            
            logger.info(f"Saved processed image to: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving processed image: {e}")
            return None

    def process_image(self, image_url: str, save_locally: bool = True, output_dir: str = "processed_images") -> Optional[Dict[str, Any]]:
        """
        Process a single image: detect text, faces, logos and apply modifications.
        
        Args:
            image_url: URL of the image to process
            save_locally: Whether to save processed image to local storage
            output_dir: Directory to save processed images if save_locally is True
            
        Returns:
            Dictionary with processing results, or None if processing failed
        """
        try:
            # Download image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            image_bytes = response.content
            
            # Load image with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Detect text, faces, and logos
            text_detections = self.detect_text(image_bytes)
            face_detections = self.detect_faces(image_bytes)
            logo_detections = self.detect_logos(image_bytes)
            
            # Apply modifications
            processed_image = image
            
            # Blur faces
            if face_detections:
                processed_image = self.blur_faces(processed_image, face_detections)
            
            # Remove logos
            if logo_detections:
                processed_image = self.remove_logos(processed_image, logo_detections)
            
            # Replace Chinese text with Japanese
            if text_detections:
                processed_image = self.replace_text_with_japanese(processed_image, text_detections)
            
            # Convert back to bytes
            output_buffer = io.BytesIO()
            processed_image.save(output_buffer, format='JPEG', quality=95)
            processed_bytes = output_buffer.getvalue()
            
            # Prepare result dictionary
            result = {
                "original_url": image_url,
                "processed_bytes": processed_bytes,
                "processed_size": len(processed_bytes),
                "text_detections": len(text_detections),
                "face_detections": len(face_detections),
                "logo_detections": len(logo_detections),
                "local_path": None
            }
            
            # Save to local storage if requested
            if save_locally:
                local_path = self.save_processed_image(processed_bytes, image_url, output_dir)
                result["local_path"] = local_path
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing image {image_url}: {e}")
            return None
    
    def process_image_from_bytes(self, image_bytes: bytes) -> Optional[bytes]:
        """
        Process image from bytes: detect text, faces, logos and apply modifications.
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            Processed image as bytes, or None if processing failed
        """
        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Detect text, faces, and logos
            text_detections = self.detect_text(image_bytes)
            face_detections = self.detect_faces(image_bytes)
            logo_detections = self.detect_logos(image_bytes)
            
            # Apply modifications
            processed_image = image
            
            # Blur faces
            if face_detections:
                processed_image = self.blur_faces(processed_image, face_detections)
            
            # Remove logos
            if logo_detections:
                processed_image = self.remove_logos(processed_image, logo_detections)
            
            # Replace Chinese text with Japanese
            if text_detections:
                processed_image = self.replace_text_with_japanese(processed_image, text_detections)
            
            # Convert back to bytes
            output_buffer = io.BytesIO()
            processed_image.save(output_buffer, format='JPEG', quality=95)
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error processing image from bytes: {e}")
            return None


def process_product_images_from_db(product_id: str, dsn: Optional[str] = None, save_locally: bool = True, output_dir: str = "processed_images") -> Dict[str, Any]:
    """
    Process all images for a specific product from the database.
    
    Args:
        product_id: Product ID to process
        dsn: Database connection string
        save_locally: Whether to save processed images to local storage
        output_dir: Directory to save processed images if save_locally is True
        
    Returns:
        Dictionary with processing results
    """
    from .db import _get_dsn, _ensure_import
    
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured")
    
    processor = ImageProcessor()
    results = {
        "product_id": product_id,
        "processed_images": [],
        "errors": []
    }
    
    # Update status to processing
    from .db import update_image_processing_status
    update_image_processing_status(product_id, "processing", dsn=dsn_final)
    
    try:
        import psycopg2
        with psycopg2.connect(dsn_final) as conn:
            with conn.cursor() as cur:
                # Get product images
                cur.execute("""
                    SELECT product_image, image_1, image_2, image_3, image_4, 
                           image_5, image_6, image_7, image_8
                    FROM products_clean 
                    WHERE product_id = %s
                """, (product_id,))
                
                row = cur.fetchone()
                if not row:
                    results["errors"].append(f"Product {product_id} not found")
                    return results
                
                # Collect all image URLs
                image_urls = []
                
                # Add individual image columns
                for i in range(1, 9):
                    image_url = row[i]
                    if image_url:
                        image_urls.append(image_url)
                
                # Add images from JSONB column
                product_images = row[0]
                if product_images:
                    try:
                        if isinstance(product_images, str):
                            images_data = json.loads(product_images)
                        else:
                            images_data = product_images
                        
                        if isinstance(images_data, list):
                            image_urls.extend(images_data)
                    except Exception as e:
                        logger.error(f"Error parsing product_image JSON: {e}")
                
                # Remove duplicates while preserving order
                seen = set()
                unique_image_urls = []
                for url in image_urls:
                    if url and url not in seen:
                        seen.add(url)
                        unique_image_urls.append(url)
                
                # Process each image
                for i, image_url in enumerate(unique_image_urls):
                    try:
                        logger.info(f"Processing image {i+1}/{len(unique_image_urls)}: {image_url}")
                        result = processor.process_image(image_url, save_locally=save_locally, output_dir=output_dir)
                        
                        if result:
                            results["processed_images"].append({
                                "original_url": image_url,
                                "processed_size": result["processed_size"],
                                "text_detections": result["text_detections"],
                                "face_detections": result["face_detections"],
                                "logo_detections": result["logo_detections"],
                                "local_path": result["local_path"],
                                "status": "success"
                            })
                        else:
                            results["processed_images"].append({
                                "original_url": image_url,
                                "status": "failed"
                            })
                            results["errors"].append(f"Failed to process image: {image_url}")
                            
                    except Exception as e:
                        logger.error(f"Error processing image {image_url}: {e}")
                        results["processed_images"].append({
                            "original_url": image_url,
                            "status": "error",
                            "error": str(e)
                        })
                        results["errors"].append(f"Error processing {image_url}: {e}")
                
                logger.info(f"Processed {len(results['processed_images'])} images for product {product_id}")
                
                # Update status to completed
                update_image_processing_status(
                    product_id, 
                    "completed", 
                    processed_images=results,
                    dsn=dsn_final
                )
                
    except Exception as e:
        logger.error(f"Database error: {e}")
        results["errors"].append(f"Database error: {e}")
        
        # Update status to failed
        update_image_processing_status(product_id, "failed", dsn=dsn_final)
    
    return results


def process_all_product_images(dsn: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Process images for all products in the database.
    
    Args:
        dsn: Database connection string
        limit: Maximum number of products to process (None for all)
        
    Returns:
        Dictionary with processing results
    """
    from .db import _get_dsn, _ensure_import
    
    _ensure_import()
    dsn_final = dsn or _get_dsn()
    if not dsn_final:
        raise RuntimeError("PostgreSQL DSN is not configured")
    
    results = {
        "total_products": 0,
        "processed_products": 0,
        "product_results": [],
        "errors": []
    }
    
    try:
        import psycopg2
        with psycopg2.connect(dsn_final) as conn:
            with conn.cursor() as cur:
                # Get all product IDs
                query = "SELECT DISTINCT product_id FROM products_clean WHERE product_id IS NOT NULL"
                if limit:
                    query += f" LIMIT {limit}"
                
                cur.execute(query)
                product_ids = [row[0] for row in cur.fetchall()]
                
                results["total_products"] = len(product_ids)
                
                # Process each product
                for product_id in product_ids:
                    try:
                        logger.info(f"Processing product {product_id}")
                        product_result = process_product_images_from_db(product_id, dsn_final)
                        results["product_results"].append(product_result)
                        results["processed_products"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing product {product_id}: {e}")
                        results["errors"].append(f"Error processing product {product_id}: {e}")
                
                logger.info(f"Completed processing {results['processed_products']}/{results['total_products']} products")
                
    except Exception as e:
        logger.error(f"Database error: {e}")
        results["errors"].append(f"Database error: {e}")
    
    return results


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python image-processing.py <command> [args]")
        print("Commands:")
        print("  process-product <product_id>  - Process images for a specific product")
        print("  process-all [limit]           - Process images for all products")
        print("  test-image <image_url>        - Test processing on a single image")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "process-product":
        if len(sys.argv) < 3:
            print("Usage: python image-processing.py process-product <product_id>")
            sys.exit(1)
        
        product_id = sys.argv[2]
        result = process_product_images_from_db(product_id)
        print(json.dumps(result, indent=2))
        
    elif command == "process-all":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        result = process_all_product_images(limit=limit)
        print(json.dumps(result, indent=2))
        
    elif command == "test-image":
        if len(sys.argv) < 3:
            print("Usage: python image-processing.py test-image <image_url>")
            sys.exit(1)
        
        image_url = sys.argv[2]
        processor = ImageProcessor()
        processed_bytes = processor.process_image(image_url)
        
        if processed_bytes:
            # Save processed image
            output_path = f"processed_{Path(image_url).stem}.jpg"
            with open(output_path, "wb") as f:
                f.write(processed_bytes)
            print(f"Processed image saved to: {output_path}")
        else:
            print("Failed to process image")
            
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
