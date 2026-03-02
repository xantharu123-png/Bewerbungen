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
    """Extract text from DOCX bytes, preserving bullet points and structure."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(docx_bytes))
        lines = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                lines.append("")
                continue
            # Detect bullet/list paragraphs by style or numbering
            is_bullet = False
            style_name = (para.style.name or "").lower()
            if "list" in style_name or "bullet" in style_name or "aufz" in style_name:
                is_bullet = True
            # Also check if paragraph has numbering format (Word list items)
            if hasattr(para, '_element'):
                numPr = para._element.find(
                    './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr'
                )
                if numPr is not None:
                    is_bullet = True
            # Check for manual bullets
            if text.startswith(('- ', '• ', '– ', '* ')):
                is_bullet = True

            if is_bullet and not text.startswith('- '):
                lines.append(f"- {text}")
            else:
                lines.append(text)
        return "\n".join(lines)
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
    """Generate a tailored cover letter using Claude API.

    Returns ONLY the body text: greeting → paragraphs with bullet list → closing → signature.
    """

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
- Falls die Vorlage eine Aufzählung mit "- " hat, behalte diese Aufzählung bei

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
- Ende mit: "Freundliche Grüsse" und dann "Miroslav Mikulic" auf einer neuen Zeile
- KEIN Briefkopf, KEINE Adresse, KEIN Datum, KEIN Betreff — nur der Brieftext
- Aufzählungspunkte mit "- " am Zeilenanfang kennzeichnen
- Gib NUR den fertigen Brieftext zurück, keine Kommentare"""

    else:
        # FREE MODE: Generate from scratch — Swiss style with bullet list
        prompt = f"""Schreibe ein professionelles Schweizer Bewerbungsschreiben {lang_instruction}.

**Stellenanzeige:**
Stelle: {job_title}
Unternehmen: {company}
Beschreibung: {job_description[:2000]}

**Lebenslauf des Bewerbers:**
{cv_text[:2000]}

**WICHTIG — Gib NUR den Brieftext zurück, EXAKT in diesem Format:**

{greeting}

[Einleitung: 2-3 Sätze, warum diese Stelle mich anspricht und wie ich darauf aufmerksam wurde]

[Überleitung: 1-2 Sätze, dann "Was kann ich Ihrem Unternehmen bieten:" gefolgt von einer Aufzählung]

- [Stärke 1 mit konkretem Bezug zur Stelle]
- [Stärke 2 mit konkretem Bezug zum Lebenslauf]
- [Stärke 3 mit relevanter Erfahrung]
- [Stärke 4 falls passend]

[Schluss: 2-3 Sätze mit Motivation und Gesprächswunsch]

Freundliche Grüsse

Miroslav Mikulic

**REGELN:**
- Schreibe NUR die Absätze zwischen Anrede und Gruss — KEIN Briefkopf, KEINE Adresse, KEIN Datum, KEIN Betreff
- Beginne direkt mit "{greeting}"
- Ende mit "Freundliche Grüsse" und dann "Miroslav Mikulic"
- Die Aufzählung mit "- " am Zeilenanfang, 3-5 Punkte
- Professioneller, selbstbewusster Ton — schweizerisch
- Keine Floskeln, keine Superlative
- Aufzählungspunkte sollen konkret und auf die Stelle bezogen sein"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def _sanitize_company(company: str) -> str:
    """Clean company name: remove scraped garbage, keep only the actual company name."""
    if not company:
        return ""
    # If company contains line breaks, take only the first line
    company = company.split('\n')[0].strip()

    # Always try to split on common scraper artifacts
    scraper_artifacts = ['Speichern', 'Bewerben', 'Gestern', 'Heute', 'Einfach bewerben']
    for artifact in scraper_artifacts:
        if artifact in company:
            company = company.split(artifact)[0].strip()

    # Split on ® — company name is before it, rest is usually location/garbage
    if '®' in company:
        parts = company.split('®')
        if len(parts[0]) > 2:
            after = '®'.join(parts[1:]).strip()
            # If after ® there's short text like " AG" keep it, otherwise drop
            if after and (after.startswith(' AG') or after.startswith(' GmbH') or after.startswith(' SA') or len(after) < 5):
                company = parts[0].strip() + '®' + after
            else:
                company = parts[0].strip()

    # If still too long, it's scraped garbage
    if len(company) > 60:
        # Try common separators
        for sep in [' - ', '|', '·', '  ']:
            if sep in company:
                company = company.split(sep)[0].strip()
                break
        if len(company) > 60:
            company = company[:50].strip()

    # Remove trailing punctuation artifacts
    company = company.rstrip('|·-– ')
    return company


def generate_cover_letter_pdf(
    letter_text: str,
    job_title: str = "",
    company: str = "",
    contact_person: str = "",
    company_address: str = "",
) -> bytes:
    """Generate a Swiss business letter PDF matching the user's DOCX template exactly.

    Template layout (Bewerbungsschreiben_Mikulic.docx):
    - Sender: Name, Street, City (3 lines, left, 11pt)
    - Phone [TAB 9.8cm] Company name (same line)
    - [TAB 9.8cm] Company address lines
    - Empty line
    - [TAB 9.8cm] "Gerlikon, DD.MM.YYYY"
    - 2 empty lines
    - Betreff bold 11pt
    - Empty line
    - Sehr geehrte Damen und Herren
    - Body text (11pt, single spacing, space_after=6pt)
    - Bullet points (• with indent)
    - Closing + signature
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.colors import HexColor

    buffer = io.BytesIO()
    page_w, page_h = A4  # 21.0 x 29.7 cm

    # Margins from DOCX: top=2.5, bottom=2.0, left=2.5, right=2.5
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2.5*cm,
        bottomMargin=2.0*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    content_width = page_w - 5*cm   # 16.0 cm
    TAB_POS = 9.8*cm                # Tab stop from DOCX template
    col_left = TAB_POS              # left column width
    col_right = content_width - TAB_POS  # right column width

    # All text is 11pt, single spacing (leading ~14pt), color black
    COLOR = HexColor('#222222')
    FONT = 'Helvetica'
    SIZE = 11
    LEADING = 14
    SP_AFTER = 6  # space_after from template: 6pt

    s_normal = ParagraphStyle(
        'Normal', fontName=FONT, fontSize=SIZE, leading=LEADING,
        alignment=TA_LEFT, textColor=COLOR, spaceAfter=0,
    )
    s_bold = ParagraphStyle(
        'Bold', fontName='Helvetica-Bold', fontSize=SIZE, leading=LEADING,
        alignment=TA_LEFT, textColor=COLOR, spaceAfter=0,
    )
    s_body = ParagraphStyle(
        'Body', fontName=FONT, fontSize=SIZE, leading=LEADING,
        alignment=TA_LEFT, textColor=COLOR, spaceAfter=SP_AFTER,
    )
    s_bullet = ParagraphStyle(
        'Bullet', fontName=FONT, fontSize=SIZE, leading=LEADING,
        alignment=TA_LEFT, textColor=COLOR, spaceAfter=4,
        leftIndent=14, firstLineIndent=-14,
    )

    no_pad = [
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]

    story = []

    # Clean company name
    clean_company = _sanitize_company(company)

    # ═══ 1. SENDER BLOCK: Name, Street, City (3 lines, left-aligned) ═══
    story.append(Paragraph("Miroslav Mikulic", s_normal))
    story.append(Paragraph("Im Weberlis Rebberg 42", s_normal))
    story.append(Paragraph("8500 Gerlikon", s_normal))

    # ═══ 2. PHONE [TAB] COMPANY — same line, using table ═══
    # Line: "079 602 83 31" [tab] "Company Name"
    phone_para = Paragraph("079 602 83 31", s_normal)
    company_para = Paragraph(clean_company if clean_company else "", s_normal)
    row1 = Table([[phone_para, company_para]], colWidths=[col_left, col_right])
    row1.setStyle(TableStyle(no_pad))
    story.append(row1)

    # Recipient address lines (tabbed to right)
    recipient_lines = []
    if contact_person:
        recipient_lines.append(contact_person)
    if company_address:
        for addr_line in company_address.strip().split('\n'):
            if addr_line.strip():
                recipient_lines.append(addr_line.strip())

    for rline in recipient_lines:
        empty = Paragraph("", s_normal)
        rpara = Paragraph(rline, s_normal)
        row = Table([[empty, rpara]], colWidths=[col_left, col_right])
        row.setStyle(TableStyle(no_pad))
        story.append(row)

    # ═══ 3. EMPTY LINE ═══
    story.append(Spacer(1, LEADING))

    # ═══ 4. DATE at tab position ═══
    date_str = f"Gerlikon, {datetime.now().strftime('%d.%m.%Y')}"
    empty = Paragraph("", s_normal)
    date_para = Paragraph(date_str, s_normal)
    date_row = Table([[empty, date_para]], colWidths=[col_left, col_right])
    date_row.setStyle(TableStyle(no_pad))
    story.append(date_row)

    # ═══ 5. TWO EMPTY LINES ═══
    story.append(Spacer(1, LEADING * 2))

    # ═══ 6. BETREFF (bold) ═══
    betreff = job_title if job_title else "Bewerbung"
    story.append(Paragraph(betreff, s_bold))

    # ═══ 7. EMPTY LINE ═══
    story.append(Spacer(1, LEADING))

    # ═══ 8. LETTER BODY (from AI) ═══
    body_text = letter_text.strip()

    # Remove any header/address/date/betreff the AI might have added
    clean_lines = body_text.split('\n')
    body_start = 0
    for idx, line in enumerate(clean_lines):
        stripped = line.strip()
        if stripped.lower().startswith('sehr geehrte') or stripped.lower().startswith('dear'):
            body_start = idx
            break
        if any(kw in stripped.lower() for kw in [
            'miroslav', 'weberlis', 'gerlikon', '8500', '079 602',
            'bewerbung als', 'betreff', '@gmail', 'z.hd', 'z. hd',
            'im weberlis', 'eichmatt',
        ]):
            continue
        if stripped and len(stripped) < 60 and not stripped.endswith('.'):
            continue
        if stripped:
            body_start = idx
            break

    clean_body = '\n'.join(clean_lines[body_start:])

    # Parse into typed paragraphs
    paragraphs = []
    current_lines = []

    def flush_current():
        if current_lines:
            paragraphs.append(('text', ' '.join(current_lines)))
            current_lines.clear()

    for line in clean_body.split('\n'):
        stripped = line.strip()

        if not stripped:
            flush_current()
            continue

        if stripped.startswith('- ') or stripped.startswith('• '):
            flush_current()
            paragraphs.append(('bullet', stripped.lstrip('-•').strip()))
        elif stripped.lower().startswith('sehr geehrte') or stripped.lower().startswith('dear'):
            flush_current()
            paragraphs.append(('greeting', stripped))
        elif stripped.lower().startswith('freundliche gr') or stripped.lower().startswith('mit freundlichen'):
            flush_current()
            paragraphs.append(('closing', stripped))
        elif stripped == 'Miroslav Mikulic':
            flush_current()
            paragraphs.append(('signature', stripped))
        else:
            current_lines.append(stripped)

    flush_current()

    # Render
    for ptype, text in paragraphs:
        if not text:
            continue
        if ptype == 'greeting':
            story.append(Paragraph(text, s_body))
            story.append(Spacer(1, SP_AFTER))
        elif ptype == 'bullet':
            story.append(Paragraph(f"\u2022  {text}", s_bullet))
        elif ptype == 'closing':
            story.append(Spacer(1, SP_AFTER))
            story.append(Paragraph(text, s_body))
        elif ptype == 'signature':
            story.append(Paragraph(text, s_body))
        else:
            story.append(Paragraph(text, s_body))

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
