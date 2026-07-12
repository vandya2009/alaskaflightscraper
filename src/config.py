"""Loads project settings and secrets used by every other file."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"

load_dotenv(PROJECT_ROOT / ".env")


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    if not value or value.startswith("paste_your_"):
        return None
    return value


# Only needed if you write results to Google Sheets (src/sheets.py). The default
# CSV output (src/csv_output.py) doesn't touch either of these.
SHEET_ID = _optional_env("SHEET_ID")
_creds_path = _optional_env("GOOGLE_APPLICATION_CREDENTIALS")
SERVICE_ACCOUNT_FILE = (PROJECT_ROOT / _creds_path) if _creds_path else None

if SERVICE_ACCOUNT_FILE and not SERVICE_ACCOUNT_FILE.exists():
    raise RuntimeError(
        f"Service account file not found at {SERVICE_ACCOUNT_FILE}. "
        f"Put service_account.json into the credentials/ folder."
    )

with SETTINGS_FILE.open() as f:
    SETTINGS = yaml.safe_load(f)
