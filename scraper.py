import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def parse_relative_date(date_str: str) -> str:
    """Convert relative date strings to approximate ISO dates."""
    today = datetime.now()
    date_str = date_str.lower().strip()

    if not date_str:
        return today.strftime("%Y-%m-%d")

    # "Heute", "Gestern", immediate time references
    if "heute" in date_str or "today" in date_str or "minuten" in date_str or "stunden" in date_str or "hour" in date_str:
        return today.strftime("%Y-%m-%d")
    if "gestern" in date_str or "yesterday" in date_str:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    if "vorgestern" in date_str:
        return (today - timedelta(days=2)).strftime("%Y-%m-%d")

    # "Vor X Tagen/Wochen/Monaten"
    num_match = re.search(r"vor\s+(\d+)\s+(tag|tage|tagen|woche|wochen|monat|monaten)", date_str)
    if num_match:
        amount = int(num_match.group(1))
        unit = num_match.group(2)
        if "tag" in unit:
            return (today - timedelta(days=amount)).strftime("%Y-%m-%d")
        elif "woche" in unit:
            return (today - timedelta(weeks=amount)).strftime("%Y-%m-%d")
        elif "monat" in unit:
            return (today - timedelta(days=amount * 30)).strftime("%Y-%m-%d")

    # Named relative dates
    if "letzte woche" in date_str or "last week" in date_str:
        return (today - timedelta(days=7)).strftime("%Y-%m-%d")
    if "letzten monat" in date_str or "last month" in date_str:
        return (today - timedelta(days=30)).strftime("%Y-%m-%d")

    # Try to parse "21 Februar 2026" style dates
    months = {
        "januar": 1, "februar": 2, "märz": 3, "april": 4,
        "mai": 5, "juni": 6, "juli": 7, "august": 8,
        "september": 9, "oktober": 10, "november": 11, "dezember": 12,
    }
    for month_name, month_num in months.items():
        if month_name in date_str:
            day_match = re.search(r"(\d{1,2})\s+" + month_name, date_str)
            year_match = re.search(month_name + r"\s+(\d{4})", date_str)
            if day_match and year_match:
                try:
                    return datetime(
                        int(year_match.group(1)),
                        month_num,
                        int(day_match.group(1))
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    pass

    return today.strftime("%Y-%m-%d")


def _extract_field(link_el, label: str) -> str:
    """Extract a labeled field (Arbeitsort, Pensum, etc.) from a job card link element."""
    # jobs.ch uses a grid layout: <div>Label</div><div>Value</div>
    # Look for div pairs inside the link
    text = link_el.get_text(" ", strip=True)
    pattern = re.compile(re.escape(label) + r"\s*:\s*(.+?)(?:Pensum|Vertragsart|Arbeitsort|$)", re.IGNORECASE)
    m = pattern.search(text)
    if m:
        return m.group(1).strip().rstrip(":")
    return ""


def search_jobs_ch(keywords: list, regions: list = None, days_back: int = 30) -> list:
    """Search jobs.ch for job listings.

    Uses the current jobs.ch HTML structure (2025/2026):
    - Job cards are <a> tags linking to /de/stellenangebote/detail/<uuid>/
    - Title is in a <span> with fw_bold class
    - Date is in a <p> with textStyle_caption1 class
    - Arbeitsort, Pensum, Company are in nested divs
    """
    results = []
    base_url = "https://www.jobs.ch/de/stellenangebote/"

    # Build search terms: use the full keyword phrase
    search_terms = [" ".join(keywords)]
    # Also search individual multi-word terms if they differ
    for kw in keywords[:3]:
        if kw not in search_terms:
            search_terms.append(kw)

    seen_urls = set()

    for term in search_terms:
        try:
            params = {"term": term}
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Find all job detail links
            detail_links = soup.find_all("a", href=re.compile(r"/de/stellenangebote/detail/"))

            for link in detail_links:
                href = link.get("href", "")
                if not href or href in seen_urls:
                    continue

                full_url = f"https://www.jobs.ch{href}" if href.startswith("/") else href
                seen_urls.add(href)

                # ── Title ──
                # Title is in a <span> with bold styling inside a wrapper div
                title_span = link.find("span", class_=re.compile(r"fw_bold"))
                title = title_span.get_text(strip=True) if title_span else ""

                if not title or len(title) < 3:
                    continue

                # ── Date ──
                date_el = link.find("p", class_=re.compile(r"textStyle_caption"))
                date_raw = date_el.get_text(strip=True) if date_el else ""
                posted_date = parse_relative_date(date_raw)

                # Filter by date
                cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                if posted_date < cutoff:
                    continue

                # ── Location ──
                location = _extract_field(link, "Arbeitsort")

                # ── Pensum ──
                pensum = _extract_field(link, "Pensum")

                # ── Company ──
                # Company name is usually the last text block before action buttons
                company = ""
                # Look for company in the card — often in a div after the metadata
                all_divs = link.find_all("div")
                card_text = link.get_text(" ", strip=True)

                # Company often appears after "Festanstellung" or "Temporär" and before "Einfach bewerben" / "Ist der Job"
                company_match = re.search(
                    r"(?:Festanstellung|Temporär|Praktikum|Freelance|Lehrstelle)\s+(.+?)(?:\s+(?:Promoted|Einfach bewerben|Ist der Job|$))",
                    card_text
                )
                if company_match:
                    company = company_match.group(1).strip()

                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "pensum": pensum,
                    "posted_date": posted_date,
                    "posted_date_raw": date_raw,
                    "url": full_url,
                    "source": "jobs.ch",
                    "status": "Neu",
                })

            time.sleep(0.8)  # Be polite

        except Exception as e:
            print(f"Error searching jobs.ch for '{term}': {e}")
            continue

    # Deduplicate by URL
    seen = set()
    unique = []
    for job in results:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)

    return unique


def _extract_jobs_ch_details(soup, html_text: str) -> dict:
    """Extract job details from jobs.ch using JSON-LD and embedded JS data.

    jobs.ch renders content via JavaScript, so normal HTML scraping gets almost nothing.
    Instead we extract from:
    1. JSON-LD (schema.org JobPosting) — description, company, address
    2. Embedded JSON in HTML — contacts (firstName/lastName)
    """
    import json as _json

    result = {"description": "", "company": "", "contact": "", "email": "", "address": ""}

    # ── 1. JSON-LD: description, company, address ──
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") != "JobPosting":
                    continue

                # Description (HTML → plain text)
                raw_desc = item.get("description", "")
                if raw_desc:
                    desc_soup = BeautifulSoup(raw_desc, "html.parser")
                    result["description"] = desc_soup.get_text("\n", strip=True)

                # Company
                org = item.get("hiringOrganization", {})
                if isinstance(org, dict):
                    result["company"] = org.get("name", "")

                # Address from jobLocation
                loc = item.get("jobLocation", {})
                if isinstance(loc, dict):
                    addr = loc.get("address", {})
                    if isinstance(addr, dict):
                        street = addr.get("streetAddress", "")
                        plz = addr.get("postalCode", "")
                        city = addr.get("addressLocality", "")
                        if street and plz and city:
                            result["address"] = f"{street}\n{plz} {city}"
        except Exception:
            continue

    # ── 2. Embedded JSON: contacts ──
    contacts_match = re.search(r'"contacts"\s*:\s*\[([^\]]+)\]', html_text)
    if contacts_match:
        try:
            contacts = _json.loads(f"[{contacts_match.group(1)}]")
            if contacts and isinstance(contacts[0], dict):
                first = contacts[0].get("firstName", "")
                last = contacts[0].get("lastName", "")
                if first and last:
                    result["contact"] = f"{first} {last}"
                    print(f"[Scraper] jobs.ch Kontaktperson: {result['contact']}")
        except Exception:
            pass

    # ── 3. Email from description text ──
    if result["description"]:
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", result["description"])
        if email_match:
            result["email"] = email_match.group(0)

    return result


def get_job_details(url: str) -> dict:
    """Fetch full job details from a job listing URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        html_text = resp.text

        # ── jobs.ch: use specialized extractor ──
        if "jobs.ch" in url:
            result = _extract_jobs_ch_details(soup, html_text)
            if result["description"]:
                print(f"[Scraper] jobs.ch: desc={len(result['description'])} chars, "
                      f"company='{result['company']}', contact='{result['contact']}', "
                      f"address='{result['address']}'")
                return result
            # Fall through to generic if JSON-LD failed

        # ── Generic scraper for other sites ──
        content_div = (
            soup.find("div", class_=re.compile(r"job.*detail|detail.*job|content|description", re.I))
            or soup.find("main")
            or soup.find("article")
        )

        description = ""
        if content_div:
            for el in content_div.find_all(["nav", "header", "footer", "script", "style"]):
                el.decompose()
            description = content_div.get_text("\n", strip=True)

        # Extract company
        company = ""
        company_el = soup.find(["span", "a"], class_=re.compile(r"company|employer|firma", re.I))
        if company_el:
            company_text = company_el.get_text(strip=True)
            if len(company_text) < 100:
                company = company_text
        if not company:
            og_company = soup.find("meta", {"property": "og:site_name"})
            if og_company:
                company = og_company.get("content", "")[:100]

        # Extract contact info — search multiple patterns
        contact = ""
        contact_patterns = [
            r"(?:Kontakt|Kontaktperson|Ansprechperson|Ansprechpartner(?:in)?|Bewerbungen an|Deine Ansprechperson|Ihre Ansprechperson|Fragen beantwortet)[:\s]*([^\n]+)",
            r"(?:Frau|Herr)\s+[A-ZÄÖÜ][a-zäöüé]+\s+[A-ZÄÖÜ][a-zäöüé]+",
        ]
        for pattern in contact_patterns:
            contact_match = re.search(pattern, description, re.I)
            if contact_match:
                contact = contact_match.group(1).strip() if contact_match.lastindex else contact_match.group(0).strip()
                contact = re.sub(r"[,\.]$", "", contact).strip()
                break

        # Also check embedded JSON contacts (works for multiple platforms)
        if not contact:
            contacts_match = re.search(r'"contacts"\s*:\s*\[([^\]]+)\]', html_text)
            if contacts_match:
                try:
                    import json as _json
                    contacts = _json.loads(f"[{contacts_match.group(1)}]")
                    if contacts and isinstance(contacts[0], dict):
                        first = contacts[0].get("firstName", "")
                        last = contacts[0].get("lastName", "")
                        if first and last:
                            contact = f"{first} {last}"
                except Exception:
                    pass

        # Extract email
        email = ""
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", description)
        if email_match:
            email = email_match.group(0)

        # Extract address (Swiss PLZ pattern)
        address = ""
        addr_match = re.search(
            r"([A-ZÄÖÜ][a-zäöüé]+(?:strasse|str\.|weg|gasse|platz|allee|rain|matte)\s+\d+[a-z]?)\s*[,\n]\s*(\d{4}\s+[A-ZÄÖÜ][a-zäöüé]+(?:\s+[A-ZÄÖÜ][a-zäöüé]+)?)",
            description
        )
        if addr_match:
            address = f"{addr_match.group(1)}\n{addr_match.group(2)}"

        # Also check JSON-LD for address (works on many platforms)
        if not address:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json as _json
                    data = _json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") != "JobPosting":
                            continue
                        loc = item.get("jobLocation", {})
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            if isinstance(addr, dict):
                                street = addr.get("streetAddress", "")
                                plz = addr.get("postalCode", "")
                                city = addr.get("addressLocality", "")
                                if street and plz and city:
                                    address = f"{street}\n{plz} {city}"
                except Exception:
                    continue

        return {
            "description": description[:5000],
            "company": company,
            "contact": contact,
            "email": email,
            "address": address,
        }
    except Exception as e:
        print(f"Error fetching job details from {url}: {e}")
        return {}


def search_indeed_ch(keywords: list, days_back: int = 30) -> list:
    """Search Indeed Switzerland for job listings.

    Note: Indeed actively blocks automated scraping (HTTP 401/403).
    This function fails gracefully and returns an empty list if blocked.
    """
    results = []
    base_url = "https://ch.indeed.com/jobs"
    seen_urls = set()

    query = " ".join(keywords)
    # Indeed's fromage parameter: number of days back
    params = {
        "q": query,
        "l": "Schweiz",
        "fromage": str(min(days_back, 30)),
        "lang": "de",
    }

    try:
        resp = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code in (401, 403):
            # Indeed blocks scraping — fail silently to avoid log spam
            return []
        if resp.status_code != 200:
            print(f"[Indeed] HTTP {resp.status_code} for '{query}'")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Indeed job cards: <a> or <div> with data-jk attribute, or job_seen_beacon class
        job_cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|cardOutline|result"))
        if not job_cards:
            # Fallback: find all links to job views
            job_cards = soup.find_all("a", href=re.compile(r"/rc/clk|/viewjob|/pagead"))

        for card in job_cards:
            try:
                # Title
                title_el = card.find(["h2", "span"], class_=re.compile(r"jobTitle|title"))
                if not title_el:
                    title_el = card.find("a", class_=re.compile(r"jcs-JobTitle"))
                title = title_el.get_text(strip=True) if title_el else ""
                if not title or len(title) < 3:
                    continue

                # URL
                link_el = card.find("a", href=True)
                if link_el:
                    href = link_el.get("href", "")
                    if href.startswith("/"):
                        href = f"https://ch.indeed.com{href}"
                else:
                    continue

                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Company
                company_el = card.find("span", class_=re.compile(r"company|companyName"))
                if not company_el:
                    company_el = card.find("span", {"data-testid": re.compile(r"company")})
                company = company_el.get_text(strip=True) if company_el else ""

                # Location
                loc_el = card.find("div", class_=re.compile(r"companyLocation|location"))
                location = loc_el.get_text(strip=True) if loc_el else ""

                # Date
                date_el = card.find("span", class_=re.compile(r"date|posted"))
                date_raw = date_el.get_text(strip=True) if date_el else ""
                posted_date = parse_relative_date(date_raw)

                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "pensum": "",
                    "posted_date": posted_date,
                    "posted_date_raw": date_raw or "Kürzlich",
                    "url": href,
                    "source": "indeed.ch",
                    "status": "Neu",
                })

            except Exception as e:
                continue

        time.sleep(1.0)

    except Exception as e:
        print(f"[Indeed] Error searching for '{query}': {e}")

    return results


def search_linkedin_jobs(keywords: list, days_back: int = 30) -> list:
    """Search LinkedIn public job listings (no login required)."""
    results = []
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    seen_urls = set()

    query = " ".join(keywords)
    # LinkedIn time filters: r86400=24h, r604800=week, r2592000=month
    if days_back <= 1:
        time_filter = "r86400"
    elif days_back <= 7:
        time_filter = "r604800"
    else:
        time_filter = "r2592000"

    params = {
        "keywords": query,
        "location": "Schweiz",
        "geoId": "106693272",  # Switzerland
        "f_TPR": time_filter,
        "start": "0",
    }

    try:
        resp = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            # Fallback: try the regular public search page
            fallback_url = "https://www.linkedin.com/jobs/search/"
            resp = requests.get(fallback_url, params={
                "keywords": query,
                "location": "Schweiz",
                "f_TPR": time_filter,
            }, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"[LinkedIn] HTTP {resp.status_code} for '{query}'")
                return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # LinkedIn public job cards
        job_cards = soup.find_all("li")
        if not job_cards:
            job_cards = soup.find_all("div", class_=re.compile(r"base-card|job-search-card"))

        for card in job_cards:
            try:
                # Title
                title_el = card.find(["h3", "span"], class_=re.compile(r"base-search-card__title|job-title"))
                title = title_el.get_text(strip=True) if title_el else ""
                if not title or len(title) < 3:
                    continue

                # URL
                link_el = card.find("a", href=re.compile(r"linkedin\.com/jobs/view"))
                if not link_el:
                    link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
                if link_el:
                    href = link_el.get("href", "").split("?")[0]  # Remove tracking params
                else:
                    continue

                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Company
                company_el = card.find(["h4", "a"], class_=re.compile(r"base-search-card__subtitle|company-name"))
                company = company_el.get_text(strip=True) if company_el else ""

                # Location
                loc_el = card.find("span", class_=re.compile(r"job-search-card__location|base-search-card__metadata"))
                location = loc_el.get_text(strip=True) if loc_el else ""

                # Date
                date_el = card.find("time")
                date_raw = ""
                posted_date = datetime.now().strftime("%Y-%m-%d")
                if date_el:
                    date_raw = date_el.get("datetime", "") or date_el.get_text(strip=True)
                    if re.match(r"\d{4}-\d{2}-\d{2}", date_raw):
                        posted_date = date_raw[:10]
                    else:
                        posted_date = parse_relative_date(date_raw)

                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "pensum": "",
                    "posted_date": posted_date,
                    "posted_date_raw": date_raw or "Kürzlich",
                    "url": href,
                    "source": "LinkedIn",
                    "status": "Neu",
                })

            except Exception as e:
                continue

        time.sleep(1.5)

    except Exception as e:
        print(f"[LinkedIn] Error searching for '{query}': {e}")

    return results


def search_jobscout24(keywords: list, days_back: int = 30) -> list:
    """Search JobScout24.ch for job listings."""
    results = []
    seen_urls = set()

    query = " ".join(keywords)

    try:
        url = f"https://www.jobscout24.ch/de/jobs/{requests.utils.quote(query)}/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[JobScout24] HTTP {resp.status_code} for '{query}'")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # JobScout24 job cards
        job_links = soup.find_all("a", href=re.compile(r"/de/stellenangebote/|/de/jobs/detail/"))

        for link in job_links:
            try:
                href = link.get("href", "")
                if not href or href in seen_urls:
                    continue

                full_url = f"https://www.jobscout24.ch{href}" if href.startswith("/") else href
                seen_urls.add(href)

                # Title
                title_el = link.find(["h2", "h3", "span"], class_=re.compile(r"title|job"))
                if not title_el:
                    title = link.get_text(strip=True)
                else:
                    title = title_el.get_text(strip=True)

                if not title or len(title) < 5 or len(title) > 150:
                    continue

                # Company & Location from surrounding context
                card = link.find_parent(["li", "div", "article"])
                company = ""
                location = ""
                if card:
                    comp_el = card.find(["span", "div"], class_=re.compile(r"company|employer"))
                    if comp_el:
                        company = comp_el.get_text(strip=True)
                    loc_el = card.find(["span", "div"], class_=re.compile(r"location|ort|region"))
                    if loc_el:
                        location = loc_el.get_text(strip=True)

                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "pensum": "",
                    "posted_date": datetime.now().strftime("%Y-%m-%d"),
                    "posted_date_raw": "Kürzlich",
                    "url": full_url,
                    "source": "JobScout24",
                    "status": "Neu",
                })

            except Exception:
                continue

        time.sleep(1.0)

    except Exception as e:
        print(f"[JobScout24] Error searching for '{query}': {e}")

    return results


# ── ERP companies in German-speaking Switzerland ──
# These firms implement Abacus, SAP, Dynamics — check their career pages directly
ERP_COMPANIES_CH = [
    {"name": "Abacus Research AG", "url": "https://www.abacus.ch/de/unternehmen/jobs", "focus": "Abacus"},
    {"name": "All for One Switzerland", "url": "https://www.all-for-one.com/de-ch/karriere/stellenangebote", "focus": "SAP"},
    {"name": "BaseNet Informatik AG", "url": "https://www.basenet.ch/jobs", "focus": "Abacus, ERP"},
    {"name": "Dynasoft AG", "url": "https://www.dynasoft.ch/jobs", "focus": "ERP, Dynamics"},
    {"name": "Anica AG", "url": "https://anica.ch/karriere", "focus": "Abacus"},
    # {"name": "Nybble Group", "url": "https://nybble.ch/karriere", "focus": "ERP"},  # Domain offline (2026-03)
    {"name": "Elvadata AG", "url": "https://www.elvadata.ch/karriere", "focus": "ERP, SAP"},
    # {"name": "Fusion Consulting", "url": "https://fusion-consulting.ch/careers", "focus": "SAP"},  # Domain offline (2026-03)
    # {"name": "GAMBIT Consulting", "url": "https://gambitswitzerland.ch/karriere", "focus": "SAP"},  # Domain nicht auflösbar (2026-03)
    {"name": "Innflow AG", "url": "https://www.innflow.com/de/karriere", "focus": "SAP"},
    {"name": "CONSILIO GmbH", "url": "https://www.consilio-gmbh.de/karriere", "focus": "SAP"},
    {"name": "Ekspert AG", "url": "https://ekspert.com/karriere", "focus": "Abacus"},
    # {"name": "Mattig-Suter und Partner", "url": "https://mattig.swiss/karriere", "focus": "Abacus"},  # SSL-Fehler (2026-03)
    {"name": "PwC Switzerland", "url": "https://www.pwc.ch/en/careers", "focus": "SAP, Abacus"},
    {"name": "KCS.net", "url": "https://www.kcsnet.com/karriere", "focus": "Dynamics"},
    {"name": "Synoptek Switzerland", "url": "https://synoptek.com/careers", "focus": "Dynamics 365"},
    {"name": "Fidigit AG", "url": "https://fidigit.ch/karriere", "focus": "Abacus"},
    # {"name": "Data World Consulting AG", "url": "https://dataworldconsulting.ch/karriere", "focus": "SAP"},  # Domain nicht auflösbar (2026-03)
    {"name": "Opacc Software AG", "url": "https://www.opacc.ch/de/jobs", "focus": "ERP"},
    {"name": "redIT Services AG", "url": "https://www.redit.ch/jobs", "focus": "ERP, Dynamics"},
]


def search_erp_company_careers(keywords: list) -> list:
    """Check career pages of known ERP companies in Deutschschweiz."""
    results = []
    seen_urls = set()
    kw_lower = [k.lower() for k in keywords if len(k) > 2]

    for company_info in ERP_COMPANIES_CH:
        try:
            resp = requests.get(company_info["url"], headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            text_content = soup.get_text(" ", strip=True).lower()

            # Check if page mentions any of our keywords
            has_relevant_job = any(kw in text_content for kw in kw_lower)
            if not has_relevant_job:
                continue

            # Find job links on the page
            job_links = soup.find_all("a", href=True)
            for link in job_links:
                href = link.get("href", "")
                link_text = link.get_text(strip=True)

                # Filter for job-related links
                if not link_text or len(link_text) < 5 or len(link_text) > 150:
                    continue

                # Check if link text contains relevant keywords
                link_lower = link_text.lower()
                if not any(kw in link_lower for kw in kw_lower + ["projekt", "consult", "berater", "analyst", "erp"]):
                    continue

                # Build full URL
                if href.startswith("/"):
                    base = re.match(r"(https?://[^/]+)", company_info["url"])
                    full_url = f"{base.group(1)}{href}" if base else href
                elif href.startswith("http"):
                    full_url = href
                else:
                    continue

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                results.append({
                    "title": link_text,
                    "company": company_info["name"],
                    "location": "Deutschschweiz",
                    "pensum": "",
                    "posted_date": datetime.now().strftime("%Y-%m-%d"),
                    "posted_date_raw": "Aktuell",
                    "url": full_url,
                    "source": f"Karriereseite ({company_info['focus']})",
                    "status": "Neu",
                })

            time.sleep(0.5)

        except Exception as e:
            print(f"[ERP] Error checking {company_info['name']}: {e}")
            continue

    return results


def search_multiple_platforms(keywords: list, days_back: int = 30) -> list:
    """Search across multiple job platforms and ERP company career pages."""
    all_results = []

    # 1. jobs.ch (primary)
    try:
        results = search_jobs_ch(keywords, days_back=days_back)
        all_results.extend(results)
    except Exception as e:
        print(f"[Multi] jobs.ch error: {e}")

    # 2. Indeed.ch
    try:
        results = search_indeed_ch(keywords, days_back=days_back)
        all_results.extend(results)
    except Exception as e:
        print(f"[Multi] Indeed error: {e}")

    # 3. LinkedIn (public)
    try:
        results = search_linkedin_jobs(keywords, days_back=days_back)
        all_results.extend(results)
    except Exception as e:
        print(f"[Multi] LinkedIn error: {e}")

    # 4. JobScout24
    try:
        results = search_jobscout24(keywords, days_back=days_back)
        all_results.extend(results)
    except Exception as e:
        print(f"[Multi] JobScout24 error: {e}")

    # 5. ERP company career pages (keyword-based, no date filter)
    try:
        results = search_erp_company_careers(keywords)
        all_results.extend(results)
    except Exception as e:
        print(f"[Multi] ERP careers error: {e}")

    return all_results
