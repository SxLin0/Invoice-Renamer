from pathlib import Path
from io import BytesIO


def test_open_output_folder_endpoint_uses_processed_folder(monkeypatch, tmp_path):
    import app

    called_paths = []

    monkeypatch.setenv("INVOICE_RENAMER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app, "open_folder", lambda path: called_paths.append(Path(path)))

    app.configure_runtime()
    client = app.app.test_client()

    response = client.post("/open-output-folder")

    assert response.status_code == 200
    assert response.get_json() == {"message": "已打开输出文件夹"}
    assert called_paths == [tmp_path / "processed"]


def test_upload_uses_temporary_source_file_and_removes_it(monkeypatch, tmp_path):
    import app

    seen_paths = []

    def fake_process_pdf_file(file_path, original_filename, processed_folder):
        seen_paths.append(Path(file_path))
        assert Path(file_path).exists()
        assert original_filename == "invoice.pdf"
        assert Path(processed_folder) == tmp_path / "processed"
        return {
            "success": True,
            "amount": 12.34,
            "new_filename": "12.34.pdf",
            "original_filename": original_filename,
        }

    monkeypatch.setenv("INVOICE_RENAMER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app, "process_pdf_file", fake_process_pdf_file)

    app.configure_runtime()
    client = app.app.test_client()
    response = client.post(
        "/upload",
        data={"files": (BytesIO(b"%PDF test"), "invoice.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert seen_paths
    assert all(not path.exists() for path in seen_paths)
    assert list((tmp_path / "uploads").iterdir()) == []


def test_non_pdf_inputs_are_rejected_without_saving(monkeypatch, tmp_path):
    import app

    monkeypatch.setenv("INVOICE_RENAMER_DATA_DIR", str(tmp_path))
    app.configure_runtime()

    client = app.app.test_client()
    response = client.post(
        "/upload",
        data={"files": (BytesIO(b"not a pdf"), "note.txt")},
        content_type="multipart/form-data",
    )

    result = response.get_json()["results"][0]
    assert response.status_code == 200
    assert result["success"] is False
    assert result["error"] == "仅支持PDF文件，未保存"
    assert "new_filename" not in result
    assert list((tmp_path / "processed").iterdir()) == []


def test_frontend_has_desktop_output_folder_controls():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "id=\"chooseOutputBtn\"" in template
    assert "id=\"openOutputBtn\"" in template
    assert "选择输出文件夹" in template
    assert "打开输出文件夹" in template
    assert "window.pywebview.api.select_output_folder" in template
    assert "fetch('/app-info')" in template
    assert "fetch('/open-output-folder', { method: 'POST' })" in template


def test_frontend_clear_only_resets_current_lists():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "清空列表" in template
    assert "fetch('/clear-files'" not in template
    assert "function clearCurrentList()" in template


def test_clear_files_endpoint_is_not_exposed():
    import app

    client = app.app.test_client()

    assert client.post("/clear-files").status_code == 404


def test_desktop_build_workflow_creates_installer_and_dmg():
    workflow = Path(".github/workflows/build-desktop.yml").read_text(encoding="utf-8")
    dmg_script = Path("scripts/create_macos_dmg.sh").read_text(encoding="utf-8")

    assert "InvoiceRenamerSetup.exe" in workflow
    assert "ISCC" in workflow
    assert "InvoiceRenamer-macos.dmg" in workflow
    assert "hdiutil create" in dmg_script


def test_windows_installer_uses_only_inno_setup_builtin_language_files():
    script = Path("installer/windows/InvoiceRenamer.iss").read_text(encoding="utf-8")

    assert "ChineseSimplified.isl" not in script
    assert 'MessagesFile: "compiler:Default.isl"' in script


def test_windows_installer_bundles_webview2_bootstrapper():
    script = Path("installer/windows/InvoiceRenamer.iss").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/build-desktop.yml").read_text(encoding="utf-8")

    assert "MicrosoftEdgeWebview2Setup.exe" in script
    assert "/silent /install" in script
    assert "LinkId=2124703" in workflow
