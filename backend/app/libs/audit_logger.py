from datetime import datetime, timezone
from typing import Dict, Any, Optional
from google.cloud import firestore  # type: ignore

class AuditLogger:
    """
    Immutable Audit Logger for TechTalk Enterprise SaaS.
    
    Provides SOC2 / ISO27001 compliance tracking by logging all sensitive
    configuration changes, overrides, and config downloads to an append-only
    Firestore collection scoped to the customer.
    """
    
    def __init__(self, db_client: firestore.Client):
        self.db = db_client
        
    def log_action(
        self,
        user_email: str,
        customer_id: str,
        action: str,
        details: Dict[str, Any],
        project_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log an administrative or provisioning event.
        
        Args:
            user_email: User who performed the action
            customer_id: The enterprise customer's tenant ID
            action: The event name (e.g., 'downloaded_ztp_config', 'resolved_cabling_alert')
            details: JSON payload of what changed or what was accessed
            project_id: Optional specific GPU cluster project ID
            ip_address: Optional user IP
            user_agent: Optional user agent string
            
        Returns:
            Firestore Document ID of the new audit log entry
        """
        # Ensure details are fully serializable
        safe_details = {k: str(v) for k, v in details.items()}
        
        log_entry = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "datetimeIso": datetime.now(timezone.utc).isoformat(),
            "userEmail": user_email,
            "action": action,
            "details": safe_details,
            "projectId": project_id,
            "networkContext": {
                "ipAddress": ip_address,
                "userAgent": user_agent
            }
        }
        
        # Write to customer-scoped audit logs collection
        logs_ref = self.db.collection(f"customers/{customer_id}/audit_logs")
        _, doc_ref = logs_ref.add(log_entry)
        
        print(f"🔒 AUDIT: {user_email} performed '{action}' in tenant {customer_id}")
        return doc_ref.id
        
    def get_logs(
        self,
        customer_id: str,
        limit: int = 100,
        user_email: Optional[str] = None,
        action: Optional[str] = None
    ) -> list:
        """
        Retrieve recent audit logs for a customer.
        Useful for the UI compliance viewers.
        """
        logs_ref = self.db.collection(f"customers/{customer_id}/audit_logs")
        query = logs_ref.order_by("timestamp", direction=firestore.Query.DESCENDING)
        
        if user_email:
            query = query.where("userEmail", "==", user_email)
        if action:
            query = query.where("action", "==", action)
            
        query = query.limit(limit)
        
        results = []
        for doc in query.stream():
            log_data = doc.to_dict()
            log_data["id"] = doc.id
            results.append(log_data)
            
        return results
