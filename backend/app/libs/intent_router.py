# Intent Router Library for Multi-Source RAG
# Classifies user queries to determine which knowledge bases to search

from typing import Dict, Any
from app.libs.namespace_utils import get_company_intent_definitions
from app.libs.gemini_client import get_gemini_client

class IntentRouter:
    """
    Routes queries to appropriate knowledge base namespaces.
    Uses LLM to classify intent and target the most relevant data source.
    """
    
    def __init__(self, company_id: str = None):
        """
        Initialize the IntentRouter with optional company-specific configuration.
        
        Args:
            company_id: Optional company ID to load custom intent definitions.
                       If not provided, uses default intents.
        """
        self.llm = get_gemini_client()
        self.company_id = company_id
        
        # Load intent definitions (custom or default)
        if company_id:
            self.intent_definitions = get_company_intent_definitions(company_id)
        else:
            # Fallback to hardcoded defaults
            self.intent_definitions = [
                {"id": "general", "displayName": "General", "description": "General knowledge", "keywords": []},
                {"id": "baseline_comparison", "displayName": "Baseline Comparison", "description": "Standard guidelines", "keywords": ["compare", "baseline", "standard", "correct", "normal", "should be", "supposed to"]},
                {"id": "historic", "displayName": "Historic", "description": "Historical records", "keywords": ["last time", "previous", "history", "before", "past", "how did we fix"]},
                {"id": "expert", "displayName": "Expert", "description": "Expert tips", "keywords": ["expert", "tip", "best practice", "recommendation", "field"]},
                {"id": "multi", "displayName": "Multi", "description": "Broad query", "keywords": []}
            ]
        
        print(f"[INTENT_ROUTER] Loaded {len(self.intent_definitions)} intent definitions for company '{company_id}'")
    
    def classify(self, query: str, has_uploaded_file: bool = False) -> Dict[str, Any]:
        """
        Classifies the user's intent.
        
        Returns:
        {
            "intent": "baseline_comparison",
            "confidence": "high",
            "reasoning": "Query contains 'compare' and user uploaded a file",
            "method": "keyword"  # or "llm"
        }
        """
        
        # TIER 1: Fast keyword-based classification
        query_lower = query.lower()
        
        # Check each intent's keywords
        for intent_def in self.intent_definitions:
            intent_id = intent_def["id"]
            keywords = intent_def.get("keywords", [])
            
            # Skip intents with no keywords (they'll be handled by LLM)
            if not keywords:
                continue
            
            # Check if any keyword matches
            if any(keyword.lower() in query_lower for keyword in keywords):
                confidence = "high" if has_uploaded_file else "medium"
                return {
                    "intent": intent_id,
                    "confidence": confidence,
                    "reasoning": f"Query matches '{intent_def['displayName']}' keywords",
                    "method": "keyword"
                }
        
        # TIER 2: Ambiguous - use LLM
        print("[INTENT_ROUTER] Query is ambiguous, calling LLM for classification...")
        return self._llm_classify(query, has_uploaded_file)
    
    def _llm_classify(self, query: str, has_uploaded_file: bool) -> Dict[str, Any]:
        """
        Uses LLM to classify ambiguous queries using dynamic intent definitions.
        """
        # Build dynamic intent list for LLM prompt
        intent_descriptions = []
        for intent_def in self.intent_definitions:
            intent_id = intent_def["id"]
            display_name = intent_def.get("displayName", intent_id)
            description = intent_def.get("description", "")
            intent_descriptions.append(f'- "{intent_id}": {display_name} - {description}')
        
        intent_list_str = "\n".join(intent_descriptions)
        valid_intent_ids = [intent["id"] for intent in self.intent_definitions]
        
        prompt = f"""You are an intent classifier for a technical troubleshooting assistant.

User's query: "{query}"
User uploaded a file: {has_uploaded_file}

Classify the user's intent into ONE of these categories:
{intent_list_str}

Respond in this EXACT JSON format:
{{
  "intent": "<one of: {', '.join(valid_intent_ids)}>",
  "confidence": "<high|medium|low>",
  "reasoning": "<brief explanation of your classification>"
}}
"""
        
        try:
            response = self.llm.generate_content(prompt, model='gemini-2.0-flash-exp')
            result_text = response.strip()
            
            # Parse JSON response
            import json
            # Remove markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            result["method"] = "llm"
            
            # Validate that returned intent is in our list
            if result["intent"] not in valid_intent_ids:
                print(f"[INTENT_ROUTER] LLM returned invalid intent '{result['intent']}', defaulting to general")
                result["intent"] = valid_intent_ids[0] if valid_intent_ids else "general"
            
            return result
            
        except Exception as e:
            print(f"[INTENT_ROUTER] LLM classification failed: {e}")
            # Fallback to first intent (usually 'general')
            fallback_intent = valid_intent_ids[0] if valid_intent_ids else "general"
            return {
                "intent": fallback_intent,
                "confidence": "low",
                "reasoning": "LLM classification failed, defaulting to fallback",
                "method": "fallback"
            }

# Usage example:
# router = IntentRouter()
# intent_result = router.classify("Compare these logs to the baseline", has_uploaded_file=True)
# print(intent_result["intent"])  # "baseline_comparison"
