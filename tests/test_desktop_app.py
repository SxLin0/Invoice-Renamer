from pathlib import Path


def test_desktop_api_select_output_folder_updates_app_config(tmp_path):
    import app
    from desktop_app import DesktopApi

    api = DesktopApi(folder_picker=lambda initial_dir: str(tmp_path))
    result = api.select_output_folder()

    assert result == {"selected": True, "output_folder": str(tmp_path)}
    assert Path(app.app.config["PROCESSED_FOLDER"]) == tmp_path
    assert tmp_path.is_dir()


def test_desktop_api_select_output_folder_keeps_existing_folder_when_cancelled(tmp_path):
    import app
    from desktop_app import DesktopApi

    app.app.config["PROCESSED_FOLDER"] = str(tmp_path / "existing")

    api = DesktopApi(folder_picker=lambda initial_dir: None)
    result = api.select_output_folder()

    assert result == {"selected": False, "output_folder": str(tmp_path / "existing")}
    assert Path(app.app.config["PROCESSED_FOLDER"]) == tmp_path / "existing"


def test_folder_picker_initial_dir_falls_back_to_desktop(monkeypatch, tmp_path):
    from desktop_app import folder_picker_initial_dir

    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setattr("desktop_app.desktop_dir", lambda: desktop)

    assert folder_picker_initial_dir(str(tmp_path / "missing")) == str(desktop)


def test_desktop_start_uses_persistent_webview_storage():
    source = Path("desktop_app.py").read_text(encoding="utf-8")

    assert "private_mode=False" in source
    assert "storage_path=str(webview_storage_path())" in source


def test_pyinstaller_includes_tkinter_for_windows_folder_dialog():
    spec = Path("InvoiceRenamer.spec").read_text(encoding="utf-8")

    assert '"tkinter"' in spec
    assert '"tkinter.filedialog"' in spec
