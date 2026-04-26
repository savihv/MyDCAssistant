# This module handles application startup tasks, specifically ensuring that
# pre-cached machine learning models are available in the local filesystem.

import os
import databutton as db
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the target directory for the unstructured.io models cache.
# Using /tmp/ is standard for temporary, non-persistent files in cloud environments.
CACHE_DIR = "/tmp/unstructured_cache"
MODEL_ARCHIVE_KEY = "unstructured_models.zip"

def ensure_models_are_available():
    """
    Checks if the VLM models are present in the local cache. If not, it downloads
    the pre-packaged model archive from db.storage and unpacks it. This function
    is designed to be called once when the application instance starts.
    """
    # Critical: Set the environment variable BEFORE any part of the app can
    # import and use the 'unstructured' library.
    os.environ["UNSTRUCTURED_CACHE_DIR"] = CACHE_DIR
    logger.info(f"Set environment variable UNSTRUCTURED_CACHE_DIR to: {CACHE_DIR}")

    # Check if the cache directory already exists and is populated.
    # This prevents re-downloading on a warm instance.
    if os.path.exists(CACHE_DIR) and os.listdir(CACHE_DIR):
        logger.info("✅ VLM models already available in local cache.")
        return

    logger.info("VLM models not found locally. Attempting to hydrate from db.storage...")
    archive_path = os.path.join("/tmp", f"{MODEL_ARCHIVE_KEY}")
    
    try:
        # Create the cache directory if it doesn't exist.
        os.makedirs(CACHE_DIR, exist_ok=True)

        # Download the model archive from db.storage.
        logger.info(f"Downloading '{MODEL_ARCHIVE_KEY}' from db.storage.binary...")
        model_archive_bytes = db.storage.binary.get(MODEL_ARCHIVE_KEY)

        # Write the downloaded bytes to a temporary zip file.
        with open(archive_path, "wb") as f:
            f.write(model_archive_bytes)
        logger.info(f"Model archive saved temporarily to {archive_path}")

        # Unpack the archive into the designated cache directory.
        logger.info(f"Unpacking archive to {CACHE_DIR}...")
        shutil.unpack_archive(archive_path, CACHE_DIR)

        # Verify that unpacking was successful
        if not os.listdir(CACHE_DIR):
             raise Exception("Unpacking completed, but the cache directory is still empty.")
        
        logger.info("✅ Successfully hydrated VLM models to local cache.")

    except FileNotFoundError:
        logger.critical(f"CRITICAL: '{MODEL_ARCHIVE_KEY}' not found in db.storage. The 'vlm' processing strategy will fail and fallback will be attempted.")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to hydrate VLM models due to an error: {e}", exc_info=True)
    finally:
        # Clean up the temporary zip file regardless of success or failure.
        if os.path.exists(archive_path):
            os.remove(archive_path)
            logger.info(f"Cleaned up temporary archive file: {archive_path}")
