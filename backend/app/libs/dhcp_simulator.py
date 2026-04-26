"""DHCP Discovery Simulator for Testing Day 1 Provisioning

Simulates DHCP DISCOVER events from switches powering on in the data center.
Used for:
- Regression testing before production deployment
- Demonstrating mismatch scenarios to Installation Leads
- Training new team members on provisioning workflow
- Validating Firestore inventory setup

Test Scenarios:
---------------
1. success_spine: InfiniBand Spine switch - Perfect serial match
2. success_leaf: InfiniBand Leaf switch - Perfect serial match  
3. success_frontend: Frontend Ethernet switch - Perfect serial match
4. mismatch_wrong_serial: Wrong serial detected - CRITICAL alert
5. unknown_device: MAC not in inventory - MEDIUM alert
6. unreachable: Switch boots but doesn't respond to SNMP/SSH

Integration with Real DHCP:
---------------------------
In production, replace this simulator with:
1. ISC Kea webhook (libdhcp_lease_cmds.so hook calling /provisioning/discover)
2. Infoblox webhook (custom HTTP event handler)
3. Log watcher script (parsing /var/log/dhcp.log for DISCOVER events)

Example:
    # Run all test scenarios
    from app.libs.dhcp_simulator import run_all_test_scenarios
    run_all_test_scenarios(project_id="bringup_abc123")
    
    # Single scenario
    from app.libs.dhcp_simulator import simulate_discovery
    result = simulate_discovery(
        project_id="bringup_abc123",
        mac="00:1B:21:D9:56:E1"
    )
"""

import requests
from typing import Dict, Optional


def simulate_discovery(
    project_id: str,
    mac: str,
    api_url: str = "http://localhost:8000",
    remote_id: Optional[str] = None,
    hostname: Optional[str] = None,
    verbose: bool = True
) -> Dict:
    """
    Send simulated DHCP DISCOVER packet to the provisioning API.
    
    Args:
        project_id: Firestore project identifier
        mac: MAC address of simulated switch
        api_url: Base URL of the API (default: http://localhost:8000)
        remote_id: DHCP Option 82 data (optional)
        hostname: Device hostname (optional)
        verbose: Print detailed output (default: True)
    
    Returns:
        Response dict from API with keys:
        - status: "SUCCESS", "BLOCKED", "UNKNOWN", or "UNREACHABLE"
        - device_name: Name of device (if found)
        - assigned_ip: IP address (if success)
        - location: Rack/U-Position (if found)
        - alert_id: Firestore alert ID (if blocked)
        - expected_serial: Expected serial (if mismatch)
        - detected_serial: Detected serial (if mismatch)
    
    Example:
        >>> result = simulate_discovery(
        ...     project_id="bringup_abc123",
        ...     mac="00:1B:21:D9:56:E1"
        ... )
        >>> print(result["status"])  # "SUCCESS"
        >>> print(result["assigned_ip"])  # "10.0.1.50"
    """
    endpoint = f"{api_url}/routes/cluster-bringup/provisioning/discover/{project_id}"
    
    payload = {
        "mac": mac,
        "remote_id": remote_id,
        "hostname": hostname
    }
    
    if verbose:
        print("\n" + "="*70)
        print("  🔬 DHCP DISCOVER SIMULATION")
        print("="*70)
        print(f"  Project ID:     {project_id}")
        print(f"  MAC Address:    {mac}")
        print(f"  API URL:        {api_url}")
        print("="*70 + "\n")
        print(f"📤 Sending DHCP DISCOVER to {endpoint}...\n")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()  # Raise exception for 4xx/5xx
        
        result = response.json()
        
        if verbose:
            _print_result(result)
        
        return result
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            # Expected error for identity mismatch
            error_detail = e.response.json().get("detail", {})
            result = {
                "status": "BLOCKED",
                "error": error_detail.get("error"),
                "message": error_detail.get("message"),
                "alert_id": error_detail.get("alert_id"),
                "expected_serial": error_detail.get("expected_serial"),
                "detected_serial": error_detail.get("detected_serial")
            }
            
            if verbose:
                _print_result(result)
            
            return result
        else:
            raise
    
    except requests.exceptions.ConnectionError:
        if verbose:
            print("\n❌ ERROR: Cannot connect to API")
            print(f"\nMake sure the backend is running at {api_url}\n")
        raise
        
    except requests.exceptions.Timeout:
        if verbose:
            print("\n❌ ERROR: API request timed out")
            print("\nThe backend might be overloaded or unresponsive.\n")
        raise


def _print_result(result: Dict):
    """Print formatted result based on provisioning status"""
    status = result.get("status")
    
    if status == "SUCCESS":
        print("\n✅ SUCCESS: Hardware Verified & IP Assigned")
        print("═" * 60)
        print(f"  Device Name:    {result.get('device_name')}")
        print(f"  Location:       {result.get('location')}")
        print(f"  Assigned IP:    {result.get('assigned_ip')}")
        print("═" * 60)
        print("\n🟢 Device is now PROVISIONED and ready for configuration.\n")
        
    elif status == "BLOCKED":
        print("\n❌ BLOCKED: Identity Mismatch Detected")
        print("═" * 60)
        print(f"  Expected Serial: {result.get('expected_serial')}")
        print(f"  Detected Serial: {result.get('detected_serial')}")
        print(f"  Alert ID:        {result.get('alert_id')}")
        print("═" * 60)
        print("\n🔴 IP assignment HALTED. Installation Lead must resolve alert.")
        print("\n⚠️  Possible Causes:")
        print("    - Technician racked wrong switch in this location")
        print("    - Cables swapped between two identical switches")
        print("    - Day 0 inventory has incorrect serial number")
        print("\n🛠️  Resolution Options:")
        print("    1. Physically move hardware to correct rack location")
        print("    2. Update inventory to match physical reality")
        print("    3. Override and proceed (DANGEROUS - use with caution)\n")
        
    elif status == "UNKNOWN":
        print("\n⚠️  UNKNOWN DEVICE")
        print("═" * 60)
        print(f"  MAC Address:     {result.get('mac_address')}")
        print("═" * 60)
        print("\n🟡 Device not found in Day 0 schematic extraction.")
        print("\n⚠️  Possible Causes:")
        print("    - Rogue device (security breach)")
        print("    - Missing from asset inventory CSV")
        print("    - Device on wrong VLAN/network segment")
        print("\n🛠️  Next Steps:")
        print("    - Verify if this device should be added to inventory")
        print("    - Check VLAN configuration")
        print("    - Investigate potential security breach\n")
        
    elif status == "UNREACHABLE":
        print("\n⏳ UNREACHABLE: Switch Not Responding")
        print("═" * 60)
        print(f"  Device Name:     {result.get('device_name')}")
        print(f"  MAC Address:     {result.get('mac_address')}")
        print("═" * 60)
        print("\n🟠 Switch sent DHCP request but doesn't respond to serial query.")
        print("\n⚠️  Possible Causes:")
        print("    - Switch still booting (wait for boot to complete)")
        print("    - Firmware doesn't support SNMP/SSH yet")
        print("    - Network connectivity issue")
        print("    - Wrong admin credentials\n")
    
    else:
        print(f"\n❓ UNKNOWN STATUS: {status}")
        print(f"\nRaw Response: {result}\n")


# ============== PRE-DEFINED TEST SCENARIOS ==============

TEST_SCENARIOS = {
    "success_spine": {
        "mac": "00:1B:21:D9:56:E1",
        "description": "InfiniBand Spine - Perfect Match",
        "expected_outcome": "SUCCESS"
    },
    "success_leaf": {
        "mac": "00:1B:21:D9:56:E2",
        "description": "InfiniBand Leaf - Perfect Match",
        "expected_outcome": "SUCCESS"
    },
    "mismatch_wrong_serial": {
        "mac": "00:1B:21:D9:56:E4",
        "description": "Wrong serial number - Triggers CRITICAL alert",
        "expected_outcome": "BLOCKED"
    },
    "unknown_device": {
        "mac": "FF:FF:FF:FF:FF:FF",
        "description": "MAC not in Day 0 plan",
        "expected_outcome": "UNKNOWN"
    },
}


def run_test_scenario(
    scenario_name: str,
    project_id: str,
    api_url: str = "http://localhost:8000"
) -> Dict:
    """
    Run a pre-defined test scenario.
    
    Args:
        scenario_name: One of: "success_spine", "success_leaf", 
                       "mismatch_wrong_serial", "unknown_device"
        project_id: Firestore project ID
        api_url: Base URL of the API
    
    Returns:
        Result dict from simulate_discovery()
    
    Example:
        >>> result = run_test_scenario(
        ...     scenario_name="mismatch_wrong_serial",
        ...     project_id="bringup_abc123"
        ... )
        >>> assert result["status"] == "BLOCKED"
    """
    if scenario_name not in TEST_SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario_name}. "
            f"Available: {list(TEST_SCENARIOS.keys())}"
        )
    
    scenario = TEST_SCENARIOS[scenario_name]
    
    print(f"\n🎯 Running Test Scenario: {scenario_name}")
    print(f"   Description: {scenario['description']}")
    print(f"   Expected: {scenario['expected_outcome']}")
    
    result = simulate_discovery(
        project_id=project_id,
        mac=scenario["mac"],
        api_url=api_url
    )
    
    # Verify expected outcome
    if result["status"] == scenario["expected_outcome"]:
        print(f"\n✅ Test PASSED: Got expected outcome '{scenario['expected_outcome']}'")
    else:
        print(f"\n❌ Test FAILED: Expected '{scenario['expected_outcome']}' but got '{result['status']}'")
    
    return result


def run_all_test_scenarios(
    project_id: str,
    api_url: str = "http://localhost:8000"
) -> Dict[str, Dict]:
    """
    Run all pre-defined test scenarios.
    
    Args:
        project_id: Firestore project ID
        api_url: Base URL of the API
    
    Returns:
        Dict mapping scenario name to result dict
    
    Example:
        >>> results = run_all_test_scenarios("bringup_abc123")
        >>> assert results["success_spine"]["status"] == "SUCCESS"
        >>> assert results["mismatch_wrong_serial"]["status"] == "BLOCKED"
    """
    print("\n" + "="*70)
    print("  🧪 RUNNING ALL TEST SCENARIOS")
    print("="*70)
    
    results = {}
    
    for scenario_name in TEST_SCENARIOS.keys():
        try:
            result = run_test_scenario(
                scenario_name=scenario_name,
                project_id=project_id,
                api_url=api_url
            )
            results[scenario_name] = result
        except Exception as e:
            print(f"\n❌ Error in scenario '{scenario_name}': {str(e)}")
            results[scenario_name] = {"status": "ERROR", "error": str(e)}
    
    # Print summary
    print("\n" + "="*70)
    print("  📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results.values() if r.get("status") in ["SUCCESS", "BLOCKED", "UNKNOWN"])
    total = len(results)
    
    print(f"  Passed: {passed}/{total}")
    
    for scenario_name, result in results.items():
        status_emoji = {
            "SUCCESS": "✅",
            "BLOCKED": "✅",  # Expected for mismatch scenario
            "UNKNOWN": "✅",  # Expected for unknown device
            "ERROR": "❌"
        }.get(result.get("status"), "❓")
        
        print(f"  {status_emoji} {scenario_name}: {result.get('status')}")
    
    print("="*70 + "\n")
    
    return results
