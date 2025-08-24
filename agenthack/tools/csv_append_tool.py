import os
import csv

def append_row(csv_path: str, row: list) -> str:
    """
    Append a single row to a CSV file.
    Creates the file with headers if it doesn't exist.
    """
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    file_exists = os.path.isfile(csv_path)

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            # Write headers
            writer.writerow(["page", "url", "forms", "inputs", "cookies", "trackers", "ai_summary"])

        writer.writerow(row)

    return f"✅ Row appended to: {csv_path}"
