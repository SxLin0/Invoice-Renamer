import os
import sys
from pathlib import Path


def test_user_data_dir_uses_platform_app_location(monkeypatch, tmp_path):
    monkeypatch.delenv("INVOICE_RENAMER_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from invoice_renamer.runtime import APP_NAME, user_data_dir

    if sys.platform == "darwin":
        expected = tmp_path / "Library" / "Application Support" / APP_NAME
    elif sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
        expected = tmp_path / "LocalAppData" / APP_NAME
    else:
        expected = tmp_path / ".local" / "share" / APP_NAME

    assert user_data_dir() == expected


def test_work_folders_are_created_under_user_data_dir(tmp_path):
    from invoice_renamer.runtime import ensure_work_folders

    upload_dir, processed_dir = ensure_work_folders(tmp_path)

    assert upload_dir == tmp_path / "uploads"
    assert processed_dir == tmp_path / "processed"
    assert upload_dir.is_dir()
    assert processed_dir.is_dir()


def test_resource_path_uses_pyinstaller_extract_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    from invoice_renamer.runtime import resource_path

    assert resource_path("templates/index.html") == tmp_path / "templates" / "index.html"


def test_configure_tesseract_uses_bundled_binary_and_tessdata(monkeypatch, tmp_path):
    from invoice_renamer.runtime import configure_tesseract

    runtime_dir = tmp_path / "runtime" / "tesseract"
    tessdata_dir = runtime_dir / "tessdata"
    tessdata_dir.mkdir(parents=True)
    binary = runtime_dir / ("tesseract.exe" if sys.platform == "win32" else "tesseract")
    binary.write_text("", encoding="utf-8")

    configured = configure_tesseract(tmp_path)

    assert configured is True
    assert os.environ["TESSDATA_PREFIX"] == str(tessdata_dir)

    import pytesseract

    assert pytesseract.pytesseract.tesseract_cmd == str(binary)


def test_configure_tesseract_is_false_when_bundle_is_missing(tmp_path):
    from invoice_renamer.runtime import configure_tesseract

    assert configure_tesseract(tmp_path) is False


def test_flask_app_uses_runtime_work_folders(monkeypatch, tmp_path):
    monkeypatch.setenv("INVOICE_RENAMER_DATA_DIR", str(tmp_path))

    import app

    app.configure_runtime()

    assert Path(app.app.config["UPLOAD_FOLDER"]) == tmp_path / "uploads"
    assert Path(app.app.config["PROCESSED_FOLDER"]) == tmp_path / "processed"


def test_desktop_log_path_is_under_user_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("INVOICE_RENAMER_DATA_DIR", str(tmp_path))

    from invoice_renamer.runtime import desktop_log_path

    assert desktop_log_path() == tmp_path / "logs" / "desktop.log"


def test_normalize_output_dir_expands_environment_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("INVOICE_TEST_OUTPUT", str(tmp_path))

    from invoice_renamer.runtime import normalize_output_dir

    assert normalize_output_dir(r"%INVOICE_TEST_OUTPUT%\Desktop") == tmp_path / "Desktop"
    assert (tmp_path / "Desktop").is_dir()


def test_ensure_writable_dir_returns_existing_writable_folder(tmp_path):
    from invoice_renamer.runtime import ensure_writable_dir

    assert ensure_writable_dir(tmp_path) == tmp_path
