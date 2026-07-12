import importlib

import pytest

from src import config, csv_output, output


def _reload_output():
    return importlib.reload(output)


@pytest.fixture(autouse=True)
def restore_output_module():
    """output.py picks its backend at import/reload time as a module-level
    side effect, which outlives monkeypatch's teardown — always leave it back
    on 'csv' so later tests (and the rest of the app) see a sane module."""
    yield
    config.SETTINGS["output_backend"] = "csv"
    _reload_output()


def test_default_backend_is_csv():
    config.SETTINGS["output_backend"] = "csv"
    reloaded = _reload_output()
    assert reloaded._impl is csv_output
    assert reloaded.append_results is csv_output.append_results
    assert reloaded.reset_results is csv_output.reset_results


def test_sheets_backend_without_credentials_raises_clearly():
    config.SETTINGS["output_backend"] = "sheets"
    with pytest.raises(RuntimeError, match="SHEET_ID"):
        _reload_output()


def test_unknown_backend_raises_clearly():
    config.SETTINGS["output_backend"] = "bogus"
    with pytest.raises(ValueError, match="Unknown output_backend"):
        _reload_output()


def test_sheets_backend_works_once_credentials_present(monkeypatch):
    monkeypatch.setattr(config, "SHEET_ID", "fake-sheet-id")
    monkeypatch.setattr(config, "SERVICE_ACCOUNT_FILE", "fake-path.json")
    config.SETTINGS["output_backend"] = "sheets"

    from src import sheets

    reloaded = _reload_output()
    assert reloaded._impl is sheets
    assert reloaded.append_results is sheets.append_results
    assert reloaded.reset_results is sheets.reset_results
