"""Constraint Manager Library

Provides core business logic for managing domain-specific constraints:
- Firestore client initialization
- User domain retrieval
- Active constraint queries with filtering
- Gemini-compatible formatting
- Constraint statistics

Supported Domains:
- dcdc: Datacenter Deployment and Ops
- healthcare: Healthcare Operations and Safety
- finance: Financial Trading Infrastructure
- manufacturing: Manufacturing and Industrial Technologies
- general: General/Others
"""

import databutton as db
import json
from typing import List, Dict, Optional
from google.cloud import firestore
from google.oauth2 import service_account


# Domain configuration
DOMAINS = {
    'dcdc': 'Datacenter Deployment and Ops (DCDC)',
    'media_entertainment': 'Media and Entertainment',
    'healthcare': 'Healthcare Operations and Safety',
    'finance': 'Financial Trading Infrastructure',
    'manufacturing': 'Manufacturing and Industrial Technologies',
    'general': 'General/Others'
}

# Severity ordering for sorting (higher = more critical)
SEVERITY_ORDER = {
    'critical': 3,
    'warning': 2,
    'info': 1
}

# Category labels
CATEGORIES = {
    'safety': 'Safety',
    'compliance': 'Compliance',
    'workflow': 'Workflow',
    'equipment': 'Equipment',
    'policy': 'Policy'
}

# App ID for Firestore path
APP_ID = 'techtalk'


def get_firestore_client() -> firestore.Client:
    """Initialize authenticated Firestore client using Firebase Admin credentials.
    
    Returns:
        firestore.Client: Authenticated Firestore client
        
    Raises:
        Exception: If credentials are missing or invalid
    """
    try:
        credentials_json = db.secrets.get("FIREBASE_ADMIN_CREDENTIALS")
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        client = firestore.Client(
            credentials=credentials,
            project=credentials_dict['project_id']
        )
        return client
    except Exception as e:
        print(f"❌ Failed to initialize Firestore client: {e}")
        raise


def get_user_domain(user_id: str) -> Optional[str]:
    """Fetch user's assigned domain from their profile.
    
    Args:
        user_id: Firebase user ID
        
    Returns:
        str: Domain key (e.g., 'dcdc', 'healthcare') or None if not set
        
    Path: users/{user_id}
    Field: assignedDomain
    """
    try:
        client = get_firestore_client()
        # Changed path to root users collection
        user_ref = client.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            # Look for assignedDomain set by admin
            domain = user_data.get('assignedDomain', None)
            
            # Fallback to old location for backward compatibility if needed, 
            # but priority is assignedDomain
            if not domain:
                print(f"ℹ️ No assignedDomain for user {user_id}, checking legacy settings...")
                try:
                    profile_ref = user_ref.collection('profile').document('settings')
                    profile_doc = profile_ref.get()
                    if profile_doc.exists:
                        domain = profile_doc.to_dict().get('selectedDomain')
                except Exception as e:
                    print(f"⚠️ Error checking legacy domain: {e}")

            # Validate domain
            if domain and domain in DOMAINS:
                print(f"✅ User {user_id} domain: {domain}")
                return domain
            else:
                print(f"⚠️ User {user_id} has invalid or no domain set (found: {domain})")
                return None
        else:
            print(f"⚠️ No user profile found for {user_id}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching user domain: {e}")
        return None


def get_user_company(user_id: str) -> Optional[str]:
    """Fetch user's company from their profile.
    
    Args:
        user_id: Firebase user ID
        
    Returns:
        str: Company identifier or None if not set
        
    Path: users/{user_id}
    """
    try:
        client = get_firestore_client()
        user_ref = client.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            company = user_data.get('company', None)
            
            if company:
                print(f"✅ User {user_id} company: {company}")
                return company
            else:
                print(f"⚠️ User {user_id} has no company set")
                return None
        else:
            print(f"⚠️ No user profile found for {user_id}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching user company: {e}")
        return None


def get_user_role(user_id: str) -> Optional[str]:
    """Fetch user's role from their profile.
    
    Args:
        user_id: Firebase user ID
        
    Returns:
        str: User role ('technician', 'company_admin', 'system_admin') or None
        
    Path: users/{user_id}
    """
    try:
        client = get_firestore_client()
        user_ref = client.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            role = user_data.get('role', 'technician')  # Default to technician
            print(f"✅ User {user_id} role: {role}")
            return role
        else:
            print(f"⚠️ No user profile found for {user_id}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching user role: {e}")
        return None

def get_user_role_and_company(user_id: str) -> tuple[Optional[str], Optional[str]]:
    """Fetch user's role and company in a single Firestore read.
    
    Args:
        user_id: Firebase user ID
        
    Returns:
        tuple: (role, company) - Both can be None if user not found
        
    Path: users/{user_id}
    """
    try:
        client = get_firestore_client()
        user_ref = client.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            role = user_data.get('role', 'technician')  # Default to technician
            company = user_data.get('company', None)
            
            print(f"✅ User {user_id} role: {role}")
            print(f"✅ User {user_id} company: {company}")
            
            return role, company
        else:
            print(f"⚠️ No user profile found for {user_id}")
            return None, None
            
    except Exception as e:
        print(f"❌ Error fetching user role and company: {e}")
        return None, None
        
def get_active_constraints(
    user_id: str,
    domain: str,
    current_phase: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """Query active constraints filtered by user's company and domain.
    
    Args:
        user_id: Firebase user ID (to determine company)
        domain: Domain key to filter by
        current_phase: Optional phase to filter by (e.g., 'assessment', 'diagnosis')
        limit: Maximum number of constraints to return (default: 50)
        
    Returns:
        List[Dict]: List of constraint documents, sorted by severity (critical first)
        
    Query Path: artifacts/{APP_ID}/constraints
    Query: where('company', '==', user_company).where('domain', '==', domain).where('active', '==', True)
    """
    try:
        client = get_firestore_client()
        
        # Get user's company first
        user_company = get_user_company(user_id)
        if not user_company:
            print(f"⚠️ User {user_id} has no company, returning empty constraints")
            return []
        
        # Build query - NEW PATH: constraints at app level
        query = (
            client.collection('artifacts')
            .document(APP_ID)
            .collection('constraints')
            .where('company', '==', user_company)
            .where('domain', '==', domain)
            .where('active', '==', True)
        )
        
        # Add optional phase filter
        if current_phase:
            query = query.where('context.applicablePhases', 'array_contains', current_phase)
        
        # Execute query
        docs = query.limit(limit).stream()
        
        # Convert to list with metadata
        constraints = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            constraints.append(data)
        
        # Sort by severity: critical > warning > info
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        constraints.sort(key=lambda x: severity_order.get(x.get('severity', 'info'), 3))
        
        print(f"✅ Retrieved {len(constraints)} active constraints for company '{user_company}' in domain '{domain}'")
        return constraints
        
    except Exception as e:
        print(f"❌ Error fetching constraints: {e}")
        return []


def format_constraints_for_gemini(constraints: List[Dict]) -> str:
    """Format constraints into readable text for Gemini system instruction.
    
    Groups constraints by severity with visual indicators:
    - 🔴 Critical: Must follow strictly
    - 🟡 Warning: Strong recommendation
    - 🔵 Info: Helpful context
    
    Args:
        constraints: List of constraint dictionaries
        
    Returns:
        str: Formatted text ready for Gemini system prompt
    """
    if not constraints:
        return "No active constraints for this domain."
    
    # Group by severity
    critical = [c for c in constraints if c.get('severity') == 'critical']
    warning = [c for c in constraints if c.get('severity') == 'warning']
    info = [c for c in constraints if c.get('severity') == 'info']
    
    output = []
    output.append("=" * 80)
    output.append("DOMAIN-SPECIFIC CONSTRAINTS")
    output.append("=" * 80)
    output.append("")
    output.append("**IMPORTANT INSTRUCTIONS:**")
    output.append("- When these constraints apply to your response, reference them explicitly")
    output.append("- Use format: '[Constraint: <Rule>]' in your response")
    output.append("- Critical constraints MUST be followed")
    output.append("- Warning constraints should be followed unless user explicitly overrides")
    output.append("- Info constraints provide helpful context")
    output.append("")
    
    # Critical constraints
    if critical:
        output.append("🔴 CRITICAL CONSTRAINTS (MUST FOLLOW)")
        output.append("-" * 80)
        for i, c in enumerate(critical, 1):
            output.append(f"{i}. [{c.get('category', 'general').upper()}] {c.get('rule', '')}")
            output.append(f"   Reasoning: {c.get('reasoning', '')}")
            
            # Add context if available
            context = c.get('context', {})
            if context.get('example'):
                output.append(f"   Example: {context.get('example')}")
            if context.get('consequence'):
                output.append(f"   ⚠️ Consequence: {context.get('consequence')}")
            output.append("")
    
    # Warning constraints
    if warning:
        output.append("🟡 WARNING CONSTRAINTS (STRONG RECOMMENDATION)")
        output.append("-" * 80)
        for i, c in enumerate(warning, 1):
            output.append(f"{i}. [{c.get('category', 'general').upper()}] {c.get('rule', '')}")
            output.append(f"   Reasoning: {c.get('reasoning', '')}")
            
            context = c.get('context', {})
            if context.get('example'):
                output.append(f"   Example: {context.get('example')}")
            output.append("")
    
    # Info constraints
    if info:
        output.append("🔵 INFO CONSTRAINTS (HELPFUL CONTEXT)")
        output.append("-" * 80)
        for i, c in enumerate(info, 1):
            output.append(f"{i}. [{c.get('category', 'general').upper()}] {c.get('rule', '')}")
            output.append(f"   Reasoning: {c.get('reasoning', '')}")
            output.append("")
    
    output.append("=" * 80)
    output.append(f"Total: {len(constraints)} constraints ({len(critical)} critical, {len(warning)} warning, {len(info)} info)")
    output.append("=" * 80)
    
    return "\n".join(output)


def get_constraint_summary(constraints: List[Dict]) -> Dict:
    """Generate statistics about constraints.
    
    Args:
        constraints: List of constraint dictionaries
        
    Returns:
        Dict with counts by severity and category:
        {
            'total': int,
            'by_severity': {'critical': int, 'warning': int, 'info': int},
            'by_category': {'safety': int, 'compliance': int, ...}
        }
    """
    summary = {
        'total': len(constraints),
        'by_severity': {'critical': 0, 'warning': 0, 'info': 0},
        'by_category': {'safety': 0, 'compliance': 0, 'workflow': 0, 'equipment': 0, 'policy': 0}
    }
    
    for constraint in constraints:
        # Count by severity
        severity = constraint.get('severity', 'info')
        if severity in summary['by_severity']:
            summary['by_severity'][severity] += 1
        
        # Count by category
        category = constraint.get('category', 'policy')
        if category in summary['by_category']:
            summary['by_category'][category] += 1
    
    return summary


def get_all_constraints(user_id: str, domain: Optional[str] = None, active_only: bool = True) -> List[Dict]:
    """Get all constraints for a user, optionally filtered by domain.
    
    Useful for management UI and admin dashboards.
    
    Args:
        user_id: Firebase user ID
        domain: Optional domain filter
        active_only: If True, only return active constraints (default: True)
        
    Returns:
        List[Dict]: List of all matching constraints
    """
    try:
        client = get_firestore_client()
        constraints_ref = (
            client.collection('artifacts')
            .document(APP_ID)
            .collection('users')
            .document(user_id)
            .collection('constraints')
        )
        
        # Build query
        query = constraints_ref
        
        if domain:
            query = query.where('domain', '==', domain)
        
        if active_only:
            query = query.where('active', '==', True)
        
        # Order by creation date (newest first)
        query = query.order_by('createdAt', direction=firestore.Query.DESCENDING)
        
        # Execute
        docs = query.stream()
        constraints = []
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            constraints.append(data)
        
        print(f"✅ Retrieved {len(constraints)} constraints (domain: {domain or 'all'}, active: {active_only})")
        return constraints
        
    except Exception as e:
        print(f"❌ Error fetching all constraints: {e}")
        return []


def get_constraints(
    company: Optional[str] = None,
    filters: Optional[Dict] = None
) -> List[Dict]:
    """Get constraints with company-based multi-tenancy and optional filtering.
    
    This is the new company-based query method that replaces user-scoped queries.
    
    Args:
        company: Company identifier to filter by. If None, returns all constraints
                 (for system admins only)
        filters: Optional dict of filters:
            - id: str (exact document ID match)
            - domain: str
            - category: str
            - severity: str
            - active: bool
    
    Returns:
        List[Dict]: List of matching constraints with document IDs
        
    Path: artifacts/{APP_ID}/constraints (company-scoped)
    """
    try:
        client = get_firestore_client()
        constraints_ref = (
            client.collection('artifacts')
            .document(APP_ID)
            .collection('constraints')
        )
        
        # Handle exact ID lookup
        if filters and 'id' in filters:
            doc = constraints_ref.document(filters['id']).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                
                # If company filter specified, verify it matches
                if company and data.get('company') != company:
                    return []  # Access denied - wrong company
                
                # Convert timestamps
                if 'createdAt' in data and data['createdAt']:
                    data['createdAt'] = data['createdAt'].isoformat() if hasattr(data['createdAt'], 'isoformat') else str(data['createdAt'])
                if 'updatedAt' in data and data['updatedAt']:
                    data['updatedAt'] = data['updatedAt'].isoformat() if hasattr(data['updatedAt'], 'isoformat') else str(data['updatedAt'])
                
                return [data]
            return []
        
        # Build query with filters
        query = constraints_ref
        
        # Company filter (required for company admins)
        if company:
            query = query.where('company', '==', company)
        
        # Additional filters
        if filters:
            if 'domain' in filters:
                query = query.where('domain', '==', filters['domain'])
            if 'category' in filters:
                query = query.where('category', '==', filters['category'])
            if 'severity' in filters:
                query = query.where('severity', '==', filters['severity'])
            if 'active' in filters:
                query = query.where('active', '==', filters['active'])
        
        # Execute query
        docs = query.stream()
        constraints = []
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            
            # Convert timestamps to ISO strings
            if 'createdAt' in data and data['createdAt']:
                data['createdAt'] = data['createdAt'].isoformat() if hasattr(data['createdAt'], 'isoformat') else str(data['createdAt'])
            if 'updatedAt' in data and data['updatedAt']:
                data['updatedAt'] = data['updatedAt'].isoformat() if hasattr(data['updatedAt'], 'isoformat') else str(data['updatedAt'])
            
            constraints.append(data)
        
        print(f"✅ Retrieved {len(constraints)} constraints (company: {company or 'all'})")
        return constraints
        
    except Exception as e:
        print(f"❌ Error getting constraints: {e}")
        return []


def create_constraint(user_id: str, company: Optional[str], constraint_data: Dict) -> str:
    """Create a new constraint.
    
    Args:
        user_id: Firebase user ID (creator)
        company: Company identifier to assign constraint to. Required for company-wide constraints.
        constraint_data: Dictionary containing constraint fields:
            - domain: str (required)
            - category: str (required)
            - severity: str (required: 'critical', 'warning', or 'info')
            - rule: str (required)
            - reasoning: str (optional)
            - source: str (optional)
            - context: dict (optional)
            - active: bool (optional, default: True)
    
    Returns:
        str: Document ID of created constraint
        
    Raises:
        ValueError: If required fields are missing
        Exception: If Firestore operation fails
    """
    # Validate required fields
    required_fields = ['domain', 'category', 'severity', 'rule']
    for field in required_fields:
        if field not in constraint_data:
            raise ValueError(f"Missing required field: {field}")
    
    try:
        client = get_firestore_client()
        constraints_ref = (
            client.collection('artifacts')
            .document(APP_ID)
            .collection('constraints')
        )
        
        # Prepare document data
        doc_data = {
            'userId': user_id,
            'company': company,
            'domain': constraint_data['domain'],
            'category': constraint_data['category'],
            'severity': constraint_data['severity'],
            'rule': constraint_data['rule'],
            'reasoning': constraint_data.get('reasoning', ''),
            'source': constraint_data.get('source', ''),
            'active': constraint_data.get('active', True),
            'createdAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP,
        }
        
        # Add context if provided
        if 'context' in constraint_data:
            doc_data['context'] = constraint_data['context']
        
        # Create document
        doc_ref = constraints_ref.document()
        doc_ref.set(doc_data)
        
        print(f"✅ Created constraint {doc_ref.id} for user {user_id} in company {company}")
        return doc_ref.id
        
    except Exception as e:
        print(f"❌ Error creating constraint: {e}")
        raise


def update_constraint(constraint_id: str, update_data: Dict, company: Optional[str] = None) -> None:
    """Update an existing constraint with company-based access control.
    
    Args:
        constraint_id: Document ID of constraint to update
        update_data: Dictionary of fields to update
        company: Optional company filter for access control. If provided,
                 will verify constraint belongs to this company before updating.
    
    Raises:
        ValueError: If constraint not found or access denied
        Exception: If Firestore operation fails
        
    Path: artifacts/{APP_ID}/constraints/{constraintId}
    """
    try:
        client = get_firestore_client()
        constraints_ref = (
            client.collection('artifacts')
            .document(APP_ID)
            .collection('constraints')
        )
        
        # Get the constraint document
        doc_ref = constraints_ref.document(constraint_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise ValueError(f"Constraint {constraint_id} not found")
        
        # Verify company access if specified
        if company:
            doc_data = doc.to_dict()
            if doc_data.get('company') != company:
                raise ValueError(f"Access denied: Constraint {constraint_id} does not belong to company {company}")
        
        # Add updatedAt timestamp
        update_data['updatedAt'] = firestore.SERVER_TIMESTAMP
        
        # Update document
        doc_ref.update(update_data)
        
        print(f"✅ Updated constraint {constraint_id}")
        
    except Exception as e:
        print(f"❌ Error updating constraint: {e}")
        raise


def delete_constraint(constraint_id: str, company: Optional[str] = None) -> None:
    """Delete a constraint.
    
    Args:
        constraint_id: Document ID of constraint to delete
        company: Optional company filter for access control.
    
    Raises:
        ValueError: If constraint not found or access denied
        Exception: If Firestore operation fails
    """
    try:
        client = get_firestore_client()
        constraints_ref = (
            client.collection('artifacts')
            .document(APP_ID)
            .collection('constraints')
        )
        
        doc_ref = constraints_ref.document(constraint_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise ValueError(f"Constraint {constraint_id} not found")
        
        # Verify company access if specified
        if company:
            doc_data = doc.to_dict()
            if doc_data.get('company') != company:
                raise ValueError(f"Access denied: Constraint {constraint_id} does not belong to company {company}")
        
        # Delete document
        doc_ref.delete()
        
        print(f"✅ Deleted constraint {constraint_id}")
        
    except Exception as e:
        print(f"❌ Error deleting constraint: {e}")
        raise
