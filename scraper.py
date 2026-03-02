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


def get_job_details(url: str) -> dict:
    """Fetch full job details from a job listing URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract main content
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
        company_el = soup.find(["span", "div", "a"], class_=re.compile(r"company|employer|firma", re.I))
        if company_el:
            company = company_el.get_text(strip=True)

        # Extract contact info
        contact = ""
        contact_match = re.search(r"(?:Kontakt|Bewerbungen an|Ansprechperson)[:\s]*([^\n]+)", description, re.I)
        if contact_match:
            contact = contact_match.group(1).strip()

        # Extract email
        email = ""
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", description)
        if email_match:
            email = email_match.group(0)

        return {
            "description": description[:3000],
            "company": company,
            "contact": contact,
            "email": email,
        }
    except Exception as e:
        print(f"Error fetching job details from {url}: {e}")
        return {}


def search_multiple_platforms(keywords: list, days_back: int = 30) -> list:
    """Search across multiple job platforms."""
    all_results = []

    # Search jobs.ch
    results = search_jobs_ch(keywords, days_back=days_back)
    all_results.extend(results)

    return all_results
