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


SCOPES = ["https://www.googleapis.com/auth/drive"]


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


def test_drive_connection() -> tuple[bool, str]:
    """Actually test the Drive connection with a real API call.

    Returns (success, message) — use this to show status in the UI.
    """
    if not GOOGLE_AVAILABLE:
        return False, "Google API Bibliotheken nicht installiert"

    service = _get_service()
    if not service:
        return False, "Service Account Credentials nicht gefunden"

    folder_id = _get_folder_id()
    if not folder_id:
        return False, "GOOGLE_DRIVE_FOLDER_ID nicht konfiguriert"

    try:
        # Actually list files to verify the connection works
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            fields="files(id, name, mimeType, size)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = results.get("files", [])
        # Show only real files, skip folders
        real_files = [f for f in files if f.get("mimeType") != "application/vnd.google-apps.folder"]
        file_names = [f.get("name", "?") for f in real_files[:5]]
        if real_files:
            return True, f"Verbunden — {len(real_files)} Datei(en): {', '.join(file_names)}"
        else:
            return True, "Verbunden — Daten werden synchronisiert"
    except Exception as e:
        error_msg = str(e)
        if "accessNotConfigured" in error_msg or "API has not been" in error_msg:
            return False, "Google Drive API nicht aktiviert im GCP Projekt"
        if "403" in error_msg:
            return False, f"Kein Zugriff auf den Drive-Ordner ({error_msg[:120]})"
        if "404" in error_msg:
            return False, f"Drive-Ordner nicht gefunden ({error_msg[:120]})"
        return False, f"Drive Fehler: {error_msg[:200]}"


def verify_file_on_drive(filename: str) -> bool:
    """Check if a specific file exists on Drive."""
    service = _get_service()
    folder_id = _get_folder_id()
    if not service or not folder_id:
        return False
    return _find_file(service, folder_id, filename) is not None


def _find_or_create_subfolder(service, parent_id: str, folder_name: str) -> str | None:
    """Find or create a subfolder inside the parent folder. Returns folder ID."""
    try:
        query = (f"name='{folder_name}' and '{parent_id}' in parents "
                 f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
        results = service.files().list(
            q=query, spaces="drive", fields="files(id)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]
        # Create it
        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(
            body=metadata, fields="id", supportsAllDrives=True
        ).execute()
        print(f"[Drive] Created subfolder '{folder_name}' → {folder.get('id')}")
        return folder.get("id")
    except Exception as e:
        print(f"[Drive] Subfolder error: {e}")
        return None


def _resolve_path(service, root_folder_id: str, filepath: str) -> tuple[str, str]:
    """Resolve 'docs/filename.pdf' into (actual_parent_id, bare_filename).

    If filepath contains '/', creates subfolders as needed.
    """
    parts = filepath.replace("\\", "/").split("/")
    bare_name = parts[-1]
    parent_id = root_folder_id
    for subfolder in parts[:-1]:
        sub_id = _find_or_create_subfolder(service, parent_id, subfolder)
        if not sub_id:
            return root_folder_id, bare_name  # fallback to root
        parent_id = sub_id
    return parent_id, bare_name


def _find_file(service, folder_id: str, filename: str):
    """Find a file by name in the target folder (supports 'docs/file.pdf' paths).
    Returns file ID or None."""
    try:
        parent_id, bare_name = _resolve_path(service, folder_id, filename)
        query = f"name='{bare_name}' and '{parent_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, spaces="drive", fields="files(id, name)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None
    except Exception as e:
        print(f"[Drive] Find file error: {e}")
        return None


def upload_file(filename: str, content: bytes, mime_type: str = "application/octet-stream") -> tuple[bool, str]:
    """Upload or update a file in the Google Drive folder.

    Returns (success, error_message). error_message is empty on success.
    """
    service = _get_service()
    folder_id = _get_folder_id()
    if not service or not folder_id:
        return False, "Drive Service oder Folder ID fehlt"

    try:
        # Resolve path (e.g. "docs/file.pdf" → subfolder + bare name)
        parent_id, bare_name = _resolve_path(service, folder_id, filename)
        media = MediaInMemoryUpload(content, mimetype=mime_type)
        existing_id = _find_file(service, folder_id, filename)

        if existing_id:
            # Update existing file
            service.files().update(
                fileId=existing_id, media_body=media,
                supportsAllDrives=True,
            ).execute()
        else:
            # Create new file in resolved parent folder
            metadata = {"name": bare_name, "parents": [parent_id]}
            service.files().create(
                body=metadata, media_body=media, fields="id",
                supportsAllDrives=True,
            ).execute()

        return True, ""
    except Exception as e:
        error_msg = str(e)
        print(f"[Drive] Upload error for {filename}: {error_msg}")
        # ALWAYS include raw error for debugging
        raw_hint = f" (API: {error_msg[:300]})"
        # Parse common errors but show raw text too
        if "insufficientPermissions" in error_msg or "forbidden" in error_msg.lower():
            return False, f"Service Account hat keine Schreibrechte auf den Ordner.{raw_hint}"
        if "notFound" in error_msg:
            return False, f"Drive-Ordner nicht gefunden.{raw_hint}"
        if "storageQuota" in error_msg:
            return False, f"Speicher-Fehler — evtl. Service-Account-Quota.{raw_hint}"
        return False, f"Upload-Fehler: {error_msg[:300]}"


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

        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
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
    success, error = upload_file(filename, content, mime_type="application/json")
    if not success:
        print(f"[Drive] JSON upload failed for {filename}: {error}")
    return success


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
            orderBy="modifiedTime desc",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return results.get("files", [])
    except Exception as e:
        print(f"[Drive] List error: {e}")
        return []
