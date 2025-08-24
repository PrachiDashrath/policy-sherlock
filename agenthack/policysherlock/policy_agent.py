# policysherlock/policy_agent.py

import re

def analyze_policy(text: str) -> str:
    """
    Very basic demo tool that 'analyzes' a given policy or legal-like text.
    It checks for keywords like 'data', 'privacy', 'liability' etc. and returns insights.
    """

    issues = []

    if re.search(r"\bdata\b", text, re.IGNORECASE):
        issues.append("Mentions 'data' → possible privacy implications.")
    
    if re.search(r"\bprivacy\b", text, re.IGNORECASE):
        issues.append("Mentions 'privacy' → check GDPR/DPDP Act compliance.")
    
    if re.search(r"\bliability\b", text, re.IGNORECASE):
        issues.append("Mentions 'liability' → check contractual obligations.")
    
    if re.search(r"\btermination\b", text, re.IGNORECASE):
        issues.append("Mentions 'termination' → review conditions for fairness.")
    
    if not issues:
        return "No specific risks detected in this text."

    return "Policy Analysis:\n" + "\n".join([f"- {issue}" for issue in issues])
