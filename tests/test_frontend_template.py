from pathlib import Path


def test_frontend_accumulates_result_batches():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "let processedResults = [];" in template
    assert "processedResults.push(...(data.results || []));" in template
    assert "statTotal.textContent = processedResults.length;" in template
    assert "statTotal.textContent = data.total_files" not in template
