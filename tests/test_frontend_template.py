from pathlib import Path


def test_frontend_accumulates_result_batches():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "let processedResults = [];" in template
    assert "processedResults.push(...(data.results || []));" in template
    assert "statTotal.textContent = processedResults.length;" in template
    assert "statTotal.textContent = data.total_files" not in template


def test_frontend_appends_selected_files_instead_of_replacing_them():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "function addFiles(fileListLike)" in template
    assert "files = [...files, ...newFiles]" in template
    assert "files = Array.from(fileListLike)" not in template


def test_frontend_uses_caojie_app_name():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "曹姐发票改名器" in template
    assert "冰冰发票改名器" not in template
