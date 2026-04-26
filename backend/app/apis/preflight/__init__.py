"""Pre-flight design validation API endpoints.
Public endpoints for lead generation: validate BoM compatibility and estimate costs.
"""

from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.libs.bom_validator import parse_bom
from app.libs.license_manager import LicenseManager
from google.cloud import firestore
import json
import os

router = APIRouter(prefix="/preflight", tags=["preflight"])

class CostEstimate(BaseModel):
    tier: str
    monthly_cost: float
    gpus_included: int

class PreflightValidationResponse(BaseModel):
    valid: bool
    gpu_count: int
    switch_count: int
    warnings: List[str]
    errors: List[str]
    cost_estimation: CostEstimate
    compatibility_score: int

def get_db():
    credentials_json = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if credentials_json:
        from google.oauth2 import service_account
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return firestore.Client(credentials=credentials)
    else:
        return firestore.Client(project="test_project_123")

@router.post("/validate-design", response_model=PreflightValidationResponse)
async def validate_design(file: UploadFile = File(...)):
    """
    Public-facing endpoint to validate a design BoM (Bill of Materials) 
    and return an estimated monthly cost based on the GPU count.
    """
    try:
        content = await file.read()
        result = parse_bom(content, file.filename or "upload.csv")
        
        gpu_count = result.get("gpu_count", 0)
        switch_count = result.get("switch_count", 0)
        
        # Initialize LicenseManager
        lm = LicenseManager(get_db())
        
        # Estimate cost
        # Find appropriate tier
        tier = "Starter"
        if gpu_count > lm.TIER_LIMITS["Starter"]["max_gpus"]:
            tier = "Pro"
        if gpu_count > lm.TIER_LIMITS["Pro"]["max_gpus"]:
            tier = "Enterprise"
            
        monthly_cost = lm.estimate_monthly_cost(gpu_count, custom_tier=tier)
        
        cost_estimate = CostEstimate(
            tier=tier,
            monthly_cost=monthly_cost,
            gpus_included=gpu_count
        )
        
        # Calculate a mock compatibility score based on valid/warnings
        score = 100
        if not result.get("valid", False):
            score -= 50
        score -= len(result.get("warnings", [])) * 5
        score = max(0, score)
        
        return PreflightValidationResponse(
            valid=result.get("valid", False),
            gpu_count=gpu_count,
            switch_count=switch_count,
            warnings=result.get("warnings", []),
            errors=result.get("errors", []),
            cost_estimation=cost_estimate,
            compatibility_score=score
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
