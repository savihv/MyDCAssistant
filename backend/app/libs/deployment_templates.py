"""Deployment templates for onboarding wizard.
Defines BasePOD, SuperPOD-256, and Custom topology templates.
"""

from typing import Optional


DEPLOYMENT_TEMPLATES = [
    {
        "id": "single_su",
        "name": "Single SU BasePOD",
        "description": "A single Scalable Unit with 8 compute nodes. Ideal for teams getting started with GPU clusters.",
        "gpu_count": 64,
        "node_count": 8,
        "su_count": 1,
        "leaf_switches": 4,
        "spine_switches": 0,
        "topology": "2-tier leaf-only",
        "fabric": "NVIDIA Spectrum-4 InfiniBand",
        "bandwidth": "400Gbps per GPU",
        "use_cases": ["LLM fine-tuning", "Small model training", "Inference clusters"],
        "icon": "single",
        "bom_example": [
            {"model": "MQM9700-NS2F", "role": "Leaf Switch", "quantity": 4},
            {"model": "HGX H100 SXM5", "role": "Compute Node", "quantity": 8},
        ],
        "topology_params": {
            "G": 8,   # GPUs per node
            "N": 8,   # Nodes per SU
            "S": 1,   # SUs
            "R": 1,   # Racks per SU
            "P": 1,   # Planes
            "L": 4,   # Leaf switches per SU
        },
    },
    {
        "id": "multi_su_superpod",
        "name": "Multi-SU SuperPOD",
        "description": "4 Scalable Units with full spine layer for maximum GPU cluster performance. Production-grade for large model training.",
        "gpu_count": 256,
        "node_count": 32,
        "su_count": 4,
        "leaf_switches": 16,
        "spine_switches": 8,
        "topology": "3-tier spine-leaf",
        "fabric": "NVIDIA Spectrum-4 InfiniBand",
        "bandwidth": "800Gbps per GPU",
        "use_cases": ["Large model pre-training", "Multi-node distributed training", "Research clusters"],
        "icon": "multi",
        "bom_example": [
            {"model": "MQM9700-NS2F", "role": "Spine Switch", "quantity": 8},
            {"model": "MQM9700-NS2F", "role": "Leaf Switch", "quantity": 16},
            {"model": "HGX H100 SXM5", "role": "Compute Node", "quantity": 32},
        ],
        "topology_params": {
            "G": 8,
            "N": 8,
            "S": 4,
            "R": 2,
            "P": 2,
            "L": 4,
        },
    },
    {
        "id": "custom",
        "name": "Custom Deployment",
        "description": "Define your own cluster topology. Specify exact GPU counts, switch models, and network design for specialized workloads.",
        "gpu_count": None,
        "node_count": None,
        "su_count": None,
        "leaf_switches": None,
        "spine_switches": None,
        "topology": "User-defined",
        "fabric": "Multi-vendor supported",
        "bandwidth": "Configurable",
        "use_cases": ["Hybrid environments", "Custom fabric requirements", "Mixed vendor deployments"],
        "icon": "custom",
        "bom_example": [],
        "topology_params": None,
    },
]


SUPPORTED_SWITCH_MODELS = [
    "MQM9700-NS2F",  # NVIDIA Quantum-2 400G
    "MQM9700-NS2R",
    "MQM8790-HS2F",  # NVIDIA Quantum 200G
    "DCS-7050CX3-32S",  # Arista 32x100GbE
    "DCS-7060CX2-32S",  # Arista 32x100GbE
    "DCS-7170-32CD",     # Arista 32x400GbE
    "N9K-C9336C-FX2",   # Cisco Nexus
    "N9K-C93600CD-GX",  # Cisco Nexus
]

SUPPORTED_COMPUTE_MODELS = [
    "HGX H100 SXM5",
    "HGX H100 NVL",
    "HGX H200 SXM5",
    "HGX A100 SXM4",
    "DGX H100",
    "DGX A100",
    "DGX H200",
]


def get_template_by_id(template_id: str) -> Optional[dict]:
    """Fetch a template by its ID."""
    for t in DEPLOYMENT_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def get_all_templates() -> list:
    """Return all deployment templates."""
    return DEPLOYMENT_TEMPLATES
