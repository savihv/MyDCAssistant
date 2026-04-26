"""Datasheet Fetcher - Dynamic Hardware Specification Extraction

Fetches switch hardware specifications from vendor datasheets using
web search (Tavily API) and intelligent regex extraction.

This is the "eyes" of the cluster - it reads datasheets so humans don't have to.

Key Features:
- Searches web for vendor datasheets
- Extracts port count (handles "64 ports", "32x 400G", etc.)
- Detects split-port capability (32 physical → 64 logical)
- Identifies interface naming conventions (vendor-specific)
- Extracts OS version from datasheet text

Example:
    fetcher = DatasheetFetcher(tavily_api_key="sk-...")
    specs = fetcher.fetch_specs("NVIDIA", "QM9700")
    # → Returns {port_count: 64, interface_prefix: "p{id}", ...}
"""

import re
import requests
from typing import Dict


class DatasheetFetcher:
    """Fetches switch specifications from vendor datasheets via web search.
    
    Uses Tavily API for intelligent web search, then applies regex patterns
    to extract structured hardware specifications from unstructured text.
    
    The extraction logic handles vendor inconsistencies:
    - NVIDIA: "64 ports OSFP" → 64 logical ports
    - Arista: "32x 400G QSFP-DD" → 32 ports
    - Cisco: "48-port switch" → 48 ports
    
    Split-Port Detection:
    - Looks for keywords: "radix", "split", "breakout"
    - NVIDIA QM9700: 32 OSFP connectors, 64 logical ports (twin-port)
    """
    
    def __init__(self, tavily_api_key: str):
        """Initialize fetcher with Tavily API credentials.
        
        Args:
            tavily_api_key: Tavily API key for web search
        """
        self.tavily_api_key = tavily_api_key
        self.tavily_url = "https://api.tavily.com/search"
    
    def fetch_specs(self, vendor: str, model: str) -> Dict:
        """Main entry point: Search web and extract hardware specs.
        
        This method orchestrates the entire fetching process:
        1. Construct search query
        2. Search web via Tavily
        3. Extract text from results
        4. Parse specifications using regex
        5. Return structured spec dict
        
        Args:
            vendor: Switch vendor (e.g., "NVIDIA", "Arista", "Cisco")
            model: Model number (e.g., "QM9700", "7060X4")
            
        Returns:
            Dict with keys:
            - vendor: str
            - model: str
            - data_port_count: int (logical ports for ZTP config)
            - physical_port_count: int (actual connectors)
            - interface_prefix: str (template with {id} placeholder)
            - os_version: str
            - datasheet_url: str
            - split_port_capable: bool
            
        Raises:
            ValueError: If datasheet cannot be found or specs cannot be extracted
            
        Example:
            >>> fetcher = DatasheetFetcher(api_key="sk-...")
            >>> specs = fetcher.fetch_specs("NVIDIA", "QM9700")
            >>> print(specs['data_port_count'])
            64
        """
        print(f"\n🔍 Fetching datasheet for {vendor} {model}...")
        
        # Step 1: Search web for datasheet
        search_query = f"{vendor} {model} datasheet specifications port count"
        search_results = self._search_web(search_query)
        
        if not search_results:
            raise ValueError(f"No datasheet found for {vendor} {model}")
        
        # Step 2: Extract text from top results
        datasheet_text = self._extract_text_from_results(search_results[:3])
        
        # Step 3: Parse specifications
        port_count = self._extract_port_count(datasheet_text)
        physical_ports = self._extract_physical_port_count(datasheet_text, port_count)
        interface_template = self._extract_interface_naming(vendor, datasheet_text)
        os_version = self._extract_os_version(vendor, datasheet_text)
        split_capable = self._detect_split_port_capability(datasheet_text)
        
        specs = {
            "vendor": vendor,
            "model": model,
            "data_port_count": port_count,
            "physical_port_count": physical_ports,
            "interface_prefix": interface_template,
            "os_version": os_version,
            "datasheet_url": search_results[0]['url'],
            "split_port_capable": split_capable
        }
        
        print("✅ Specs extracted:")
        print(f"   Port Count: {port_count} logical ({physical_ports} physical)")
        print(f"   Interface Template: {interface_template}")
        print(f"   OS Version: {os_version}")
        print(f"   Split-Port: {split_capable}")
        
        return specs
    
    def _search_web(self, query: str) -> list:
        """Search web using Tavily API.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results with 'content' and 'url' keys
            
        Raises:
            ValueError: If Tavily API request fails
        """
        print(f"📡 Searching: {query}")
        
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5,
            "include_answer": False,
            "include_raw_content": False
        }
        
        try:
            response = requests.post(self.tavily_url, json=payload, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            print(f"   Found {len(results)} results")
            return results
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Tavily search failed: {e}")
    
    def _extract_text_from_results(self, results: list) -> str:
        """Combine text content from search results.
        
        Args:
            results: List of search result dicts
            
        Returns:
            Combined text from all results
        """
        text_parts = []
        for result in results:
            content = result.get("content", "")
            if content:
                text_parts.append(content)
        
        combined = "\n".join(text_parts)
        print(f"   Extracted {len(combined)} characters of text")
        return combined
    
    def _extract_port_count(self, text: str) -> int:
        """Extract logical port count from datasheet text.
        
        Handles multiple format variations:
        - "64 ports" → 64
        - "32x 400G" → 32
        - "48-port switch" → 48
        - "96 x 100 GbE QSFP28" → 96
        
        Args:
            text: Datasheet text to parse
            
        Returns:
            Number of logical ports
            
        Raises:
            ValueError: If port count cannot be extracted
        """
        patterns = [
            r'(\d+)\s*(?:x\s*)?(?:\d+G|ports?)',  # "64 ports" or "32x 400G"
            r'(\d+)-port',                         # "48-port switch"
            r'(\d+)\s*x\s*\d+\s*(?:G|GbE)',      # "96 x 100 GbE"
            r'(\d+)\s*QSFP',                       # "32 QSFP-DD"
            r'(\d+)\s*OSFP',                       # "64 OSFP"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                port_count = int(match.group(1))
                print(f"   Detected port count: {port_count}")
                return port_count
        
        raise ValueError("Could not extract port count from datasheet")
    
    def _extract_physical_port_count(self, text: str, logical_ports: int) -> int:
        """Extract physical connector count (may differ from logical ports).
        
        Split-port switches have fewer physical connectors than logical ports.
        Example: NVIDIA QM9700 has 32 OSFP connectors but supports 64 logical ports.
        
        Args:
            text: Datasheet text
            logical_ports: Number of logical ports already extracted
            
        Returns:
            Number of physical connectors
        """
        # Look for explicit physical connector count
        physical_patterns = [
            r'(\d+)\s*(?:physical|OSFP|QSFP)\s*(?:connectors?|ports?)',
            r'(\d+)\s*x\s*(?:OSFP|QSFP)',
        ]
        
        for pattern in physical_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                physical = int(match.group(1))
                if physical < logical_ports:
                    print(f"   Split-port detected: {physical} physical → {logical_ports} logical")
                    return physical
        
        # Default: assume physical = logical
        return logical_ports
    
    def _detect_split_port_capability(self, text: str) -> bool:
        """Detect if switch supports port splitting/breakout.
        
        Looks for keywords indicating split-port capability:
        - "radix", "split", "breakout", "twin-port"
        
        Args:
            text: Datasheet text
            
        Returns:
            True if split-port capable
        """
        keywords = ["radix", "split", "breakout", "twin-port", "port splitting"]
        text_lower = text.lower()
        
        for keyword in keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def _extract_interface_naming(self, vendor: str, text: str) -> str:
        """Determine interface naming convention.
        
        Different vendors use different naming schemes:
        - NVIDIA/Mellanox: p1, p2, ... p64
        - Arista: Ethernet1, Ethernet2, ...
        - Cisco: Ethernet1/1, Ethernet1/2, ...
        - Juniper: et-0/0/0, et-0/0/1, ...
        
        Args:
            vendor: Vendor name
            text: Datasheet text (may contain interface examples)
            
        Returns:
            Interface template with {id} placeholder
        """
        vendor_lower = vendor.lower()
        
        # Vendor-specific conventions (most reliable)
        conventions = {
            "nvidia": "p{{id}}",
            "mellanox": "p{{id}}",
            "arista": "Ethernet{{id}}",
            "cisco": "Ethernet1/{{id}}",
            "juniper": "et-0/0/{{id}}",
        }
        
        if vendor_lower in conventions:
            return conventions[vendor_lower]
        
        # Fallback: generic naming
        return "Ethernet{{id}}"
    
    def _extract_os_version(self, vendor: str, text: str) -> str:
        """Extract OS version from datasheet text.
        
        Looks for OS keywords in the text:
        - NVIDIA: "Onyx", "Cumulus"
        - Arista: "EOS"
        - Cisco: "NX-OS", "IOS-XE"
        - Juniper: "Junos"
        
        Args:
            vendor: Vendor name
            text: Datasheet text
            
        Returns:
            OS version string (e.g., "Onyx 5.2.0", "EOS 4.28")
        """
        vendor_lower = vendor.lower()
        text_lower = text.lower()
        
        # Vendor-specific OS detection
        if "nvidia" in vendor_lower or "mellanox" in vendor_lower:
            if "onyx" in text_lower:
                # Try to extract version number
                version_match = re.search(r'onyx\s+v?(\d+\.\d+\.?\d*)', text_lower)
                if version_match:
                    return f"Onyx {version_match.group(1)}"
                return "Onyx 5.2.0"  # Default version
            elif "cumulus" in text_lower:
                return "Cumulus Linux 5.x"
        
        elif "arista" in vendor_lower:
            if "eos" in text_lower:
                version_match = re.search(r'eos\s+v?(\d+\.\d+)', text_lower)
                if version_match:
                    return f"EOS {version_match.group(1)}"
                return "EOS 4.28"
        
        elif "cisco" in vendor_lower:
            if "nx-os" in text_lower:
                return "NX-OS 10.2"
            elif "ios" in text_lower:
                return "IOS-XE 17.x"
        
        elif "juniper" in vendor_lower:
            return "Junos 22.x"
        
        # Fallback
        return "latest"
