import requests
import json
import time

# Correct Portia API base
PORTIA_API_BASE = "http://localhost:9001/api"

def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {"status_code": r.status_code, "text": r.text}

def add_sample(project_name, spider_name, url):
    data = {"url": url}
    r = requests.post(f"{PORTIA_API_BASE}/projects/{project_name}/spiders/{spider_name}/samples/", json=data)
    return safe_json(r)

def run_spider(project_name, spider_name):
    r = requests.post(f"{PORTIA_API_BASE}/projects/{project_name}/spiders/{spider_name}/run/")
    return safe_json(r)

def get_samples(project_name, spider_name):
    r = requests.get(f"{PORTIA_API_BASE}/projects/{project_name}/spiders/{spider_name}/samples/")
    return safe_json(r)

def get_portia_data_dynamic(url, project_name="template_project", spider_name="template_spider"):
    """
    Hybrid dynamic scraping:
    1. Add URL as a sample to template spider
    2. Run spider
    3. Fetch results
    """
    add_sample(project_name, spider_name, url)
    run_spider(project_name, spider_name)
    time.sleep(2)  # small delay for scraping
    samples = get_samples(project_name, spider_name)
    return samples
