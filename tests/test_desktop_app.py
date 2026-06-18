from pathlib import Path


def test_desktop_api_select_output_folder_updates_app_config(tmp_path):
    import app
    from desktop_app import DesktopApi

    class Window:
        def create_file_dialog(self, dialog_type):
            return [str(tmp_path)]

    api = DesktopApi(Window())
    result = api.select_output_folder()

    assert result == {"selected": True, "output_folder": str(tmp_path)}
    assert Path(app.app.config["PROCESSED_FOLDER"]) == tmp_path
    assert tmp_path.is_dir()


def test_desktop_api_select_output_folder_keeps_existing_folder_when_cancelled(tmp_path):
    import app
    from desktop_app import DesktopApi

    app.app.config["PROCESSED_FOLDER"] = str(tmp_path / "existing")

    class Window:
        def create_file_dialog(self, dialog_type):
            return None

    api = DesktopApi(Window())
    result = api.select_output_folder()

    assert result == {"selected": False, "output_folder": str(tmp_path / "existing")}
    assert Path(app.app.config["PROCESSED_FOLDER"]) == tmp_path / "existing"
