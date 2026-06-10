from pathlib import Path

from app import extract_amount
from invoice_renamer.processor import process_pdf_file


def test_extracts_total_amount_from_sample_invoices():
    for pdf_path in sorted(Path("test").glob("*.pdf")):
        assert extract_amount(str(pdf_path)) == pdf_path.stem


def test_renames_sample_invoices_to_expected_amount_names(tmp_path):
    for pdf_path in sorted(Path("test").glob("*.pdf")):
        result = process_pdf_file(str(pdf_path), "original.pdf", str(tmp_path))
        assert result["success"] is True
        assert result["new_filename"] == pdf_path.name
