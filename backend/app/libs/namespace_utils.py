"""
Namespace configuration utilities
Provides centralized access to company-specific namespace configuration
"""
from app.libs.firebase_config import get_firestore_client
from typing import List, Dict, Any

# Default namespaces for backward compatibility
DEFAULT_NAMESPACES = [
    {
        "id": "general", 
        "displayName": "General Documents", 
        "isDefault": True,
        "intents": ["general", "multi"]
    },
    {
        "id": "baseline", 
        "displayName": "Standard Guidelines", 
        "isDefault": False,
        "intents": ["baseline_comparison", "multi"]
    },
    {
        "id": "expert", 
        "displayName": "Expert Tips", 
        "isDefault": False,
        "intents": ["expert", "multi"]
    },
    {
        "id": "historic", 
        "displayName": "Historical Sessions", 
        "isDefault": False,
        "intents": ["historic", "multi"]
    }
]

def get_company_intent_definitions(company_id: str) -> List[Dict[str, Any]]:
    """
    Get custom intent definitions for a company
    
    Args:
        company_id: The company identifier
        
    Returns:
        List of intent definitions with structure:
        [
            {
                "id": "taxonomy",
                "displayName": "Taxonomy",
                "description": "Master ontology for domain classification",
                "keywords": ["taxonomy", "classify", "category"]
            },
            ...
        ]
    """
    try:
        db_firestore = get_firestore_client()
        settings_doc = db_firestore.collection("settings").document(company_id).get()
        
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            namespace_config = settings.get("namespaceConfiguration", {})
            
            # Check if custom intents are configured
            if namespace_config.get("enabled", False):
                intents = namespace_config.get("intents", [])
                if intents:
                    return intents
        
        # Return default intents for backward compatibility
        return [
            {
                "id": "general",
                "displayName": "General",
                "description": "General knowledge and documentation",
                "keywords": []
            },
            {
                "id": "baseline_comparison",
                "displayName": "Baseline Comparison",
                "description": "Standard guidelines and procedures",
                "keywords": ["compare", "baseline", "standard", "correct", "normal", "should be", "supposed to"]
            },
            {
                "id": "historic",
                "displayName": "Historic",
                "description": "Historical records and cases",
                "keywords": ["last time", "previous", "history", "before", "past", "how did we fix"]
            },
            {
                "id": "expert",
                "displayName": "Expert",
                "description": "Expert tips and insights",
                "keywords": ["expert", "tip", "best practice", "recommendation", "field"]
            },
            {
                "id": "multi",
                "displayName": "Multi",
                "description": "Query spans multiple categories or is very broad",
                "keywords": []
            }
        ]
        
    except Exception as e:
        print(f"[NAMESPACE_UTILS] Error fetching intent definitions for {company_id}: {e}")
        # Return default on error
        return [
            {"id": "general", "displayName": "General", "description": "General knowledge", "keywords": []},
            {"id": "baseline_comparison", "displayName": "Baseline Comparison", "description": "Standard guidelines", "keywords": ["compare", "baseline", "standard"]},
            {"id": "historic", "displayName": "Historic", "description": "Historical records", "keywords": ["last time", "previous", "history"]},
            {"id": "expert", "displayName": "Expert", "description": "Expert tips", "keywords": ["expert", "tip", "best practice"]},
            {"id": "multi", "displayName": "Multi", "description": "Broad query", "keywords": []}
        ]

def get_company_namespaces(company_id: str) -> List[str]:
    """
    Get list of namespace IDs for a company
    Returns custom namespaces if configured, otherwise returns defaults
    
    Args:
        company_id: The company identifier
        
    Returns:
        List of namespace IDs (e.g., ["general", "baseline", "expert", "historic"])
    """
    try:
        db_firestore = get_firestore_client()
        settings_doc = db_firestore.collection("settings").document(company_id).get()
        
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            namespace_config = settings.get("namespaceConfiguration", {})
            
            # Check if custom namespaces are enabled
            if namespace_config.get("enabled", False):
                namespaces = namespace_config.get("namespaces", [])
                return [ns["id"] for ns in namespaces]
        
        # Return default namespace IDs
        return [ns["id"] for ns in DEFAULT_NAMESPACES]
        
    except Exception as e:
        print(f"[NAMESPACE_UTILS] Error fetching namespaces for {company_id}: {e}")
        # Fallback to defaults on error
        return [ns["id"] for ns in DEFAULT_NAMESPACES]


def get_intent_to_namespaces_mapping(company_id: str) -> Dict[str, List[str]]:
    """
    Get mapping of intents to namespace IDs for a company
    
    Args:
        company_id: The company identifier
        
    Returns:
        Dict mapping intent names to list of namespace IDs
        Example: {
            "general": ["general"],
            "baseline_comparison": ["general", "baseline"],
            "expert": ["expert"],
            "historic": ["historic"],
            "multi": ["general", "baseline", "expert", "historic"]
        }
    """
    try:
        db_firestore = get_firestore_client()
        settings_doc = db_firestore.collection("settings").document(company_id).get()
        
        # Initialize mapping
        intent_mapping = {}
        namespaces = DEFAULT_NAMESPACES
        
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            namespace_config = settings.get("namespaceConfiguration", {})
            
            # Use custom namespaces if enabled
            if namespace_config.get("enabled", False):
                namespaces = namespace_config.get("namespaces", DEFAULT_NAMESPACES)
        
        # Build intent mapping from namespace configuration
        for namespace in namespaces:
            ns_id = namespace["id"]
            ns_intents = namespace.get("intents", [])
            
            for intent in ns_intents:
                if intent not in intent_mapping:
                    intent_mapping[intent] = []
                intent_mapping[intent].append(ns_id)
        
        # Ensure we have at least a default mapping
        if not intent_mapping:
            intent_mapping = {
                "general": ["general"],
                "baseline_comparison": ["general", "baseline"],
                "historic": ["historic"],
                "expert": ["expert"],
                "multi": [ns["id"] for ns in DEFAULT_NAMESPACES]
            }
        
        print(f"[NAMESPACE_UTILS] Intent mapping for {company_id}: {intent_mapping}")
        return intent_mapping
        
    except Exception as e:
        print(f"[NAMESPACE_UTILS] Error building intent mapping for {company_id}: {e}")
        # Fallback to default mapping
        return {
            "general": ["general"],
            "baseline_comparison": ["general", "baseline"],
            "historic": ["historic"],
            "expert": ["expert"],
            "multi": [ns["id"] for ns in DEFAULT_NAMESPACES]
        }


def get_default_namespace(company_id: str) -> str:
    """
    Get the default/fallback namespace for a company
    
    Args:
        company_id: The company identifier
        
    Returns:
        ID of the default namespace (usually "general")
    """
    try:
        db_firestore = get_firestore_client()
        settings_doc = db_firestore.collection("settings").document(company_id).get()
        
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            namespace_config = settings.get("namespaceConfiguration", {})
            
            if namespace_config.get("enabled", False):
                namespaces = namespace_config.get("namespaces", [])
                # Find the default namespace
                for ns in namespaces:
                    if ns.get("isDefault", False):
                        return ns["id"]
                # If no default marked, return first namespace
                if namespaces:
                    return namespaces[0]["id"]
        
        # Return default
        return "general"
        
    except Exception as e:
        print(f"[NAMESPACE_UTILS] Error fetching default namespace for {company_id}: {e}")
        return "general"


def get_namespace_display_name(company_id: str, namespace_id: str) -> str:
    """
    Get display name for a namespace
    
    Args:
        company_id: The company identifier
        namespace_id: The namespace ID
        
    Returns:
        Display name of the namespace
    """
    try:
        db_firestore = get_firestore_client()
        settings_doc = db_firestore.collection("settings").document(company_id).get()
        
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            namespace_config = settings.get("namespaceConfiguration", {})
            
            if namespace_config.get("enabled", False):
                namespaces = namespace_config.get("namespaces", [])
                for ns in namespaces:
                    if ns["id"] == namespace_id:
                        return ns.get("displayName", namespace_id)
        
        # Find in defaults
        for ns in DEFAULT_NAMESPACES:
            if ns["id"] == namespace_id:
                return ns["displayName"]
        
        return namespace_id  # Fallback to ID itself
        
    except Exception as e:
        print(f"[NAMESPACE_UTILS] Error fetching display name: {e}")
        return namespace_id
