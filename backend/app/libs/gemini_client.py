"""Centralized Gemini AI Client Wrapper

This module provides a stable, maintainable interface to Google's Gemini AI SDK.
If Google changes their SDK in the future, only this file needs updates.

Usage:
    from app.libs.gemini_client import get_gemini_client
    
    client = get_gemini_client()
    text = client.generate_content("Hello, world!")
    embedding = client.embed_text("Some text to embed")
"""

from google import genai  # type: ignore
from google.genai import types  # type: ignore
from typing import List, Any, Optional, Union
import traceback
import base64
import threading
import os


# Video and image file extensions
VIDEO_EXTENSIONS = {'.mov', '.mp4', '.avi', '.webm', '.mkv', '.m4v', '.3gp', '.flv'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic'}

# MIME type mappings
VIDEO_MIME_TYPES = {
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.avi': 'video/x-msvideo',
    '.webm': 'video/webm',
    '.mkv': 'video/x-matroska',
    '.m4v': 'video/x-m4v',
    '.3gp': 'video/3gpp',
    '.flv': 'video/x-flv'
}

IMAGE_MIME_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.heic': 'image/heic'
}

def get_media_type_and_mime(file_path: str) -> tuple[str, str]:
    """Determine if file is image or video and return MIME type.
    
    Args:
        file_path: File path or GCS URL
        
    Returns:
        Tuple of (media_type, mime_type)
        media_type: 'image', 'video', or 'unknown'
        mime_type: Corresponding MIME type or empty string
    """
    from pathlib import Path
    
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext in VIDEO_EXTENSIONS:
        mime_type = VIDEO_MIME_TYPES.get(file_ext, 'video/mp4')
        return ('video', mime_type)
    elif file_ext in IMAGE_EXTENSIONS:
        mime_type = IMAGE_MIME_TYPES.get(file_ext, 'image/jpeg')
        return ('image', mime_type)
    else:
        return ('unknown', '')


class GeminiClient:
    """Wrapper for Google Gemini AI SDK.
    
    Provides simplified methods for common operations:
    - Text generation
    - Text embeddings
    - Vision (image + text) generation
    - Batch operations
    
    Abstracts SDK details to protect against future API changes.
    """
    
    # Class-level cache for Vertex AI resources (shared across all instances)
    _vertexai_initialized = False
    _multimodal_model = None
    _vertexai_lock = threading.Lock()  # Initialize at class level to prevent race conditions
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini client.
        
        Args:
            api_key: Optional API key. If not provided, reads from GOOGLE_GEMINI_API_KEY secret.
            
        Raises:
            ValueError: If API key is not found
        """
        if api_key is None:
            api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_GEMINI_API_KEY not found in secrets")
        
        self.client = genai.Client(api_key=api_key)
        
        print("[GeminiClient] ✅ Initialized successfully")
    
    def generate_content(
        self, 
        prompt: Union[str, List[Any]], 
        model: str = "gemini-2.5-flash",
        **kwargs
    ) -> str:
        """Generate text content using Gemini.
        
        Args:
            prompt: Text prompt or list of parts (for multi-modal prompts)
                    Can include strings, Part objects, or dicts with {mime_type, data}
            model: Model name (gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-pro, etc.)
            **kwargs: Additional generation parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If generation fails
            
        Example:
            client = GeminiClient()
            response = client.generate_content("Write a haiku about technology")
            print(response)
        """
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Auto-convert raw dicts to proper Part objects for backward compatibility
                if isinstance(prompt, list):
                    converted_prompt = []
                    for item in prompt:
                        if isinstance(item, dict) and 'mime_type' in item and 'data' in item:
                            # Convert base64 dict to proper Part object
                            print(f"[GeminiClient] Converting dict to Part object (mime_type: {item['mime_type']})")
                            converted_prompt.append(
                                types.Part.from_bytes(
                                    data=base64.b64decode(item['data']),
                                    mime_type=item['mime_type']
                                )
                            )
                        else:
                            converted_prompt.append(item)
                    prompt = converted_prompt
                
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    **kwargs
                )
                return response.text
            except Exception as e:
                last_error = e
                # Retry on 503 UNAVAILABLE
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    print(f"[GeminiClient] 🔄 Attempt {attempt + 1}/{max_retries} failed with 503 (UNAVAILABLE). Retrying in {2**(attempt+1)}s...")
                    import time
                    time.sleep(2**(attempt+1))
                    continue
                
                # If model is not found (404), try fallback to 1.5 if 2.5 was requested
                if "404" in str(e) and model == "gemini-2.5-flash":
                    print(f"[GeminiClient] 🔄 Model {model} not found. Attempting fallback to gemini-1.5-flash...")
                    model = "gemini-2.0-flash-exp" # Switching to a known exp model as fallback
                    continue

                print(f"[GeminiClient] ❌ Content generation failed: {e}")
                print(f"[GeminiClient] Traceback: {traceback.format_exc()}")
                raise
        
        raise last_error
    
    def embed_text(
        self,
        text: str,
        model: str = "text-embedding-004",
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int = 768
    ) -> List[float]:
        """Generate text embeddings using Gemini.
        
        Args:
            text: Text to embed
            model: Model to use for embedding (default: text-embedding-004)
            task_type: Task type (RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY, etc.) - for API compatibility but not used in new SDK
            output_dimensionality: Dimensionality of output embeddings (default: 768)
            
        Returns:
            List of float values representing the embedding
            
        Raises:
            Exception: If embedding generation fails
            
        Example:
            client = GeminiClient()
            embedding = client.embed_text("Machine learning is fascinating", output_dimensionality=768)
            print(f"Embedding dimension: {len(embedding)}")
        """
        try:
            response = self.client.models.embed_content(
                model=model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=output_dimensionality)
            )
            # New SDK returns embeddings in response.embeddings[0].values
            if hasattr(response, 'embeddings') and len(response.embeddings) > 0:
                return response.embeddings[0].values
            elif hasattr(response, 'embedding'):
                return response.embedding
            else:
                raise ValueError(f"Unexpected response format: {response}")
        except Exception as e:
            print(f"[GeminiClient] ❌ Text embedding failed: {e}")
            print(f"[GeminiClient] Traceback: {traceback.format_exc()}")
            raise
    
    def embed_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        model: str = "multimodalembedding@001",
        output_dimensionality: int = 1408
    ) -> List[float]:
        """Generate image embeddings using Vertex AI's multimodal model.
        
        NOTE: This uses Vertex AI SDK because the multimodalembedding@001 model
        is only available through Vertex AI, not google.genai SDK.
        
        Args:
            image_bytes: Raw image bytes
            mime_type: MIME type of the image (default: image/jpeg)
            model: Model to use for embedding (default: multimodalembedding@001)
            output_dimensionality: Dimensionality of output embeddings (default: 1408)
            
        Returns:
            List of float values representing the image embedding
            
        Raises:
            Exception: If embedding generation fails
            
        Example:
            client = GeminiClient()
            with open("image.jpg", "rb") as f:
                image_bytes = f.read()
            embedding = client.embed_image(image_bytes)
            print(f"Image embedding dimension: {len(embedding)}")
        """
        try:
            # Initialize Vertex AI and model only once (with thread-safe locking)
            if not GeminiClient._vertexai_initialized:
                with GeminiClient._vertexai_lock:
                    # Double-check after acquiring lock
                    if not GeminiClient._vertexai_initialized:
                        import vertexai
                        from vertexai.vision_models import MultiModalEmbeddingModel
                        from app.libs.firebase_config import get_firebase_credentials_dict
                        from google.oauth2 import service_account
                        
                        print("[GeminiClient] 🔄 Initializing Vertex AI for image embeddings (one-time setup)...")
                        
                        try:
                            creds_dict = get_firebase_credentials_dict()
                            credentials = service_account.Credentials.from_service_account_info(creds_dict)
                            project_id = os.environ.get("GCP_PROJECT_ID")
                            
                            vertexai.init(
                                project=project_id,
                                location="us-central1",
                                credentials=credentials
                            )
                            
                            # Load the model once and cache it
                            GeminiClient._multimodal_model = MultiModalEmbeddingModel.from_pretrained(model)
                            GeminiClient._vertexai_initialized = True
                            
                            print("[GeminiClient] ✅ Vertex AI initialized and model cached successfully")
                            
                        except Exception as init_error:
                            print(f"[GeminiClient] ❌ Failed to initialize Vertex AI for image embedding: {init_error}")
                            raise
            
            # Import Image class (lightweight import, no overhead)
            from vertexai.vision_models import Image
            
            # Create Image object from bytes
            image = Image(image_bytes=image_bytes)
            
            # Use the cached model instance
            embeddings = GeminiClient._multimodal_model.get_embeddings(
                image=image,
                dimension=output_dimensionality
            )
            
            # Extract the image embedding vector
            image_embedding = embeddings.image_embedding
            
            print(f"[GeminiClient] ✅ Image embedding generated (dimension: {len(image_embedding)})")
            return image_embedding
            
        except Exception as e:
            print(f"[GeminiClient] ❌ Image embedding failed: {e}")
            print(f"[GeminiClient] Traceback: {traceback.format_exc()}")
            raise
    
    def embed_text_for_image_search(
        self,
        text: str,
        model: str = "multimodalembedding@001",
        output_dimensionality: int = 1408
    ) -> List[float]:
        """Generate text embedding compatible with image search using Vertex AI.
        
        This creates a text embedding that can be used to search in image vector space,
        enabling cross-modal search (text query → find similar images).
        
        NOTE: This uses Vertex AI SDK because cross-modal embeddings require
        the multimodalembedding@001 model which is only available in Vertex AI.
        
        Args:
            text: Text query to embed
            model: Model name (must be 'multimodalembedding@001')
            output_dimensionality: Embedding dimension (1408 for cross-modal)
            
        Returns:
            List of floats representing the text embedding (1408 dimensions)
            
        Raises:
            Exception: If embedding generation fails
            
        Example:
            client = GeminiClient()
            query_embedding = client.embed_text_for_image_search("red car")
            # Use this embedding to search against image embeddings
        """
        try:
            # Import Vertex AI components
            import vertexai
            from vertexai.vision_models import MultiModalEmbeddingModel
            from app.libs.firebase_config import get_firebase_credentials_dict
            from google.oauth2 import service_account
            
            # Initialize Vertex AI
            try:
                creds_dict = get_firebase_credentials_dict()
                credentials = service_account.Credentials.from_service_account_info(creds_dict)
                project_id = os.environ.get("GCP_PROJECT_ID")
                
                vertexai.init(
                    project=project_id,
                    location="us-central1",
                    credentials=credentials
                )
            except Exception as init_error:
                print(f"[GeminiClient] ❌ Failed to initialize Vertex AI for text-to-image: {init_error}")
                raise
            
            # Load the multimodal embedding model
            model_instance = MultiModalEmbeddingModel.from_pretrained(model)
            
            # Generate embedding with contextual_text parameter for cross-modal search
            embeddings = model_instance.get_embeddings(
                contextual_text=text,
                dimension=output_dimensionality
            )
            
            # Extract the text embedding vector
            text_embedding = embeddings.text_embedding
            
            print(f"[GeminiClient] ✅ Text-for-image embedding generated (dimension: {len(text_embedding)})")
            return text_embedding
            
        except Exception as e:
            print(f"[GeminiClient] ❌ Text-for-image embedding failed: {e}")
            print(f"[GeminiClient] Traceback: {traceback.format_exc()}")
            raise
    
    def generate_with_image(
        self,
        text_prompt: str,
        image_data: bytes,
        model: str = "gemini-2.5-flash",
        mime_type: str = "image/jpeg",
        **kwargs
    ) -> str:
        """Generate content using vision model (text + image).
        
        Args:
            text_prompt: Text part of the prompt
            image_data: Image bytes
            model: Vision-capable model name (gemini-2.5-flash, gemini-2.5-pro, etc.)
            mime_type: Image MIME type (image/jpeg, image/png, image/webp)
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If vision generation fails
            
        Example:
            client = GeminiClient()
            with open('machine.jpg', 'rb') as f:
                image_bytes = f.read()
            description = client.generate_with_image(
                "Describe this machine part",
                image_bytes
            )
            print(description)
        """
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use Part.from_bytes for proper image handling
                image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
                
                # Combine text and image
                contents = [text_prompt, image_part]
                
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    **kwargs
                )
                return response.text
            except Exception as e:
                last_error = e
                # Retry on 503 UNAVAILABLE
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    print(f"[GeminiClient] 🔄 Vision Attempt {attempt + 1}/{max_retries} failed with 503 (UNAVAILABLE). Retrying in {2**(attempt+1)}s...")
                    import time
                    time.sleep(2**(attempt+1))
                    continue
                
                print(f"[GeminiClient] ❌ Vision generation failed: {e}")
                print(f"[GeminiClient] Image size: {len(image_data)} bytes, MIME: {mime_type}")
                # print(f"[GeminiClient] Traceback: {traceback.format_exc()}")
                raise
        
        raise last_error
    
    def generate_with_video(
        self,
        text_prompt: str,
        video_data: bytes,
        model: str = "gemini-2.5-flash",
        mime_type: str = "video/mp4",
        **kwargs
    ) -> str:
        """Generate content using vision model (text + video).
        
        Args:
            text_prompt: Text part of the prompt
            video_data: Video bytes
            model: Vision-capable model name (gemini-2.5-flash, gemini-2.5-pro, etc.)
            mime_type: Video MIME type (video/mp4, video/quicktime, etc.)
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If vision generation fails
            
        Example:
            client = GeminiClient()
            with open('movie.mp4', 'rb') as f:
                video_bytes = f.read()
            description = client.generate_with_video(
                "Describe this scene",
                video_bytes
            )
            print(description)
        """
        try:
            # Use Part.from_bytes for proper video handling
            video_part = types.Part.from_bytes(data=video_data, mime_type=mime_type)
            
            # Combine text and video
            contents = [text_prompt, video_part]
            
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                **kwargs
            )
            return response.text
        except Exception as e:
            print(f"[GeminiClient] ❌ Vision generation failed: {e}")
            print(f"[GeminiClient] Video size: {len(video_data)} bytes, MIME: {mime_type}")
            print(f"[GeminiClient] Traceback: {traceback.format_exc()}")
            raise
    
    def batch_embed(
        self,
        texts: List[str],
        model: str = "text-embedding-004",
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int = 768
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts (batch operation).
        
        Args:
            texts: List of texts to embed
            model: Embedding model name
            task_type: Type of embedding task
            output_dimensionality: Vector dimension
            
        Returns:
            List of embedding vectors
            
        Note:
            This currently processes texts sequentially. For true batch processing,
            you may need to implement async/parallel processing.
            
        Example:
            client = GeminiClient()
            texts = ["First text", "Second text", "Third text"]
            embeddings = client.batch_embed(texts)
            print(f"Generated {len(embeddings)} embeddings")
        """
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = self.embed_text(text, model, task_type, output_dimensionality)
                embeddings.append(embedding)
            except Exception as e:
                print(f"[GeminiClient] ⚠️ Failed to embed text {i+1}/{len(texts)}: {e}")
                # Optionally: append None or empty list for failed embeddings
                # embeddings.append(None)
                raise  # Re-raise to maintain strict error handling
        return embeddings
    
    def get_raw_client(self) -> genai.Client:
        """Get the underlying Gemini client for advanced usage.
        
        Use this only when you need SDK features not exposed by the wrapper.
        Prefer using wrapper methods when possible to maintain abstraction.
        
        Returns:
            The raw genai.Client instance
            
        Example:
            client = GeminiClient()
            raw = client.get_raw_client()
            # Use raw client for advanced features
        """
        return self.client


# Singleton pattern for efficient reuse across the application
_gemini_client_instance: Optional[GeminiClient] = None


def get_gemini_client(api_key: Optional[str] = None) -> GeminiClient:
    """Get the singleton Gemini client instance.
    
    Creates one if it doesn't exist. Reuses the existing instance for efficiency.
    
    Args:
        api_key: Optional API key. Only used on first call to create the singleton.
                Subsequent calls ignore this parameter.
    
    Returns:
        Shared GeminiClient instance
        
    Example:
        from app.libs.gemini_client import get_gemini_client
        
        # In any API or library file:
        client = get_gemini_client()
        response = client.generate_content("Hello!")
    """
    global _gemini_client_instance
    if _gemini_client_instance is None:
        _gemini_client_instance = GeminiClient(api_key=api_key)
    return _gemini_client_instance


def reset_gemini_client():
    """Reset the singleton instance.
    
    Useful for testing or when you need to reinitialize with a different API key.
    """
    global _gemini_client_instance
    _gemini_client_instance = None
