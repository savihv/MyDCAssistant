from fastapi import HTTPException
from app.libs.firebase_config import get_firestore_client

# Note: This utility requires 'google-cloud-firestore' to be installed.

def verify_admin_role(user_data: dict) -> bool:
    """
    Checks if the user's role string contains 'admin'.
    Case-insensitive.
    """
    role = user_data.get('role', '')
    if not isinstance(role, str):
        return False
    return 'admin' in role.lower()

def get_user_data(uid: str, credentials_path: str) -> dict:
    """
    Retrieves a user's document from the 'users' collection in Firestore.
    
    Args:
        uid: The user's unique ID (from Firebase Auth).
        credentials_path: The local file path to the Google Cloud service account JSON.

    Returns:
        A dictionary containing the user's data.

    Raises:
        HTTPException: If the user is not found (404) or if there's a problem
                       communicating with Firestore (500).
    """
    try:
        # It's generally better to pass the client instance, but for simplicity
        # in this refactoring, we'll create it here.
        db_client = get_firestore_client()
        user_doc_ref = db_client.collection('users').document(uid)
        user_doc = user_doc_ref.get()
        
        if not user_doc.exists:
            # This is a client error, so a 4xx is appropriate.
            raise HTTPException(status_code=404, detail=f"User with ID '{uid}' not found in database.")
            
        return user_doc.to_dict()
        
    except HTTPException:
        # Re-raise the specific HTTPException to preserve the status code.
        raise
    except Exception as e:
        # Catch any other potential errors (e.g., network issues, permissions)
        # and wrap them in a generic 500 server error.
        print(f"❌ [USER_UTILS] Error getting user data for UID '{uid}': {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred while retrieving user data.")



