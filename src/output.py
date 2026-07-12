"""Dispatches result/log writing to the backend configured in settings.yaml
(output_backend: csv | sheets). scrape.py imports from here instead of
importing csv_output or sheets directly, so switching backends is a one-line
settings.yaml change rather than a code edit.
"""
from src.config import SETTINGS

_BACKEND = str(SETTINGS.get("output_backend", "csv")).lower()

if _BACKEND == "csv":
    from src import csv_output as _impl
elif _BACKEND == "sheets":
    from src.config import SERVICE_ACCOUNT_FILE, SHEET_ID

    if not SHEET_ID or not SERVICE_ACCOUNT_FILE:
        raise RuntimeError(
            "settings.yaml has output_backend: sheets, but SHEET_ID and/or "
            "GOOGLE_APPLICATION_CREDENTIALS aren't set in .env. Either configure "
            "those (see README.md), or set output_backend back to 'csv'."
        )
    from src import sheets as _impl
else:
    raise ValueError(
        f"Unknown output_backend '{_BACKEND}' in settings.yaml — expected 'csv' or 'sheets'."
    )

append_results = _impl.append_results
append_log = _impl.append_log
existing_keys = _impl.existing_keys
