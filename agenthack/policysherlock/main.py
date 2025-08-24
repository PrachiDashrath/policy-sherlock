import sys
import os
import re
import requests
from bs4 import BeautifulSoup
import datetime
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.table import Table

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.csv_append_tool import append_row
from tools.file_writer_tool import write_file
from policysherlock.policy_agent import analyze_policy
from tools.ollama_agent import ask_ollama

# -----------------------
# Config
# -----------------------
OUTPUTS_ROOT = "outputs"
OUTPUT_CSV_NAME = "data_inventory.csv"
OUTPUT_POLICY_MD_NAME = "policy_gaps.md"
MAX_RUNS_TO_KEEP = 5
PORTIA_API_BASE = "http://localhost:9001"
MAX_THREADS = 5

console = Console()

# -----------------------
# Helpers
# -----------------------
def sanitize_name(name: str) -> str:
    sanitized = re.sub(r'[^A-Za-z0-9_-]', '_', name.strip())
    if not sanitized:
        sanitized = "default_name"
    return sanitized

def fetch_page(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        return f"Failed to fetch page, status code {response.status_code}"
    except Exception as e:
        return f"Error fetching page: {e}"

def detect_cookies_and_trackers(soup: BeautifulSoup):
    cookies = bool(soup.find(string=lambda s: s and "cookie" in s.lower()))
    trackers = soup.find_all("script", src=True)
    return cookies, len(trackers)

# -----------------------
# Portia Helpers
# -----------------------
def create_portia_project(project_name: str) -> bool:
    try:
        payload = {"name": project_name}
        response = requests.post(f"{PORTIA_API_BASE}/api/projects", json=payload)
        if response.status_code in (200, 201):
            return True
        elif response.status_code == 400 and "already exists" in str(response.json()).lower():
            return True  # project already exists
        else:
            console.print(f"[red]Failed to create project {project_name}: {response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]Error creating project: {e}[/red]")
        return False

def create_portia_spider(project_name: str, spider_name: str) -> bool:
    try:
        payload = {"name": spider_name}
        response = requests.post(f"{PORTIA_API_BASE}/api/projects/{project_name}/spiders", json=payload)
        if response.status_code in (200, 201):
            return True
        elif response.status_code == 400 and "already exists" in str(response.json()).lower():
            return True  # spider already exists
        else:
            console.print(f"[red]Failed to create spider {spider_name}: {response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]Error creating spider: {e}[/red]")
        return False

def list_portia_spiders(project_name):
    url = f"http://localhost:9001/api/projects/{project_name}/spiders"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        spiders = [spider["id"] for spider in data.get("data", [])]
        return spiders
    else:
        print("Error:", response.status_code, response.text)
        return []

def get_portia_data(url: str, project_name: str, spider_name: str):
    try:
        api_url = f"{PORTIA_API_BASE}/api/projects/{project_name}/spiders/{spider_name}/samples"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return str(data)[:200] if isinstance(data, (dict, list)) else str(data)
        elif response.status_code == 404:
            return "No Portia samples available yet."
        return f"Failed to fetch Portia data, status: {response.status_code}"
    except Exception as e:
        return f"Portia error: {e}"

def cleanup_old_outputs():
    if os.path.exists(OUTPUTS_ROOT):
        all_runs = sorted(
            [os.path.join(OUTPUTS_ROOT, d) for d in os.listdir(OUTPUTS_ROOT)],
            key=os.path.getmtime,
            reverse=True
        )
        for old_run in all_runs[MAX_RUNS_TO_KEEP:]:
            shutil.rmtree(old_run)

# -----------------------
# AI Helpers
# -----------------------
def summarize_policy(policy_text: str) -> str:
    return policy_text[:200] + "..." if len(policy_text) > 200 else policy_text

def compare_policies(policy_a: str, policy_b: str) -> str:
    diff = set(policy_a.split()) ^ set(policy_b.split())
    return "Differences: " + ", ".join(list(diff)[:20]) + "..."

def detect_bias(policy_text: str) -> str:
    if "unlimited" in policy_text.lower():
        return "⚠️ Possible over-promising detected."
    return "No obvious bias detected."

# -----------------------
# Audit Function
# -----------------------
def audit_page(page_name: str, url: str, output_csv: str, output_folder: str, project_name: str, spider_name: str):
    console.print(f"\n[bold cyan]🔎 Auditing {url} ...[/bold cyan]")
    page_html = fetch_page(url)
    soup = BeautifulSoup(page_html, "html.parser")

    form_count = len(soup.find_all("form"))
    input_count = len(soup.find_all("input"))
    cookies_present, tracker_count = detect_cookies_and_trackers(soup)

    prompt = f"""
    Analyze the following HTML page for data collection, forms, cookies, trackers, and privacy issues.
    Mention forms, inputs, cookies banners, trackers, and any potential privacy gaps.

    HTML:
    {page_html[:5000]}
    """
    ai_analysis = ask_ollama(prompt)
    portia_summary = get_portia_data(url, project_name, spider_name)

    row = [
        page_name,
        url,
        form_count,
        input_count,
        "Yes" if cookies_present else "No",
        tracker_count,
        ai_analysis[:200],
        portia_summary[:200]
    ]
    msg = append_row(output_csv, row)
    console.print(f"[green]{msg}[/green]")

    page_md_path = os.path.join(output_folder, f"{page_name}_analysis.md")
    write_file(page_md_path, ai_analysis)

    return {
        "Page": page_name,
        "URL": url,
        "Forms": form_count,
        "Inputs": input_count,
        "Cookies": "Yes" if cookies_present else "No",
        "Trackers": tracker_count,
        "Ollama": ai_analysis[:50] + "...",
        "Portia": portia_summary[:50] + "..."
    }

# -----------------------
# Main Function
# -----------------------
def main():
    console.print("[bold magenta]🚀 PolicySherlock started with Ollama AI & Portia![/bold magenta]\n")

    # ---- Project setup ----
    project_name = sanitize_name(input("Enter Portia project name: "))

    if not create_portia_project(project_name):
        console.print("[red]Could not create or access project. Exiting.[/red]")
        return

    # ---- Spider selection / creation ----
    spiders = list_portia_spiders(project_name)

    if spiders:
        console.print(f"[yellow]Spiders available: {spiders}[/yellow]")
        spider_name = input("Choose a spider from the list or type a new one: ").strip()
        spider_name = sanitize_name(spider_name)
    else:
        spider_name = sanitize_name(input("No spiders found. Enter a new spider name: "))

    if not create_portia_spider(project_name, spider_name):
        console.print("[red]Could not create or access spider. Exiting.[/red]")
        return

    # ---- Output setup ----
    cleanup_old_outputs()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(OUTPUTS_ROOT, timestamp)
    os.makedirs(output_folder, exist_ok=True)

    output_csv = os.path.join(output_folder, OUTPUT_CSV_NAME)
    output_policy_md = os.path.join(output_folder, OUTPUT_POLICY_MD_NAME)

    # ---- Pages input ----
    pages_to_audit = []
    num_pages = int(input("How many pages do you want to audit? "))
    for i in range(num_pages):
        page_name = input(f"Enter a name for page {i+1}: ")
        url = input(f"Enter URL for page {i+1}: ")
        pages_to_audit.append((page_name, url))

    # ---- Audit execution ----
    table = Table(title="PolicySherlock Audit Results")
    for col in ["Page", "URL", "Forms", "Inputs", "Cookies", "Trackers", "Ollama", "Portia"]:
        table.add_column(col, style="cyan")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_page = {
            executor.submit(audit_page, page_name, url, output_csv, output_folder, project_name, spider_name): (page_name, url)
            for page_name, url in pages_to_audit
        }
        for future in as_completed(future_to_page):
            result = future.result()
            table.add_row(
                result["Page"], result["URL"], str(result["Forms"]),
                str(result["Inputs"]), result["Cookies"], str(result["Trackers"]),
                result["Ollama"], result["Portia"]
            )
            console.clear()
            console.print(table)

    # ---- Policy analysis ----
    sample_policy_text = """
    Our site collects user data for analytics. Privacy policy is limited. Liability not mentioned.
    """
    policy_analysis = analyze_policy(sample_policy_text)
    write_file(output_policy_md, policy_analysis)
    console.print(f"\n✅ Policy analysis saved to {output_policy_md}")
    console.print(f"✅ All page analyses and CSV summary saved in {output_folder}")

if __name__ == "__main__":
    main()
