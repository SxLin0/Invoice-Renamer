import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "INVOICE_RENAMER_DATA_DIR",
    tempfile.mkdtemp(prefix="invoice-renamer-tests-"),
)
