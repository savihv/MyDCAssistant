from typing import Optional
from datetime import datetime, timezone

class LicenseManager:
    """
    LicenseManager for AI Factory SaaS.
    Enforces GPU quotas per customer tier (Starter, Pro, Enterprise).
    Integrates with Stripe billing (or mock Stripe for now).
    """
    
    TIER_LIMITS = {
        "Starter": {
            "max_gpus": 64,
            "max_users": 5,
            "max_projects": 1,
            "price_per_gpu_mo": 10.0
        },
        "Pro": {
            "max_gpus": 512,
            "max_users": 25,
            "max_projects": 5,
            "price_per_gpu_mo": 8.0
        },
        "Enterprise": {
            "max_gpus": float('inf'),
            "max_users": float('inf'),
            "max_projects": float('inf'),
            "price_per_gpu_mo": 5.0
        }
    }
    
    def __init__(self, db_client):
        """
        Initialize the LicenseManager with a Firestore client instance.
        """
        self.db = db_client
        
    def get_customer_tier(self, customer_id: str) -> str:
        """
        Fetch the customer's subscription tier. Defaults to 'Starter' if none found.
        """
        try:
            doc_ref = self.db.collection('customers').document(customer_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get('subscription_tier', 'Starter')
            return 'Starter'
        except Exception as e:
            print(f"Error fetching customer tier: {e}")
            return 'Starter'
            
    def _count_active_gpus(self, customer_id: str) -> int:
        """
        Count the total number of provisioned GPUs for this customer across all projects.
        We aggregate this by looking at the live_infrastructure collections.
        """
        total_gpus = 0
        try:
            # Query all hardware records for the customer that are active
            # Assuming hardware records have a 'gpu_count' field
            hw_query = self.db.collection(f'customers/{customer_id}/live_infrastructure').where('status', '==', 'PROVISIONED').stream()
            for hw in hw_query:
                data = hw.to_dict()
                total_gpus += data.get('gpu_count', 0)
            return total_gpus
        except Exception as e:
            print(f"Error counting active GPUs: {e}")
            return 0
            
    def can_provision_gpus(self, customer_id: str, requested_gpus: int) -> tuple[bool, str]:
        """
        Check if the customer has enough quota to provision more GPUs.
        """
        tier = self.get_customer_tier(customer_id)
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS['Starter'])
        
        current_gpus = self._count_active_gpus(customer_id)
        
        if current_gpus + requested_gpus > limits['max_gpus']:
            msg = f"Quota exceeded. Tier '{tier}' allows up to {limits['max_gpus']} GPUs. You currently have {current_gpus} active GPUs and requested {requested_gpus} more. Please upgrade your subscription."
            return False, msg
            
        return True, "Quota check passed."
        
    def estimate_monthly_cost(self, gpus: int, custom_tier: Optional[str] = None) -> float:
        """
        Estimate the monthly cost for a given number of GPUs based on the calculated tier.
        """
        if custom_tier and custom_tier in self.TIER_LIMITS:
            tier = custom_tier
        else:
            # Auto-select the appropriate tier based on GPU count
            if gpus <= self.TIER_LIMITS["Starter"]["max_gpus"]:
                tier = "Starter"
            elif gpus <= self.TIER_LIMITS["Pro"]["max_gpus"]:
                tier = "Pro"
            else:
                tier = "Enterprise"
                
        price = self.TIER_LIMITS[tier]["price_per_gpu_mo"]
        return gpus * price
        
    def generate_stripe_checkout_session(self, customer_id: str, new_tier: str) -> dict:
        """
        Mock Stripe Checkout Session generation.
        """
        if new_tier not in self.TIER_LIMITS:
            raise ValueError(f"Invalid tier: {new_tier}")
            
        session_id = f"cs_test_{customer_id}_{int(datetime.now(timezone.utc).timestamp())}"
        checkout_url = f"https://checkout.stripe.com/pay/{session_id}"
        
        return {
            "session_id": session_id,
            "url": checkout_url,
            "tier": new_tier,
            "status": "pending"
        }
