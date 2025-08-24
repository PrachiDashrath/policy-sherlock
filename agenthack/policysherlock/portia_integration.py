import json
from tools.ollama_agent import ask_ollama

def _safe_json_parse(text: str):
    """
    Try to extract and parse the first top-level JSON object from a text blob.
    Falls back to a dict with the raw text.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        blob = text[start:end+1]
        try:
            return json.loads(blob)
        except Exception:
            pass
    return {"raw_ai": text}

def portia_enrich(page_name: str, url: str, html_sample: str, counts: dict) -> dict:
    """
    Ask the local LLM (standing in for Portia) to return a STRICT JSON assessment.
    Returns a Python dict ready to be saved/merged later.
    """
    prompt = f"""
You are Portia, a strict compliance auditor. Return ONLY valid minified JSON
(no markdown, no backticks, no commentary).

Required keys and types:
{{
  "personal_data_types": [string],           // e.g., ["email", "password", "name"]
  "consent_mechanisms_seen": [string],       // e.g., ["cookie_banner", "checkbox", "none"]
  "trackers_suspected": [string],            // e.g., ["google_analytics", "meta_pixel"]
  "policy_gaps": [{{"issue": string, "evidence": string}}], // concise list
  "lawful_basis_guess": [string],            // e.g., ["consent", "contract", "legitimate_interest"]
  "risk_score": "low" | "medium" | "high",
  "remediations": [string]                   // concrete fixes in short bullets
}}

Context:
page_name: {page_name}
url: {url}
counts: {counts}

HTML sample (truncated):
{html_sample[:4000]}
"""
    ai = ask_ollama(prompt)
    return _safe_json_parse(ai)
