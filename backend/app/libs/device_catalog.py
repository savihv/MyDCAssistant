"""Device Catalog for AI Factory SaaS.
Handles specifications for various networking and processing hardware across multiple vendors.
Supports NVIDIA, Dell, Cisco, Arista, and AMD.
"""

from typing import Dict, Any, List, Optional

class DeviceCatalog:
    """Read-only catalog for hardware compatibility, roles, and properties."""

    SUPPORTED_VENDORS = ["NVIDIA", "Dell", "Cisco", "Arista", "AMD"]

    DEVICES = {
        # NVIDIA Spectrum-4
        "sn5600": {
            "vendor": "NVIDIA",
            "model": "Spectrum-sn5600",
            "type": "switch",
            "role_support": ["spine", "leaf"],
            "ports": 64,
            "speed": "800G",
            "os": "SONiC",
            "power_w": 1200
        },
        "sn4600": {
            "vendor": "NVIDIA",
            "model": "Spectrum-sn4600",
            "type": "switch",
            "role_support": ["spine", "leaf", "management"],
            "ports": 64,
            "speed": "400G",
            "os": "SONiC",
            "power_w": 800
        },
        
        # Arista
        "dcs-7800r3": {
            "vendor": "Arista",
            "model": "DCS-7800R3",
            "type": "switch",
            "role_support": ["spine"],
            "ports": 576,
            "speed": "400G",
            "os": "EOS",
            "power_w": 5000
        },
        "dcs-7060x5": {
            "vendor": "Arista",
            "model": "DCS-7060X5",
            "type": "switch",
            "role_support": ["leaf"],
            "ports": 32,
            "speed": "800G",
            "os": "EOS",
            "power_w": 1000
        },
        
        # Cisco
        "nexus-9332d": {
            "vendor": "Cisco",
            "model": "Nexus 9332D-GX2B",
            "type": "switch",
            "role_support": ["leaf", "spine"],
            "ports": 32,
            "speed": "400G",
            "os": "NX-OS",
            "power_w": 1100
        },

        # Dell Compute
        "xe9680": {
            "vendor": "Dell",
            "model": "PowerEdge XE9680",
            "type": "compute",
            "role_support": ["gpu_node"],
            "gpu_slots": 8,
            "gpu_type_support": ["H100", "A100", "MI300X"],
            "power_w": 4000
        },
        
        # NVIDIA Compute
        "dgx-h100": {
            "vendor": "NVIDIA",
            "model": "DGX H100",
            "type": "compute",
            "role_support": ["gpu_node"],
            "gpu_slots": 8,
            "gpu_type_support": ["H100"],
            "power_w": 10200
        },
        
        # AMD
        "instinct-mi300x": {
            "vendor": "AMD",
            "model": "Instinct MI300X OAM",
            "type": "gpu",
            "role_support": ["accelerator"],
            "memory": "192GB",
            "power_w": 750
        }
    }

    @classmethod
    def get_device(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve device details by model slug/id."""
        return cls.DEVICES.get(model_id.lower())

    @classmethod
    def find_devices_by_vendor(cls, vendor: str) -> List[Dict[str, Any]]:
        """Return all devices from a specific vendor."""
        vendor_lower = vendor.lower()
        return [
            {**data, "id": model_id} 
            for model_id, data in cls.DEVICES.items() 
            if data["vendor"].lower() == vendor_lower
        ]

    @classmethod
    def find_devices_by_type(cls, device_type: str) -> List[Dict[str, Any]]:
        """Return all devices of a specific type (e.g., 'switch', 'compute')."""
        return [
            {**data, "id": model_id} 
            for model_id, data in cls.DEVICES.items() 
            if data["type"].lower() == device_type.lower()
        ]
        
    @classmethod
    def is_vendor_supported(cls, vendor: str) -> bool:
        """Check if a vendor is officially supported."""
        return any(vendor.lower() == v.lower() for v in cls.SUPPORTED_VENDORS)

    @classmethod
    def get_supported_vendors(cls) -> List[str]:
        """Get the list of supported vendors."""
        return cls.SUPPORTED_VENDORS
