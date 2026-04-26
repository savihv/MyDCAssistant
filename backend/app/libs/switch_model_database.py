"""Switch Model Database - Self-Learning Hardware Inventory Cache

Caches switch hardware specifications to prevent redundant datasheet lookups.
Each time a new switch model is discovered via DHCP, its specs are saved
locally for instant retrieval on future requests.

This is the "memory" of the cluster - once it learns a hardware model,
it never forgets.

Example:
    db = SwitchModelDatabase()
    
    # First time seeing QM9700 - triggers web search
    specs = db.get_or_learn_specs("NVIDIA", "QM9700", fetcher)
    # → Returns {port_count: 64, interface_prefix: "p{id}", ...}
    
    # Next QM9700 - instant retrieval from cache
    specs = db.get_or_learn_specs("NVIDIA", "QM9700", fetcher)
    # → Returns cached specs (no web search)
"""

from typing import Dict
from datetime import datetime
import databutton as db


class SwitchModelDatabase:
    """Local cache for switch hardware specifications.
    
    The database persists to Databutton storage (db.storage.json) to survive
    app restarts. This ensures the cluster "remembers" learned hardware
    even after system reboots.
    
    Schema:
    {
        "NVIDIA_QM9700": {
            "vendor": "NVIDIA",
            "model": "QM9700",
            "data_port_count": 64,
            "physical_port_count": 32,  # OSFP connectors
            "interface_prefix": "p{id}",
            "os_version": "Onyx 5.2.0",
            "datasheet_url": "https://...",
            "learned_at": "2026-01-29T10:30:00Z",
            "split_port_capable": true
        },
        "Arista_7060X4": { ... }
    }
    """
    
    STORAGE_KEY = "switch_hardware_database"
    
    def __init__(self):
        """Initialize database and load cached specs from storage."""
        self.cached_models = self._load_from_storage()
        print(f"🗄️ SwitchModelDatabase initialized ({len(self.cached_models)} models cached)")
    
    def _load_from_storage(self) -> Dict:
        """Load cached specs from Databutton storage.
        
        Returns:
            Dict of model specs keyed by "vendor_model"
        """
        try:
            cached = db.storage.json.get(self.STORAGE_KEY, default={})
            if cached:
                print(f"📦 Loaded {len(cached)} cached switch models from storage")
                for key in list(cached.keys())[:3]:  # Show first 3
                    print(f"   - {key}")
            return cached
        except Exception as e:
            print(f"⚠️ Could not load cache: {e}")
            return {}
    
    def _save_to_storage(self):
        """Persist cached specs to Databutton storage."""
        try:
            db.storage.json.put(self.STORAGE_KEY, self.cached_models)
            print(f"💾 Saved {len(self.cached_models)} models to storage")
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
    
    def _make_cache_key(self, vendor: str, model: str) -> str:
        """Create cache key from vendor and model.
        
        Args:
            vendor: Vendor name (e.g., "NVIDIA")
            model: Model number (e.g., "QM9700")
            
        Returns:
            Cache key like "NVIDIA_QM9700"
        """
        # Normalize to uppercase and remove spaces
        vendor_clean = vendor.upper().replace(" ", "_")
        model_clean = model.upper().replace(" ", "_")
        return f"{vendor_clean}_{model_clean}"
    
    def get_or_learn_specs(self, vendor: str, model: str, fetcher) -> Dict:
        """Get switch specs from cache or fetch from web if new model.
        
        This is the main entry point. It implements the JIT learning loop:
        1. Check cache for model
        2. If found: return cached specs
        3. If not found: fetch from web, save to cache, return specs
        
        Args:
            vendor: Switch vendor (e.g., "NVIDIA", "Arista")
            model: Model number (e.g., "QM9700", "7060X4")
            fetcher: DatasheetFetcher instance for web lookups
            
        Returns:
            Dict with keys:
            - vendor: str
            - model: str
            - data_port_count: int (logical ports)
            - physical_port_count: int (physical connectors)
            - interface_prefix: str (e.g., "p{id}", "Ethernet{id}")
            - os_version: str
            - datasheet_url: str
            - learned_at: str (ISO timestamp)
            - split_port_capable: bool
        
        Example:
            >>> db = SwitchModelDatabase()
            >>> specs = db.get_or_learn_specs("NVIDIA", "QM9700", fetcher)
            >>> print(specs['data_port_count'])
            64
        """
        cache_key = self._make_cache_key(vendor, model)
        
        # Check cache first
        if cache_key in self.cached_models:
            print(f"✅ Cache HIT: {vendor} {model} (specs already known)")
            return self.cached_models[cache_key]
        
        # Cache miss - fetch from web
        print(f"\n🔍 Cache MISS: {vendor} {model}")
        print("📡 Fetching datasheet from web...")
        
        try:
            specs = fetcher.fetch_specs(vendor, model)
            
            # Add metadata
            specs["learned_at"] = datetime.utcnow().isoformat() + "Z"
            
            # Save to cache
            self.cached_models[cache_key] = specs
            self._save_to_storage()
            
            print(f"✅ Learned new model: {vendor} {model}")
            print(f"   Port Count: {specs['data_port_count']} (logical)")
            print(f"   Interface: {specs['interface_prefix']}")
            
            return specs
            
        except Exception as e:
            print(f"❌ Failed to learn specs for {vendor} {model}: {e}")
            # Return fallback specs to prevent total failure
            return self._get_fallback_specs(vendor, model)
    
    def _get_fallback_specs(self, vendor: str, model: str) -> Dict:
        """Return reasonable default specs when datasheet fetch fails.
        
        This prevents the system from crashing if Tavily API is down
        or the datasheet is unavailable.
        
        Args:
            vendor: Switch vendor
            model: Model number
            
        Returns:
            Generic specs dict with conservative defaults
        """
        print(f"⚠️ Using fallback specs for {vendor} {model}")
        
        # Conservative defaults (most switches are in this range)
        return {
            "vendor": vendor,
            "model": model,
            "data_port_count": 32,  # Conservative default
            "physical_port_count": 32,
            "interface_prefix": "Ethernet{{id}}",  # Most common
            "os_version": "latest",
            "datasheet_url": "UNAVAILABLE",
            "learned_at": datetime.utcnow().isoformat() + "Z",
            "split_port_capable": False,
            "fallback": True  # Flag indicating this is a fallback
        }
    
    def list_cached_models(self) -> list[str]:
        """Get list of all cached model names.
        
        Returns:
            List of model keys (e.g., ["NVIDIA_QM9700", "ARISTA_7060X4"])
        """
        return list(self.cached_models.keys())
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache.
        
        Returns:
            Dict with cache metrics
        """
        total_models = len(self.cached_models)
        fallback_count = sum(1 for m in self.cached_models.values() if m.get("fallback"))
        
        vendors = set(m["vendor"] for m in self.cached_models.values())
        
        return {
            "total_models": total_models,
            "learned_models": total_models - fallback_count,
            "fallback_models": fallback_count,
            "vendors": list(vendors),
            "vendor_count": len(vendors)
        }
    
    def clear_cache(self):
        """Clear all cached specs (for testing/debugging)."""
        self.cached_models = {}
        self._save_to_storage()
        print("🗑️ Cache cleared")
    
    def seed_initial_models(self, seed_data: list[Dict]):
        """Manually seed database with known models (bootstrapping).
        
        Useful for pre-populating the database with common models
        before deployment to reduce initial web lookups.
        
        Args:
            seed_data: List of spec dicts to add to cache
        
        Example:
            >>> db.seed_initial_models([
            ...     {
            ...         "vendor": "NVIDIA",
            ...         "model": "QM9700",
            ...         "data_port_count": 64,
            ...         "physical_port_count": 32,
            ...         "interface_prefix": "p{id}",
            ...         "os_version": "Onyx 5.2.0",
            ...         "split_port_capable": True
            ...     }
            ... ])
        """
        for specs in seed_data:
            cache_key = self._make_cache_key(specs["vendor"], specs["model"])
            specs["learned_at"] = datetime.utcnow().isoformat() + "Z"
            self.cached_models[cache_key] = specs
        
        self._save_to_storage()
        print(f"🌱 Seeded {len(seed_data)} models into database")
