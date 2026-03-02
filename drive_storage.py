"""
Google Drive Storage für JobTracker Pro.

Speichert jobs.json und Dokumente (CV, Diplome) persistent in einem
geteilten Google Drive Ordner via Service Account.

Setup:
1. Google Cloud Console → Projekt erstellen
2. Google Drive API aktivieren
3. Service Account erstellen → JSON-Key herunterladen
4. In Streamlit Secrets den JSON-Key als GOOGLE_SERVICE_ACCOUNT eintragen
5. Google Drive Ordner erstellen und mit Service-Account-Email teilen (Editor)
6. Ordner-ID in Streamlit Secrets als GOOGLE_DRIVE_FOLDER_ID eintragen
"""

import json
import io
import os
from pathlib import Path

# Try to import Google libraries (optional dependency)
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload, MediaIoBaseDownload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _load_credentials():
    """Load Google Service Account credentials from Streamlit secrets or env."""
    if not GOOGLE_AVAILABLE:
        return None

    creds_json = None

    # 1. Try Streamlit secrets
    try:
        import streamlit as st
        sa = st.secrets.get("GOOGLE_SERVICE_ACCOUNT", None)
        if sa:
            # Streamlit secrets returns a dict-like object
            creds_json = dict(sa)
    except Exception:
        pass

    # 2. Try environment variable (JSON string)
    if not creds_json:
        env_val = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "")
        if env_val:
            try:
                creds_json = json.loads(env_val)
            except json.JSONDecodeError:
                pass

    # 3. Try local files (multiple locations)
    if not creds_json:
        possible_paths = [
            Path("data/service_account.json"),
            Path("bewerbungen-489007-58c2a2254a41.json"),
            *Path(".").glob("*service*account*.json"),
            *Path(".").glob("*bewerbungen*.json"),
        ]
        for local_path in possible_paths:
            if local_path.exists():
                try:
                    with open(local_path, "r") as f:
                        creds_json = json.load(f)
                    if creds_json.get("type") == "service_account":
                        print(f"[Drive] Loaded credentials from {local_path}")
                        break
                    else:
                        creds_json = None
                except (json.JSONDecodeError, KeyError):
                    creds_json = None

    if not creds_json:
        return None

    try:
        return Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    except Exception as e:
        print(f"[Drive] Credentials error: {e}")
        return None


def _get_folder_id() -> str:
    """Get the target Google Drive folder ID."""
    # 1. Streamlit secrets
    try:
        import streamlit as st
        fid = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "")
        if fid:
            return str(fid)
    except Exception:
        pass

    # 2. Environment variable
    return os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")


def _get_service():
    """Build Google Drive API service."""
    creds = _load_credentials()
    if not creds:
        return None
    try:
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"[Drive] Service build error: {e}")
        return None


def is_drive_available() -> bool:
    """Check if Google Drive storage is configured and available."""
    if not GOOGLE_AVAILABLE:
        return False
    service = _get_service()
    folder_id = _get_folder_id()
    return service is not None and bool(folder_id)


def _find_file(service, folder_id: str, filename: str):
    """Find a file by name in the target folder. Returns file ID or None."""
    try:
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, spaces="drive", fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None
    except Exception as e:
        print(f"[Drive] Find file error: {e}")
        return None


def upload_file(filename: str, content: bytes, mime_type: str = "application/octet-stream") -> bool:
    """Upload or update a file in the Google Drive folder."""
    service = _get_service()
    folder_id = _get_folder_id()
    if not service or not folder_id:
        return False

    try:
        media = MediaInMemoryUpload(content, mimetype=mime_type)
        existing_id = _find_file(service, folder_id, filename)

        if existing_id:
            # Update existing file
            service.files().update(
                fileId=existing_id, media_body=media
            ).execute()
        else:
            # Create new file
            metadata = {"name": filename, "parents": [folder_id]}
            service.files().create(
                body=metadata, media_body=media, fields="id"
            ).execute()

        return True
    except Exception as e:
        print(f"[Drive] Upload error for {filename}: {e}")
        return False


def download_file(filename: str) -> bytes | None:
    """Download a file from the Google Drive folder. Returns bytes or None."""
    service = _get_service()
    folder_id = _get_folder_id()
    if not service or not folder_id:
        return None

    try:
        file_id = _find_file(service, folder_id, filename)
        if not file_id:
            return None

        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return buffer.getvalue()
    except Exception as e:
        print(f"[Drive] Download error for {filename}: {e}")
        return None


def upload_json(filename: str, data: dict) -> bool:
    """Upload a dict as JSON file to Drive."""
    content = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    return upload_file(filename, content, mime_type="application/json")


def download_json(filename: str) -> dict | None:
    """Download a JSON file from Drive and return as dict."""
    content = download_file(filename)
    if content:
        try:
            return json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[Drive] JSON parse error for {filename}: {e}")
    return None


def list_files() -> list:
    """List all files in the Google Drive folder."""
    service = _get_service()
    folder_id = _get_folder_id()
    if not service or not folder_id:
        return []

    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, spaces="drive",
            fields="files(id, name, mimeType, size, modifiedTime)",
            orderBy="modifiedTime desc"
        ).execute()
        return results.get("files", [])
    except Exception as e:
        print(f"[Drive] List error: {e}")
        return []
