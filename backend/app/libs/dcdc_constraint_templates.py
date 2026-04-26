"""DCDC Constraint Templates Data

Pre-configured constraints for Data Center Deployment & Commissioning (DCDC) operations.
Stored as Python constants for easy access without file I/O.
"""

DCDC_TEMPLATES = {
    "domain": "dcdc",
    "version": "1.0",
    "description": "Pre-configured constraints for Data Center Deployment & Commissioning (DCDC) operations",
    "categories": [
        "safety",
        "compliance",
        "workflow",
        "equipment",
        "policy"
    ],
    "constraints": [
        {
            "category": "safety",
            "severity": "critical",
            "rule": "Always verify power is OFF before connecting/disconnecting DC-DC converter modules or PDUs",
            "reasoning": "Hot-swapping DC-DC converters or PDUs can cause electrical arcs, component damage, severe burns, and arc flash hazards",
            "source": "OSHA 1910.333, NFPA 70E",
            "context": {
                "appliesToPhase": ["deployment", "maintenance", "troubleshooting"],
                "appliesToEquipment": ["DC-DC converters", "PDUs", "power supplies"],
                "consequence": "Equipment damage, personal injury, arc flash (up to 40 cal/cm²), fire hazard",
                "example": "Before replacing faulty converter in server rack, use multimeter to verify 0V at all terminals"
            }
        },
        {
            "category": "safety",
            "severity": "critical",
            "rule": "Install PDUs before mounting servers in rack",
            "reasoning": "Ensures proper power distribution infrastructure is in place before energizing equipment, prevents overloading",
            "source": "TIA-942, Internal SOP-DC-001",
            "context": {
                "appliesToPhase": ["deployment"],
                "appliesToEquipment": ["PDUs", "servers", "racks"],
                "consequence": "Electrical overload, fire risk, equipment damage",
                "example": "Mount and wire PDUs to rack power feeds, verify circuit breakers, then begin server installation"
            }
        },
        {
            "category": "safety",
            "severity": "critical",
            "rule": "Verify proper rack grounding and bonding before equipment installation",
            "reasoning": "Prevents electrical shock, ensures fault protection, and reduces EMI interference",
            "source": "NFPA 70 (NEC) Article 250, TIA-942",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["racks", "cabinets", "grounding systems"],
                "consequence": "Electric shock hazard, equipment damage from ground faults, EMI issues",
                "example": "Test continuity between rack frame and building ground: must be < 0.1 ohm resistance"
            }
        },
        {
            "category": "safety",
            "severity": "critical",
            "rule": "Secure all racks to floor using seismic anchoring before loading equipment",
            "reasoning": "Prevents rack tip-over during equipment installation or seismic events",
            "source": "ANSI/TIA-942, FEMA P-2006",
            "context": {
                "appliesToPhase": ["deployment"],
                "appliesToEquipment": ["racks", "cabinets"],
                "consequence": "Rack collapse, equipment damage, personnel injury or death",
                "example": "Install 4 anchor bolts per rack into concrete floor, torque to spec (typically 75-100 ft-lbs)"
            }
        },
        {
            "category": "safety",
            "severity": "warning",
            "rule": "Maintain minimum 36-inch clearance in hot/cold aisles for emergency egress",
            "reasoning": "Required for fire safety and emergency evacuation per building codes",
            "source": "NFPA 1, IBC, OSHA 1910.36",
            "context": {
                "appliesToPhase": ["deployment", "layout"],
                "appliesToEquipment": ["racks", "aisle containment"],
                "consequence": "Fire code violations, impeded emergency egress, fines",
                "example": "Measure aisle width after containment installation, verify compliance"
            }
        },
        {
            "category": "safety",
            "severity": "warning",
            "rule": "Use thermal imaging to verify balanced airflow before declaring deployment complete",
            "reasoning": "Detects hotspots, cooling failures, and airflow blockages that can lead to thermal runaway",
            "source": "ASHRAE TC 9.9, Internal Best Practice",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["servers", "cooling systems", "racks"],
                "consequence": "Thermal shutdown, reduced equipment lifespan, cooling inefficiency",
                "example": "Use FLIR camera to scan racks under full load, verify delta-T within 15°F spec"
            }
        },
        {
            "category": "compliance",
            "severity": "critical",
            "rule": "Document all power circuit IDs, panel locations, and load calculations in DCIM system",
            "reasoning": "Required for capacity planning, troubleshooting, and regulatory compliance",
            "source": "ISO/IEC 22237, SOC 2 Type II",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["PDUs", "power circuits", "panels"],
                "consequence": "Audit failures, capacity planning errors, troubleshooting delays",
                "example": "Log: Rack 42A-PDU1 → Panel MDP-3B, Circuit 24, 30A breaker, 18A current load"
            }
        },
        {
            "category": "compliance",
            "severity": "critical",
            "rule": "Complete and retain commissioning checklists for all critical infrastructure (power, cooling, network)",
            "reasoning": "Required for warranty validation, compliance audits, and incident investigation",
            "source": "ISO/IEC 27001, SSAE 18, Internal QMS",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["all critical systems"],
                "consequence": "Warranty voidance, audit failures, legal liability",
                "example": "Sign-off checklist must include: power validation, cooling validation, network validation, timestamp, technician ID"
            }
        },
        {
            "category": "compliance",
            "severity": "warning",
            "rule": "Label all network cables with both ends' port IDs within 6 inches of termination",
            "reasoning": "Required by TIA-606-B for traceability and troubleshooting efficiency",
            "source": "TIA-606-B, Internal Labeling Standard",
            "context": {
                "appliesToPhase": ["deployment", "cabling"],
                "appliesToEquipment": ["network cables", "fiber optics"],
                "consequence": "Troubleshooting delays, mislabeling errors, failed audits",
                "example": "Label format: SRC-SW01-P24 → DST-SRV05-ETH0"
            }
        },
        {
            "category": "compliance",
            "severity": "warning",
            "rule": "Photograph all rack elevations and cable routing before and after deployment",
            "reasoning": "Documentation for change management, troubleshooting, and dispute resolution",
            "source": "ITIL Change Management, Internal Policy",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["racks", "cabling"],
                "consequence": "Incomplete documentation, change management failures",
                "example": "Minimum 3 photos per rack: front elevation, rear elevation, overhead cable routing"
            }
        },
        {
            "category": "workflow",
            "severity": "critical",
            "rule": "Install structured cabling infrastructure (fiber backbone, copper horizontal) before servers",
            "reasoning": "Prevents re-work, ensures proper cable management, reduces deployment time",
            "source": "TIA-568-C, Data Center Best Practice",
            "context": {
                "appliesToPhase": ["deployment"],
                "appliesToEquipment": ["fiber cables", "copper cables", "cable trays"],
                "consequence": "Deployment delays, poor cable management, increased labor costs",
                "example": "Complete sequence: 1) Install cable trays, 2) Run fiber backbone, 3) Install ToR switches, 4) Run copper horizontals, 5) Mount servers"
            }
        },
        {
            "category": "workflow",
            "severity": "critical",
            "rule": "Bottom-to-top loading sequence for rack equipment installation",
            "reasoning": "Prevents rack instability and reduces risk of equipment dropping during installation",
            "source": "Equipment Manufacturer Guidelines, OSHA Best Practice",
            "context": {
                "appliesToPhase": ["deployment"],
                "appliesToEquipment": ["servers", "switches", "rack equipment"],
                "consequence": "Rack tip-over, dropped equipment, personnel injury",
                "example": "Install UPS at bottom (U1-U4), then PDUs (U5-U8), then servers working upward"
            }
        },
        {
            "category": "workflow",
            "severity": "warning",
            "rule": "Clean all fiber optic connectors immediately before mating",
            "reasoning": "Contamination is the #1 cause of fiber optic link failures and performance degradation",
            "source": "IEC 61300-3-35, Fiber Optic Best Practice",
            "context": {
                "appliesToPhase": ["deployment", "maintenance"],
                "appliesToEquipment": ["fiber optic cables", "transceivers"],
                "consequence": "Link failures, intermittent connectivity, reduced optical budget",
                "example": "Use lint-free wipes + isopropyl alcohol, inspect with scope for scratches/contamination"
            }
        },
        {
            "category": "workflow",
            "severity": "warning",
            "rule": "Perform cable pull tension testing when running cables through tight cable trays",
            "reasoning": "Exceeding cable bend radius or tension limits damages internal conductors",
            "source": "TIA-568-C.0, Cable Manufacturer Specs",
            "context": {
                "appliesToPhase": ["deployment", "cabling"],
                "appliesToEquipment": ["fiber cables", "copper cables"],
                "consequence": "Cable damage, intermittent failures, warranty voidance",
                "example": "Max pull tension for Cat6A: 25 lbf, Min bend radius: 4x cable diameter"
            }
        },
        {
            "category": "workflow",
            "severity": "info",
            "rule": "Use color-coded cable ties for different network segments (e.g., management, production, storage)",
            "reasoning": "Simplifies troubleshooting and reduces risk of disconnecting wrong cables",
            "source": "Internal Best Practice",
            "context": {
                "appliesToPhase": ["deployment", "cabling"],
                "appliesToEquipment": ["network cables"],
                "example": "Blue=Management, Red=Production, Yellow=Storage, Green=Backup"
            }
        },
        {
            "category": "equipment",
            "severity": "critical",
            "rule": "Configure RAID arrays and verify rebuild procedures before deploying servers into production",
            "reasoning": "Prevents data loss and ensures disaster recovery procedures are validated",
            "source": "RAID Best Practice, ISO/IEC 27001",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["servers", "storage arrays"],
                "consequence": "Data loss, extended downtime during failures, recovery failures",
                "example": "RAID-6 config: Create array, simulate single drive failure, verify rebuild < 4hrs, test I/O during rebuild"
            }
        },
        {
            "category": "equipment",
            "severity": "critical",
            "rule": "Enable and configure out-of-band management (iDRAC, iLO, IPMI) before rack installation",
            "reasoning": "Allows remote troubleshooting and prevents need for physical access during incidents",
            "source": "Data Center Operations Best Practice",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["servers", "management controllers"],
                "consequence": "Inability to remotely troubleshoot, increased MTTR, site visits required",
                "example": "Configure iDRAC with dedicated management IP, enable SSH/HTTPS, test remote console access"
            }
        },
        {
            "category": "equipment",
            "severity": "critical",
            "rule": "Verify dual power supply configuration and test automatic failover before production deployment",
            "reasoning": "Ensures high availability and prevents single point of failure in power delivery",
            "source": "High Availability Best Practice, TIA-942 Tier III+",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["servers", "switches", "storage"],
                "consequence": "Unplanned downtime, SLA violations, service interruptions",
                "example": "Connect PSU-A to PDU-A and PSU-B to PDU-B (different circuits), simulate PDU failure, verify no service interruption"
            }
        },
        {
            "category": "equipment",
            "severity": "warning",
            "rule": "Configure network port LACP (Link Aggregation) for redundancy before production use",
            "reasoning": "Provides bandwidth aggregation and automatic failover for network resilience",
            "source": "IEEE 802.3ad, Network HA Best Practice",
            "context": {
                "appliesToPhase": ["commissioning", "network config"],
                "appliesToEquipment": ["servers", "switches"],
                "consequence": "Single point of failure, no automatic failover, reduced bandwidth",
                "example": "Configure LACP on eth0+eth1, mode=802.3ad, test failover by unplugging one cable"
            }
        },
        {
            "category": "equipment",
            "severity": "warning",
            "rule": "Update firmware on all network equipment to manufacturer-recommended stable version before deployment",
            "reasoning": "Addresses known bugs, security vulnerabilities, and compatibility issues",
            "source": "Security Best Practice, Vendor Recommendations",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["switches", "routers", "servers"],
                "consequence": "Security vulnerabilities, compatibility issues, known bugs",
                "example": "Check vendor support site for latest stable firmware, backup config, apply update, verify functionality"
            }
        },
        {
            "category": "equipment",
            "severity": "info",
            "rule": "Enable SNMP monitoring and syslog forwarding to centralized monitoring system",
            "reasoning": "Provides proactive monitoring and historical logging for troubleshooting",
            "source": "Operations Best Practice",
            "context": {
                "appliesToPhase": ["commissioning"],
                "appliesToEquipment": ["servers", "switches", "storage", "PDUs"],
                "example": "Configure SNMPv3 with auth+priv, forward syslog to 10.1.1.100:514, test alert generation"
            }
        },
        {
            "category": "policy",
            "severity": "critical",
            "rule": "Obtain change management approval before modifying production infrastructure",
            "reasoning": "Required by ITIL, SOC 2, and ISO 27001 for change control and audit compliance",
            "source": "ITIL v4, SOC 2, ISO/IEC 27001",
            "context": {
                "appliesToPhase": ["maintenance", "upgrades"],
                "appliesToEquipment": ["all production systems"],
                "consequence": "Audit failures, unauthorized changes, potential service disruptions",
                "example": "Submit change ticket with: scope, risk assessment, rollback plan, approval from CAB"
            }
        },
        {
            "category": "policy",
            "severity": "warning",
            "rule": "Implement two-person rule for physical access to data center during deployments",
            "reasoning": "Security best practice to prevent unauthorized changes and ensure accountability",
            "source": "Security Policy, SOC 2 Type II",
            "context": {
                "appliesToPhase": ["deployment", "maintenance"],
                "appliesToEquipment": ["all data center assets"],
                "consequence": "Security policy violations, audit findings, insider threat risk",
                "example": "Log access with both technician names, badge swipes, and task description"
            }
        },
        {
            "category": "policy",
            "severity": "warning",
            "rule": "Perform equipment inventory verification before and after deployment to prevent asset loss",
            "reasoning": "Required for asset tracking, financial accounting, and security compliance",
            "source": "Asset Management Policy, Financial Controls",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["all assets"],
                "consequence": "Asset loss, financial discrepancies, audit failures",
                "example": "Scan all asset tags into CMDB before deployment, verify 100% match after installation"
            }
        },
        {
            "category": "policy",
            "severity": "info",
            "rule": "Schedule deployments during approved maintenance windows to minimize business impact",
            "reasoning": "Reduces risk of service disruption during business-critical hours",
            "source": "Change Management Policy",
            "context": {
                "appliesToPhase": ["deployment", "maintenance"],
                "appliesToEquipment": ["production systems"],
                "example": "Standard maintenance window: Saturday 2AM-6AM local time"
            }
        },
        {
            "category": "safety",
            "severity": "critical",
            "rule": "Wear appropriate PPE (safety glasses, ESD wrist straps, insulated gloves) when working on energized equipment",
            "reasoning": "Prevents electrical shock, arc flash injuries, and ESD damage to components",
            "source": "OSHA 1910.335, NFPA 70E, ANSI/ESD S20.20",
            "context": {
                "appliesToPhase": ["deployment", "maintenance", "troubleshooting"],
                "appliesToEquipment": ["all electrical equipment"],
                "consequence": "Electric shock, burns, ESD component damage, OSHA violations",
                "example": "Minimum PPE for DC power work: safety glasses, insulated gloves rated for voltage, ESD wrist strap"
            }
        },
        {
            "category": "compliance",
            "severity": "critical",
            "rule": "Record all voltage and current measurements in deployment documentation with timestamp",
            "reasoning": "Required for warranty claims, troubleshooting, and capacity verification",
            "source": "Quality Assurance SOP, Warranty Requirements",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["power systems", "DC-DC converters"],
                "consequence": "Warranty voidance, troubleshooting difficulties, no baseline for comparison",
                "example": "Log format: 2024-12-10 14:35 - Input: 48.2VDC, Output: 12.1VDC, Load: 18.5A, Technician: JDoe"
            }
        },
        {
            "category": "workflow",
            "severity": "critical",
            "rule": "Perform cable certification testing (not just continuity) for all critical network links",
            "reasoning": "Ensures cables meet performance specifications and prevents intermittent failures",
            "source": "TIA-568-C.2, Fluke Certification Standards",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["copper cables", "fiber cables"],
                "consequence": "Intermittent failures, performance degradation, failed warranty claims",
                "example": "Use Fluke DTX-1800 to certify Cat6A cables to 10GBASE-T standards, save test results"
            }
        },
        {
            "category": "equipment",
            "severity": "warning",
            "rule": "Configure BIOS settings for optimal power management and performance profile before OS installation",
            "reasoning": "Default BIOS settings may not be optimal for data center workloads",
            "source": "Server Tuning Best Practice",
            "context": {
                "appliesToPhase": ["deployment", "commissioning"],
                "appliesToEquipment": ["servers"],
                "consequence": "Reduced performance, increased power consumption, thermal issues",
                "example": "Set power profile to 'Performance', enable turbo boost, disable C-states for latency-sensitive workloads"
            }
        },
        {
            "category": "safety",
            "severity": "warning",
            "rule": "Verify cooling system operation and airflow direction before energizing high-density racks",
            "reasoning": "Prevents thermal damage to equipment from inadequate cooling",
            "source": "ASHRAE TC 9.9, Cooling Best Practice",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["cooling systems", "high-density racks"],
                "consequence": "Thermal shutdown, equipment damage, cooling system overload",
                "example": "Verify CRAC/CRAH output temp 65-70°F, airflow >400 CFM/kW, hot aisle temp <80°F"
            }
        },
        {
            "category": "workflow",
            "severity": "info",
            "rule": "Take baseline performance measurements (network throughput, disk I/O, CPU) after deployment",
            "reasoning": "Establishes performance baseline for future troubleshooting and capacity planning",
            "source": "Operations Best Practice",
            "context": {
                "appliesToPhase": ["commissioning", "validation"],
                "appliesToEquipment": ["servers", "storage", "network"],
                "example": "Run iperf3 for network, fio for storage, stress-ng for CPU, document results in CMDB"
            }
        },
        {
            "category": "compliance",
            "severity": "info",
            "rule": "Tag all equipment with asset ID and deployment date for lifecycle tracking",
            "reasoning": "Enables proactive maintenance scheduling and warranty tracking",
            "source": "Asset Management Policy",
            "context": {
                "appliesToPhase": ["deployment"],
                "appliesToEquipment": ["all assets"],
                "example": "Affix barcode label with Asset ID, Purchase Date, Warranty Expiration"
            }
        }
    ]
}
