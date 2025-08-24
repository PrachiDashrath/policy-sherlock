# policysherlock/reporting.py

def build_policy_report_md(title, summary, risks, key_clauses):
    """
    Build a Markdown report string for policy analysis.
    """
    md = f"# Policy Report: {title}\n\n"
    md += f"## 🧠 Executive Summary\n{summary}\n\n"
    md += f"## ⚠️ Risks & Gaps\n{risks}\n\n"
    md += f"## 📑 Key Clauses\n{key_clauses}\n"
    return md

def to_bytes(text):
    """
    Convert string to bytes for download.
    """
    return text.encode("utf-8")
