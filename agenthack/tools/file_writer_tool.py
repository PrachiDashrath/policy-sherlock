import os

def write_file(path: str, content: str):
    """
    Writes content to a file.
    Creates parent directories if they don’t exist.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"[✅] File written: {path}"
