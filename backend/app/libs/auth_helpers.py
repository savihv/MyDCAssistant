from fastapi import Header, HTTPException
import databutton as db

async def verify_internal_worker_request(authorization: str = Header(None)):
    """
    Dependency to verify that a request is from an internal worker.
    It checks for a 'Bearer' token in the 'Authorization' header
    and validates it against the 'INTERNAL_WORKER_AUTH_KEY' secret.
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()

    if parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme. Must be Bearer.")
    elif len(parts) == 1:
        raise HTTPException(status_code=401, detail="Token not found")
    elif len(parts) > 2:
        raise HTTPException(status_code=401, detail="Token contains spaces")

    token = parts[1]
    expected_token = db.secrets.get("INTERNAL_WORKER_AUTH_KEY")

    if not expected_token:
        print("CRITICAL: INTERNAL_WORKER_AUTH_KEY secret is not set.")
        raise HTTPException(status_code=500, detail="Internal server configuration error: Auth key not set.")

    if token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid internal authentication key.")
    
    return True
