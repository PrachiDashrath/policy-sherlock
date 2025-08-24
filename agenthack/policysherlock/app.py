import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from bs4 import BeautifulSoup
import requests
import json

# --- App Logic Imports (unchanged) ---
from policysherlock.main import (
    ask_ollama,
    analyze_policy,
    fetch_page,
    summarize_policy,
    compare_policies,
    detect_bias,
    detect_cookies_and_trackers,
)
from policysherlock.text_utils import load_text_from_upload, chunk_text, keyword_rank
from policysherlock.reporting import build_policy_report_md, to_bytes

# =========================
# Dynamic Portia API Client
# =========================
class PortiaAPIClient:
    def __init__(self, portia_url="http://localhost:9001", scrapyd_url="http://localhost:6800"):
        self.portia_url = portia_url
        self.scrapyd_url = scrapyd_url

    def get_projects(self):
        try:
            r = requests.get(f"{self.portia_url}/api/projects", timeout=5)
            if r.status_code == 200:
                data = r.json()
                return [p["id"] for p in data.get("data", [])]
            return []
        except Exception as e:
            st.error(f"Error fetching projects: {e}")
            return []


    def get_scrapyd_spiders(self, project_name):
        try:
            r = requests.get(f"{self.scrapyd_url}/api/projects/{project_name}/spiders", params={"project": project_name}, timeout=5)
            if r.status_code == 200:
                data = r.json()
                return data.get("spiders", [])
            return []
        except Exception as e:
            st.error(f"Error fetching Scrapyd spiders: {e}")
            return []

    def get_spider_pages(self, project_name, spider_name):
      try:
        r = requests.get(f"{self.portia_url}/api/projects/{project_name}/spiders/{spider_name}/samples",timeout=5)
        if r.status_code == 200:
            data = r.json()
            pages = [s["id"] for s in data.get("data", [])]
            return pages
        return []
      except Exception as e:
            st.warning(f"Could not fetch spider pages: {e}")
            return []


    def get_spiders(self, project_name):
     try:
        url = f"{self.portia_url}/api/projects/{project_name}/spiders"
        r = requests.get(url, timeout=5)

        if r.status_code == 200:
            try:
                data = r.json()
                spiders = [s.get("id", s) for s in data.get("data", [])]
                return spiders
            except Exception as parse_err:
                st.error(f"JSON parse error: {parse_err}")
                return []
        else:
            st.error(f"Failed with status {r.status_code}: {r.text}")
            return []
     except Exception as e:
        st.warning(f"Could not fetch spiders: {e}")
        return []


    def schedule_spider(self, project_name, spider_name, page_name=None):
        try:
            data = {"project": project_name, "spider": spider_name}
            if page_name:
                data["page"] = page_name
            r = requests.post(f"{self.scrapyd_url}/schedule.json", data=data, timeout=10)
            return r.json()
        except Exception as e:
            st.error(f"Error scheduling spider: {e}")
            return None

    def check_connection_status(self):
        portia_status = "❌ Not Connected"
        scrapyd_status = "❌ Not Connected"
        try:
            pr = requests.get(f"{self.portia_url}/api/projects", timeout=5)
            portia_status = "✅ Connected" if pr.status_code == 200 else "❌ Error"
        except:
            pass
        try:
            sr = requests.get(f"{self.scrapyd_url}/daemonstatus.json", timeout=5)
            scrapyd_status = "✅ Connected" if sr.status_code == 200 else "❌ Error"
        except:
            pass
        return portia_status, scrapyd_status

def get_portia_data_dynamic(url, api_client, project_name, spider_name, page_name=None):
    try:
        result = api_client.schedule_spider(project_name, spider_name, page_name)
        if result and result.get("status") == "ok":
            return {
                "status": "scheduled",
                "job_id": result["jobid"],
                "url": url,
                "project": project_name,
                "spider": spider_name,
                "page": page_name or "default",
            }
        else:
            return {"status": "failed", "error": "Could not schedule spider"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ===================
# Streamlit Page Meta
# ===================
st.set_page_config(
    page_title="PolicySherlock · Next-Gen Policy & Web Auditor",
    page_icon="🕵️‍♀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========
# NEW THEME
# =========
st.markdown("""
<style>
/* Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Color system with variables */
:root {
  --bg: #0b1220;
  --bg-soft: rgba(255,255,255,0.04);
  --card: rgba(255,255,255,0.06);
  --card-strong: rgba(255,255,255,0.10);
  --text: #e6e8ee;
  --muted: #9aa4b2;
  --brand1: #7c5cff;
  --brand2: #22c1c3;
  --accent: #00d4ff;
  --success: #10b981;
  --warn: #f59e0b;
  --danger: #ef4444;
  --ring: rgba(124, 92, 255, 0.35);
}

/* Optional light theme (auto if user has light preference) */
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f7f8fb;
    --bg-soft: rgba(0,0,0,0.04);
    --card: rgba(255,255,255,0.9);
    --card-strong: rgba(255,255,255,1);
    --text: #0f172a;
    --muted: #475569;
    --brand1: #5a48ff;
    --brand2: #0ea5e9;
    --accent: #06b6d4;
    --ring: rgba(14,165,233,0.35);
  }
}

/* Global base */
html, body, [class*="css"] {
  font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif !important;
  color: var(--text);
}

.main {
  background:
    radial-gradient(1200px 800px at 0% 0%, rgba(124,92,255,0.18), transparent 50%),
    radial-gradient(900px 600px at 100% 0%, rgba(0,212,255,0.15), transparent 50%),
    linear-gradient(180deg, var(--bg), var(--bg));
}

/* Sticky top bar */
.ps-topbar {
  position: sticky; top: 0; z-index: 1000;
  backdrop-filter: blur(10px);
  background: linear-gradient(90deg, var(--card), transparent);
  border-bottom: 1px solid var(--bg-soft);
  padding: 14px 18px; border-radius: 14px;
  margin-bottom: 16px;
}
.ps-topbar .row { display:flex; align-items:center; gap:12px; justify-content:space-between; }
.ps-badge {
  display:inline-flex; align-items:center; gap:8px;
  padding:8px 12px; border-radius: 999px; font-weight:600; font-size:13px;
  background: linear-gradient(135deg, var(--brand1), var(--accent));
  color: white; box-shadow: 0 10px 30px rgba(124,92,255,0.35);
}
.ps-quick {
  display:flex; gap:8px; align-items:center;
}
.ps-quick button {
  all:unset; cursor:pointer;
  padding:10px 14px; border-radius:12px; font-weight:600; font-size:14px;
  background: var(--card); border: 1px solid var(--bg-soft);
}
.ps-quick button:hover { transform: translateY(-1px); box-shadow: 0 6px 14px rgba(0,0,0,0.25); }

/* Containers / cards */
.ps-section { margin-top: 8px; margin-bottom: 12px; }
.ps-card {
  background: var(--card);
  border: 1px solid var(--bg-soft);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.15);
  transition:.2s transform, .2s box-shadow;
}


.ps-card:hover { transform: translateY(-2px); box-shadow: 0 16px 36px rgba(0,0,0,0.25); }

/* Headings */
.ps-h1 {
  font-size: 36px; font-weight: 800; letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--brand1), var(--accent));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin:0 0 8px 0;
}
.ps-sub {
  color: var(--muted); font-size: 14px; margin-bottom: 14px;
}

/* Metric chips */
.ps-chip {
  display:inline-flex; align-items:center; gap:8px;
  padding: 8px 12px; border-radius: 999px; font-size: 12.5px; font-weight: 700;
  color:#fff; background: linear-gradient(135deg, var(--brand1), var(--brand2));
  box-shadow: 0 6px 18px rgba(124,92,255,0.35); margin:4px 6px 0 0;
}
.ps-chip--muted { background: var(--bg-soft); color: var(--text); box-shadow: none; }

/* Buttons */
.ps-btn {
  all:unset; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; gap:8px;
  padding: 12px 16px; border-radius: 12px; font-weight: 700; border: 1px solid var(--bg-soft);
  background: linear-gradient(135deg, var(--brand1), var(--accent)); color: white;
  box-shadow: 0 10px 26px rgba(124,92,255,0.35);
}
.ps-btn.secondary { background: var(--card-strong); color: var(--text); }
.ps-btn:hover { transform: translateY(-1px); }

/* Status labels */
.ps-status { display:inline-flex; gap:8px; align-items:center; padding:8px 12px; border-radius:999px; font-weight:700; font-size:12.5px; }
.ps-ok { background: rgba(16,185,129,.18); color:#10b981; border:1px solid rgba(16,185,129,.28); }
.ps-bad { background: rgba(239,68,68,.18); color:#ef4444; border:1px solid rgba(239,68,68,.28); }

/* Inputs polish */
input, textarea, select {
  border-radius: 10px !important; border: 1.5px solid var(--bg-soft) !important;
}
textarea:focus, input:focus, select:focus {
  outline: none !important; box-shadow: 0 0 0 3px var(--ring) !important; border-color: transparent !important;
}

/* Tables/Dataframe wrapper */
.ps-table-wrap { border-radius: 12px; overflow: hidden; border: 1px solid var(--bg-soft); }

/* Subtle separators */
.ps-sep { height:1px; background: var(--bg-soft); margin: 14px 0; }

/* Code/context block */
.ps-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  background: rgba(2,6,23,.6); border:1px solid var(--bg-soft); border-radius: 10px; padding:12px; white-space: pre-wrap;
}

/* Hide default Streamlit header/footer whitespace feel */
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { border-right: 1px solid var(--bg-soft); }

/* Small helper classes */
.center { display:flex; align-items:center; justify-content:center; }
.right { display:flex; justify-content:flex-end; }
.space { height: 8px; }
</style>
""", unsafe_allow_html=True)

# ==========
# Top Bar UI
# ==========
st.markdown("""
<div class="ps-topbar">
  <div class="row">
    <div class="left">
      <div class="ps-badge">🕵️‍♀️ PolicySherlock</div>
    </div>
    <div class="ps-quick">
      <button onclick="window.location.reload()">⟳ Refresh</button>
      <button id="ps-scroll-top">↑ Top</button>
    </div>
  </div>
</div>
<script>
  const btn = document.getElementById('ps-scroll-top');
  if (btn) btn.onclick = () => window.scrollTo({top:0, behavior:'smooth'});
</script>
""", unsafe_allow_html=True)

# =========
# Hero Head
# =========
st.markdown("""
<div class="ps-section">
  <div class="ps-card">
    <div class="ps-h1">Next-Gen Website Auditor & Policy Intelligence</div>
    <div class="ps-sub">Audit websites for privacy risks, analyze and compare policies, and ask precise questions — all accelerated by your Portia scraping hub and AI.</div>
    <div>
      <span class="ps-chip">⚡ Real-time AI</span>
      <span class="ps-chip">🕷️ Portia Enhanced</span>
      <span class="ps-chip">🔒 Privacy-first</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ===============
# Sidebar Control
# ===============
api_client = PortiaAPIClient()
with st.sidebar:
    st.markdown("### 🔧 Connections")
    portia_status, scrapyd_status = api_client.check_connection_status()
    ok = "✅" in portia_status and "✅" in scrapyd_status
    st.markdown(
        f'<div class="ps-card"><div class="ps-sub">Service Status</div>'
        f'<div class="space"></div>'
        f'<span class="ps-status {"ps-ok" if "✅" in portia_status else "ps-bad"}">Portia: {portia_status}</span>'
	f'<div class="space"></div>'
        f'<span class="ps-status {"ps-ok" if "✅" in scrapyd_status else "ps-bad"}">Scrapyd: {scrapyd_status}</span>'
        f'</div>', unsafe_allow_html=True
    )

    st.markdown("### 🕷️ Portia Setup")
    portia_connected = "✅" in portia_status
    if portia_connected:
        with st.spinner("Loading projects..."):
            projects = api_client.get_projects()
        if projects:
            selected_project = st.selectbox("Project", options=projects, key="ps_project")
            with st.spinner("Loading spiders..."):
                portia_spiders = api_client.get_spiders(selected_project)
            selected_spider = st.selectbox("Spider", options=portia_spiders or ["—"], key="ps_spider")

            if selected_spider and selected_spider != "—":
                with st.spinner("Loading pages..."):
                    spider_pages = api_client.get_spider_pages(selected_project, selected_spider)
                selected_page = st.selectbox("Page/Template", options=(spider_pages or []) + ["default"], key="ps_page")
            else:
                selected_page = "default"

            st.session_state.update({
                                  "portia_project": selected_project,
                                  "portia_spider": selected_spider,
                                  "portia_page": selected_page,
                                  "portia_available": True if portia_spiders else False
                               })


            st.markdown('<div class="space"></div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="ps-card"><div class="ps-sub">Current Config</div>'
                f'<div class="ps-sep"></div>'
                f'📦 <b>Project</b>: {st.session_state.get("portia_project","—")}<br>'
                f'🕷️ <b>Spider</b>: {st.session_state.get("portia_spider","—")}<br>'
                f'📄 <b>Page</b>: {st.session_state.get("portia_page","default")}'
                f'</div>', unsafe_allow_html=True
            )
        else:
            st.warning("No projects found.")
            st.session_state["portia_available"] = False
    else:
        st.info("Connect Portia & Scrapyd to enable enhanced scraping.")
        st.session_state["portia_available"] = False

# =========
# NAV TABS
# =========
tabs = st.tabs(["🌐 Audit", "📄 Analyze", "🤝 Compare", "💬 Ask"])

# ==========================
# TAB 1: Website Audit (Updated)
# ==========================
with tabs[0]:
    st.markdown(
        '<div class="ps-section"><div class="ps-h1" style="font-size:24px">'
        'Website Privacy & Security Audit</div>'
        '<div class="ps-sub">Audit websites for forms, inputs, cookies, trackers, and AI insights. '
        'Choose Portia AI or enter URLs manually.</div></div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([3, 1], gap="large")

    with c1:
        portia_available = st.session_state.get("portia_available", False)
        use_portia = st.toggle(
            "Enable Portia Scraping",
            value=False,
            disabled=not portia_available,
            help="Use configured Portia spiders instead of manual URLs.",
        )

        urls = []
        if use_portia and portia_available:
            st.success("✅ Portia mode enabled")

            projects = api_client.get_projects()
            st.selectbox("Project", projects or [], key="audit_project")

            spiders = api_client.get_spiders(st.session_state.get("audit_project")) if st.session_state.get("audit_project") else []
            selected_spider = st.selectbox("Spider", spiders or [], key="audit_spider")

            pages = api_client.get_spider_pages(
                st.session_state.get("audit_project"), 
                st.session_state.get("audit_spider")
            ) if st.session_state.get("audit_spider") else []
            st.selectbox("Page/Template", (pages or ["default"]), key="audit_page")

            # Store selections
            selected_project = st.session_state.get("audit_project")
            selected_spider = st.session_state.get("audit_spider")
            selected_page = st.session_state.get("audit_page", "default")

        else:
            st.info("✏️ Manual mode enabled (Portia disabled). Enter URLs below:")
            urls_text = st.text_area(
                "URLs (one per line)",
                placeholder="https://github.com/\nhttps://www.wikipedia.org/\nhttps://example.com/privacy",
                height=140,
            )
            urls = [u.strip() for u in urls_text.splitlines() if u.strip()]

    with c2:
        st.markdown('<div class="space"></div>', unsafe_allow_html=True)
        run_audit = st.button("🚀 Run Audit", use_container_width=True)

    if run_audit:
        progress_bar = st.progress(0)
        status = st.empty()
        results_container = st.container()
        rows = []

        if use_portia and portia_available:
            # --- Portia-based audit ---
            project = st.session_state.get("audit_project")
            spider = st.session_state.get("audit_spider")
            page = st.session_state.get("audit_page", "default")

            if not (project and spider):
                st.error("Please select Project and Spider before running the audit.")
            else:
                with results_container:
                    st.markdown('<div class="ps-card">', unsafe_allow_html=True)
                    with st.spinner("Scheduling Portia job..."):
                        portia_result = get_portia_data_dynamic(None, api_client, project, spider, page)

                    if portia_result.get("status") == "scheduled":
                        st.success(f"Portia job scheduled · Job ID: {portia_result['job_id']}")
                        st.json(portia_result)
                    else:
                        st.warning("Could not schedule spider. Showing raw JSON from Portia:")
                        try:
                            raw_url = f"{api_client.portia_url}/api/projects/{selected_project}/spiders/{selected_spider}/samples"
                            response = requests.get(raw_url, timeout=5)
                            if response.status_code == 200:
                                st.json(response.json())  # Display raw JSON directly
                            else:
                                st.error(f"Failed to fetch JSON: {response.status_code}")
                        except Exception as e:
                            st.error(f"Error fetching JSON: {e}")

                    rows.append({
                        "Mode": "Portia",
                        "Project": project,
                        "Spider": spider,
                        "Page": page,
                        "Result": "Scheduled" if portia_result.get("status") == "scheduled" else "Error",
                    })
                    st.markdown('</div>', unsafe_allow_html=True)

        else:
            # --- Manual audit with URLs ---
            if not urls:
                st.warning("Please enter at least one URL to audit.")
            else:
                for i, url in enumerate(urls):
                    progress_bar.progress((i + 1) / len(urls))
                    status.info(f"Auditing {i+1}/{len(urls)}: {url}")

                    with results_container:
                        with st.container():
                            st.markdown('<div class="ps-card">', unsafe_allow_html=True)

                            # Parse HTML
                            html = fetch_page(url)
                            soup = BeautifulSoup(html, "html.parser")
                            forms = soup.find_all("form")
                            inputs = soup.find_all("input")
                            cookies_present, tracker_count = detect_cookies_and_trackers(soup)

                            # Metrics row
                            st.markdown(
                                f"""
                                <div style="display:flex; flex-wrap:wrap; gap:8px;">
                                  <span class="ps-chip">📝 Forms: {len(forms)}</span>
                                  <span class="ps-chip">⌨️ Inputs: {len(inputs)}</span>
                                  <span class="ps-chip">🍪 Cookies: {"Yes" if cookies_present else "No"}</span>
                                  <span class="ps-chip">👁️ Trackers: {tracker_count}</span>
                                  <span class="ps-chip ps-chip--muted">🔗 {url}</span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            st.markdown('<div class="ps-sep"></div>', unsafe_allow_html=True)

                            # AI analysis
                            with st.spinner("AI insights..."):
                                ai_prompt = f"""
Analyze this website for privacy and data collection practices. Focus on forms, inputs, cookies, trackers, and potential privacy risks. Be concise and actionable.

URL: {url}
HTML (truncated): {html[:4000]}
"""
                                ai_summary = ask_ollama(ai_prompt)

                            st.markdown("**🤖 AI Insights**")
                            st.write(ai_summary[:600] + ("..." if len(ai_summary) > 600 else ""))

                            st.markdown('</div>', unsafe_allow_html=True)

                            rows.append({
                                "URL": url,
                                "Forms": len(forms),
                                "Inputs": len(inputs),
                                "Cookies": "Yes" if cookies_present else "No",
                                "Trackers": tracker_count,
                                "AI Summary": (ai_summary[:200] + "...") if len(ai_summary) > 200 else ai_summary,
                            })

                progress_bar.progress(1.0)
                status.success(f"Audit complete · {len(urls)} site(s) analyzed.")

        # --- Summary Table ---
        if rows:
            st.markdown(
                '<div class="ps-section"><div class="ps-h1" style="font-size:22px">Summary</div></div>',
                unsafe_allow_html=True,
            )
            with st.container():
                st.markdown('<div class="ps-card ps-table-wrap">', unsafe_allow_html=True)
                st.dataframe(rows, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
# ==========================
# TAB 2: Policy Analyzer UI
# ==========================
with tabs[1]:
    st.markdown('<div class="ps-section"><div class="ps-h1" style="font-size:24px">AI-Powered Policy Analyzer</div><div class="ps-sub">Upload a policy to get an executive summary, risks, and key clauses.</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1], gap="large")
    with c1:
        uploaded = st.file_uploader("Upload Policy", type=["pdf", "docx", "txt"])
    with c2:
        analyze_btn = st.button("🔬 Analyze Policy", use_container_width=True, disabled=not bool(uploaded))

    if uploaded:
        use_portia_policy = st.toggle(
            "Use Portia for related context",
            value=st.session_state.get("portia_available", False),
            disabled=not st.session_state.get("portia_available", False),
        )
        if use_portia_policy:
            policy_url = st.text_input("Related Policy URL (optional)", placeholder="https://company.com/privacy-policy")

    if uploaded and analyze_btn:
        with st.spinner("Extracting text..."):
            text = load_text_from_upload(uploaded)

        if not text.strip():
            st.error("Could not extract text from the file.")
        else:
            ca, cb, cc = st.columns(3)
            with ca:
                with st.spinner("Generating summary..."):
                    summary = ask_ollama(f"Provide a concise executive summary. Focus on scope, obligations, data handling, and user rights.\n\n{text[:6000]}")
                st.markdown('<div class="ps-card"><b>🧠 Executive Summary</b><div class="ps-sep"></div>' + summary + '</div>', unsafe_allow_html=True)
            with cb:
                with st.spinner("Detecting risks..."):
                    risks_text = ask_ollama(f"List risks, loopholes or non-compliance gaps with severity (Low/Medium/High). Max 12 bullets.\n\n{text[:6000]}")
                st.markdown('<div class="ps-card"><b>⚠️ Risks & Gaps</b><div class="ps-sep"></div>' + risks_text + '</div>', unsafe_allow_html=True)
            with cc:
                with st.spinner("Extracting key clauses..."):
                    clauses_text = ask_ollama(f"Extract the most important clauses or definitions as bullets (max 12). Be short.\n\n{text[:6000]}")
                st.markdown('<div class="ps-card"><b>📑 Key Clauses</b><div class="ps-sep"></div>' + clauses_text + '</div>', unsafe_allow_html=True)

            if st.session_state.get("portia_available") and 'use_portia_policy' in locals() and use_portia_policy and policy_url.strip():
                st.markdown('<div class="ps-card"><b>🕷️ Additional Context</b><div class="ps-sep"></div>', unsafe_allow_html=True)
                with st.spinner("Scheduling Portia scrape..."):
                    project = st.session_state.get("portia_project", "")
                    spider = st.session_state.get("portia_spider", "")
                    page = st.session_state.get("portia_page", "default")
                    portia_result = get_portia_data_dynamic(policy_url, api_client, project, spider, page)
                if portia_result.get("status") == "scheduled":
                    st.success(f"Job scheduled: {portia_result['job_id']}")
                    st.json(portia_result)
                st.markdown('</div>', unsafe_allow_html=True)

            report_md = build_policy_report_md(
                title=uploaded.name, summary=summary, risks=risks_text, key_clauses=clauses_text
            )
            st.download_button(
                "📥 Download Markdown Report",
                data=to_bytes(report_md),
                file_name=f"PolicySherlock_Analysis_{uploaded.name}.md",
                mime="text/markdown",
                use_container_width=True,
            )

# ==========================
# TAB 3: Compare Policies UI
# ==========================
with tabs[2]:
    st.markdown('<div class="ps-section"><div class="ps-h1" style="font-size:24px">Policy Comparison Engine</div><div class="ps-sub">Compare two policies for differences, risks, gaps, and recommendations.</div></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 2, 1], gap="large")
    with c1:
        file_a = st.file_uploader("Policy A", type=["pdf", "docx", "txt"], key="file_a")
        if file_a: st.caption(f"Loaded: {file_a.name}")
    with c2:
        file_b = st.file_uploader("Policy B", type=["pdf", "docx", "txt"], key="file_b")
        if file_b: st.caption(f"Loaded: {file_b.name}")
    with c3:
        st.markdown('<div class="space"></div>', unsafe_allow_html=True)
        compare_btn = st.button("🔍 Compare", use_container_width=True, disabled=not (file_a and file_b))

    if file_a and file_b:
        use_portia_compare = st.toggle(
            "Use Portia for web context",
            value=st.session_state.get("portia_available", False),
            disabled=not st.session_state.get("portia_available", False),
        )
        if use_portia_compare:
            u1, u2 = st.columns(2)
            with u1:
                url_a = st.text_input("Related URL for Policy A", placeholder="https://company-a.com/privacy")
            with u2:
                url_b = st.text_input("Related URL for Policy B", placeholder="https://company-b.com/privacy")

    if file_a and file_b and compare_btn:
        ta = load_text_from_upload(file_a) if file_a else ""
        tb = load_text_from_upload(file_b) if file_b else ""
        if not ta.strip() or not tb.strip():
            st.error("Could not extract text from one or both files.")
        else:
            with st.spinner("AI comparison..."):
                diff_prompt = f"""Compare these two policies and provide a comprehensive analysis.

Sections:
1) Overview
2) Major Differences
3) Risk Analysis
4) Compliance Gaps
5) Recommendations

Policy A ({file_a.name}):
{ta[:6000]}

Policy B ({file_b.name}):
{tb[:6000]}
"""
                comparison_result = ask_ollama(diff_prompt)

            st.markdown(
                f"""
                <div class="ps-card">
                    <div class="ps-sub">Documents</div>
                    <div class="ps-sep"></div>
                    <div style="display:flex; gap:12px; flex-wrap:wrap;">
                        <span class="ps-chip">A · {file_a.name}</span>
                        <span class="ps-chip">B · {file_b.name}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="space"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ps-card"><b>🤖 AI Comparison</b><div class="ps-sep"></div>{comparison_result}</div>', unsafe_allow_html=True)

            if 'use_portia_compare' in locals() and use_portia_compare:
                st.markdown('<div class="space"></div>', unsafe_allow_html=True)
                colA, colB = st.columns(2, gap="large")
                if 'url_a' in locals() and url_a.strip():
                    with colA:
                        st.markdown('<div class="ps-card"><b>🌐 Policy A Web Context</b><div class="ps-sep"></div>', unsafe_allow_html=True)
                        with st.spinner("Scheduling A..."):
                            p = st.session_state.get("portia_project", "")
                            s = st.session_state.get("portia_spider", "")
                            g = st.session_state.get("portia_page", "default")
                            pa = get_portia_data_dynamic(url_a, api_client, p, s, g)
                        if pa.get("status") == "scheduled":
                            st.success(f"Job scheduled: {pa['job_id']}")
                        st.json(pa)
                        st.markdown('</div>', unsafe_allow_html=True)
                if 'url_b' in locals() and url_b.strip():
                    with colB:
                        st.markdown('<div class="ps-card"><b>🌐 Policy B Web Context</b><div class="ps-sep"></div>', unsafe_allow_html=True)
                        with st.spinner("Scheduling B..."):
                            p = st.session_state.get("portia_project", "")
                            s = st.session_state.get("portia_spider", "")
                            g = st.session_state.get("portia_page", "default")
                            pb = get_portia_data_dynamic(url_b, api_client, p, s, g)
                        if pb.get("status") == "scheduled":
                            st.success(f"Job scheduled: {pb['job_id']}")
                        st.json(pb)
                        st.markdown('</div>', unsafe_allow_html=True)

# ==========================
# TAB 4: Ask the Policy UI
# ==========================
with tabs[3]:
    st.markdown('<div class="ps-section"><div class="ps-h1" style="font-size:24px">Interactive Policy Q&A</div><div class="ps-sub">Ask targeted questions. We’ll cite the most relevant sections.</div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1], gap="large")
    with c1:
        up = st.file_uploader("Upload Policy", type=["pdf", "docx", "txt"], key="qfile")
        q = st.text_input("Your Question", placeholder="Does this policy allow sharing data with third parties?")
        if up: st.caption(f"Loaded: {up.name}")
    with c2:
        ask_btn = st.button("🤖 Ask AI", use_container_width=True, disabled=not (up and q.strip()))

    if up:
        use_portia_qa = st.toggle(
            "Use Portia for extra web context",
            value=st.session_state.get("portia_available", False),
            disabled=not st.session_state.get("portia_available", False),
        )
        if use_portia_qa:
            context_url = st.text_input("Additional Context URL", placeholder="https://company.com/help/privacy-faq")

    if up and q.strip() and ask_btn:
        text = load_text_from_upload(up)
        if not text.strip():
            st.error("Could not extract text.")
        else:
            with st.spinner("Finding relevant sections..."):
                chunks = chunk_text(text)
                top_contexts = keyword_rank(chunks, q)[:3]
                context = "\n\n---\n\n".join(top_contexts)

            additional_context = ""
            if 'use_portia_qa' in locals() and use_portia_qa and 'context_url' in locals() and context_url.strip():
                with st.spinner("Scheduling Portia context..."):
                    p = st.session_state.get("portia_project", "")
                    s = st.session_state.get("portia_spider", "")
                    g = st.session_state.get("portia_page", "default")
                    portia_context = get_portia_data_dynamic(context_url, api_client, p, s, g)
                    if portia_context.get("status") == "scheduled":
                        additional_context = f"\n\nAdditional web context scheduled from: {context_url} (Job ID: {portia_context['job_id']})"

            with st.spinner("Generating answer..."):
                prompt = f"""You are an expert policy analyst. Answer the user's question using ONLY the context provided.
Quote relevant phrases exactly. If info is insufficient, say what's missing.

Question: {q}

Document Context:
{context}

{additional_context}

Return a precise, helpful answer with quotes and, if applicable, a short "What’s missing" note.
"""
                answer = ask_ollama(prompt)

            st.markdown(f'<div class="ps-card"><b>💡 Answer</b><div class="ps-sep"></div>{answer}</div>', unsafe_allow_html=True)

            with st.expander("Context used"):
                st.markdown(f'<div class="ps-mono">{context}</div>', unsafe_allow_html=True)

            if 'portia_context' in locals() and portia_context.get("status") == "scheduled":
                with st.expander("Scheduled web context"):
                    st.json(portia_context)

# =========
# FOOTER
# =========
st.markdown("""
<div class="ps-section">
  <div class="ps-card center" style="flex-direction:column;">
    <div style="font-weight:800; font-size:16px;">PolicySherlock Pro</div>
    <div class="ps-sub">Powered by AI • Enhanced by Portia • Built for Privacy Teams</div>
    <div>
      <span class="ps-chip">🤖 Ollama</span>
      <span class="ps-chip">🕷️ Portia</span>
      <span class="ps-chip">🛡️ Compliance-ready</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
