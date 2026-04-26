# Comparative Analyzer Library for Baseline Comparison
# Performs sophisticated analysis between technician data and baseline reference data

from typing import List, Dict, Optional
from app.libs.gemini_client import get_gemini_client

class ComparativeAnalyzer:
    """
    Performs comparative analysis between technician's data and baseline/reference data.
    """
    
    def __init__(self):
        """Initialize the comparative analyzer with Gemini LLM."""
        self.llm = get_gemini_client()
    
    def analyze(
        self, 
        query: str, 
        general_chunks: List[Dict], 
        baseline_chunks: List[Dict],
        technician_data: Optional[str] = None,
        constraints: Optional[str] = None
    ) -> str:
        """Perform comparative analysis."""
        prompt = self._build_comparative_prompt(
            query, general_chunks, baseline_chunks, technician_data, constraints
        )
        
        try:
            response = self.llm.generate_content(prompt, model='gemini-1.5-pro')
            return response
        except Exception as e:
            print(f"[COMPARATIVE_ANALYZER] Error: {e}")
            return f"Analysis failed: {str(e)}"
    
    def _build_comparative_prompt(
        self, 
        query: str, 
        general_chunks: List[Dict], 
        baseline_chunks: List[Dict],
        technician_data: Optional[str] = None,
        constraints: Optional[str] = None
    ) -> str:
        """
        Builds the detailed comparative analysis prompt.
        """
        
        # Extract text content from chunks
        general_context = self._chunks_to_text(general_chunks)
        baseline_context = self._chunks_to_text(baseline_chunks)
        
        # Build base prompt
        base_prompt = """You are an expert diagnostic assistant helping a field technician troubleshoot equipment.

Your task is to perform a **COMPARATIVE ANALYSIS** between the technician's current situation and the established baseline (known-good reference state)."""
        
        # Inject constraints if available
        if constraints:
            print("[COMPARATIVE_ANALYZER] Injecting constraints into baseline comparison prompt")
            base_prompt += f"\n\n{constraints}\n"
        
        prompt = f"""{base_prompt}

═══════════════════════════════════════════════════════════════
📋 TECHNICIAN'S QUERY
═══════════════════════════════════════════════════════════════
{query}

═══════════════════════════════════════════════════════════════
📚 GENERAL CONTEXT (Background information about the equipment)
═══════════════════════════════════════════════════════════════
{general_context if general_context else "No general context available."}

═══════════════════════════════════════════════════════════════
✅ BASELINE DATA (How the system SHOULD behave - Known Good State)
═══════════════════════════════════════════════════════════════
{baseline_context if baseline_context else "⚠️ WARNING: No baseline data found. Cannot perform comparison."}

═══════════════════════════════════════════════════════════════
🔍 TECHNICIAN'S CURRENT DATA (How the system IS behaving)
═══════════════════════════════════════════════════════════════
{technician_data if technician_data else "Data is embedded in the query above."}

═══════════════════════════════════════════════════════════════
🎯 YOUR ANALYSIS INSTRUCTIONS
═══════════════════════════════════════════════════════════════

1. **COMPARE** the technician's data against the baseline data
2. **IDENTIFY** specific deviations, differences, or anomalies
3. **ASSESS** the severity of each deviation (Critical, High, Medium, Low)
4. **HYPOTHESIZE** the most likely root cause(s)
5. **RECOMMEND** a step-by-step troubleshooting plan

═══════════════════════════════════════════════════════════════
📤 REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

Please structure your response as follows:

## 🔴 CRITICAL DEVIATIONS FOUND

| Parameter | Baseline (Expected) | Actual (Observed) | Deviation | Severity |
|-----------|---------------------|-------------------|-----------|----------|
| [param]   | [value]             | [value]           | [delta]   | [level]  |

## 💡 ROOT CAUSE HYPOTHESIS

[Your analysis of what is most likely causing these deviations]

## 🛠️ RECOMMENDED ACTION PLAN

1. **[First Step]**: [Detailed instructions]
   - Expected outcome: [what should happen]
   - If successful: [next step]
   - If unsuccessful: [alternative action]

2. **[Second Step]**: ...

## ⚠️ SAFETY WARNINGS

[Any safety concerns the technician should be aware of]

## 📎 REFERENCES

[List which baseline documents were used for comparison]

═══════════════════════════════════════════════════════════════

If NO baseline data is available, inform the technician that you cannot perform a proper comparison and suggest they:
1. Request that an admin upload baseline/reference data for this equipment
2. Use general troubleshooting mode instead

Begin your analysis now:
"""
        
        return prompt
    
    def _chunks_to_text(self, chunks: List[Dict]) -> str:
        """
        Converts chunk list to formatted text for the prompt.
        """
        if not chunks:
            return ""
        
        text_lines = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            doc_title = metadata.get("title", "Unknown Document")
            chunk_type = metadata.get("type", "text")
            
            if chunk_type == "text":
                content = chunk.get("content", "")
                text_lines.append(f"[Source {i}: {doc_title}]")
                text_lines.append(content)
                text_lines.append("---")
            elif chunk_type == "image":
                # For images, just reference them
                gcs_url = metadata.get("gcs_url", "")
                text_lines.append(f"[Source {i}: {doc_title} - Image]")
                text_lines.append(f"Image reference: {gcs_url}")
                text_lines.append("---")
        
        return "\n".join(text_lines)

# Usage:
# analyzer = ComparativeAnalyzer()
# result = analyzer.analyze(query, general_chunks, baseline_chunks, technician_file_content)
