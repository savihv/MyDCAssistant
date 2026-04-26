"""Configure cache directories for ML models.

This module MUST be imported before any code that uses the 'unstructured' library.
It sets the UNSTRUCTURED_CACHE_DIR environment variable to ensure models are cached
at /tmp/unstructured_cache, which persists across requests in the same container.

The unstructured library will automatically download models (e.g., YOLOX for layout detection)
to this directory on first use, then reuse them on subsequent requests.
"""

import os                                                
# Set cache directory BEFORE unstructured library is imported anywhere
CACHE_DIR = "/tmp/unstructured_cache"
os.environ["UNSTRUCTURED_CACHE_DIR"] = CACHE_DIR 


print(f"[CACHE_CONFIG] ✅ Set UNSTRUCTURED_CACHE_DIR to: {CACHE_DIR}")
print("[CACHE_CONFIG] Models will auto-download on first document processing and be cached for reuse.")
