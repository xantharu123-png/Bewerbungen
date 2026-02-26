import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/jobs.json")
DOCS_PATH = Path("data/documents")

def init_db():
    """Initialize database files and directories."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        save_db({"jobs": [], "settings": {}, "documents": {}})

def load_db() -> dict:
    init_db()
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data: dict):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def get_jobs() -> list:
    return load_db().get("jobs", [])

def save_job(job: dict):
    db = load_db()
    # Check if job already exists (by URL)
    existing = [j for j in db["jobs"] if j.get("url") == job.get("url")]
    if existing:
        return False  # Duplicate
    job["id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    job["added_at"] = datetime.now().isoformat()
    job["status"] = job.get("status", "Neu")
    job["notes"] = job.get("notes", "")
    job["applied_at"] = job.get("applied_at", "")
    job["response"] = job.get("response", "")
    db["jobs"].append(job)
    save_db(db)
    return True

def update_job(job_id: str, updates: dict):
    db = load_db()
    for i, job in enumerate(db["jobs"]):
        if job["id"] == job_id:
            db["jobs"][i].update(updates)
            save_db(db)
            return True
    return False

def delete_job(job_id: str):
    db = load_db()
    db["jobs"] = [j for j in db["jobs"] if j["id"] != job_id]
    save_db(db)

def get_settings() -> dict:
    return load_db().get("settings", {})

def save_settings(settings: dict):
    db = load_db()
    db["settings"] = settings
    save_db(db)

def save_document(name: str, content: bytes, doc_type: str):
    db = load_db()
    filepath = DOCS_PATH / name
    with open(filepath, "wb") as f:
        f.write(content)
    db["documents"][doc_type] = {
        "filename": name,
        "path": str(filepath),
        "uploaded_at": datetime.now().isoformat()
    }
    save_db(db)

def get_document(doc_type: str) -> dict | None:
    return load_db().get("documents", {}).get(doc_type)

STATUS_OPTIONS = [
    "Neu",
    "Interessant",
    "Beworben",
    "Antwort erhalten",
    "Interview",
    "Absage",
    "Zusage",
    "Ignorieren"
]

STATUS_COLORS = {
    "Neu": "#6c757d",
    "Interessant": "#0d6efd",
    "Beworben": "#fd7e14",
    "Antwort erhalten": "#6f42c1",
    "Interview": "#20c997",
    "Absage": "#dc3545",
    "Zusage": "#198754",
    "Ignorieren": "#adb5bd"
}
