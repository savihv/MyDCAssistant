from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, Depends, HTTPException
from app.auth import AuthorizedUser
from firebase_admin import auth, firestore
import databutton as db
import json
from datetime import datetime, timedelta, timezone
from app.libs.firebase_config import get_firestore_client

router = APIRouter()

# Centralized Firebase initialization in src/main.py makes the old init block obsolete.
# We can now directly use the firestore client.
# db_firestore = firestore.client()

class AdminMetricsResponse(BaseModel):
    totalDocuments: int = 0
    totalFeedback: int = 0
    totalUsers: int = 0
    totalCompanies: int = 0
    totalResponses: int = 0
    ragUsageRate: float = 0
    webSearchUsageRate: float = 0
    totalWebSearches: int = 0
    companyWebsiteHits: int = 0
    totalTechnicians: int = 0
    activeTechnicians: int = 0
    responsesUsingRAG: int = 0
    responsesUsingWeb: int = 0
    documentsPerCompany: Dict[str, int] = Field(default_factory=dict)
    documentTrends: List[Dict[str, Any]] = Field(default_factory=list)
    responseTimeAvg: Optional[float] = None
    recentDocuments: List[Dict[str, Any]] = Field(default_factory=list)
    usersByRole: Dict[str, int] = Field(default_factory=lambda: {"system_admin": 0, "company_admin": 0, "technician": 0})

@router.get("/admin/metrics")
async def get_admin_metrics(
    user: AuthorizedUser,
    company: Optional[str] = Query(None, description="Filter metrics by company")
):
    """Get admin dashboard metrics"""
    try:
        # Get user custom claims to check role
        # Force Firebase App initialization before using the admin SDK
        try:
            get_firestore_client()
            user_record = auth.get_user(user.sub)
            user_claims = user_record.custom_claims or {}
            role = user_claims.get('role', 'technician')
            
            # Ensure the user is an admin
            if role not in ['system_admin', 'company_admin']:
                raise HTTPException(status_code=403, detail="Not authorized to view admin metrics")
            
            # System admin can see all data, company admin only sees their company
            is_system_admin = role == 'system_admin'
            company_filter = company if company else (user_claims.get('company') if not is_system_admin else None)
        except Exception as auth_err:
            print(f"Error verifying admin role: {auth_err}")
            company_filter = company
            is_system_admin = True  # Fallback for development/testing
        
        # Initialize metrics with default values
        metrics = AdminMetricsResponse()
        
        try:
            # Get document count
            documents_ref = get_firestore_client().collection('documents')
            try:
                if company_filter:
                    documents_query = documents_ref.where('company', '==', company_filter).get()
                    documents_list = list(documents_query)
                    metrics.totalDocuments = len(documents_list)
                    
                    # Calculate document trends
                    from datetime import datetime
                    from collections import defaultdict
                    
                    monthly_counts = defaultdict(int)
                    for doc in documents_list:
                        doc_data = doc.to_dict()
                        created_at = doc_data.get('createdAt')
                        if created_at:
                            # Handle Firestore timestamp
                            if hasattr(created_at, 'seconds'):
                                doc_date = datetime.fromtimestamp(created_at.seconds)
                            elif isinstance(created_at, datetime):
                                doc_date = created_at
                            else:
                                continue
                            
                            month_key = doc_date.strftime('%Y-%m')
                            monthly_counts[month_key] += 1
                    
                    # Convert to sorted list of dicts
                    document_trends = [
                        {"month": month, "count": count}
                        for month, count in sorted(monthly_counts.items())
                    ]
                    metrics.documentTrends = document_trends[-12:]  # Last 12 months
                else:
                    # Get all documents for system admin
                    documents_query = documents_ref.get()
                    documents_list = list(documents_query)
                    metrics.totalDocuments = len(documents_list)
                    
                    # Calculate documents per company
                    documents_per_company = {}
                    for doc in documents_list:
                        doc_data = doc.to_dict()
                        doc_company = doc_data.get('company', 'Unknown')
                        documents_per_company[doc_company] = documents_per_company.get(doc_company, 0) + 1
                    
                    # Only set if we have data to avoid overriding default empty dict
                    if documents_per_company:
                        metrics.documentsPerCompany = documents_per_company
            except Exception as inner_err:
                print(f"Error in documents query: {inner_err}")
                # Keep default values for these metrics
        except Exception as doc_err:
            print(f"Error fetching document metrics: {doc_err}")
            # Keep default values for these metrics
        
        try:
            # Get user count and company count
            users_ref = get_firestore_client().collection('users')
            try:
                # Initialize user role counts
                user_role_counts = {
                    "system_admin": 0,
                    "company_admin": 0,
                    "technician": 0
                }
                unique_companies = set()
                technician_count = 0
                active_technician_count = 0
                
                if company_filter:
                    users_query = users_ref.where('company', '==', company_filter).get()
                    users_list = list(users_query)
                    metrics.totalUsers = len(users_list)
                    
                    # Count users by role and gather companies
                    for user_doc in users_list:
                        user_data = user_doc.to_dict()
                        role = user_data.get('role', 'technician')
                        if role in user_role_counts:
                            user_role_counts[role] += 1
                        
                        # Count technicians and check activity
                        if role == 'technician':
                            technician_count += 1
                            # Consider active if they have activity in last 30 days
                            last_active = user_data.get('lastActive')
                            if last_active:
                                from datetime import datetime, timedelta
                                if hasattr(last_active, 'seconds'):
                                    last_active_dt = datetime.fromtimestamp(last_active.seconds)
                                elif isinstance(last_active, datetime):
                                    last_active_dt = last_active
                                else:
                                    last_active_dt = None
                                
                                if last_active_dt and last_active_dt > datetime.now(timezone.utc) - timedelta(days=30):
                                    active_technician_count += 1
                        
                        company_name = user_data.get('company')
                        if company_name:
                            unique_companies.add(company_name)

                else:
                    users_query = users_ref.get()
                    users_list = list(users_query)
                    metrics.totalUsers = len(users_list)
                    
                    # Count users by role and gather companies
                    for user_doc in users_list:
                        user_data = user_doc.to_dict()
                        role = user_data.get('role', 'technician')
                        if role in user_role_counts:
                            user_role_counts[role] += 1
                        
                        # Count technicians for system admin view
                        if role == 'technician':
                            technician_count += 1
                            last_active = user_data.get('lastActive')
                            if last_active:
                                from datetime import datetime, timedelta
                                if hasattr(last_active, 'seconds'):
                                    last_active_dt = datetime.fromtimestamp(last_active.seconds)
                                elif isinstance(last_active, datetime):
                                    last_active_dt = last_active
                                else:
                                    last_active_dt = None
                                
                                if last_active_dt and last_active_dt > datetime.now(timezone.utc) - timedelta(days=30):
                                    active_technician_count += 1
                        
                        company_name = user_data.get('company')
                        if company_name:
                            unique_companies.add(company_name)
                
                # Set the usersByRole and totalCompanies fields in metrics
                metrics.usersByRole = user_role_counts
                metrics.totalCompanies = len(unique_companies)
                metrics.totalTechnicians = technician_count
                metrics.activeTechnicians = active_technician_count

            except Exception as inner_err:
                print(f"Error in users query: {inner_err}")
                # Keep default values for these metrics
        except Exception as user_err:
            print(f"Error fetching user metrics: {user_err}")
            # Keep default values for these metrics
        
        try:
            # Get feedback count
            feedback_ref = get_firestore_client().collection('feedback')
            try:
                if company_filter:
                    feedback_query = feedback_ref.where('company', '==', company_filter).get()
                    metrics.totalFeedback = len(feedback_query)
                else:
                    # Get all feedback for system admin
                    feedback_query = feedback_ref.get()
                    metrics.totalFeedback = len(feedback_query)
            except Exception as inner_err:
                print(f"Error in feedback query: {inner_err}")
                # Keep default values for these metrics
        except Exception as feedback_err:
            print(f"Error fetching feedback metrics: {feedback_err}")
            # Keep default values for these metrics
            
        try:
            # Get response count and RAG usage
            responses_ref = get_firestore_client().collection('responseLogs')
            rag_used_count = 0
            web_search_used_count = 0
            total_web_searches = 0
            company_website_hits = 0
            
            try:
                if company_filter:
                    responses_query = responses_ref.where('company', '==', company_filter).get()
                    all_responses = list(responses_query)
                    metrics.totalResponses = len(all_responses)
                    
                    for resp in all_responses:
                        resp_data = resp.to_dict()
                        if resp_data.get('usedRAG', False):
                            rag_used_count += 1
                        
                        # Track web search usage
                        if resp_data.get('usedWebSearch', False):
                            web_search_used_count += 1
                            web_sources = resp_data.get('webSources', [])
                            total_web_searches += len(web_sources)
                            
                            # Count company website hits
                            for source in web_sources:
                                source_url = source.get('url', '') if isinstance(source, dict) else str(source)
                                # Check if company name appears in URL
                                if company_filter and company_filter.lower() in source_url.lower():
                                    company_website_hits += 1
                else:
                    # Get all responses for system admin
                    responses_query = responses_ref.get()
                    all_responses = list(responses_query)
                    metrics.totalResponses = len(all_responses)
                    
                    for resp in all_responses:
                        resp_data = resp.to_dict()
                        if resp_data.get('usedRAG', False):
                            rag_used_count += 1
                        
                        # Track web search usage (system admin)
                        if resp_data.get('usedWebSearch', False):
                            web_search_used_count += 1
                            web_sources = resp_data.get('webSources', [])
                            total_web_searches += len(web_sources)
                
                # Calculate usage rates only if we have responses
                if metrics.totalResponses > 0:
                    metrics.ragUsageRate = (rag_used_count / metrics.totalResponses) * 100
                    metrics.webSearchUsageRate = (web_search_used_count / metrics.totalResponses) * 100
                else:
                    metrics.ragUsageRate = 0
                    metrics.webSearchUsageRate = 0
                
                # Set the counts
                metrics.responsesUsingRAG = rag_used_count
                metrics.responsesUsingWeb = web_search_used_count
                metrics.totalWebSearches = total_web_searches
                metrics.companyWebsiteHits = company_website_hits
            except Exception as inner_err:
                print(f"Error in responses query: {inner_err}")
                # Keep default values for these metrics
        except Exception as response_err:
            print(f"Error fetching response metrics: {response_err}")
            # Keep default values for these metrics
        
        return metrics
    
    except Exception as e:
        print(f"Error getting admin metrics: {e}")
        # Return empty metrics with explicit error message
        metrics = AdminMetricsResponse()
        # Add error message to help with debugging - won't be visible to end users
        print(f"Returning empty metrics due to error: {str(e)}")
        return metrics

class ReprocessRequest(BaseModel):
    document_id: str

class ReprocessResponse(BaseModel):
    message: str
    document_id: str

@router.post("/admin/reprocess_document", response_model=ReprocessResponse)
async def reprocess_stuck_document(
    request: ReprocessRequest,
    user: AuthorizedUser
):
    """
    Dummy endpoint to reprocess a document that might be stuck.
    In a real scenario, this would trigger a background task.
    """
    # Authorization check
    user_record = auth.get_user(user.sub)
    user_claims = user_record.custom_claims or {}
    role = user_claims.get('role')
    
    if role not in ['system_admin', 'company_admin']:
        raise HTTPException(status_code=403, detail="Not authorized for this action")

    doc_ref = get_firestore_client().collection('documents').document(request.document_id)
    doc_snapshot = doc_ref.get()

    if not doc_snapshot.exists:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Company admin can only reprocess documents for their own company
    if role == 'company_admin':
        doc_company = doc_snapshot.to_dict().get('company')
        admin_company = user_claims.get('company')
        if doc_company != admin_company:
            raise HTTPException(status_code=403, detail="Not authorized to reprocess this document")

    # In a real implementation, you would trigger your processing logic here.
    # For now, we just log and return a success message.
    print(f"Reprocessing requested for document: {request.document_id} by user {user.email}")
    
    # Optionally, you could update the document status
    # doc_ref.update({"status": "processing"})
    
    return ReprocessResponse(
        message="Document reprocessing initiated.",
        document_id=request.document_id
    )
