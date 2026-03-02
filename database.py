import json
import os
from datetime import datetime
from pathlib import Path

# Google Drive sync (optional — works without it too)
from drive_storage import (
    is_drive_available, upload_json, download_json,
    upload_file, download_file
)

DB_PATH = Path("data/jobs.json")
DOCS_PATH = Path("data/documents")
DRIVE_DB_NAME = "jobtracker_data.json"


def init_db():
    """Initialize database files and directories.
    If Google Drive is available, sync from Drive on first load."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.mkdir(parents=True, exist_ok=True)

    # Try to restore from Google Drive if local DB is missing or empty
    if not DB_PATH.exists() or DB_PATH.stat().st_size < 10:
        if is_drive_available():
            print("[DB] Restoring from Google Drive...")
            cloud_data = download_json(DRIVE_DB_NAME)
            if cloud_data:
                save_db_local(cloud_data)
                # Also restore documents
                _restore_documents_from_drive(cloud_data)
                print("[DB] Restored from Google Drive!")
                return

    if not DB_PATH.exists():
        save_db({"jobs": [], "settings": {}, "documents": {}})


def _restore_documents_from_drive(db_data: dict):
    """Restore uploaded documents from Drive."""
    docs = db_data.get("documents", {})
    for doc_type, doc_info in docs.items():
        filename = doc_info.get("filename", "")
        if filename:
            filepath = DOCS_PATH / filename
            # Skip if file already exists locally
            if filepath.exists() and filepath.stat().st_size > 0:
                continue
            content = download_file(f"docs/{filename}")
            if content:
                with open(filepath, "wb") as f:
                    f.write(content)
                # Fix path in DB to match local path
                doc_info["path"] = str(filepath)
                print(f"[DB] Restored document: {filename}")
            else:
                print(f"[DB] WARNING: Could not restore {filename} from Drive")


def save_db_local(data: dict):
    """Save to local file only (no Drive sync)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_db() -> dict:
    init_db()
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data: dict):
    """Save to local file and sync to Google Drive."""
    save_db_local(data)

    # Sync to Drive in background
    if is_drive_available():
        try:
            upload_json(DRIVE_DB_NAME, data)
        except Exception as e:
            print(f"[DB] Drive sync error: {e}")


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
    """Save document locally and to Google Drive."""
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

    # Also upload the actual file to Drive
    if is_drive_available():
        try:
            mime = "application/pdf" if name.endswith(".pdf") else "application/octet-stream"
            upload_file(f"docs/{name}", content, mime_type=mime)
        except Exception as e:
            print(f"[DB] Document upload to Drive error: {e}")


def get_document(doc_type: str) -> dict | None:
    """Get document info. Re-downloads from Drive if local file is missing."""
    doc_info = load_db().get("documents", {}).get(doc_type)
    if not doc_info:
        return None

    filepath = Path(doc_info.get("path", ""))
    filename = doc_info.get("filename", "")

    # If local file missing, try to restore from Drive
    if not filepath.exists() or filepath.stat().st_size == 0:
        if is_drive_available() and filename:
            content = download_file(f"docs/{filename}")
            if content:
                DOCS_PATH.mkdir(parents=True, exist_ok=True)
                local_path = DOCS_PATH / filename
                with open(local_path, "wb") as f:
                    f.write(content)
                doc_info["path"] = str(local_path)
                print(f"[DB] Re-downloaded document: {filename}")
                return doc_info
        return None  # File truly missing

    return doc_info


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
