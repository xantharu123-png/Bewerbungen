import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

def parse_relative_date(date_str: str) -> str:
    """Convert relative date strings to approximate ISO dates."""
    today = datetime.now()
    date_str = date_str.lower().strip()
    
    if "heute" in date_str or "today" in date_str or "minuten" in date_str or "stunden" in date_str or "hour" in date_str:
        return today.strftime("%Y-%m-%d")
    elif "gestern" in date_str or "yesterday" in date_str or "vorgestern" not in date_str and "yesterday" in date_str:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif "vorgestern" in date_str:
        return (today - timedelta(days=2)).strftime("%Y-%m-%d")
    elif "letzte woche" in date_str or "last week" in date_str:
        return (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif "vor 2 wochen" in date_str or "2 weeks" in date_str:
        return (today - timedelta(days=14)).strftime("%Y-%m-%d")
    elif "vor 3 wochen" in date_str or "3 weeks" in date_str:
        return (today - timedelta(days=21)).strftime("%Y-%m-%d")
    elif "vor 4 wochen" in date_str or "letzten monat" in date_str or "last month" in date_str:
        return (today - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Try to parse direct date formats like "21 Februar 2026" or "09 Februar 2026"
    months = {
        "januar": "01", "februar": "02", "märz": "03", "april": "04",
        "mai": "05", "juni": "06", "juli": "07", "august": "08",
        "september": "09", "oktober": "10", "november": "11", "dezember": "12"
    }
    for month_de, month_num in months.items():
        if month_de in date_str:
            parts = date_str.split()
            for part in parts:
                if part.isdigit() and int(part) <= 31:
                    day = part.zfill(2)
                for part2 in parts:
                    if part2.isdigit() and int(part2) > 1000:
                        year = part2
                        try:
                            return f"{year}-{month_num}-{day}"
                        except:
                            pass
    
    return today.strftime("%Y-%m-%d")

def search_jobs_ch(keywords: list, regions: list = None, days_back: int = 14) -> list:
    """Search jobs.ch for job listings."""
    results = []
    base_url = "https://www.jobs.ch/de/stellenangebote/"
    
    search_terms = [
        " ".join(keywords),
    ]
    # Add individual keyword searches for broader results
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
            
            # Find job listings
            job_links = soup.find_all("a", href=re.compile(r"/de/stellenangebote/detail/"))
            
            for link in job_links:
                href = link.get("href", "")
                if not href or href in seen_urls:
                    continue
                
                full_url = f"https://www.jobs.ch{href}" if href.startswith("/") else href
                seen_urls.add(href)
                
                # Get title
                title_el = link.find(["h2", "h3", "h4", "strong", "span"])
                title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                
                # Get parent container for more info
                container = link.parent
                for _ in range(5):
                    if container and container.get_text(strip=True):
                        container = container.parent
                    else:
                        break
                
                container_text = container.get_text(" ", strip=True) if container else ""
                
                # Extract date
                date_text = ""
                date_patterns = [
                    r"\d{1,2}\s+(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}",
                    r"Vor \d+ (?:Minuten|Stunden|Tagen|Wochen)",
                    r"(?:Heute|Gestern|Vorgestern|Letzte Woche|Letzten Monat)",
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, container_text, re.IGNORECASE)
                    if match:
                        date_text = match.group(0)
                        break
                
                posted_date = parse_relative_date(date_text) if date_text else datetime.now().strftime("%Y-%m-%d")
                
                # Filter by date
                cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                if posted_date < cutoff:
                    continue
                
                # Extract location and company
                location = ""
                company = ""
                
                loc_match = re.search(r"Arbeitsort:\s*([^\n]+)", container_text)
                if loc_match:
                    location = loc_match.group(1).strip()
                
                pensum_match = re.search(r"Pensum:\s*([\d\s–%]+)", container_text)
                pensum = pensum_match.group(1).strip() if pensum_match else ""
                
                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "pensum": pensum,
                    "posted_date": posted_date,
                    "posted_date_raw": date_text,
                    "url": full_url,
                    "source": "jobs.ch",
                    "status": "Neu"
                })
            
            time.sleep(1)  # Be polite
            
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
            soup.find("div", class_=re.compile(r"job.*detail|detail.*job|content|description", re.I)) or
            soup.find("main") or
            soup.find("article")
        )
        
        description = ""
        if content_div:
            # Remove nav, header, footer elements
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
            "description": description[:3000],  # Limit for AI processing
            "company": company,
            "contact": contact,
            "email": email
        }
    except Exception as e:
        print(f"Error fetching job details from {url}: {e}")
        return {}

def search_multiple_platforms(keywords: list, days_back: int = 14) -> list:
    """Search across multiple job platforms."""
    all_results = []
    
    # Search jobs.ch
    results = search_jobs_ch(keywords, days_back=days_back)
    all_results.extend(results)
    
    return all_results
