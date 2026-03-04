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
from database import test_storage_connection
from ai_assistant import (
    extract_text_from_pdf, extract_text_from_docx,
    generate_cover_letter, generate_cover_letter_pdf, calculate_match_score,
    calculate_quick_score, _sanitize_company, extract_company_details
)

# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="JobTracker Pro",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* ══════════════════════════════════════════
       Warm Light Theme — Claude-inspired
       ══════════════════════════════════════════ */

    /* Main background — warm off-white/cream */
    .stApp {
        background-color: #f5f0e8 !important;
    }

    /* Sidebar — warm white with subtle border */
    [data-testid="stSidebar"] {
        background: #faf7f2 !important;
        border-right: 1px solid #e5ddd0;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #2d2417;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: #5c4f3d !important;
    }

    /* ── Cards ── */
    .job-card {
        background: #ffffff;
        border: 1px solid #e5ddd0;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .job-card:hover {
        border-color: #c4956a;
        box-shadow: 0 4px 16px rgba(180,130,80,0.1);
        transform: translateY(-1px);
    }

    .job-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #2d2417;
        margin-bottom: 6px;
    }
    .job-meta {
        font-size: 0.82rem;
        color: #7a6b56;
        margin-bottom: 8px;
        line-height: 1.6;
    }
    .job-company {
        color: #b47a3e;
        font-weight: 600;
    }

    /* ── Status badges ── */
    .badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.73rem;
        font-weight: 600;
        color: white;
    }

    /* ── Score ── */
    .score-high { color: #16a34a; font-size: 1.4rem; font-weight: 700; }
    .score-mid  { color: #d97706; font-size: 1.4rem; font-weight: 700; }
    .score-low  { color: #dc2626; font-size: 1.4rem; font-weight: 700; }

    /* ── Metric cards ── */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e5ddd0;
        border-radius: 12px;
        padding: 22px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .metric-num {
        font-size: 2rem;
        font-weight: 700;
        color: #b47a3e;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #7a6b56;
        margin-top: 4px;
    }

    /* ── Tabs — pill style ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #ede7db;
        border-radius: 12px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 10px;
        color: #7a6b56;
        padding: 8px 18px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #2d2417;
        background: rgba(255,255,255,0.6);
    }
    .stTabs [aria-selected="true"] {
        background: #c4956a !important;
        color: white !important;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(196,149,106,0.3);
    }

    /* ── Buttons ── */
    .stButton button {
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
    }
    .stButton button[kind="primary"] {
        background: #c4956a !important;
        color: white !important;
        border: none;
    }
    .stButton button[kind="primary"]:hover {
        background: #b0844f !important;
    }

    /* ── Input fields ── */
    .stTextInput input, .stSelectbox select, .stTextArea textarea {
        background: #ffffff !important;
        border: 1px solid #ddd4c4 !important;
        color: #2d2417 !important;
        border-radius: 10px !important;
        transition: border-color 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #c4956a !important;
        box-shadow: 0 0 0 2px rgba(196,149,106,0.15) !important;
    }

    /* ── Multiselect ── */
    .stMultiSelect [data-baseweb="tag"] {
        background: #c4956a !important;
        border-radius: 8px;
        color: white;
    }

    /* ── Expanders ── */
    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #e5ddd0;
        border-radius: 12px;
    }

    /* ── Typography ── */
    h1, h2, h3 { color: #2d2417; }
    h2 { letter-spacing: -0.02em; }
    p, li { color: #4a3d2e; }
    label { color: #5c4f3d !important; }

    /* ── Alerts ── */
    .stAlert { border-radius: 12px; }

    /* ── Search header ── */
    .search-header {
        background: linear-gradient(135deg, #faf7f2 0%, #f0e6d6 100%);
        border: 1px solid #ddd4c4;
        border-radius: 14px;
        padding: 28px;
        margin-bottom: 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border-radius: 12px;
    }

    /* ── Dividers ── */
    hr {
        border-color: #e5ddd0 !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #d4c9b8; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #c4956a; }

    /* ── Sidebar metrics ── */
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(196,149,106,0.06);
        border-radius: 10px;
        padding: 8px 12px;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #b47a3e;
    }

    /* ── Download buttons ── */
    .stDownloadButton button {
        background: #ffffff !important;
        border: 1px solid #ddd4c4 !important;
        color: #2d2417 !important;
    }
    .stDownloadButton button:hover {
        background: #f5f0e8 !important;
        border-color: #c4956a !important;
    }

    /* ── Selectbox dropdown ── */
    [data-baseweb="select"] > div {
        background: #ffffff !important;
        border-color: #ddd4c4 !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div {
        background: #c4956a !important;
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
# Main Content
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔍 Stellensuche",
    "📋 Meine Bewerbungen",
    "📄 Unterlagen",
    "🤖 KI-Anschreiben",
    "📊 Statistiken",
    "⚙️ Einstellungen"
])

# ═══════════════════════════════════════════
# TAB 1: Job Search
# ═══════════════════════════════════════════
with tab1:
    st.markdown("""
    <div class="search-header">
        <h2 style="margin:0; color:#2d2417;">🔍 Stellensuche Schweiz</h2>
        <p style="margin:6px 0 0 0; color:#7a6b56;">Wähle Jobprofile aus und durchsuche jobs.ch nach aktuellen Stellen</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Predefined job search categories ──
    JOB_CATEGORIES = {
        "ERP & Business Software": [
            "ERP Projektleiter",
            "ERP Consultant",
            "ERP Berater",
            "SAP Consultant",
            "SAP FI/CO Berater",
            "Dynamics 365 Consultant",
            "Dynamics AX Berater",
            "Abacus Consultant",
            "Abacus Berater",
            "Navision Consultant",
            "Infor Consultant",
            "Oracle ERP Consultant",
        ],
        "Business Analyse & Consulting": [
            "Business Analyst",
            "Business Analyst IT",
            "Requirements Engineer",
            "IT Consultant",
            "IT Berater",
            "Management Consultant",
            "Unternehmensberater",
            "Digitalisierung Berater",
            "Prozessberater",
            "Business Consultant",
        ],
        "Projektmanagement": [
            "IT Projektleiter",
            "Projektmanager IT",
            "Projekt Manager Digitalisierung",
            "Programm Manager",
            "Scrum Master",
            "Agile Coach",
            "Product Owner",
            "PMO",
        ],
        "Finance & Controlling IT": [
            "Finance Consultant",
            "Controlling Consultant",
            "FI CO Consultant",
            "Financial Analyst IT",
            "Controller Digitalisierung",
            "Treasury Consultant",
        ],
        "IT Management & Strategie": [
            "IT Manager",
            "IT Leiter",
            "CIO",
            "Head of IT",
            "IT Strategie Berater",
            "Digital Transformation Manager",
            "Change Manager IT",
        ],
        "Data & Analytics": [
            "Data Analyst",
            "BI Consultant",
            "Business Intelligence Berater",
            "Power BI Consultant",
            "Data Engineer",
            "Reporting Analyst",
        ],
    }

    # Build flat list of all options for multiselect
    all_job_options = []
    for category, jobs_list in JOB_CATEGORIES.items():
        for job in jobs_list:
            all_job_options.append(job)

    # Default selections matching user profile
    default_selections = [
        "ERP Projektleiter",
        "ERP Consultant",
        "Business Analyst IT",
        "IT Consultant",
        "SAP Consultant",
        "Abacus Consultant",
        "IT Projektleiter",
    ]

    # Category expander to browse available options
    with st.expander("📂 Jobprofile nach Kategorie durchsuchen", expanded=False):
        st.markdown("*Klicke auf eine Kategorie um alle verfügbaren Suchbegriffe zu sehen:*")
        for cat_name, cat_jobs in JOB_CATEGORIES.items():
            st.markdown(f"**{cat_name}:** {', '.join(cat_jobs)}")

    # Multiselect for job profiles
    selected_profiles = st.multiselect(
        "🎯 Jobprofile auswählen",
        options=all_job_options,
        default=[s for s in default_selections if s in all_job_options],
        help="Wähle ein oder mehrere Jobprofile aus. Jedes Profil wird einzeln auf jobs.ch gesucht.",
        key="search_profiles_select"
    )

    # Optional: custom search term
    col_custom, col_days, col_btn = st.columns([3, 1, 1])

    with col_custom:
        custom_search = st.text_input(
            "➕ Eigener Suchbegriff (optional)",
            placeholder="z.B. 'Implementierung Berater' oder 'Dynamics Finance'",
            key="custom_search_input"
        )

    with col_days:
        days_filter = st.number_input(
            "Tage zurück",
            min_value=1, max_value=60, value=7,
            key="days_filter_input"
        )

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_search = st.button("🚀 Suche starten", use_container_width=True, type="primary")

    # Info about selection and sources
    if selected_profiles or custom_search:
        all_terms = list(selected_profiles)
        if custom_search.strip():
            all_terms.append(custom_search.strip())
        st.caption(f"🔎 {len(all_terms)} Suchbegriff(e) ausgewählt — jeder wird einzeln gesucht")
    st.caption("📡 Quellen: [jobs.ch](https://www.jobs.ch) · [Indeed.ch](https://ch.indeed.com) · [LinkedIn](https://www.linkedin.com/jobs) · [JobScout24](https://www.jobscout24.ch) · 20 ERP-Firmen Karriereseiten")

    if run_search:
        # Build search terms from selected profiles + custom
        search_terms = list(selected_profiles)
        if custom_search.strip():
            search_terms.append(custom_search.strip())

        if not search_terms:
            st.error("Bitte mindestens ein Jobprofil auswählen oder einen eigenen Suchbegriff eingeben.")
        else:
            all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, term in enumerate(search_terms):
                status_text.text(f"🔍 Suche {idx+1}/{len(search_terms)}: «{term}»...")
                progress_bar.progress((idx) / len(search_terms))

                results = search_multiple_platforms(term.split(), days_back=days_filter)
                all_results.extend(results)

            progress_bar.progress(1.0)
            status_text.empty()
            progress_bar.empty()

            # Deduplicate by URL
            seen_urls = set()
            unique_results = []
            for job in all_results:
                if job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    unique_results.append(job)

            # ── Relevance filter: remove jobs that don't match search terms ──
            # Keep important short keywords like IT, ERP, SAP, BI, etc.
            IMPORTANT_SHORT_WORDS = {"it", "bi", "erp", "sap", "ax", "fi", "co", "pm", "ki", "ai"}
            # Generic words that alone are too broad (must be paired with a domain keyword)
            GENERIC_WORDS = {
                "projektleiter", "projektleiterin", "consultant", "berater", "beraterin",
                "manager", "managerin", "analyst", "analystin", "leiter", "leiterin",
                "engineer", "head", "coach", "master", "owner", "specialist", "spezialist",
            }

            # Build per-search-term keyword sets (for compound matching)
            search_term_words = []
            for t in search_terms:
                words = set()
                for word in t.lower().split():
                    if len(word) > 2 or word in IMPORTANT_SHORT_WORDS:
                        words.add(word)
                if words:
                    search_term_words.append(words)

            # All keywords flat (for quick lookup)
            all_keywords = set()
            for words in search_term_words:
                all_keywords.update(words)
            domain_keywords = all_keywords - GENERIC_WORDS

            import re as _re

            def _word_match(keyword, text):
                """Check if keyword appears as a whole word (not substring) in text."""
                return bool(_re.search(r'(?<![a-zäöü])' + _re.escape(keyword) + r'(?![a-zäöü])', text))

            filtered_results = []
            removed_count = 0
            for job in unique_results:
                title_lower = job.get("title", "").lower()
                company_lower = job.get("company", "").lower()
                searchable = title_lower + " " + company_lower

                # Strategy: job must match at least one full search term
                # (= at least one domain keyword + one generic, OR just a domain keyword)
                matched = False
                for term_words in search_term_words:
                    term_domain = term_words - GENERIC_WORDS
                    term_generic = term_words & GENERIC_WORDS

                    if term_domain:
                        # Must match at least one domain keyword as whole word
                        has_domain = any(_word_match(kw, searchable) for kw in term_domain)
                        if has_domain:
                            matched = True
                            break
                    elif term_generic:
                        # Only generic words (e.g. "Scrum Master") — require all words
                        if all(_word_match(kw, searchable) for kw in term_generic):
                            matched = True
                            break

                if matched:
                    filtered_results.append(job)
                else:
                    removed_count += 1

            st.session_state.search_results = filtered_results

            if filtered_results:
                dup_count = len(all_results) - len(unique_results)
                msg = f"✅ {len(filtered_results)} relevante Stellen gefunden!"
                if dup_count > 0 or removed_count > 0:
                    details = []
                    if dup_count > 0:
                        details.append(f"{dup_count} Duplikate (gleiche Stelle, mehrere Suchbegriffe)")
                    if removed_count > 0:
                        details.append(f"{removed_count} irrelevante entfernt")
                    msg += f" ({', '.join(details)})"
                st.success(msg)
            else:
                st.warning("Keine relevanten Stellen gefunden. Versuche andere Jobprofile.")
    
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
        cv_text_for_score = st.session_state.get("cv_text", "")

        # Calculate quick scores and sort by score
        results_with_scores = []
        for job in st.session_state.search_results:
            if cv_text_for_score:
                quick = calculate_quick_score(
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    cv_text_for_score
                )
            else:
                quick = 0
            results_with_scores.append((job, quick))

        # Sort by score descending
        results_with_scores.sort(key=lambda x: x[1], reverse=True)

        # ── Batch selection: checkboxes + "Alle Anschreiben erstellen" button ──
        selected_indices = []

        for i, (job, quick_score) in enumerate(results_with_scores):
            already_saved = job["url"] in existing_urls

            with st.container():
                col_check, col_main, col_btn = st.columns([0.3, 5, 1])

                with col_check:
                    st.markdown("<br>", unsafe_allow_html=True)
                    is_selected = st.checkbox("", key=f"select_{i}", label_visibility="collapsed")
                    if is_selected:
                        selected_indices.append(i)

                with col_main:
                    saved_badge = ' <span style="background:#16a34a;color:white;padding:2px 8px;border-radius:10px;font-size:0.7rem;">✓ Gespeichert</span>' if already_saved else ""
                    # Score badge — small pill next to title
                    if cv_text_for_score and quick_score > 0:
                        s_bg = "#dcfce7" if quick_score >= 65 else "#fef9c3" if quick_score >= 40 else "#f3f4f6"
                        s_color = "#16a34a" if quick_score >= 65 else "#b45309" if quick_score >= 40 else "#6b7280"
                        score_badge = f' <span style="background:{s_bg};color:{s_color};padding:2px 7px;border-radius:8px;font-size:0.7rem;font-weight:600;">{quick_score}%</span>'
                    else:
                        score_badge = ""
                    # Build meta parts without blank lines (Streamlit 1.45+ breaks HTML on blank lines)
                    meta_parts = [f'<span class="job-company">{job.get("company", "–")}</span>']
                    if job.get('location'):
                        meta_parts.append(f'&nbsp;&nbsp;📍 {job["location"]}')
                    if job.get('posted_date_raw') or job.get('posted_date'):
                        meta_parts.append(f'&nbsp;&nbsp;🗓️ {job.get("posted_date_raw", job.get("posted_date", ""))}')
                    if job.get('pensum'):
                        meta_parts.append(f'&nbsp;&nbsp;⏱️ {job["pensum"]}')
                    meta_parts.append(f'&nbsp;&nbsp;📌 {job.get("source", "jobs.ch")}')
                    meta_html = " ".join(meta_parts)
                    card_html = f'<div class="job-card"><div class="job-title">{job["title"]}{score_badge}{saved_badge}</div><div class="job-meta">{meta_html}</div><a href="{job["url"]}" target="_blank" style="color:#4a9eff;font-size:0.8rem;">🔗 Zum Inserat →</a></div>'
                    st.markdown(card_html, unsafe_allow_html=True)

                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if not already_saved:
                        if st.button("💾 Speichern", key=f"save_{i}", use_container_width=True):
                            if save_job(job):
                                existing_urls.add(job["url"])
                                st.success("Gespeichert!")
                                st.rerun()
                    if st.button("✍️ Bewerbung", key=f"apply_{i}", use_container_width=True):
                        # Save if not yet saved
                        if not already_saved:
                            save_job(job)
                        st.session_state[f"generating_{i}"] = True

                # ── Inline cover letter generation ──
                if st.session_state.get(f"generating_{i}"):
                    st.markdown("---")
                    cv_text = st.session_state.get("cv_text", "")
                    if not cv_text:
                        st.error("⚠️ Bitte zuerst deinen CV hochladen (Tab 'Unterlagen'), damit ein Anschreiben erstellt werden kann.")
                        st.session_state[f"generating_{i}"] = False
                    else:
                        # Step 1: Fetch job description
                        with st.spinner(f"📥 Lade Stellenbeschreibung für «{job['title']}»..."):
                            details = get_job_details(job.get("url", ""))
                            job_desc = details.get("description", "")
                            if details.get("company") and not job.get("company"):
                                job["company"] = details["company"]
                            contact_person = details.get("contact", "")
                            contact_email = details.get("email", "")
                            scraper_address = details.get("address", "")

                        if not job_desc:
                            st.warning("Konnte Stellenbeschreibung nicht laden. Bitte manuell im Tab 'KI-Anschreiben' eingeben.")
                            st.session_state.selected_job_for_ai = job
                            st.session_state[f"generating_{i}"] = False
                        else:
                            # Step 1b: Extract company details (address + contact)
                            with st.spinner("🔍 Extrahiere Firmendetails..."):
                                company_details = extract_company_details(job.get("company", ""), job_desc)
                                if company_details.get("contact_person") and not contact_person:
                                    contact_person = company_details["contact_person"]
                                # Address priority: scraper regex > AI extraction
                                company_address = scraper_address or company_details.get("company_address", "")

                            # Step 2: Generate cover letter
                            with st.spinner("✍️ KI generiert Anschreiben... (ca. 15-30 Sek.)"):
                                try:
                                    letter = generate_cover_letter(
                                        job_title=job.get("title", ""),
                                        company=job.get("company", ""),
                                        job_description=job_desc,
                                        cv_text=cv_text,
                                        existing_letter=st.session_state.get("cover_letter_text", ""),
                                        language="de",
                                        contact_person=contact_person,
                                        company_address=company_address,
                                    )
                                    st.session_state[f"letter_{i}"] = letter
                                    st.session_state[f"contact_email_{i}"] = contact_email
                                    st.session_state[f"contact_person_{i}"] = contact_person
                                    st.session_state[f"company_address_{i}"] = company_address
                                    st.session_state[f"generating_{i}"] = False
                                    st.success("✅ Anschreiben generiert!")
                                except Exception as e:
                                    st.error(f"Fehler bei der Generierung: {e}")
                                    st.session_state[f"generating_{i}"] = False

                # ── Show generated letter inline ──
                if st.session_state.get(f"letter_{i}"):
                    letter_text = st.session_state[f"letter_{i}"]
                    with st.expander(f"✉️ Anschreiben für «{job['title']}»", expanded=True):
                        st.text_area("", value=letter_text, height=300, key=f"letter_text_{i}")

                        # ── Editable company details for PDF ──
                        st.markdown("**📬 Empfänger-Adresse im PDF:**")
                        col_cp, col_addr = st.columns(2)
                        with col_cp:
                            edit_contact = st.text_input(
                                "Kontaktperson",
                                value=st.session_state.get(f"contact_person_{i}", ""),
                                placeholder="z.B. Frau Anna Müller",
                                key=f"edit_contact_{i}",
                            )
                        with col_addr:
                            edit_address = st.text_input(
                                "Firmenadresse (Strasse, PLZ Ort)",
                                value=st.session_state.get(f"company_address_{i}", ""),
                                placeholder="z.B. Hauptstrasse 25, 8500 Frauenfeld",
                                key=f"edit_address_{i}",
                            )

                        # Generate PDF with possibly edited values
                        try:
                            pdf_bytes = generate_cover_letter_pdf(
                                letter_text,
                                job_title=job.get('title', ''),
                                company=job.get('company', ''),
                                contact_person=edit_contact,
                                company_address=edit_address,
                            )
                            company_clean = _sanitize_company(job.get('company', 'Firma')).replace(' ', '_').replace('/', '-')[:40]
                            pdf_filename = f"Anschreiben_{company_clean}.pdf"
                        except Exception as e:
                            pdf_bytes = None
                            st.warning(f"PDF-Erstellung fehlgeschlagen: {e}")

                        # ── Email recipient ──
                        to_email = st.session_state.get(f"contact_email_{i}", "")
                        subject = f"Bewerbung: {job.get('title', '')}" + (f" — {job.get('company', '')}" if job.get('company') else "")
                        body_text = f"Sehr geehrte Damen und Herren,\n\nanbei sende ich Ihnen meine Bewerbungsunterlagen für die Stelle «{job.get('title', '')}».\n\nBitte finden Sie im Anhang:\n- Bewerbungsschreiben\n- Lebenslauf\n- Diplome & Zertifikate\n- Arbeitszeugnisse\n\nFreundliche Grüsse\nMiroslav Mikulic"

                        # ── Recipient email input ──
                        send_to = st.text_input(
                            "Empfänger E-Mail",
                            value=to_email,
                            placeholder="hr@firma.ch",
                            key=f"email_to_{i}"
                        )

                        # ── Action buttons ──
                        btn_cols = st.columns([2, 2, 1])
                        with btn_cols[0]:
                            send_clicked = st.button("📧 Bewerbung senden", key=f"send_{i}", use_container_width=True, type="primary")
                        with btn_cols[1]:
                            if pdf_bytes:
                                st.download_button(
                                    "📄 Anschreiben PDF",
                                    data=pdf_bytes,
                                    file_name=pdf_filename,
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"dl_pdf_{i}"
                                )
                        with btn_cols[2]:
                            if st.button("🗑️ Schliessen", key=f"close_{i}", use_container_width=True):
                                del st.session_state[f"letter_{i}"]
                                st.rerun()

                        # ── Send email with all attachments ──
                        if send_clicked:
                            if not send_to:
                                st.error("Bitte eine Empfänger-E-Mail eingeben.")
                            else:
                                settings = get_settings()
                                app_password = settings.get("gmail_app_password", "")
                                if not app_password:
                                    st.error("⚠️ Gmail App-Passwort fehlt! Bitte unter Einstellungen (Sidebar) das Gmail App-Passwort eintragen.")
                                else:
                                    with st.spinner("📧 Sende E-Mail mit allen Anhängen..."):
                                        try:
                                            attachments = []
                                            # 1. Cover letter PDF
                                            if pdf_bytes:
                                                attachments.append((pdf_filename, pdf_bytes))
                                            # 2. CV
                                            cv_d = get_document("cv")
                                            if cv_d and Path(cv_d["path"]).exists():
                                                with open(cv_d["path"], "rb") as f:
                                                    attachments.append((cv_d["filename"], f.read()))
                                            # 3. Diplome
                                            dip_d = get_document("diplome")
                                            if dip_d and Path(dip_d["path"]).exists():
                                                with open(dip_d["path"], "rb") as f:
                                                    attachments.append((dip_d["filename"], f.read()))
                                            # 4. Zeugnisse
                                            zeu_d = get_document("zeugnisse")
                                            if zeu_d and Path(zeu_d["path"]).exists():
                                                with open(zeu_d["path"], "rb") as f:
                                                    attachments.append((zeu_d["filename"], f.read()))

                                            from email_sender import send_email_with_attachments
                                            success, msg = send_email_with_attachments(
                                                to_email=send_to,
                                                subject=subject,
                                                body=body_text,
                                                attachments=attachments,
                                                gmail_app_password=app_password,
                                            )
                                            if success:
                                                st.success(f"✅ Bewerbung mit {len(attachments)} Anhängen an {send_to} gesendet!")
                                            else:
                                                st.error(f"Fehler beim Senden: {msg}")
                                        except Exception as e:
                                            st.error(f"Fehler: {e}")
        
        if st.button("📥 Alle speichern", type="primary"):
            count = 0
            for job in st.session_state.search_results:
                if save_job(job):
                    count += 1
            st.success(f"✅ {count} neue Stellen gespeichert!")
            st.rerun()

        # ── Batch cover letter generation ──
        if selected_indices:
            st.markdown("---")
            st.markdown(f"**{len(selected_indices)} Stelle(n) ausgewählt**")
            if st.button(f"✍️ Bewerbungsschreiben erstellen ({len(selected_indices)} Stellen)", type="primary", key="batch_generate"):
                cv_text = st.session_state.get("cv_text", "")
                if not cv_text:
                    st.error("⚠️ Bitte zuerst deinen CV hochladen (Tab 'Unterlagen').")
                else:
                    for idx in selected_indices:
                        job, _ = results_with_scores[idx]
                        st.markdown(f"---")
                        st.markdown(f"#### ✉️ {job['title']} — {job.get('company', '')}")

                        with st.spinner(f"📥 Lade Inserat «{job['title']}»..."):
                            details = get_job_details(job.get("url", ""))
                            job_desc = details.get("description", "")
                            contact_person = details.get("contact", "")
                            contact_email = details.get("email", "")
                            scraper_address = details.get("address", "")

                        if not job_desc:
                            st.warning(f"Konnte Beschreibung für «{job['title']}» nicht laden.")
                            continue

                        with st.spinner(f"🔍 Firmendetails für «{job.get('company', '')}»..."):
                            company_details = extract_company_details(job.get("company", ""), job_desc)
                            if company_details.get("contact_person") and not contact_person:
                                contact_person = company_details["contact_person"]
                            company_address = scraper_address or company_details.get("company_address", "")

                        with st.spinner(f"✍️ Generiere Anschreiben für «{job['title']}»..."):
                            try:
                                letter = generate_cover_letter(
                                    job_title=job.get("title", ""),
                                    company=job.get("company", ""),
                                    job_description=job_desc,
                                    cv_text=cv_text,
                                    existing_letter=st.session_state.get("cover_letter_text", ""),
                                    language="de",
                                    contact_person=contact_person,
                                    company_address=company_address,
                                )

                                # Save job if not yet saved
                                if job["url"] not in existing_urls:
                                    save_job(job)
                                    existing_urls.add(job["url"])

                                st.text_area("", value=letter, height=250, key=f"batch_letter_{idx}")

                                # Generate PDF
                                pdf_bytes = generate_cover_letter_pdf(
                                    letter,
                                    job_title=job.get("title", ""),
                                    company=job.get("company", ""),
                                    contact_person=contact_person,
                                    company_address=company_address,
                                )
                                company_clean = _sanitize_company(job.get("company", "Firma")).replace(" ", "_").replace("/", "-")[:40]
                                st.download_button(
                                    f"📄 PDF herunterladen — {company_clean}",
                                    data=pdf_bytes,
                                    file_name=f"Anschreiben_{company_clean}.pdf",
                                    mime="application/pdf",
                                    key=f"batch_pdf_{idx}",
                                )
                                st.success(f"✅ Anschreiben für «{job['title']}» erstellt!")
                            except Exception as e:
                                st.error(f"Fehler bei «{job['title']}»: {e}")

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
            sort_by = st.selectbox("Sortieren", ["Datum (neu)", "Score", "Status", "Titel"])

        # Apply filters
        filtered = jobs
        if filter_status:
            filtered = [j for j in filtered if j["status"] in filter_status]
        if filter_search:
            q = filter_search.lower()
            filtered = [j for j in filtered if q in j.get("title", "").lower() or q in j.get("company", "").lower()]

        # Calculate quick scores for all jobs
        cv_text_tracker = st.session_state.get("cv_text", "")
        for job in filtered:
            if not job.get("quick_score") and cv_text_tracker:
                job["_quick_score"] = calculate_quick_score(
                    job.get("title", ""), job.get("company", ""),
                    job.get("location", ""), cv_text_tracker
                )
            else:
                job["_quick_score"] = job.get("match_score", 0) or 0

        # Sort
        if sort_by == "Datum (neu)":
            filtered = sorted(filtered, key=lambda x: x.get("added_at", ""), reverse=True)
        elif sort_by == "Score":
            filtered = sorted(filtered, key=lambda x: x.get("match_score", 0) or x.get("_quick_score", 0), reverse=True)
        elif sort_by == "Status":
            filtered = sorted(filtered, key=lambda x: STATUS_OPTIONS.index(x.get("status", "Neu")))
        else:
            filtered = sorted(filtered, key=lambda x: x.get("title", ""))

        st.markdown(f"**{len(filtered)} von {len(jobs)} Stellen**")

        # Job list
        for job in filtered:
            status_color = STATUS_COLORS.get(job["status"], "#6c757d")

            # Determine display score: AI score preferred, else quick score
            display_score = job.get("match_score") or job.get("_quick_score", 0)
            score_emoji = "🟢" if display_score >= 60 else "🟡" if display_score >= 30 else "⚪" if display_score > 0 else ""
            score_label = f" | {score_emoji} {display_score}%" if display_score > 0 and cv_text_tracker else ""

            status_icon = '🟢' if job['status']=='Zusage' else '🔴' if job['status']=='Absage' else '🟡' if job['status']=='Interview' else '🔵' if job['status']=='Beworben' else '⚪'

            with st.expander(
                f"{status_icon}  {job['title']} — {job.get('company', '–')} | {job.get('location', '–')}{score_label}",
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
                    if display_score > 0:
                        s_color = "#16a34a" if display_score >= 60 else "#f59e0b" if display_score >= 30 else "#9ca3af"
                        score_type = "KI" if job.get("match_score") else "Quick"
                        st.markdown(f"**🎯 Match-Score ({score_type}):** <span style='color:{s_color};font-weight:700;'>{display_score}%</span>", unsafe_allow_html=True)
                
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

    # ── Load existing documents ──
    cv_doc = get_document("cv")
    letter_doc = get_document("cover_letter")
    diplom_doc = get_document("diplome")
    zeugnis_doc = get_document("zeugnisse")

    # Auto-load CV text if not yet in session
    if not st.session_state.cv_text and cv_doc:
        try:
            with open(cv_doc["path"], "rb") as f:
                content = f.read()
            if cv_doc["filename"].endswith(".pdf"):
                st.session_state.cv_text = extract_text_from_pdf(content)
            else:
                st.session_state.cv_text = extract_text_from_docx(content)
        except:
            pass

    # Auto-load cover letter text if not yet in session
    if not st.session_state.cover_letter_text and letter_doc:
        try:
            with open(letter_doc["path"], "rb") as f:
                content = f.read()
            if letter_doc["filename"].endswith(".pdf"):
                st.session_state.cover_letter_text = extract_text_from_pdf(content)
            else:
                st.session_state.cover_letter_text = extract_text_from_docx(content)
        except:
            pass

    # ── Document list: clean, compact rows ──
    docs_config = [
        {"key": "cv", "label": "Lebenslauf", "icon": "📋", "doc": cv_doc, "types": ["pdf", "docx"], "hint": "PDF oder DOCX"},
        {"key": "cover_letter", "label": "Muster-Anschreiben", "icon": "✉️", "doc": letter_doc, "types": ["pdf", "docx"], "hint": "PDF oder DOCX"},
        {"key": "diplome", "label": "Diplome & Zertifikate", "icon": "🎓", "doc": diplom_doc, "types": ["pdf"], "hint": "Alle Diplome als ein PDF"},
        {"key": "zeugnisse", "label": "Arbeitszeugnisse", "icon": "📝", "doc": zeugnis_doc, "types": ["pdf"], "hint": "Alle Zeugnisse als ein PDF"},
    ]

    # Count uploaded
    uploaded_count = sum(1 for d in docs_config if d["doc"])

    # Cloud storage status check
    drive_connected, drive_status_msg = test_storage_connection()
    if drive_connected:
        drive_badge = f'<span style="color:#16a34a;font-size:0.82rem;">☁️ {drive_status_msg}</span>'
    else:
        drive_badge = f'<span style="color:#dc3545;font-size:0.82rem;">⚠️ {drive_status_msg}</span>'

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e5ddd0;border-radius:10px;padding:14px 20px;margin-bottom:16px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<span style="font-size:1.3rem;">📂</span>'
        f'<span style="color:#2d2417;font-weight:600;">{uploaded_count} von 4 Dokumenten hochgeladen</span>'
        f'</div>'
        f'{drive_badge}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    for cfg in docs_config:
        doc = cfg["doc"]
        if doc:
            # ── Document already uploaded: show compact row ──
            st.markdown(
                f'<div style="background:#ffffff;border:1px solid #e5ddd0;border-radius:10px;padding:12px 18px;margin-bottom:8px;'
                f'display:flex;align-items:center;justify-content:space-between;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<span style="font-size:1.1rem;">{cfg["icon"]}</span>'
                f'<div>'
                f'<div style="color:#2d2417;font-weight:600;font-size:0.92rem;">{cfg["label"]}</div>'
                f'<div style="color:#16a34a;font-size:0.82rem;">{doc["filename"]}</div>'
                f'</div></div>'
                f'<span style="color:#16a34a;font-size:1.1rem;">✓</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Expander to replace the file
            with st.expander(f"🔄 {cfg['label']} ersetzen", expanded=False):
                new_file = st.file_uploader(
                    f"Neue Datei für {cfg['label']}",
                    type=cfg["types"],
                    key=f"{cfg['key']}_replace",
                )
                if new_file:
                    content = new_file.read()
                    drive_ok, drive_msg = save_document(new_file.name, content, cfg["key"])
                    if cfg["key"] == "cv":
                        if new_file.name.endswith(".pdf"):
                            st.session_state.cv_text = extract_text_from_pdf(content)
                        else:
                            st.session_state.cv_text = extract_text_from_docx(content)
                    elif cfg["key"] == "cover_letter":
                        if new_file.name.endswith(".pdf"):
                            st.session_state.cover_letter_text = extract_text_from_pdf(content)
                        else:
                            st.session_state.cover_letter_text = extract_text_from_docx(content)
                    st.success(f"'{new_file.name}' aktualisiert!")
                    if drive_ok:
                        st.info(drive_msg)
                    else:
                        st.warning(drive_msg)
        else:
            # ── Document not yet uploaded: show upload area ──
            st.markdown(
                f'<div style="background:#fff8f0;border:1px dashed #d4c4ae;border-radius:10px;padding:12px 18px;margin-bottom:4px;'
                f'display:flex;align-items:center;gap:10px;">'
                f'<span style="font-size:1.1rem;">{cfg["icon"]}</span>'
                f'<div>'
                f'<div style="color:#2d2417;font-weight:600;font-size:0.92rem;">{cfg["label"]}</div>'
                f'<div style="color:#a0917d;font-size:0.82rem;">Noch nicht hochgeladen</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            new_file = st.file_uploader(
                cfg["hint"],
                type=cfg["types"],
                key=f"{cfg['key']}_upload",
            )
            if new_file:
                content = new_file.read()
                drive_ok, drive_msg = save_document(new_file.name, content, cfg["key"])
                if cfg["key"] == "cv":
                    if new_file.name.endswith(".pdf"):
                        st.session_state.cv_text = extract_text_from_pdf(content)
                    else:
                        st.session_state.cv_text = extract_text_from_docx(content)
                elif cfg["key"] == "cover_letter":
                    if new_file.name.endswith(".pdf"):
                        st.session_state.cover_letter_text = extract_text_from_pdf(content)
                    else:
                        st.session_state.cover_letter_text = extract_text_from_docx(content)
                st.success(f"'{new_file.name}' gespeichert!")
                if drive_ok:
                    st.info(drive_msg)
                else:
                    st.warning(drive_msg)

# ═══════════════════════════════════════════
# TAB 4: AI Cover Letter
# ═══════════════════════════════════════════
with tab4:
    st.markdown("## 🤖 KI-Anschreiben Generator")

    settings = get_settings()

    # ── Job selection: dropdown from saved jobs ──
    all_jobs = get_jobs()
    job_options = {f"{j['title']} — {j.get('company', '?')} ({j.get('location', '?')})": j for j in all_jobs}

    if not all_jobs:
        st.warning("⚠️ Noch keine Stellen gespeichert. Speichere zuerst Stellen über die Stellensuche (Tab 1).")

    # Determine default index if a job was pre-selected from tracker
    default_idx = 0
    if st.session_state.selected_job_for_ai:
        sel_id = st.session_state.selected_job_for_ai.get("id")
        for idx, (label, j) in enumerate(job_options.items()):
            if j.get("id") == sel_id:
                default_idx = idx
                break

    selected_label = st.selectbox(
        "📌 Stelle auswählen",
        options=list(job_options.keys()) if job_options else ["Keine Stellen vorhanden"],
        index=default_idx,
        help="Wähle eine gespeicherte Stelle — Titel, Firma und Beschreibung werden automatisch geladen.",
        key="ai_job_select"
    )

    selected_job = job_options.get(selected_label)

    # Auto-load job details when a job is selected
    if selected_job:
        ai_title = selected_job.get("title", "")
        ai_company = selected_job.get("company", "")
        ai_url = selected_job.get("url", "")

        # Show selected job info
        # Build meta parts without blank lines (Streamlit 1.45+ breaks HTML on blank lines)
        ai_meta_parts = [f'<span class="job-company">{ai_company or "–"}</span>']
        if selected_job.get('location'):
            ai_meta_parts.append(f'&nbsp;&nbsp;📍 {selected_job["location"]}')
        if selected_job.get('pensum'):
            ai_meta_parts.append(f'&nbsp;&nbsp;⏱️ {selected_job["pensum"]}')
        if ai_url:
            ai_meta_parts.append(f'&nbsp;&nbsp;🔗 <a href="{ai_url}" target="_blank" style="color:#b47a3e;">Zum Inserat</a>')
        ai_meta_html = " ".join(ai_meta_parts)
        ai_card_html = f'<div class="job-card"><div class="job-title">{ai_title}</div><div class="job-meta">{ai_meta_html}</div></div>'
        st.markdown(ai_card_html, unsafe_allow_html=True)

        # Auto-fetch job description if not already loaded for this job
        job_desc_key = f"ai_job_desc_{selected_job.get('id', '')}"
        contact_key = f"ai_contact_{selected_job.get('id', '')}"
        contact_email_key = f"ai_contact_email_{selected_job.get('id', '')}"
        if job_desc_key not in st.session_state:
            # Try to use stored description first
            if selected_job.get("description"):
                st.session_state[job_desc_key] = selected_job["description"]
            elif ai_url:
                with st.spinner("📥 Lade Stellenbeschreibung von jobs.ch..."):
                    details = get_job_details(ai_url)
                    if details.get("description"):
                        st.session_state[job_desc_key] = details["description"]
                        # Also update company if we got a better one
                        if details.get("company") and not ai_company:
                            ai_company = details["company"]
                        # Store contact info
                        st.session_state[contact_key] = details.get("contact", "")
                        st.session_state[contact_email_key] = details.get("email", "")
                        if details.get("address"):
                            st.session_state[f"scraper_address_{selected_job.get('id', '')}"] = details["address"]
                    else:
                        st.session_state[job_desc_key] = ""

        ai_job_desc = st.session_state.get(job_desc_key, "")

        # Show description (editable for manual adjustments)
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📝 Stellenbeschreibung")
            if ai_job_desc:
                st.caption(f"✅ {len(ai_job_desc)} Zeichen automatisch geladen")
            ai_job_desc = st.text_area(
                "Beschreibung (automatisch geladen, editierbar)",
                value=ai_job_desc,
                height=250,
                key="ai_desc_textarea",
                placeholder="Wird automatisch von jobs.ch geladen..."
            )
            if st.button("🔄 Beschreibung neu laden", key="reload_desc"):
                if ai_url:
                    with st.spinner("Lade..."):
                        details = get_job_details(ai_url)
                        if details.get("description"):
                            st.session_state[job_desc_key] = details["description"]
                            st.rerun()

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
                placeholder="z.B. spezifische Motivationen, besondere Punkte...",
                key="ai_extra_info_input"
            )

            ai_language = st.radio("Sprache", ["Deutsch", "English"], horizontal=True, key="ai_lang_radio")
            lang_code = "de" if ai_language == "Deutsch" else "en"
    else:
        ai_title = ""
        ai_company = ""
        ai_job_desc = ""
        ai_url = ""
        cv_available = bool(st.session_state.cv_text)
        ai_extra_info = ""
        lang_code = "de"

    col_gen, col_score = st.columns(2)

    with col_gen:
        generate_btn = st.button(
            "✍️ Anschreiben generieren",
            type="primary",
            use_container_width=True,
            disabled=not (ai_title and ai_job_desc and cv_available)
        )

    with col_score:
        score_btn = st.button(
            "🎯 Match-Score berechnen",
            use_container_width=True,
            disabled=not (ai_job_desc and cv_available)
        )
    
    if generate_btn:
        cv_with_extra = st.session_state.cv_text
        if ai_extra_info:
            cv_with_extra += f"\n\nZusätzliche Informationen: {ai_extra_info}"

        # Get contact info if available
        ai_contact = ""
        ai_contact_email = ""
        ai_company_address = ""
        if selected_job:
            ai_contact = st.session_state.get(f"ai_contact_{selected_job.get('id', '')}", "")
            ai_contact_email = st.session_state.get(f"ai_contact_email_{selected_job.get('id', '')}", "")

        # Extract company details (address + contact person)
        scraper_addr = ""
        if selected_job:
            scraper_addr = st.session_state.get(f"scraper_address_{selected_job.get('id', '')}", "")
        with st.spinner("🔍 Extrahiere Firmendetails..."):
            company_info = extract_company_details(ai_company, ai_job_desc)
            if company_info.get("contact_person") and not ai_contact:
                ai_contact = company_info["contact_person"]
            # Address priority: scraper regex > AI extraction
            ai_company_address = scraper_addr or company_info.get("company_address", "")

        with st.spinner("✍️ KI generiert Anschreiben... (ca. 15-30 Sekunden)"):
            try:
                result = generate_cover_letter(
                    job_title=ai_title,
                    company=ai_company,
                    job_description=ai_job_desc,
                    cv_text=cv_with_extra,
                    existing_letter=st.session_state.cover_letter_text,
                    language=lang_code,
                    contact_person=ai_contact,
                    company_address=ai_company_address,
                )
                st.session_state["generated_letter"] = result
                st.session_state["generated_letter_email"] = ai_contact_email
                st.session_state["generated_letter_contact"] = ai_contact
                st.session_state["generated_letter_address"] = ai_company_address
                st.success("✅ Anschreiben generiert!")
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    if score_btn:
        with st.spinner("Analysiere Übereinstimmung..."):
            try:
                score_result = calculate_match_score(
                    job_description=ai_job_desc,
                    cv_text=st.session_state.cv_text
                )
                st.session_state["score_result"] = score_result
                
                # Save score to job if selected
                if selected_job:
                    update_job(selected_job["id"], {
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

        # ── Editable company details for PDF ──
        st.markdown("**📬 Empfänger-Adresse im PDF:**")
        col_cp4, col_addr4 = st.columns(2)
        with col_cp4:
            edit_contact_t4 = st.text_input(
                "Kontaktperson",
                value=st.session_state.get("generated_letter_contact", ai_contact),
                placeholder="z.B. Frau Anna Müller",
                key="edit_contact_tab4",
            )
        with col_addr4:
            edit_address_t4 = st.text_input(
                "Firmenadresse (Strasse, PLZ Ort)",
                value=st.session_state.get("generated_letter_address", ""),
                placeholder="z.B. Hauptstrasse 25, 8500 Frauenfeld",
                key="edit_address_tab4",
            )

        # Generate PDF with possibly edited values
        try:
            pdf_bytes = generate_cover_letter_pdf(
                letter_text,
                job_title=ai_title,
                company=ai_company,
                contact_person=edit_contact_t4,
                company_address=edit_address_t4,
            )
            company_clean = _sanitize_company(ai_company).replace(' ', '_').replace('/', '-')[:40] if ai_company else "Firma"
            pdf_filename = f"Anschreiben_{company_clean}.pdf"
        except Exception as e:
            pdf_bytes = None
            st.warning(f"PDF-Erstellung fehlgeschlagen: {e}")

        st.markdown("#### 📥 Unterlagen herunterladen")
        dl_cols = st.columns(5)
        with dl_cols[0]:
            if pdf_bytes:
                st.download_button("📄 Anschreiben", data=pdf_bytes, file_name=pdf_filename, mime="application/pdf", use_container_width=True, key="tab4_dl_pdf")
        with dl_cols[1]:
            cv_doc = get_document("cv")
            if cv_doc:
                cv_path = Path(cv_doc.get("path", ""))
                if cv_path.exists():
                    with open(cv_path, "rb") as f:
                        cv_bytes = f.read()
                    st.download_button("📋 CV", data=cv_bytes, file_name=cv_doc.get("filename", "Lebenslauf.pdf"), mime="application/pdf", use_container_width=True, key="tab4_dl_cv")
        with dl_cols[2]:
            diploma_doc = get_document("diplome")
            if diploma_doc:
                diploma_path = Path(diploma_doc.get("path", ""))
                if diploma_path.exists():
                    with open(diploma_path, "rb") as f:
                        diploma_bytes = f.read()
                    st.download_button("🎓 Diplome", data=diploma_bytes, file_name=diploma_doc.get("filename", "Diplome.pdf"), mime="application/pdf", use_container_width=True, key="tab4_dl_diploma")
        with dl_cols[3]:
            zeugnis_doc = get_document("zeugnisse")
            if zeugnis_doc:
                zeugnis_path = Path(zeugnis_doc.get("path", ""))
                if zeugnis_path.exists():
                    with open(zeugnis_path, "rb") as f:
                        zeugnis_bytes = f.read()
                    st.download_button("📝 Zeugnisse", data=zeugnis_bytes, file_name=zeugnis_doc.get("filename", "Arbeitszeugnisse.pdf"), mime="application/pdf", use_container_width=True, key="tab4_dl_zeugnis")
        with dl_cols[4]:
            if selected_job and st.button("💾 In Stelle speichern", use_container_width=True, key="tab4_save_job"):
                update_job(selected_job["id"], {
                    "cover_letter": letter_text,
                    "status": "Interessant"
                })
                st.success("Gespeichert!")

        # Gmail compose link
        import urllib.parse
        subject = f"Bewerbung: {ai_title}" + (f" — {ai_company}" if ai_company else "")
        to_email = st.session_state.get("generated_letter_email", "")
        subject_encoded = urllib.parse.quote(subject)
        body_text = f"Sehr geehrte Damen und Herren,\n\nanbei sende ich Ihnen meine Bewerbungsunterlagen für die Stelle «{ai_title}».\n\nBitte finden Sie im Anhang:\n- Bewerbungsschreiben\n- Lebenslauf\n- Diplome & Zertifikate\n- Arbeitszeugnisse\n\nFreundliche Grüsse\nMiroslav Mikulic"
        body_encoded = urllib.parse.quote(body_text)
        gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1"
        if to_email:
            gmail_url += f"&to={urllib.parse.quote(to_email)}"
        gmail_url += f"&su={subject_encoded}&body={body_encoded}"

        st.markdown(
            f'<a href="{gmail_url}" target="_blank" style="'
            f'display:inline-block;width:100%;text-align:center;padding:12px 16px;margin-top:8px;'
            f'background:linear-gradient(135deg,#ea4335,#d93025);color:white;'
            f'border-radius:10px;text-decoration:none;font-weight:600;font-size:0.95rem;'
            f'box-sizing:border-box;">'
            f'📧 Gmail öffnen & PDFs anhängen</a>',
            unsafe_allow_html=True
        )
        st.caption("💡 Lade zuerst die PDFs oben herunter, dann öffne Gmail und hänge sie an.")

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
                paper_bgcolor="#faf7f2",
                plot_bgcolor="#faf7f2",
                font={"color": "#2d2417"},
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
                    color_discrete_sequence=["#c4956a"]
                )
                fig_bar.update_layout(
                    paper_bgcolor="#faf7f2",
                    plot_bgcolor="#faf7f2",
                    font={"color": "#2d2417"},
                    xaxis={"gridcolor": "#e5ddd0"},
                    yaxis={"gridcolor": "#e5ddd0"}
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
                paper_bgcolor="#faf7f2",
                plot_bgcolor="#faf7f2",
                font={"color": "#2d2417"},
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

# ═══════════════════════════════════════════
# TAB 6: Settings
# ═══════════════════════════════════════════
with tab6:
    st.markdown("## ⚙️ Einstellungen")

    settings = get_settings()

    # ── Gmail E-Mail-Versand ──
    st.markdown(
        '<div style="background:#ffffff;border:1px solid #e5ddd0;border-radius:12px;padding:20px 24px;margin-bottom:20px;'
        'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        '<div style="color:#2d2417;font-weight:700;font-size:1.05rem;margin-bottom:12px;">📧 Gmail E-Mail-Versand</div>'
        '<div style="color:#7a6b56;font-size:0.85rem;margin-bottom:8px;">'
        'Damit du Bewerbungen direkt aus der App versenden kannst, brauchst du ein Gmail App-Passwort.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    gmail_app_pw = st.text_input(
        "Gmail App-Passwort",
        value=settings.get("gmail_app_password", ""),
        type="password",
        placeholder="xxxx xxxx xxxx xxxx",
        help="16-stelliges App-Passwort (mit oder ohne Leerzeichen)",
    )
    st.markdown(
        '<div style="font-size:0.82rem;color:#7a6b56;margin-top:-8px;margin-bottom:16px;">'
        '1. <a href="https://myaccount.google.com/security" target="_blank" style="color:#c4956a;">2-Faktor-Auth aktivieren</a> '
        '→ 2. <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color:#c4956a;">App-Passwort erstellen</a> '
        '→ 3. Hier eintragen</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Sucheinstellungen ──
    st.markdown(
        '<div style="background:#ffffff;border:1px solid #e5ddd0;border-radius:12px;padding:20px 24px;margin-bottom:20px;'
        'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        '<div style="color:#2d2417;font-weight:700;font-size:1.05rem;margin-bottom:12px;">🔍 Sucheinstellungen</div>'
        '<div style="color:#7a6b56;font-size:0.85rem;margin-bottom:8px;">'
        'Die Jobprofile kannst du direkt im Tab «Stellensuche» per Multiselect auswählen.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    default_days = st.slider(
        "Inserate der letzten X Tage",
        min_value=3, max_value=60, value=settings.get("default_days", 7),
    )

    st.markdown("---")

    # ── Speichern ──
    if st.button("💾 Einstellungen speichern", type="primary", use_container_width=True):
        settings["default_days"] = default_days
        settings["gmail_app_password"] = gmail_app_pw
        save_settings(settings)
        st.success("✅ Einstellungen gespeichert!")

    # ── Info ──
    st.markdown("---")
    st.markdown(
        '<div style="background:#fff8f0;border:1px solid #e5ddd0;border-radius:10px;padding:16px 20px;'
        'color:#7a6b56;font-size:0.82rem;">'
        '<strong>ℹ️ Über JobTracker Pro</strong><br>'
        'Absender-E-Mail: miroslav.mikulic@gmail.com<br>'
        'Daten gespeichert via: ' + ('GitHub ☁️' if cloud_ok else 'Lokaler Speicher 💾') +
        '</div>',
        unsafe_allow_html=True,
    )
