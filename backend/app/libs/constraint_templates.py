"""Constraint Template Management Library

Provides functions to load pre-configured constraint templates
and import them into user constraint collections in Firestore.
"""

from typing import List, Dict
from firebase_admin import firestore
from app.libs.constraint_manager import get_firestore_client, APP_ID
from app.libs.dcdc_constraint_templates import DCDC_TEMPLATES


def load_dcdc_templates() -> List[Dict]:
    """Load DCDC (Data Center Deployment & Commissioning) constraint templates.
    
    Returns:
        List of constraint template dictionaries with fields:
        - category: str (safety, compliance, workflow, equipment, policy)
        - severity: str (critical, warning, info)
        - rule: str (the constraint rule text)
        - reasoning: str (why this constraint exists)
        - source: str (regulatory/standard reference)
        - context: dict (optional metadata)
    """
    return DCDC_TEMPLATES.get('constraints', [])


def import_templates_for_user(
    user_id: str,
    company: str,
    domain: str,
    templates: List[Dict] = None,
    skip_duplicates: bool = True
) -> int:
    """Bulk import constraint templates for a company.
    
    Args:
        user_id: Firebase user ID (who performed the import)
        company: Company identifier to assign constraints to
        domain: Domain to assign to imported constraints (e.g., 'dcdc', 'network', 'security')
        templates: List of template dicts to import. If None, loads DCDC templates.
        skip_duplicates: If True, skips templates with identical rule text (default: True)
    
    Returns:
        Number of constraints successfully imported
    """
    # Load templates if not provided
    if templates is None:
        templates = load_dcdc_templates()
    
    if not templates:
        return 0
    
    db_client = get_firestore_client()
    # Use consistent path: artifacts/{APP_ID}/constraints
    constraints_ref = (
        db_client.collection('artifacts')
        .document(APP_ID)
        .collection('constraints')
    )
    
    # Get existing constraint rules for this company to detect duplicates
    existing_rules = set()
    if skip_duplicates and company:
        # Filter by company instead of userId
        existing_constraints = constraints_ref.where('company', '==', company).stream()
        for constraint in existing_constraints:
            data = constraint.to_dict()
            if data.get('rule'):
                existing_rules.add(data['rule'])
    
    # Import templates
    imported_count = 0
    batch = db_client.batch()
    batch_count = 0
    
    for template in templates:
        rule_text = template.get('rule', '')
        
        # Skip if duplicate
        if skip_duplicates and rule_text in existing_rules:
            continue
        
        # Create constraint document
        constraint_data = {
            'userId': user_id,
            'company': company,
            'domain': domain,
            'category': template.get('category', 'general'),
            'severity': template.get('severity', 'info'),
            'rule': rule_text,
            'reasoning': template.get('reasoning', ''),
            'source': template.get('source', 'Template Import'),
            'active': True,
            'createdAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP,
        }
        
        # Add context if present
        if 'context' in template:
            constraint_data['context'] = template['context']
        
        # Add to batch
        doc_ref = constraints_ref.document()
        batch.set(doc_ref, constraint_data)
        batch_count += 1
        imported_count += 1
        
        # Firestore batch limit is 500 operations
        if batch_count >= 500:
            batch.commit()
            batch = db_client.batch()
            batch_count = 0
    
    # Commit remaining
    if batch_count > 0:
        batch.commit()
    
    return imported_count


def get_available_templates() -> Dict[str, Dict]:
    """Get metadata about available constraint template sets.
    
    Returns:
        Dictionary mapping template IDs to metadata:
        {
            'dcdc': {
                'name': 'Data Center Deployment & Commissioning',
                'description': '...',
                'count': 32,
                'categories': ['safety', 'compliance', ...],
                'domain': 'dcdc'
            }
        }
    """
    available = {}
    
    # Get DCDC template metadata
    constraints = DCDC_TEMPLATES.get('constraints', [])
    categories = list(set(c.get('category', 'general') for c in constraints))
    
    available['dcdc'] = {
        'name': 'Data Center Deployment & Commissioning (DCDC)',
        'description': DCDC_TEMPLATES.get('description', ''),
        'count': len(constraints),
        'categories': sorted(categories),
        'domain': DCDC_TEMPLATES.get('domain', 'dcdc'),
        'version': DCDC_TEMPLATES.get('version', '1.0')
    }
    
    return available
