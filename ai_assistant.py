import anthropic
import PyPDF2
import io
import os
from pathlib import Path

# API Key aus Environment Variable oder Streamlit Secrets
def _load_api_key() -> str:
    """Load API key from environment or Streamlit secrets."""
    # 1. Environment variable (lokal oder Streamlit Cloud)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # 2. Streamlit secrets (secrets.toml oder Cloud Secrets)
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return ""

ANTHROPIC_API_KEY = _load_api_key()

def _get_client() -> anthropic.Anthropic:
    """Create Anthropic client with the configured API key."""
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"[Fehler beim PDF-Lesen: {e}]"

def extract_text_from_docx(docx_bytes: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(docx_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        return f"[Fehler beim DOCX-Lesen: {e}]"

def generate_cover_letter(
    job_title: str,
    company: str,
    job_description: str,
    cv_text: str,
    existing_letter: str = "",
    language: str = "de",
    api_key: str = ""
) -> str:
    """Generate a tailored cover letter using Claude API."""

    client = _get_client()
    
    lang_instruction = "auf Deutsch" if language == "de" else "in English"
    
    existing_section = f"""
Als Referenz hier ein bestehendes Anschreiben des Bewerbers (Stil und Struktur beibehalten, aber auf die neue Stelle anpassen):
---
{existing_letter[:2000]}
---
""" if existing_letter else ""
    
    prompt = f"""Du bist ein professioneller Karriereberater. Schreibe ein massgeschneidertes Bewerbungsschreiben {lang_instruction}.

**Stellenanzeige:**
Stelle: {job_title}
Unternehmen: {company}
Beschreibung: {job_description[:1500]}

**Lebenslauf des Bewerbers:**
{cv_text[:2000]}

{existing_section}

**Anforderungen:**
- Professioneller, aber persönlicher Ton
- Konkrete Bezüge zwischen Erfahrungen des Bewerbers und den Stellenanforderungen
- Ca. 3-4 Absätze (Einleitung, Kernkompetenzen/Motivation, Bezug zur Stelle, Schluss)
- Schweizerische Gepflogenheiten beachten
- Keine Floskeln, keine übertriebenen Superlative
- Mit Briefkopf-Platzhalter für Adresse

Schreibe NUR das fertige Bewerbungsschreiben, ohne zusätzliche Kommentare."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text

def calculate_match_score(
    job_description: str,
    cv_text: str,
    api_key: str = ""
) -> dict:
    """Calculate how well a candidate matches a job posting."""

    client = _get_client()
    
    prompt = f"""Analysiere die Übereinstimmung zwischen diesem Stelleninserat und dem Lebenslauf.

**Stelleninserat:**
{job_description[:1500]}

**Lebenslauf:**
{cv_text[:1500]}

Antworte NUR mit einem JSON-Objekt in diesem Format:
{{
  "score": <Zahl 0-100>,
  "strengths": ["Stärke 1", "Stärke 2", "Stärke 3"],
  "gaps": ["Lücke 1", "Lücke 2"],
  "recommendation": "Kurze Empfehlung in 1-2 Sätzen"
}}"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    import json
    text = message.content[0].text.strip()
    # Extract JSON
    import re
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))
    return {"score": 0, "strengths": [], "gaps": [], "recommendation": "Fehler bei der Analyse"}
