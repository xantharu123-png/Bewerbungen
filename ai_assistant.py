import anthropic
import PyPDF2
import io
import os
from pathlib import Path
from datetime import datetime

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
    api_key: str = "",
    contact_person: str = "",
    company_address: str = "",
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

    # Build address block info
    contact_info = ""
    if contact_person:
        contact_info += f"\nAnsprechperson: {contact_person}"
    if company_address:
        contact_info += f"\nAdresse des Unternehmens: {company_address}"

    prompt = f"""Du bist ein professioneller Karriereberater in der Schweiz. Schreibe ein massgeschneidertes Bewerbungsschreiben {lang_instruction}.

**Stellenanzeige:**
Stelle: {job_title}
Unternehmen: {company}{contact_info}
Beschreibung: {job_description[:2000]}

**Lebenslauf des Bewerbers:**
{cv_text[:2000]}

{existing_section}

**Anforderungen an das Anschreiben:**
- Das Schreiben MUSS mit dem formalen Briefkopf beginnen:

  Miroslav Mikulic
  Im Weberlis Rebberg 42
  8500 Gerlikon
  079 602 83 31
  Miroslav.Mikulic@gmail.com

  {company}{"" if not contact_person else chr(10) + "  z.Hd. " + contact_person}{"" if not company_address else chr(10) + "  " + company_address}

  Gerlikon, {datetime.now().strftime("%d.%m.%Y")}

- Betreffzeile: "Bewerbung als {job_title}"
- Falls eine Ansprechperson bekannt ist, mit "Sehr geehrte/r Frau/Herr [Name]" beginnen
- Falls keine Ansprechperson bekannt: "Sehr geehrte Damen und Herren"
- Professioneller, aber persönlicher Ton
- Konkrete Bezüge zwischen Erfahrungen des Bewerbers und den Stellenanforderungen
- Ca. 3-4 Absätze (Einleitung mit Bezug zur Stelle, Kernkompetenzen/Motivation, konkreter Mehrwert, Schluss mit Vorfreude auf Gespräch)
- Schweizerische Gepflogenheiten beachten (z.B. "Freundliche Grüsse" statt "Mit freundlichen Grüssen")
- Keine Floskeln, keine übertriebenen Superlative
- Am Ende: "Freundliche Grüsse" und den Namen "Miroslav Mikulic"

Schreibe NUR das fertige Bewerbungsschreiben, ohne zusätzliche Kommentare."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def generate_cover_letter_pdf(letter_text: str, filename: str = "Anschreiben.pdf") -> bytes:
    """Generate a professionally formatted PDF from cover letter text using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.colors import HexColor

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    # Styles
    style_normal = ParagraphStyle(
        'Normal',
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )

    style_sender = ParagraphStyle(
        'Sender',
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        textColor=HexColor('#333333'),
    )

    style_bold = ParagraphStyle(
        'Bold',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        alignment=TA_LEFT,
        spaceAfter=8,
    )

    style_greeting = ParagraphStyle(
        'Greeting',
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    story = []

    # Parse the letter text into structured parts
    lines = letter_text.strip().split('\n')

    # Process lines into paragraphs
    current_paragraph = []
    in_header = True  # Track if we're still in the header section
    header_done = False
    betreff_found = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines but handle paragraph breaks
        if not stripped:
            if current_paragraph:
                text = ' '.join(current_paragraph)
                if in_header:
                    # Header lines (sender, recipient, date)
                    for header_line in current_paragraph:
                        story.append(Paragraph(header_line, style_sender))
                    story.append(Spacer(1, 4*mm))
                elif betreff_found and not header_done:
                    # Subject line
                    story.append(Paragraph(text, style_bold))
                    story.append(Spacer(1, 4*mm))
                    header_done = True
                    betreff_found = False
                else:
                    story.append(Paragraph(text, style_normal))
                current_paragraph = []
            else:
                story.append(Spacer(1, 3*mm))
            continue

        # Detect "Bewerbung als..." or "Betreff:" line
        if stripped.lower().startswith('bewerbung als') or stripped.lower().startswith('betreff'):
            if current_paragraph:
                # Flush previous paragraph as header
                for header_line in current_paragraph:
                    story.append(Paragraph(header_line, style_sender))
                story.append(Spacer(1, 6*mm))
                current_paragraph = []
            in_header = False
            betreff_found = True
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(f"<b>{stripped}</b>", style_bold))
            story.append(Spacer(1, 4*mm))
            header_done = True
            betreff_found = False
            continue

        # Detect greeting line "Sehr geehrte..."
        if stripped.startswith('Sehr geehrte') or stripped.startswith('Dear'):
            if current_paragraph:
                for header_line in current_paragraph:
                    story.append(Paragraph(header_line, style_sender))
                story.append(Spacer(1, 4*mm))
                current_paragraph = []
            in_header = False
            header_done = True
            story.append(Paragraph(stripped, style_greeting))
            story.append(Spacer(1, 3*mm))
            continue

        # Detect date line (e.g., "Gerlikon, 02.03.2026")
        if in_header and ('Gerlikon' in stripped or 'den ' in stripped.lower()):
            if current_paragraph:
                for header_line in current_paragraph:
                    story.append(Paragraph(header_line, style_sender))
                current_paragraph = []
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(stripped, style_sender))
            story.append(Spacer(1, 8*mm))
            continue

        # Detect closing "Freundliche Grüsse" / "Mit freundlichen Grüssen"
        if stripped.lower().startswith('freundliche gr') or stripped.lower().startswith('mit freundlichen'):
            if current_paragraph:
                text = ' '.join(current_paragraph)
                story.append(Paragraph(text, style_normal))
                current_paragraph = []
            story.append(Spacer(1, 6*mm))
            story.append(Paragraph(stripped, style_normal))
            continue

        # Detect signature name (after greeting)
        if stripped == 'Miroslav Mikulic' and not in_header:
            story.append(Spacer(1, 8*mm))
            story.append(Paragraph(stripped, style_normal))
            continue

        # Regular content line
        if in_header and not header_done:
            current_paragraph.append(stripped)
        else:
            in_header = False
            header_done = True
            current_paragraph.append(stripped)

    # Flush remaining paragraph
    if current_paragraph:
        if in_header:
            for header_line in current_paragraph:
                story.append(Paragraph(header_line, style_sender))
        else:
            text = ' '.join(current_paragraph)
            story.append(Paragraph(text, style_normal))

    doc.build(story)
    return buffer.getvalue()


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
