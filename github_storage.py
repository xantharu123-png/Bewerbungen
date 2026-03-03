"""GitHub API storage backend for JobTracker Pro.

Uses the GitHub API to read/write the data file directly in the repository.
This replaces Google Drive as the persistence layer because Service Accounts
cannot create files on personal Google Drive (no storage quota).

Required secrets:
  - GITHUB_TOKEN: Personal Access Token with `repo` scope
  - GITHUB_REPO: e.g. "xantharu123-png/Bewerbungen"
  - (Optional) GITHUB_BRANCH: defaults to "main"
"""

import os
import json
import base64
import requests

# ── Configuration ──

def _get_config() -> dict:
    """Load GitHub config from Streamlit secrets or environment."""
    config = {}

    # Try Streamlit secrets first
    try:
        import streamlit as st
        config["token"] = st.secrets.get("GITHUB_TOKEN", "")
        config["repo"] = st.secrets.get("GITHUB_REPO", "")
        config["branch"] = st.secrets.get("GITHUB_BRANCH", "main")
    except Exception:
        pass

    # Fallback to environment
    if not config.get("token"):
        config["token"] = os.environ.get("GITHUB_TOKEN", "")
    if not config.get("repo"):
        config["repo"] = os.environ.get("GITHUB_REPO", "xantharu123-png/Bewerbungen")
    if not config.get("branch"):
        config["branch"] = os.environ.get("GITHUB_BRANCH", "main")

    return config


def is_github_available() -> bool:
    """Check if GitHub storage is configured."""
    cfg = _get_config()
    return bool(cfg.get("token") and cfg.get("repo"))


def _headers() -> dict:
    """Build GitHub API headers."""
    cfg = _get_config()
    return {
        "Authorization": f"token {cfg['token']}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "JobTrackerPro/1.0",
    }


def _api_url(path: str) -> str:
    """Build GitHub API URL for a file path."""
    cfg = _get_config()
    repo = cfg["repo"]
    return f"https://api.github.com/repos/{repo}/contents/{path}"


def _get_file_sha(path: str) -> str | None:
    """Get the current SHA of a file (needed for updates)."""
    cfg = _get_config()
    try:
        resp = requests.get(
            _api_url(path),
            headers=_headers(),
            params={"ref": cfg["branch"]},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("sha")
    except Exception:
        pass
    return None


def download_json(path: str) -> dict | None:
    """Download a JSON file from the GitHub repo."""
    cfg = _get_config()
    if not cfg.get("token"):
        return None

    try:
        resp = requests.get(
            _api_url(path),
            headers=_headers(),
            params={"ref": cfg["branch"]},
            timeout=15,
        )
        if resp.status_code == 200:
            content_b64 = resp.json().get("content", "")
            content = base64.b64decode(content_b64).decode("utf-8")
            return json.loads(content)
        elif resp.status_code == 404:
            print(f"[GitHub] File not found: {path}")
            return None
        else:
            print(f"[GitHub] HTTP {resp.status_code} downloading {path}")
            return None
    except Exception as e:
        print(f"[GitHub] Download error for {path}: {e}")
        return None


def upload_json(path: str, data: dict) -> bool:
    """Upload/update a JSON file in the GitHub repo."""
    cfg = _get_config()
    if not cfg.get("token"):
        print("[GitHub] No token configured")
        return False

    try:
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

        # Get existing SHA (needed for update)
        sha = _get_file_sha(path)

        body = {
            "message": f"Auto-sync: {path}",
            "content": content_b64,
            "branch": cfg["branch"],
        }
        if sha:
            body["sha"] = sha  # Update existing file

        resp = requests.put(
            _api_url(path),
            headers=_headers(),
            json=body,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            print(f"[GitHub] Synced {path} ({len(content)} bytes)")
            return True
        else:
            error = resp.json().get("message", resp.text[:200])
            print(f"[GitHub] Upload failed for {path}: HTTP {resp.status_code} — {error}")
            return False
    except Exception as e:
        print(f"[GitHub] Upload error for {path}: {e}")
        return False


def test_github_connection() -> tuple[bool, str]:
    """Test the GitHub API connection."""
    cfg = _get_config()

    if not cfg.get("token"):
        return False, "GITHUB_TOKEN nicht konfiguriert"
    if not cfg.get("repo"):
        return False, "GITHUB_REPO nicht konfiguriert"

    try:
        # Test: list repo contents
        resp = requests.get(
            f"https://api.github.com/repos/{cfg['repo']}",
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            repo_info = resp.json()
            return True, f"Verbunden — {repo_info.get('full_name', cfg['repo'])}"
        elif resp.status_code == 401:
            return False, "GitHub Token ungültig"
        elif resp.status_code == 404:
            return False, f"Repository nicht gefunden: {cfg['repo']}"
        else:
            return False, f"GitHub API Fehler: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"GitHub Fehler: {str(e)[:150]}"
