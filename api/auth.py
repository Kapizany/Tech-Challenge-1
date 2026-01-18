from fastapi.security.api_key import APIKeyHeader
from fastapi import Depends
from fastapi import HTTPException

# API Key Auth
API_KEY = "mysecretkey"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True
