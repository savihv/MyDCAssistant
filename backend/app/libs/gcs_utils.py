# src/app/libs/gcs_utils.py
import logging
from google.cloud import storage
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_gcs_client(credentials_json_string: str) -> storage.Client:
    """
    Initializes and returns a Google Cloud Storage client using service account credentials.

    Args:
        credentials_json_string: The JSON string of the service account credentials.

    Returns:
        A storage.Client object.
    """
    try:
        # The credentials will be loaded from the JSON string.
        credentials = service_account.Credentials.from_service_account_info(
            eval(credentials_json_string) # Using eval to parse the string to a dict
        )
        client = storage.Client(credentials=credentials)
        logger.info("Successfully initialized Google Cloud Storage client.")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize GCS client: {e}")
        raise

def upload_to_gcs(
    client: storage.Client,
    bucket_name: str,
    destination_blob_name: str,
    data_bytes: bytes,
    content_type: str = "image/png",
) -> str:
    """
    Uploads data bytes to a specified Google Cloud Storage bucket.

    Args:
        client: The GCS client.
        bucket_name: The name of the GCS bucket.
        destination_blob_name: The full path (key) for the object in the bucket.
        data_bytes: The binary data to upload.
        content_type: The content type of the data.

    Returns:
        The GCS URI of the uploaded file (e.g., gs://bucket_name/blob_name).
    """
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_string(data_bytes, content_type=content_type)

        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        logger.info(f"Successfully uploaded {len(data_bytes)} bytes to {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logger.error(f"Failed to upload to GCS bucket '{bucket_name}': {e}")
        raise

