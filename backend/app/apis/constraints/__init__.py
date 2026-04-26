"""Constraint Management API

Provides endpoints for managing user-defined constraints:
- List constraints with filtering
- Create new constraints
- Update existing constraints
- Delete constraints
- Import pre-configured templates
- Get available template metadata
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.auth import AuthorizedUser
from app.libs.constraint_manager import (
    create_constraint,
    get_constraints,
    update_constraint,
    delete_constraint,
    get_user_role,
    get_user_company,
    get_user_role_and_company,
)
from app.libs.constraint_templates import (
    import_templates_for_user,
    get_available_templates,
    load_dcdc_templates,
)

router = APIRouter()


# ============================================================================
# Authorization Helpers
# ============================================================================

def verify_admin_role(user_id: str) -> tuple[str, str]:
    """Verify user is company_admin or system_admin.
    
    Args:
        user_id: Firebase user ID
        
    Returns:
        tuple: (role, company) where company is None for system_admin
        
    Raises:
        HTTPException: If user is not authorized (403)
    """
    # Get both role and company in a single Firestore read
    role, company = get_user_role_and_company(user_id)
    
    if not role or role not in ['company_admin', 'system_admin']:
        raise HTTPException(
            status_code=403,
            detail="Access denied. Only company administrators and system administrators can manage constraints."
        )
    
    # Verify company for company_admin
    if role == 'company_admin':
        if not company:
            raise HTTPException(
                status_code=400,
                detail="Company admin must have a company assigned"
            )
    else:
        # system_admin can have company = None
        company = None
    
    return role, company
    
# ============================================================================
# Request/Response Models
# ============================================================================

class ConstraintCreate(BaseModel):
    """Request model for creating a new constraint"""
    domain: str = Field(..., description="Domain (e.g., 'dcdc', 'network', 'security')")
    category: str = Field(..., description="Category (e.g., 'safety', 'compliance', 'workflow')")
    severity: str = Field(..., description="Severity level: 'critical', 'warning', or 'info'")
    rule: str = Field(..., min_length=1, description="The constraint rule text")
    reasoning: str = Field("", description="Why this constraint exists")
    source: str = Field("", description="Source or reference (e.g., 'OSHA 1910.333')")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context metadata")
    active: bool = Field(True, description="Whether constraint is active")


class ConstraintUpdate(BaseModel):
    """Request model for updating a constraint"""
    domain: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    rule: Optional[str] = None
    reasoning: Optional[str] = None
    source: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


class ConstraintResponse(BaseModel):
    """Response model for a single constraint"""
    id: str
    userId: str
    domain: str
    category: str
    severity: str
    rule: str
    reasoning: str
    source: str
    context: Optional[Dict[str, Any]] = None
    active: bool
    createdAt: str
    updatedAt: str


class ConstraintListResponse(BaseModel):
    """Response model for list of constraints"""
    constraints: List[ConstraintResponse]
    total: int


class ImportTemplatesRequest(BaseModel):
    """Request model for importing constraint templates"""
    domain: str = Field(..., description="Domain to assign to imported constraints")
    templateSet: str = Field("dcdc", description="Template set to import (currently only 'dcdc')")
    skipDuplicates: bool = Field(True, description="Skip templates with duplicate rule text")


class ImportTemplatesResponse(BaseModel):
    """Response model for template import"""
    imported: int
    skipped: int
    message: str


class TemplateMetadata(BaseModel):
    """Metadata about a template set"""
    name: str
    description: str
    count: int
    categories: List[str]
    domain: str
    version: str


class AvailableTemplatesResponse(BaseModel):
    """Response model for available templates"""
    templates: Dict[str, TemplateMetadata]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/constraints")
async def list_constraints(
    user: AuthorizedUser,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    active_only: bool = True,
) -> ConstraintListResponse:
    """List all constraints for the authenticated user with optional filtering.
    
    Query Parameters:
    - domain: Filter by domain (e.g., 'dcdc')
    - category: Filter by category (e.g., 'safety')
    - severity: Filter by severity (e.g., 'critical')
    - active_only: If true, only return active constraints (default: true)
    """
    try:
        # Determine company filter based on role (optimized single read)
        role, company_filter = get_user_role_and_company(user.sub)
        
        if role == 'company_admin':
            # Company admins can only see their company's constraints
            if not company_filter:
                raise HTTPException(status_code=400, detail="Company admin must have a company assigned")
        elif role == 'system_admin':
            # System admins can see all constraints (no company filter)
            company_filter = None
        else:
            # Technicians can only see their company's constraints
            if not company_filter:
                return ConstraintListResponse(constraints=[], total=0)
        
        # Build filters
        filters = {}
        if domain:
            filters['domain'] = domain
        if category:
            filters['category'] = category
        if severity:
            filters['severity'] = severity
        if active_only:
            filters['active'] = True
        
        # Get constraints with company filter
        constraints = get_constraints(company=company_filter, filters=filters)
        
        # Convert to response format
        constraint_responses = []
        for constraint in constraints:
            constraint_responses.append(
                ConstraintResponse(
                    id=constraint['id'],
                    userId=constraint['userId'],
                    domain=constraint.get('domain', ''),
                    category=constraint.get('category', 'general'),
                    severity=constraint.get('severity', 'info'),
                    rule=constraint.get('rule', ''),
                    reasoning=constraint.get('reasoning', ''),
                    source=constraint.get('source', ''),
                    context=constraint.get('context'),
                    active=constraint.get('active', True),
                    createdAt=constraint.get('createdAt', ''),
                    updatedAt=constraint.get('updatedAt', ''),
                )
            )
        
        return ConstraintListResponse(
            constraints=constraint_responses,
            total=len(constraint_responses),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list constraints: {str(e)}")


@router.post("/constraints")
async def create_new_constraint(
    user: AuthorizedUser,
    body: ConstraintCreate,
) -> ConstraintResponse:
    """Create a new constraint for the authenticated user."""
    try:
        # Verify role and get company
        role, company = verify_admin_role(user.sub)
        
        # Prepare constraint data
        constraint_data = {
            'domain': body.domain,
            'category': body.category,
            'severity': body.severity,
            'rule': body.rule,
            'reasoning': body.reasoning,
            'source': body.source,
            'active': body.active,
        }
        
        if body.context:
            constraint_data['context'] = body.context
        
        # Create constraint with company parameter
        constraint_id = create_constraint(user.sub, company, constraint_data)
        
        # Fetch the created constraint to return
        constraints = get_constraints(company=company, filters={'id': constraint_id})
        
        if not constraints:
            raise HTTPException(status_code=500, detail="Failed to retrieve created constraint")
        
        created = constraints[0]
        
        return ConstraintResponse(
            id=created['id'],
            userId=created['userId'],
            domain=created.get('domain', ''),
            category=created.get('category', 'general'),
            severity=created.get('severity', 'info'),
            rule=created.get('rule', ''),
            reasoning=created.get('reasoning', ''),
            source=created.get('source', ''),
            context=created.get('context'),
            active=created.get('active', True),
            createdAt=created.get('createdAt', ''),
            updatedAt=created.get('updatedAt', ''),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create constraint: {str(e)}")


@router.put("/constraints/{constraint_id}")
async def update_existing_constraint(
    user: AuthorizedUser,
    constraint_id: str,
    body: ConstraintUpdate,
) -> ConstraintResponse:
    """Update an existing constraint. Only admins from the same company can update it."""
    try:
        # Verify role and get company
        role, company = verify_admin_role(user.sub)
        
        # Verify ownership and access
        existing = get_constraints(company=company, filters={'id': constraint_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Constraint not found or access denied")
        
        # Prepare update data (only include fields that were provided)
        update_data = {}
        if body.domain is not None:
            update_data['domain'] = body.domain
        if body.category is not None:
            update_data['category'] = body.category
        if body.severity is not None:
            update_data['severity'] = body.severity
        if body.rule is not None:
            update_data['rule'] = body.rule
        if body.reasoning is not None:
            update_data['reasoning'] = body.reasoning
        if body.source is not None:
            update_data['source'] = body.source
        if body.context is not None:
            update_data['context'] = body.context
        if body.active is not None:
            update_data['active'] = body.active
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update constraint with company-based access control
        update_constraint(constraint_id, update_data, company=company)
        
        # Fetch updated constraint
        updated = get_constraints(company=company, filters={'id': constraint_id})
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated constraint")
        
        updated_constraint = updated[0]
        
        return ConstraintResponse(
            id=updated_constraint['id'],
            userId=updated_constraint['userId'],
            domain=updated_constraint.get('domain', ''),
            category=updated_constraint.get('category', 'general'),
            severity=updated_constraint.get('severity', 'info'),
            rule=updated_constraint.get('rule', ''),
            reasoning=updated_constraint.get('reasoning', ''),
            source=updated_constraint.get('source', ''),
            context=updated_constraint.get('context'),
            active=updated_constraint.get('active', True),
            createdAt=updated_constraint.get('createdAt', ''),
            updatedAt=updated_constraint.get('updatedAt', ''),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update constraint: {str(e)}")


@router.delete("/constraints/{constraint_id}")
async def delete_existing_constraint(
    user: AuthorizedUser,
    constraint_id: str,
) -> Dict[str, str]:
    """Delete a constraint. Only admins from the same company can delete it."""
    try:
        # Verify role and get company
        role, company = verify_admin_role(user.sub)
        
        # Verify ownership and access
        existing = get_constraints(company=company, filters={'id': constraint_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Constraint not found or access denied")
        
        # Delete constraint with company-based access control
        delete_constraint(constraint_id, company=company)
        
        return {"message": "Constraint deleted successfully", "id": constraint_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete constraint: {str(e)}")


@router.post("/constraints/import-templates")
async def import_constraint_templates(
    user: AuthorizedUser,
    body: ImportTemplatesRequest,
) -> ImportTemplatesResponse:
    """Import pre-configured constraint templates for the authenticated user.
    
    Requires: company_admin or system_admin role
    Currently supports 'dcdc' (Data Center Deployment & Commissioning) templates.
    """
    try:
        # Verify user is admin
        role, user_company = verify_admin_role(user.sub)
        
        # For company admins, use their company
        if role == 'company_admin':
            constraint_company = user_company
        else:
            # System admin - use their company if set
            constraint_company = get_user_company(user.sub)
            if not constraint_company:
                raise HTTPException(
                    status_code=400,
                    detail="System admin must have a company set to import templates"
                )
        
        # Validate template set
        if body.templateSet not in ['dcdc']:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown template set: {body.templateSet}. Available: 'dcdc'"
            )
        
        # Get total template count for comparison
        templates = load_dcdc_templates()
        total_templates = len(templates)
        
        # Import templates with company parameter
        imported_count = import_templates_for_user(
            user_id=user.sub,
            company=constraint_company,
            domain=body.domain,
            templates=templates,
            skip_duplicates=body.skipDuplicates,
        )
        
        skipped_count = total_templates - imported_count
        
        return ImportTemplatesResponse(
            imported=imported_count,
            skipped=skipped_count,
            message=f"Successfully imported {imported_count} constraints for company '{constraint_company}', skipped {skipped_count} duplicates",
        )
    
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template set not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import templates: {str(e)}")


@router.get("/constraints/templates/available")
async def get_available_constraint_templates(
    user: AuthorizedUser,
) -> AvailableTemplatesResponse:
    """Get metadata about available constraint template sets."""
    try:
        templates_metadata = get_available_templates()
        
        # Convert to response format
        templates_response = {}
        for template_id, metadata in templates_metadata.items():
            templates_response[template_id] = TemplateMetadata(
                name=metadata['name'],
                description=metadata['description'],
                count=metadata['count'],
                categories=metadata['categories'],
                domain=metadata['domain'],
                version=metadata['version'],
            )
        
        return AvailableTemplatesResponse(templates=templates_response)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available templates: {str(e)}"
        )
