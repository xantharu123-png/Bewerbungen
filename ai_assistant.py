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

    # Determine greeting
    if contact_person:
        name_parts = contact_person.strip().split()
        first_name = name_parts[0] if name_parts else ""
        if first_name.lower() in ["frau", "fr."]:
            greeting = f"Sehr geehrte Frau {' '.join(name_parts[1:])}"
        elif first_name.lower() in ["herr", "hr."]:
            greeting = f"Sehr geehrter Herr {' '.join(name_parts[1:])}"
        else:
            greeting = f"Sehr geehrte/r {contact_person}"
    else:
        greeting = "Sehr geehrte Damen und Herren"

    # ── Two modes: TEMPLATE mode (if existing letter) or FREE mode ──
    if existing_letter and len(existing_letter.strip()) > 100:
        # TEMPLATE MODE: Use existing letter as exact template
        prompt = f"""Du erhältst eine VORLAGE eines Bewerbungsschreibens und eine neue Stellenanzeige.

**DEINE AUFGABE:** Passe die Vorlage auf die neue Stelle an. Behalte dabei:
- EXAKT die gleiche Struktur und Anzahl Absätze
- EXAKT den gleichen Schreibstil und Tonfall
- EXAKT die gleiche Länge (ungefähr gleich viele Sätze pro Absatz)
- Die gleiche Art, wie der Bewerber sich vorstellt und argumentiert

Ändere NUR die stellenspezifischen Inhalte:
- Bezug zur neuen Stelle statt zur alten
- Relevante Erfahrungen/Kompetenzen für DIESE Stelle hervorheben
- Firmenname und Stellentitel anpassen
- Anrede anpassen

**VORLAGE (diese Struktur und Stil EXAKT beibehalten):**
---
{existing_letter[:3000]}
---

**NEUE STELLE:**
Stelle: {job_title}
Unternehmen: {company}
Beschreibung: {job_description[:2000]}

**Lebenslauf (für relevante Details):**
{cv_text[:1500]}

**AUSGABE-REGELN:**
- Beginne mit: "{greeting}"
- Ende mit: "Freundliche Grüsse" und "Miroslav Mikulic"
- KEIN Briefkopf, KEINE Adresse, KEIN Datum, KEIN Betreff — nur der Brieftext
- Gib NUR den fertigen Brieftext zurück, keine Kommentare"""

    else:
        # FREE MODE: Generate from scratch
        prompt = f"""Schreibe ein professionelles Schweizer Bewerbungsschreiben {lang_instruction}.

**Stellenanzeige:**
Stelle: {job_title}
Unternehmen: {company}
Beschreibung: {job_description[:2000]}

**Lebenslauf des Bewerbers:**
{cv_text[:2000]}

**WICHTIG — Gib NUR den Brieftext zurück, EXAKT in diesem Format:**

{greeting}

[Einleitung: 2-3 Sätze, konkreter Bezug zur Stelle und warum diese Stelle den Bewerber anspricht]

[Kernabsatz: 4-6 Sätze über relevante Erfahrungen, Kompetenzen und bisherige Projekte des Bewerbers, die zur Stelle passen. Konkrete Beispiele, keine Floskeln.]

[Mehrwert-Absatz: 3-4 Sätze darüber, welchen Mehrwert der Bewerber einbringt und was ihn motiviert]

[Schluss: 2-3 Sätze mit Gesprächswunsch]

Freundliche Grüsse

Miroslav Mikulic

**REGELN:**
- Schreibe NUR die Absätze zwischen Anrede und Gruss — KEIN Briefkopf, KEINE Adresse, KEIN Datum, KEIN Betreff
- Beginne direkt mit "{greeting}"
- Ende mit "Freundliche Grüsse" und "Miroslav Mikulic"
- Professioneller, persönlicher Ton — schweizerisch
- Keine Floskeln, keine Superlative
- 3-4 Absätze Haupttext"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def generate_cover_letter_pdf(
    letter_text: str,
    job_title: str = "",
    company: str = "",
    contact_person: str = "",
    company_address: str = "",
) -> bytes:
    """Generate a professionally formatted Swiss business letter PDF.

    The letter_text should contain ONLY the body (greeting through signature).
    The PDF adds the fixed sender block, recipient block, date, and Betreff automatically.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.colors import HexColor

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2.5*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    # ── Styles ──
    style_sender = ParagraphStyle(
        'Sender', fontName='Helvetica', fontSize=9, leading=13,
        alignment=TA_LEFT, textColor=HexColor('#555555'),
    )
    style_recipient = ParagraphStyle(
        'Recipient', fontName='Helvetica', fontSize=10.5, leading=15,
        alignment=TA_LEFT, textColor=HexColor('#222222'),
    )
    style_date = ParagraphStyle(
        'Date', fontName='Helvetica', fontSize=10.5, leading=15,
        alignment=TA_RIGHT, textColor=HexColor('#222222'),
    )
    style_betreff = ParagraphStyle(
        'Betreff', fontName='Helvetica-Bold', fontSize=11, leading=16,
        alignment=TA_LEFT, textColor=HexColor('#222222'), spaceAfter=4,
    )
    style_body = ParagraphStyle(
        'Body', fontName='Helvetica', fontSize=10.5, leading=15,
        alignment=TA_JUSTIFY, textColor=HexColor('#222222'), spaceAfter=10,
    )
    style_greeting = ParagraphStyle(
        'Greeting', fontName='Helvetica', fontSize=10.5, leading=15,
        alignment=TA_LEFT, textColor=HexColor('#222222'), spaceAfter=6,
    )
    style_closing = ParagraphStyle(
        'Closing', fontName='Helvetica', fontSize=10.5, leading=15,
        alignment=TA_LEFT, textColor=HexColor('#222222'),
    )

    story = []

    # ═══ 1. SENDER BLOCK ═══
    sender_lines = [
        "Miroslav Mikulic",
        "Im Weberlis Rebberg 42",
        "8500 Gerlikon",
        "079 602 83 31",
        "Miroslav.Mikulic@gmail.com",
    ]
    for line in sender_lines:
        story.append(Paragraph(line, style_sender))
    story.append(Spacer(1, 10*mm))

    # ═══ 2. RECIPIENT BLOCK ═══
    recipient_lines = []
    if company:
        recipient_lines.append(company)
    if contact_person:
        recipient_lines.append(f"z.Hd. {contact_person}")
    if company_address:
        for addr_line in company_address.split('\n'):
            recipient_lines.append(addr_line.strip())
    if not recipient_lines:
        recipient_lines.append("An die Personalabteilung")
    for line in recipient_lines:
        story.append(Paragraph(line, style_recipient))
    story.append(Spacer(1, 10*mm))

    # ═══ 3. DATE (right-aligned) ═══
    date_str = f"Gerlikon, {datetime.now().strftime('%d.%m.%Y')}"
    story.append(Paragraph(date_str, style_date))
    story.append(Spacer(1, 10*mm))

    # ═══ 4. BETREFF ═══
    betreff = f"Bewerbung als {job_title}" if job_title else "Bewerbung"
    story.append(Paragraph(betreff, style_betreff))
    story.append(Spacer(1, 8*mm))

    # ═══ 5. LETTER BODY (from AI) ═══
    # Clean up AI output: remove any header/address/date/betreff the AI might have added
    body_text = letter_text.strip()

    # Remove lines that look like sender/recipient/date/betreff before the greeting
    clean_lines = body_text.split('\n')
    body_start = 0
    for idx, line in enumerate(clean_lines):
        stripped = line.strip()
        if stripped.lower().startswith('sehr geehrte') or stripped.lower().startswith('dear'):
            body_start = idx
            break
        # Skip lines that are clearly header content
        if any(kw in stripped.lower() for kw in [
            'miroslav', 'weberlis', 'gerlikon', '8500', '079 602',
            'bewerbung als', 'betreff', '@gmail', 'z.hd', 'z. hd'
        ]):
            continue
        if stripped and not any(kw in stripped.lower() for kw in ['sehr geehrte']):
            # Check if this looks like an address line (short, no period at end)
            if len(stripped) < 50 and not stripped.endswith('.'):
                continue
            else:
                body_start = idx
                break

    clean_body = '\n'.join(clean_lines[body_start:])

    # Parse into paragraphs (split by double newline or single empty line)
    paragraphs = []
    current = []
    for line in clean_body.split('\n'):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            current.append(stripped)
    if current:
        paragraphs.append(' '.join(current))

    # Render paragraphs
    for i, para in enumerate(paragraphs):
        if not para:
            continue

        # Greeting line
        if para.lower().startswith('sehr geehrte') or para.lower().startswith('dear'):
            story.append(Paragraph(para, style_greeting))
            story.append(Spacer(1, 2*mm))
        # Closing
        elif para.lower().startswith('freundliche gr') or para.lower().startswith('mit freundlichen'):
            story.append(Spacer(1, 4*mm))
            story.append(Paragraph(para, style_closing))
        # Signature
        elif para.strip() == 'Miroslav Mikulic':
            story.append(Spacer(1, 10*mm))
            story.append(Paragraph(para, style_closing))
        # Regular body paragraph
        else:
            story.append(Paragraph(para, style_body))

    doc.build(story)
    return buffer.getvalue()


def calculate_quick_score(job_title: str, job_company: str, job_location: str, cv_text: str) -> int:
    """Fast local keyword-based match score (0-100) without API calls.

    Scoring dimensions (max 100):
      - Role fit        (0-35): Does the job role match CV experience?
      - ERP/Tech fit    (0-25): Do specific systems/technologies match?
      - Seniority fit   (0-15): Is the level appropriate?
      - Domain fit      (0-15): Does the business domain match?
      - Location fit    (0-10): Is it in Deutschschweiz?
    """
    import re

    if not cv_text or not job_title:
        return 0

    cv_lower = cv_text.lower()
    title_lower = job_title.lower()
    score = 0

    # ═══ 1. ROLE FIT (max 35) ═══
    role_score = 0
    # Primary roles - only count the BEST match, not all
    primary_roles = [
        (["projektleiter", "project manager", "it-projektleiter", "projektmanager"], 35),
        (["business analyst", "anforderungsanalyst"], 30),
        (["consultant", "berater", "it consultant", "it-berater"], 25),
        (["entwickler", "developer", "engineer", "architekt"], 15),
        (["support", "helpdesk", "service desk"], 8),
        (["sachbearbeiter", "administration", "assistenz"], 5),
        (["verkauf", "sales", "account manager"], 5),
    ]
    for role_variants, points in primary_roles:
        if any(r in title_lower for r in role_variants):
            # Check if this role appears in CV
            if any(r in cv_lower for r in role_variants):
                role_score = max(role_score, points)
            else:
                role_score = max(role_score, int(points * 0.2))
            break  # Only match first (best) role category

    score += min(role_score, 35)

    # ═══ 2. ERP / TECHNOLOGY FIT (max 25) ═══
    tech_score = 0
    tech_matches = {
        # ERP systems (high value if specific match)
        "abacus": 15, "sap": 12, "microsoft dynamics": 12,
        "dynamics 365": 12, "business central": 12, "navision": 10,
        "oracle": 8, "salesforce": 8, "netsuite": 8, "proalpha": 8,
        # General tech
        "erp": 6, "crm": 5, "bi": 4, "sql": 3, "python": 3,
    }
    matched_tech = 0
    unmatched_tech = 0
    for tech, weight in tech_matches.items():
        if tech in title_lower:
            if tech in cv_lower:
                tech_score += weight
                matched_tech += 1
            else:
                unmatched_tech += 1
    # Penalty if job requires tech NOT in CV
    if unmatched_tech > 0 and matched_tech == 0:
        tech_score = max(0, tech_score - 5)
    score += min(tech_score, 25)

    # ═══ 3. SENIORITY FIT (max 15) ═══
    seniority_score = 10  # neutral default
    # Negative signals — junior roles
    if any(w in title_lower for w in ["junior", "trainee", "praktikant", "lehrling", "werkstudent", "stagiaire"]):
        seniority_score = 2
    # Positive — senior/lead aligns with Projektleiter experience
    elif any(w in title_lower for w in ["senior", "lead", "leiter", "head of", "director"]):
        if any(w in cv_lower for w in ["leiter", "projektleiter", "lead", "senior", "führung"]):
            seniority_score = 15
        else:
            seniority_score = 6
    score += seniority_score

    # ═══ 4. DOMAIN FIT (max 15) ═══
    domain_score = 0
    domains = {
        "finanzen": 4, "finance": 4, "rechnungswesen": 4, "controlling": 4,
        "logistik": 4, "supply chain": 4, "einkauf": 3, "produktion": 3,
        "personal": 3, "hr": 2, "fertigung": 3, "lager": 2,
        "digitalisierung": 5, "transformation": 4, "migration": 4,
        "implementierung": 4, "rollout": 4, "einführung": 4,
    }
    for domain, weight in domains.items():
        if domain in title_lower and domain in cv_lower:
            domain_score += weight
    score += min(domain_score, 15)

    # ═══ 5. LOCATION FIT (max 10) ═══
    deutschschweiz = [
        "zürich", "bern", "basel", "luzern", "winterthur", "st. gallen",
        "st.gallen", "aarau", "zug", "schaffhausen", "frauenfeld", "baden",
        "olten", "solothurn", "thun", "biel", "rapperswil", "wil", "chur",
        "gerlikon", "weinfelden", "kreuzlingen",
    ]
    romandie = ["genève", "lausanne", "fribourg", "neuchâtel", "sion", "nyon", "morges"]
    if job_location:
        loc_lower = job_location.lower()
        if any(c in loc_lower for c in deutschschweiz):
            score += 10
        elif any(c in loc_lower for c in romandie):
            score += 3  # French-speaking = less ideal
        elif "schweiz" in loc_lower or "remote" in loc_lower:
            score += 7

    # ═══ 6. LANGUAGE PENALTY ═══
    # French/Italian job titles are less relevant
    french_signals = ["responsable", "ingénieur", "chargé", "gestionnaire", "conseiller"]
    if any(f in title_lower for f in french_signals):
        score = int(score * 0.5)

    return max(0, min(100, int(score)))


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
