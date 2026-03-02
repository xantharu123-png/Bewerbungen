import json
import os
import base64
from datetime import datetime
from pathlib import Path

# Google Drive sync (optional — works without it too)
from drive_storage import (
    is_drive_available, upload_json, download_json,
    test_drive_connection
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
                # Extract embedded documents to local files
                _restore_embedded_documents(cloud_data)
                save_db_local(cloud_data)
                print(f"[DB] Restored from Google Drive! Jobs: {len(cloud_data.get('jobs', []))}, "
                      f"Docs: {len(cloud_data.get('documents', {}))}, "
                      f"Settings: {list(cloud_data.get('settings', {}).keys())}")
                return
            else:
                print("[DB] WARNING: Drive available but download returned nothing!")

    if not DB_PATH.exists():
        # CRITICAL: Only save locally, NEVER overwrite Drive with empty data!
        save_db_local({"jobs": [], "settings": {}, "documents": {}})


def _restore_embedded_documents(db_data: dict):
    """Extract base64-embedded documents from DB to local files.

    Documents are stored as base64 strings in db_data["documents"][type]["data"].
    This function writes them to disk so the app can use them normally.
    """
    docs = db_data.get("documents", {})
    DOCS_PATH.mkdir(parents=True, exist_ok=True)

    for doc_type, doc_info in docs.items():
        filename = doc_info.get("filename", "")
        b64_data = doc_info.get("data", "")
        if not filename:
            continue

        filepath = DOCS_PATH / filename
        doc_info["path"] = str(filepath)

        # Skip if file already exists locally and has content
        if filepath.exists() and filepath.stat().st_size > 0:
            print(f"[DB] Document already local: {filename}")
            continue

        if b64_data:
            try:
                content = base64.b64decode(b64_data)
                with open(filepath, "wb") as f:
                    f.write(content)
                print(f"[DB] Restored embedded document: {filename} ({len(content)} bytes)")
            except Exception as e:
                print(f"[DB] ERROR decoding {filename}: {e}")
        else:
            print(f"[DB] WARNING: No embedded data for {filename}")


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
    """Save to local file and sync to Google Drive.
    Safety: never overwrite Drive with empty data."""
    save_db_local(data)

    # Sync to Drive — but NEVER upload empty data
    if is_drive_available():
        has_jobs = len(data.get("jobs", [])) > 0
        has_docs = len(data.get("documents", {})) > 0
        has_settings = len(data.get("settings", {})) > 0

        if has_jobs or has_docs or has_settings:
            try:
                upload_json(DRIVE_DB_NAME, data)
            except Exception as e:
                print(f"[DB] Drive sync error: {e}")
        else:
            print("[DB] SKIPPED Drive sync — data is empty, refusing to overwrite")


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


def save_document(name: str, content: bytes, doc_type: str) -> tuple[bool, str]:
    """Save document locally and embed as base64 in the JSON database.

    The base64 data travels with the JSON to Google Drive automatically.
    No separate file upload needed!

    Returns (success, message) for UI feedback.
    """
    db = load_db()
    filepath = DOCS_PATH / name

    # Save locally
    with open(filepath, "wb") as f:
        f.write(content)

    # Embed as base64 in the database
    b64_data = base64.b64encode(content).decode("ascii")

    db["documents"][doc_type] = {
        "filename": name,
        "path": str(filepath),
        "uploaded_at": datetime.now().isoformat(),
        "size": len(content),
        "data": b64_data,  # Base64-encoded file content
    }
    save_db(db)

    # Check if Drive sync worked
    if is_drive_available():
        return True, f"✅ '{name}' gespeichert und auf Drive gesichert ({len(content)} Bytes)"
    else:
        return True, f"✅ '{name}' lokal gespeichert (Drive nicht verfügbar)"


def get_document(doc_type: str) -> dict | None:
    """Get document info. Restores from embedded base64 if local file is missing."""
    db = load_db()
    doc_info = db.get("documents", {}).get(doc_type)
    if not doc_info:
        return None

    filename = doc_info.get("filename", "")
    if not filename:
        return None

    # Always use standard local path
    local_path = DOCS_PATH / filename
    doc_info["path"] = str(local_path)

    # If local file missing, restore from embedded base64
    if not local_path.exists() or local_path.stat().st_size == 0:
        b64_data = doc_info.get("data", "")
        if b64_data:
            try:
                content = base64.b64decode(b64_data)
                DOCS_PATH.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)
                print(f"[DB] Restored document from embedded data: {filename} ({len(content)} bytes)")
                return doc_info
            except Exception as e:
                print(f"[DB] ERROR restoring {filename}: {e}")
                return None
        return None  # No embedded data and no local file

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
