import json
import os
from datetime import datetime
from pathlib import Path

# Google Drive sync (optional — works without it too)
from drive_storage import (
    is_drive_available, upload_json, download_json,
    upload_file, download_file, verify_file_on_drive,
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
                # First restore documents (updates paths in cloud_data dict)
                _restore_documents_from_drive(cloud_data)
                # Save AFTER restore so updated paths are persisted
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


def _restore_documents_from_drive(db_data: dict):
    """Restore uploaded documents from Drive.

    Downloads each document file and updates the path in db_data (in-place).
    The caller MUST save db_data to disk afterwards!
    """
    import time
    docs = db_data.get("documents", {})
    for doc_type, doc_info in docs.items():
        filename = doc_info.get("filename", "")
        if not filename:
            continue

        filepath = DOCS_PATH / filename
        # Always update path to match current local structure
        doc_info["path"] = str(filepath)

        # Skip if file already exists locally
        if filepath.exists() and filepath.stat().st_size > 0:
            print(f"[DB] Document already local: {filename}")
            continue

        # Try download with retry (Drive can be slow on cold start)
        content = None
        for attempt in range(3):
            content = download_file(f"docs/{filename}")
            if content:
                break
            print(f"[DB] Retry {attempt + 1}/3 for {filename}...")
            time.sleep(1)

        if content:
            DOCS_PATH.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(content)
            print(f"[DB] Restored document: {filename} ({len(content)} bytes)")
        else:
            print(f"[DB] WARNING: Could not restore {filename} from Drive after 3 attempts")


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
    """Save document locally and to Google Drive.

    Returns (success, message) for UI feedback.
    """
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
    drive_ok = False
    drive_msg = "Drive nicht verfügbar"
    if is_drive_available():
        try:
            # Use proper mime types
            mime_types = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
            }
            ext = name[name.rfind('.'):].lower() if '.' in name else ""
            mime = mime_types.get(ext, "application/octet-stream")

            drive_ok, upload_err = upload_file(f"docs/{name}", content, mime_type=mime)
            if drive_ok:
                # Verify the file is actually on Drive
                if verify_file_on_drive(f"docs/{name}"):
                    drive_msg = f"✅ '{name}' auf Google Drive gesichert"
                    print(f"[DB] Document uploaded and verified on Drive: {name}")
                else:
                    drive_msg = f"⚠️ '{name}' Upload schien OK, aber Datei nicht auf Drive gefunden"
                    print(f"[DB] WARNING: Upload returned True but file not found on Drive: {name}")
            else:
                drive_msg = f"❌ {upload_err}"
                print(f"[DB] Document upload failed: {name} — {upload_err}")
        except Exception as e:
            drive_msg = f"❌ Drive Fehler: {e}"
            print(f"[DB] Document upload to Drive error: {e}")

    return drive_ok, drive_msg


def get_document(doc_type: str) -> dict | None:
    """Get document info. Re-downloads from Drive if local file is missing."""
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

    # If local file missing, try to restore from Drive
    if not local_path.exists() or local_path.stat().st_size == 0:
        if is_drive_available() and filename:
            content = download_file(f"docs/{filename}")
            if content:
                DOCS_PATH.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)
                # Update path in DB so it persists
                db["documents"][doc_type]["path"] = str(local_path)
                save_db_local(db)
                print(f"[DB] Re-downloaded document: {filename} ({len(content)} bytes)")
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
