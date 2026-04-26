"""Loads project settings and secrets used by every other file."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"

load_dotenv(PROJECT_ROOT / ".env")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or value.startswith("paste_your_"):
        raise RuntimeError(
            f"Missing {name} in .env. "
            f"Open the .env file in your project folder and fill it in."
        )
    return value


SHEET_ID = _required_env("SHEET_ID")
SERVICE_ACCOUNT_FILE = PROJECT_ROOT / _required_env("GOOGLE_APPLICATION_CREDENTIALS")

if not SERVICE_ACCOUNT_FILE.exists():
    raise RuntimeError(
        f"Service account file not found at {SERVICE_ACCOUNT_FILE}. "
        f"Put service_account.json into the credentials/ folder."
    )

with SETTINGS_FILE.open() as f:
    SETTINGS = yaml.safe_load(f)
