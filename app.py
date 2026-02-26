import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time
import os
from pathlib import Path

# Local modules
from database import (
    init_db, get_jobs, save_job, update_job, delete_job,
    get_settings, save_settings, save_document, get_document,
    STATUS_OPTIONS, STATUS_COLORS
)
from scraper import search_multiple_platforms, get_job_details
from ai_assistant import (
    extract_text_from_pdf, extract_text_from_docx,
    generate_cover_letter, calculate_match_score
)

# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="JobTracker Pro",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f1117; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1d2e;
        border-right: 1px solid #2d3154;
    }
    
    /* Cards */
    .job-card {
        background: #1e2235;
        border: 1px solid #2d3154;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: border-color 0.2s;
    }
    .job-card:hover { border-color: #4a6cf7; }
    
    .job-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 4px;
    }
    .job-meta {
        font-size: 0.82rem;
        color: #8892a4;
        margin-bottom: 8px;
    }
    .job-company { color: #4a9eff; font-weight: 500; }
    
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        color: white;
    }
    
    /* Score circle */
    .score-high { color: #22c55e; font-size: 1.4rem; font-weight: 700; }
    .score-mid  { color: #f59e0b; font-size: 1.4rem; font-weight: 700; }
    .score-low  { color: #ef4444; font-size: 1.4rem; font-weight: 700; }
    
    /* Metric cards */
    .metric-card {
        background: #1e2235;
        border: 1px solid #2d3154;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-num { font-size: 2rem; font-weight: 700; color: #4a6cf7; }
    .metric-label { font-size: 0.85rem; color: #8892a4; }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #1e2235;
        border-radius: 8px;
        color: #8892a4;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: #4a6cf7 !important;
        color: white !important;
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Input fields */
    .stTextInput input, .stSelectbox select, .stTextArea textarea {
        background: #1e2235 !important;
        border: 1px solid #2d3154 !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
    }
    
    div[data-testid="stExpander"] {
        background: #1e2235;
        border: 1px solid #2d3154;
        border-radius: 12px;
    }
    
    h1, h2, h3 { color: #e2e8f0; }
    p, li { color: #94a3b8; }
    
    .stAlert { border-radius: 10px; }
    
    /* Search header */
    .search-header {
        background: linear-gradient(135deg, #1e2235 0%, #2d1b69 100%);
        border: 1px solid #4a6cf7;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────
init_db()

# ─────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────
if "cv_text" not in st.session_state:
    st.session_state.cv_text = ""
if "cover_letter_text" not in st.session_state:
    st.session_state.cover_letter_text = ""
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_job_for_ai" not in st.session_state:
    st.session_state.selected_job_for_ai = None

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 💼 JobTracker Pro")
    st.markdown("---")
    
    # Quick stats
    jobs = get_jobs()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Stellen", len(jobs))
    with col2:
        applied = len([j for j in jobs if j["status"] == "Beworben"])
        st.metric("Beworben", applied)
    
    interviews = len([j for j in jobs if j["status"] == "Interview"])
    rejections = len([j for j in jobs if j["status"] == "Absage"])
    col3, col4 = st.columns(2)
    with col3:
        st.metric("Interviews", interviews)
    with col4:
        st.metric("Absagen", rejections)
    
    st.markdown("---")
    
    # Settings
    st.markdown("### ⚙️ Einstellungen")
    settings = get_settings()
    
    api_key = st.text_input(
        "Anthropic API Key",
        value=settings.get("api_key", ""),
        type="password",
        help="Für KI-Anschreiben & Match-Score"
    )
    
    if api_key != settings.get("api_key", ""):
        settings["api_key"] = api_key
        save_settings(settings)
        st.success("✓ Gespeichert")
    
    st.markdown("---")
    st.markdown("### 🔍 Standard-Suche")
    
    default_keywords = st.text_area(
        "Suchbegriffe (einer pro Zeile)",
        value="\n".join(settings.get("default_keywords", [
            "ERP Projektleiter",
            "Business Analyst ERP",
            "ERP Consultant",
            "Abacus Consultant",
            "IT Consultant Digitalisierung"
        ])),
        height=120
    )
    
    default_days = st.slider(
        "Inserate der letzten X Tage",
        min_value=3, max_value=60, value=settings.get("default_days", 14)
    )
    
    if st.button("💾 Einstellungen speichern", use_container_width=True):
        settings["default_keywords"] = [k.strip() for k in default_keywords.split("\n") if k.strip()]
        settings["default_days"] = default_days
        save_settings(settings)
        st.success("Gespeichert!")

# ─────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Stellensuche",
    "📋 Meine Bewerbungen",
    "📄 Unterlagen",
    "🤖 KI-Anschreiben",
    "📊 Statistiken"
])

# ═══════════════════════════════════════════
# TAB 1: Job Search
# ═══════════════════════════════════════════
with tab1:
    st.markdown("""
    <div class="search-header">
        <h2 style="margin:0; color:#e2e8f0;">🔍 Stellensuche Schweiz</h2>
        <p style="margin:6px 0 0 0; color:#94a3b8;">Automatische Suche auf jobs.ch nach aktuellen Stellen</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        search_input = st.text_input(
            "🔎 Suchbegriffe",
            value="ERP Projektleiter Business Analyst Consultant",
            help="Mehrere Begriffe mit Leerzeichen trennen"
        )
    
    with col2:
        days_filter = st.number_input(
            "Tage zurück",
            min_value=1, max_value=60, value=14
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_search = st.button("🚀 Suche starten", use_container_width=True, type="primary")
    
    if run_search:
        keywords = search_input.split()
        with st.spinner(f"Suche läuft... (jobs.ch)"):
            results = search_multiple_platforms(keywords, days_back=days_filter)
            st.session_state.search_results = results
        
        if results:
            st.success(f"✅ {len(results)} Stellen gefunden!")
        else:
            st.warning("Keine Stellen gefunden. Versuche andere Suchbegriffe.")
    
    # Manual job entry
    with st.expander("➕ Stelle manuell hinzufügen"):
        mc1, mc2 = st.columns(2)
        with mc1:
            manual_title = st.text_input("Stellentitel*")
            manual_company = st.text_input("Unternehmen")
            manual_location = st.text_input("Ort")
        with mc2:
            manual_url = st.text_input("URL (jobs.ch Link)")
            manual_date = st.date_input("Publiziert am", value=datetime.now())
            manual_pensum = st.text_input("Pensum", value="80-100%")
        
        manual_desc = st.text_area("Beschreibung / Notizen", height=80)
        
        if st.button("✅ Stelle hinzufügen", type="primary"):
            if manual_title:
                job = {
                    "title": manual_title,
                    "company": manual_company,
                    "location": manual_location,
                    "pensum": manual_pensum,
                    "posted_date": manual_date.isoformat(),
                    "posted_date_raw": manual_date.strftime("%d.%m.%Y"),
                    "url": manual_url,
                    "source": "manuell",
                    "description": manual_desc,
                    "status": "Neu"
                }
                if save_job(job):
                    st.success(f"✅ '{manual_title}' hinzugefügt!")
                    st.rerun()
                else:
                    st.warning("Diese Stelle (URL) existiert bereits.")
            else:
                st.error("Bitte mindestens den Titel angeben.")
    
    # Display search results
    if st.session_state.search_results:
        st.markdown(f"### Suchergebnisse ({len(st.session_state.search_results)} Stellen)")
        
        existing_urls = {j["url"] for j in get_jobs()}
        
        for i, job in enumerate(st.session_state.search_results):
            already_saved = job["url"] in existing_urls
            
            with st.container():
                col_main, col_btn = st.columns([5, 1])
                
                with col_main:
                    saved_badge = ' <span style="background:#22c55e;color:white;padding:2px 8px;border-radius:10px;font-size:0.7rem;">✓ Gespeichert</span>' if already_saved else ""
                    st.markdown(f"""
                    <div class="job-card">
                        <div class="job-title">{job['title']}{saved_badge}</div>
                        <div class="job-meta">
                            <span class="job-company">{job.get('company', '–')}</span>
                            {"&nbsp;&nbsp;📍 " + job['location'] if job.get('location') else ""}
                            {"&nbsp;&nbsp;🗓️ " + job.get('posted_date_raw', job.get('posted_date', '')) if job.get('posted_date_raw') or job.get('posted_date') else ""}
                            {"&nbsp;&nbsp;⏱️ " + job['pensum'] if job.get('pensum') else ""}
                            &nbsp;&nbsp;📌 {job.get('source', 'jobs.ch')}
                        </div>
                        <a href="{job['url']}" target="_blank" style="color:#4a9eff;font-size:0.8rem;">🔗 Zum Inserat →</a>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if not already_saved:
                        if st.button("💾 Speichern", key=f"save_{i}", use_container_width=True):
                            if save_job(job):
                                existing_urls.add(job["url"])
                                st.success("Gespeichert!")
                                st.rerun()
                    else:
                        if st.button("📋 Tracker", key=f"goto_{i}", use_container_width=True):
                            st.info("→ Tab 'Meine Bewerbungen'")
        
        if st.button("📥 Alle speichern", type="primary"):
            count = 0
            for job in st.session_state.search_results:
                if save_job(job):
                    count += 1
            st.success(f"✅ {count} neue Stellen gespeichert!")
            st.rerun()

# ═══════════════════════════════════════════
# TAB 2: Application Tracker
# ═══════════════════════════════════════════
with tab2:
    st.markdown("## 📋 Meine Bewerbungen")
    
    jobs = get_jobs()
    
    if not jobs:
        st.info("Noch keine Stellen gespeichert. Nutze die Stellensuche oder füge Stellen manuell hinzu.")
    else:
        # Filters
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            filter_status = st.multiselect(
                "Status filtern",
                options=STATUS_OPTIONS,
                default=[]
            )
        with col2:
            filter_search = st.text_input("🔎 Suchen", placeholder="Titel, Unternehmen...")
        with col3:
            sort_by = st.selectbox("Sortieren", ["Datum (neu)", "Status", "Titel"])
        
        # Apply filters
        filtered = jobs
        if filter_status:
            filtered = [j for j in filtered if j["status"] in filter_status]
        if filter_search:
            q = filter_search.lower()
            filtered = [j for j in filtered if q in j.get("title", "").lower() or q in j.get("company", "").lower()]
        
        # Sort
        if sort_by == "Datum (neu)":
            filtered = sorted(filtered, key=lambda x: x.get("added_at", ""), reverse=True)
        elif sort_by == "Status":
            filtered = sorted(filtered, key=lambda x: STATUS_OPTIONS.index(x.get("status", "Neu")))
        else:
            filtered = sorted(filtered, key=lambda x: x.get("title", ""))
        
        st.markdown(f"**{len(filtered)} von {len(jobs)} Stellen**")
        
        # Job list
        for job in filtered:
            status_color = STATUS_COLORS.get(job["status"], "#6c757d")
            
            with st.expander(
                f"{'🟢' if job['status']=='Zusage' else '🔴' if job['status']=='Absage' else '🟡' if job['status']=='Interview' else '🔵' if job['status']=='Beworben' else '⚪'}  {job['title']} — {job.get('company', '–')} | {job.get('location', '–')}",
                expanded=False
            ):
                col_left, col_right = st.columns([3, 2])
                
                with col_left:
                    st.markdown(f"**📍 Ort:** {job.get('location', '–')}")
                    st.markdown(f"**⏱️ Pensum:** {job.get('pensum', '–')}")
                    st.markdown(f"**📅 Publiziert:** {job.get('posted_date', '–')}")
                    st.markdown(f"**📥 Hinzugefügt:** {job.get('added_at', '–')[:10]}")
                    if job.get("url"):
                        st.markdown(f"**🔗 Link:** [Zum Inserat]({job['url']})")
                    if job.get("match_score"):
                        score = job["match_score"]
                        color_class = "score-high" if score >= 70 else "score-mid" if score >= 40 else "score-low"
                        st.markdown(f"**🎯 Match-Score:** <span class='{color_class}'>{score}%</span>", unsafe_allow_html=True)
                
                with col_right:
                    new_status = st.selectbox(
                        "Status",
                        options=STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(job["status"]),
                        key=f"status_{job['id']}"
                    )
                    
                    applied_date = st.date_input(
                        "Beworben am",
                        value=datetime.fromisoformat(job["applied_at"]).date() if job.get("applied_at") else None,
                        key=f"applied_{job['id']}"
                    )
                    
                    response_text = st.text_input(
                        "Antwort / Notiz",
                        value=job.get("response", ""),
                        key=f"response_{job['id']}"
                    )
                    
                    notes = st.text_area(
                        "Notizen",
                        value=job.get("notes", ""),
                        key=f"notes_{job['id']}",
                        height=80
                    )
                
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("💾 Speichern", key=f"update_{job['id']}", use_container_width=True):
                        update_job(job["id"], {
                            "status": new_status,
                            "applied_at": applied_date.isoformat() if applied_date else "",
                            "response": response_text,
                            "notes": notes
                        })
                        st.success("Aktualisiert!")
                        st.rerun()
                
                with col_btn2:
                    if st.button("🤖 KI-Anschreiben", key=f"ai_{job['id']}", use_container_width=True):
                        st.session_state.selected_job_for_ai = job
                        st.info("→ Wechsle zu Tab 'KI-Anschreiben'")
                
                with col_btn3:
                    if st.button("🗑️ Löschen", key=f"del_{job['id']}", use_container_width=True):
                        delete_job(job["id"])
                        st.rerun()

# ═══════════════════════════════════════════
# TAB 3: Documents
# ═══════════════════════════════════════════
with tab3:
    st.markdown("## 📄 Unterlagen verwalten")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Lebenslauf (CV)")
        cv_doc = get_document("cv")
        if cv_doc:
            st.success(f"✅ Gespeichert: {cv_doc['filename']}")
            st.markdown(f"*Hochgeladen am: {cv_doc['uploaded_at'][:10]}*")
        
        cv_file = st.file_uploader(
            "CV hochladen (PDF oder DOCX)",
            type=["pdf", "docx"],
            key="cv_upload"
        )
        
        if cv_file:
            content = cv_file.read()
            save_document(cv_file.name, content, "cv")
            
            # Extract text
            if cv_file.name.endswith(".pdf"):
                st.session_state.cv_text = extract_text_from_pdf(content)
            else:
                st.session_state.cv_text = extract_text_from_docx(content)
            
            st.success(f"✅ '{cv_file.name}' gespeichert und Text extrahiert!")
        
        if st.session_state.cv_text:
            with st.expander("📖 Extrahierter CV-Text"):
                st.text_area("", value=st.session_state.cv_text[:2000], height=200, disabled=True)
        elif cv_doc:
            # Load existing CV text
            try:
                with open(cv_doc["path"], "rb") as f:
                    content = f.read()
                if cv_doc["filename"].endswith(".pdf"):
                    st.session_state.cv_text = extract_text_from_pdf(content)
                else:
                    st.session_state.cv_text = extract_text_from_docx(content)
            except:
                pass
    
    with col2:
        st.markdown("### ✉️ Muster-Anschreiben")
        letter_doc = get_document("cover_letter")
        if letter_doc:
            st.success(f"✅ Gespeichert: {letter_doc['filename']}")
        
        letter_file = st.file_uploader(
            "Anschreiben hochladen (PDF oder DOCX)",
            type=["pdf", "docx"],
            key="letter_upload"
        )
        
        if letter_file:
            content = letter_file.read()
            save_document(letter_file.name, content, "cover_letter")
            
            if letter_file.name.endswith(".pdf"):
                st.session_state.cover_letter_text = extract_text_from_pdf(content)
            else:
                st.session_state.cover_letter_text = extract_text_from_docx(content)
            
            st.success(f"✅ '{letter_file.name}' gespeichert!")
        
        if st.session_state.cover_letter_text:
            with st.expander("📖 Anschreiben-Text (Vorlage)"):
                st.text_area("", value=st.session_state.cover_letter_text[:2000], height=200, disabled=True)
        elif letter_doc:
            try:
                with open(letter_doc["path"], "rb") as f:
                    content = f.read()
                if letter_doc["filename"].endswith(".pdf"):
                    st.session_state.cover_letter_text = extract_text_from_pdf(content)
                else:
                    st.session_state.cover_letter_text = extract_text_from_docx(content)
            except:
                pass
    
    st.markdown("---")
    st.markdown("### 📎 Weitere Unterlagen")
    
    other_docs = ["Referenz 1", "Referenz 2", "Referenz 3", "Diplom / Zertifikat"]
    for doc_name in other_docs:
        doc_key = doc_name.lower().replace(" ", "_").replace("/", "_")
        doc_info = get_document(doc_key)
        
        col_a, col_b = st.columns([3, 1])
        with col_a:
            status = f"✅ {doc_info['filename']}" if doc_info else "– Noch nicht hochgeladen"
            st.markdown(f"**{doc_name}:** {status}")
        with col_b:
            other_file = st.file_uploader(f"Upload", type=["pdf", "docx"], key=f"other_{doc_key}", label_visibility="collapsed")
            if other_file:
                save_document(other_file.name, other_file.read(), doc_key)
                st.success("✅")
                st.rerun()

# ═══════════════════════════════════════════
# TAB 4: AI Cover Letter
# ═══════════════════════════════════════════
with tab4:
    st.markdown("## 🤖 KI-Anschreiben Generator")
    
    settings = get_settings()
    api_key = settings.get("api_key", "")
    
    if not api_key:
        st.warning("⚠️ Bitte zuerst den Anthropic API Key in den Einstellungen (Sidebar) eintragen.")
    
    # Pre-fill from selected job in tracker
    if st.session_state.selected_job_for_ai:
        sel = st.session_state.selected_job_for_ai
        st.info(f"📌 Ausgewählte Stelle: **{sel['title']}** bei {sel.get('company', '–')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Stellenangaben")
        
        ai_title = st.text_input(
            "Stellentitel",
<<<<<<< HEAD
            value=st.session_state.selected_job_for_ai.get("title", "") if st.session_state.selected_job_for_ai else "",
            key="ai_title_input"
        )
        ai_company = st.text_input(
            "Unternehmen",
            value=st.session_state.selected_job_for_ai.get("company", "") if st.session_state.selected_job_for_ai else "",
            key="ai_company_input"
        )
        ai_url = st.text_input(
            "URL (optional, für automatisches Laden)",
            value=st.session_state.selected_job_for_ai.get("url", "") if st.session_state.selected_job_for_ai else "",
            key="ai_url_input"
=======
            value=st.session_state.selected_job_for_ai.get("title", "") if st.session_state.selected_job_for_ai else ""
        )
        ai_company = st.text_input(
            "Unternehmen",
            value=st.session_state.selected_job_for_ai.get("company", "") if st.session_state.selected_job_for_ai else ""
        )
        ai_url = st.text_input(
            "URL (optional, für automatisches Laden)",
            value=st.session_state.selected_job_for_ai.get("url", "") if st.session_state.selected_job_for_ai else ""
>>>>>>> 871c267af1816cba5352f8e680422e630667b70b
        )
        
        if ai_url and st.button("📥 Stellenbeschreibung laden"):
            with st.spinner("Lade Inserat..."):
                details = get_job_details(ai_url)
                if details.get("description"):
                    st.session_state["ai_job_desc"] = details["description"]
                    if details.get("company"):
                        st.session_state["ai_company"] = details["company"]
                    st.success("Geladen!")
                else:
                    st.warning("Konnte Beschreibung nicht laden.")
        
        ai_job_desc = st.text_area(
            "Stellenbeschreibung",
            value=st.session_state.get("ai_job_desc", ""),
            height=200,
            placeholder="Füge hier die Stellenbeschreibung ein..."
        )
    
    with col2:
        st.markdown("### 📋 Dein Profil")
        
        cv_available = bool(st.session_state.cv_text)
        if cv_available:
            st.success("✅ CV geladen (aus Tab 'Unterlagen')")
        else:
            st.warning("⚠️ Kein CV geladen – bitte zuerst in Tab 'Unterlagen' hochladen")
        
        letter_available = bool(st.session_state.cover_letter_text)
        if letter_available:
            st.success("✅ Muster-Anschreiben geladen (Stil wird übernommen)")
        
        ai_extra_info = st.text_area(
            "Zusätzliche Infos (optional)",
            height=100,
            placeholder="z.B. spezifische Motivationen, besondere Punkte die hervorgehoben werden sollen..."
        )
        
        ai_language = st.radio("Sprache", ["Deutsch", "English"], horizontal=True)
        lang_code = "de" if ai_language == "Deutsch" else "en"
    
    col_gen, col_score = st.columns(2)
    
    with col_gen:
        generate_btn = st.button(
            "✍️ Anschreiben generieren",
            type="primary",
            use_container_width=True,
            disabled=not (api_key and ai_title and ai_job_desc and cv_available)
        )
    
    with col_score:
        score_btn = st.button(
            "🎯 Match-Score berechnen",
            use_container_width=True,
            disabled=not (api_key and ai_job_desc and cv_available)
        )
    
    if generate_btn:
        cv_with_extra = st.session_state.cv_text
        if ai_extra_info:
            cv_with_extra += f"\n\nZusätzliche Informationen: {ai_extra_info}"
        
        with st.spinner("KI generiert Anschreiben... (ca. 15-30 Sekunden)"):
            try:
                result = generate_cover_letter(
                    job_title=ai_title,
                    company=ai_company,
                    job_description=ai_job_desc,
                    cv_text=cv_with_extra,
                    existing_letter=st.session_state.cover_letter_text,
                    language=lang_code,
                    api_key=api_key
                )
                st.session_state["generated_letter"] = result
                st.success("✅ Anschreiben generiert!")
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    if score_btn:
        with st.spinner("Analysiere Übereinstimmung..."):
            try:
                score_result = calculate_match_score(
                    job_description=ai_job_desc,
                    cv_text=st.session_state.cv_text,
                    api_key=api_key
                )
                st.session_state["score_result"] = score_result
                
                # Save score to job if selected
                if st.session_state.selected_job_for_ai:
                    update_job(st.session_state.selected_job_for_ai["id"], {
                        "match_score": score_result.get("score", 0)
                    })
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    # Display score
    if "score_result" in st.session_state:
        sr = st.session_state["score_result"]
        score = sr.get("score", 0)
        
        col_s1, col_s2, col_s3 = st.columns(3)
        color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
        
        with col_s1:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size:2.5rem;font-weight:700;color:{color}">{score}%</div>
                <div class="metric-label">Match-Score</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_s2:
            if sr.get("strengths"):
                st.markdown("**✅ Stärken:**")
                for s in sr["strengths"]:
                    st.markdown(f"• {s}")
        
        with col_s3:
            if sr.get("gaps"):
                st.markdown("**⚠️ Lücken:**")
                for g in sr["gaps"]:
                    st.markdown(f"• {g}")
        
        if sr.get("recommendation"):
            st.info(f"💡 {sr['recommendation']}")
    
    # Display generated letter
    if "generated_letter" in st.session_state:
        st.markdown("---")
        st.markdown("### ✉️ Generiertes Anschreiben")
        
        letter_text = st.text_area(
            "",
            value=st.session_state["generated_letter"],
            height=400
        )
        
        col_copy, col_save = st.columns(2)
        with col_copy:
            st.download_button(
                "📥 Als TXT herunterladen",
                data=letter_text.encode("utf-8"),
                file_name=f"Anschreiben_{ai_company}_{ai_title}.txt".replace(" ", "_"),
                mime="text/plain",
                use_container_width=True
            )
        with col_save:
            if st.session_state.selected_job_for_ai and st.button("💾 In Stelle speichern", use_container_width=True):
                update_job(st.session_state.selected_job_for_ai["id"], {
                    "cover_letter": letter_text,
                    "status": "Interessant"
                })
                st.success("Gespeichert!")

# ═══════════════════════════════════════════
# TAB 5: Statistics
# ═══════════════════════════════════════════
with tab5:
    st.markdown("## 📊 Statistiken & Übersicht")
    
    jobs = get_jobs()
    
    if not jobs:
        st.info("Noch keine Daten. Beginne mit der Stellensuche!")
    else:
        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        metrics = [
            ("Gesamt", len(jobs), "💼"),
            ("Beworben", len([j for j in jobs if j["status"] in ["Beworben", "Interview", "Zusage", "Absage"]]), "📤"),
            ("Aktiv", len([j for j in jobs if j["status"] in ["Interessant", "Neu"]]), "🔍"),
            ("Interviews", len([j for j in jobs if j["status"] == "Interview"]), "🎤"),
            ("Absagen", len([j for j in jobs if j["status"] == "Absage"]), "❌"),
        ]
        
        for col, (label, val, icon) in zip([col1, col2, col3, col4, col5], metrics):
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size:1.5rem">{icon}</div>
                    <div class="metric-num">{val}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # Status distribution
            status_counts = {}
            for job in jobs:
                s = job.get("status", "Neu")
                status_counts[s] = status_counts.get(s, 0) + 1
            
            fig_pie = px.pie(
                values=list(status_counts.values()),
                names=list(status_counts.keys()),
                title="Status-Verteilung",
                color=list(status_counts.keys()),
                color_discrete_map=STATUS_COLORS,
                hole=0.4
            )
            fig_pie.update_layout(
                paper_bgcolor="#1e2235",
                plot_bgcolor="#1e2235",
                font={"color": "#e2e8f0"},
                showlegend=True
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_chart2:
            # Timeline – jobs added per week
            df = pd.DataFrame(jobs)
            if "added_at" in df.columns:
                df["added_at"] = pd.to_datetime(df["added_at"])
                df["week"] = df["added_at"].dt.to_period("W").astype(str)
                weekly = df.groupby("week").size().reset_index(name="count")
                
                fig_bar = px.bar(
                    weekly, x="week", y="count",
                    title="Stellen hinzugefügt (pro Woche)",
                    color_discrete_sequence=["#4a6cf7"]
                )
                fig_bar.update_layout(
                    paper_bgcolor="#1e2235",
                    plot_bgcolor="#1e2235",
                    font={"color": "#e2e8f0"},
                    xaxis={"gridcolor": "#2d3154"},
                    yaxis={"gridcolor": "#2d3154"}
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        
        # Match scores
        jobs_with_scores = [j for j in jobs if j.get("match_score")]
        if jobs_with_scores:
            st.markdown("### 🎯 Match-Scores")
            score_df = pd.DataFrame([{
                "Stelle": f"{j['title']} – {j.get('company', '–')}",
                "Score": j["match_score"],
                "Status": j["status"]
            } for j in jobs_with_scores]).sort_values("Score", ascending=False)
            
            fig_scores = px.bar(
                score_df, x="Score", y="Stelle",
                orientation="h",
                color="Score",
                color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
                title="Match-Scores nach Stelle"
            )
            fig_scores.update_layout(
                paper_bgcolor="#1e2235",
                plot_bgcolor="#1e2235",
                font={"color": "#e2e8f0"},
                height=max(300, len(jobs_with_scores) * 40)
            )
            st.plotly_chart(fig_scores, use_container_width=True)
        
        # Export
        st.markdown("---")
        st.markdown("### 📥 Export")
        
        export_df = pd.DataFrame([{
            "Titel": j.get("title", ""),
            "Unternehmen": j.get("company", ""),
            "Ort": j.get("location", ""),
            "Status": j.get("status", ""),
            "Beworben am": j.get("applied_at", ""),
            "Publiziert": j.get("posted_date", ""),
            "Match Score": j.get("match_score", ""),
            "Notizen": j.get("notes", ""),
            "URL": j.get("url", "")
        } for j in jobs])
        
        csv = export_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📊 Als Excel/CSV exportieren",
            data=csv,
            file_name=f"bewerbungen_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            type="primary"
        )
