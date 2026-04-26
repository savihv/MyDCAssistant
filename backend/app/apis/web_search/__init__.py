from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import re
import databutton as db
import tempfile
import os
from datetime import datetime
import json
from google.cloud.firestore import Client as FirestoreClient  # type: ignore
from app.auth import AuthorizedUser
import time
from tavily import TavilyClient  # type: ignore
from app.libs.firebase_config import get_firestore_client, get_firebase_credentials_dict


router = APIRouter()

class WebSearchRequest(BaseModel):
    query: str = Field(..., description="The query to search for on the web")
    search_depth: str = Field("advanced", description="Search depth (basic, advanced)")
    max_results: int = Field(5, description="Maximum number of results to return")
    include_domains: Optional[List[str]] = Field(None, description="Domains to specifically include in search")
    exclude_domains: Optional[List[str]] = Field(None, description="Domains to exclude from search")

class WebSearchResult(BaseModel):
    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="URL of the search result")
    content: str = Field(..., description="Content snippet from the search result")
    score: float = Field(..., description="Relevance score")
    source: str = Field(..., description="Source domain")

class WebSearchResponse(BaseModel):
    results: List[WebSearchResult] = Field(..., description="List of search results")
    query: str = Field(..., description="Original query")
    query_id: str = Field(..., description="Unique ID for this query")
    company_context: Optional[str] = Field(None, description="Company context used for search, if any")

# Function to log web search usage
def log_web_search(user_data: dict, query: str, results: list, company_targeted: bool):
    """
    Log web search usage for analytics and auditing
    """
    try:
        # Initialize Firestore client
        db_client = get_firestore_client()
        
        # Create a web search log document
        search_log_ref = db_client.collection('webSearchLogs').document()
        
        # Prepare log data
        log_data = {
            'id': search_log_ref.id,
            'timestamp': datetime.now(),
            'userId': user_data.get('uid'),
            'userEmail': user_data.get('email'),
            'role': user_data.get('role'),
            'company': user_data.get('company'),
            'organization': user_data.get('organization'),
            'query': query,
            'resultsCount': len(results),
            'domains': list(set([result.get('source', '') for result in results])),
            'mostRelevantDomain': results[0].get('source', '') if results else '',
            'companyTargeted': company_targeted,
            'companyDomainsFound': any(
                domain.endswith(company_domain) 
                for domain in set([result.get('source', '') for result in results])
                for company_domain in [f".{re.sub(r'[^a-z0-9]', '', user_data.get('company', '').lower())}."]
                if user_data.get('company')
            ) if company_targeted else False
        }
        
        # Save the log
        search_log_ref.set(log_data)
        
    except Exception as e:
        print(f"Error logging web search: {e}")
        # Don't fail the search process if logging fails
        pass

# Cache for storing search results (simple implementation)
search_cache: dict[str, WebSearchResponse] = {}

@router.post("/search")
def search_web(request: WebSearchRequest, user: AuthorizedUser) -> WebSearchResponse:
    """Search the web for relevant technical discussions based on the query"""
    
    # Initialize variables for temporary files
    try:
        # Get user data and system settings
        user_data = None
        web_search_enabled = True  # Default to enabled
        preferred_sources = []     # Default empty list
        blocked_sources = []       # Default empty list
        
        try:
            # Get Firestore instance
            db_client = get_firestore_client()
            # Try to get user info from Firestore
            if user and user.sub:
                user_ref = db_client.collection('users').document(user.sub)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    print(f"Retrieved user data for {user.sub}: {user_data.get('email')}, Company: {user_data.get('company')}")
            
            # Get web search settings
            settings_ref = db_client.collection('settings').document('system')
            settings_doc = settings_ref.get()
            
            if settings_doc.exists:
                settings = settings_doc.to_dict()
                if 'webSearch' in settings:
                    web_search_settings = settings['webSearch']
                    web_search_enabled = web_search_settings.get('enabled', True)
                    preferred_sources = web_search_settings.get('preferredSources', [])
                    blocked_sources = web_search_settings.get('blockedSources', [])
            
            # If web search is disabled globally and no override, return empty results
            if not web_search_enabled and not request.include_domains:
                print("Web search is disabled in admin settings")
                return WebSearchResponse(
                    results=[],
                    query=request.query,
                    query_id=f"disabled_{int(time.time())}",
                    company_context=user_data.get('company') if user_data else None
                )
        
        except Exception as error:
            print(f"Error retrieving user data or settings: {str(error)}")
            # Continue with search even if we can't get user data
        
        # Simple cache key
        cache_key = f"{hash(request.query)}_{request.search_depth}_{request.max_results}"
        
        # Include domain filters in cache key if present
        if request.include_domains:
            cache_key += f"_inc_{'_'.join(sorted(request.include_domains))}"
        if request.exclude_domains:
            cache_key += f"_exc_{'_'.join(sorted(request.exclude_domains))}"
            
        # Check cache
        if cache_key in search_cache:
            print(f"Using cached web search results for query: {request.query[:30]}...")
            return search_cache[cache_key]

        # Get Tavily API key
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_api_key:
            raise HTTPException(status_code=500, detail="Tavily API key not configured")

        # Initialize Tavily client
        tavily_client = TavilyClient(api_key=tavily_api_key)
        
        print(f"Searching web with Tavily API for query: {request.query}")
        
        # Configure search parameters
        search_params = {
            "query": request.query,
            "search_depth": request.search_depth,
            "max_results": request.max_results
        }
        
        # Priority for domain targeting:
        # 1. User explicitly specified domains in request
        # 2. Admin-configured preferred sources
        # 3. Company domain derived from user data
        # 4. Default to no domain filtering
        
        # Check if we need to target company domains
        company_domains = []
        company = None
        
        if user_data and 'company' in user_data and user_data['company']:
            company = user_data['company']
            # Simple domain generation from company name - in real app would need proper domain lookup
            company_name = user_data['company'].lower()
            # Replace spaces with nothing and remove special chars
            company_domain = re.sub(r'[^a-z0-9]', '', company_name)
            # Common domain endings to try
            domain_suffixes = [".com", ".org", ".net", ".co"]
            company_domains = [f"{company_domain}{suffix}" for suffix in domain_suffixes]
            print(f"Generated potential company domains: {company_domains}")
        
        # Apply domain targeting based on priority
        if request.include_domains:
            # User specified domains take precedence
            search_params["include_domains"] = request.include_domains
            print(f"Using user-specified domains: {request.include_domains}")
        elif preferred_sources and len(preferred_sources) > 0:
            # If we have admin-configured preferred sources, use them
            search_params["include_domains"] = preferred_sources
            print(f"Using admin-configured preferred domains: {preferred_sources}")
        elif company_domains:
            # If we have company domains and no other preferences, use company domains
            search_params["include_domains"] = company_domains
            print(f"Using company domains: {company_domains}")
            
        # Apply domain exclusions based on priority
        excluded_domains = []
        if request.exclude_domains:
            # User specified exclusions take precedence
            excluded_domains.extend(request.exclude_domains)
            
        if blocked_sources and len(blocked_sources) > 0:
            # Add admin-configured blocked sources
            excluded_domains.extend(blocked_sources)
            
        if excluded_domains:
            search_params["exclude_domains"] = list(set(excluded_domains))  # Remove duplicates
            print(f"Excluding domains: {search_params['exclude_domains']}")
            
        # Perform the search
        search_response = tavily_client.search(**search_params)
        
        # Process results
        results = []
        for result in search_response.get('results', []):
            # Extract domain from URL
            url = result.get('url', '')
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            source = domain_match.group(1) if domain_match else 'unknown'
            
            # Format the result
            formatted_result = WebSearchResult(
                title=result.get('title', 'Untitled'),
                url=url,
                content=result.get('content', ''),
                score=result.get('score', 0.0),
                source=source
            )
            results.append(formatted_result)
        
        # We already got user data above, use it for logging if available
        # If we didn't get user data above, set a basic record with uid
        if not user_data and user:
            user_data = {'uid': user.sub}
        
        # Create response object with company context
        response = WebSearchResponse(
            results=results,
            query=request.query,
            query_id=search_response.get('query_id', ''),
            company_context=company
        )
        
        # Log the search with company context if available
        try:
            # Log search results with company targeting info
            log_web_search(
                user_data=user_data or {},
                query=request.query,
                results=[r.dict() for r in results],
                company_targeted=(company is not None)
            )

        except Exception as log_error:
            print(f"Error logging search: {str(log_error)}")
            # Don't fail the search if logging fails
        
        # Cache the response
        search_cache[cache_key] = response
        
        # Limit cache size
        if len(search_cache) > 50:  # Higher limit for search cache
            oldest_key = list(search_cache.keys())[0]
            search_cache.pop(oldest_key)
        
        return response

    except Exception as e:
        error_message = f"Error searching web: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)
