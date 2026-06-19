import os
import subprocess
import sys
import traceback
from pathlib import Path

import pytesseract


APP_NAME = "Invoice Renamer"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def resource_path(relative_path: str) -> Path:
    return app_root() / relative_path


def user_data_dir() -> Path:
    if configured_dir := os.environ.get("INVOICE_RENAMER_DATA_DIR"):
        return Path(configured_dir).expanduser()

    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    return home / ".local" / "share" / APP_NAME


def ensure_work_folders(base_dir: Path | None = None) -> tuple[Path, Path]:
    root = base_dir or user_data_dir()
    upload_dir = root / "uploads"
    processed_dir = root / "processed"
    upload_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir, processed_dir


def desktop_log_path() -> Path:
    return user_data_dir() / "logs" / "desktop.log"


def write_desktop_log(message: str) -> Path:
    path = desktop_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(message.rstrip())
        log_file.write("\n")
    return path


def write_exception_log(exc: BaseException) -> Path:
    return write_desktop_log("".join(traceback.format_exception(exc)))


def bundled_tesseract_binary(root: Path | None = None) -> Path:
    binary_name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    return (root or app_root()) / "runtime" / "tesseract" / binary_name


def bundled_tessdata_dir(root: Path | None = None) -> Path:
    return (root or app_root()) / "runtime" / "tesseract" / "tessdata"


def configure_tesseract(root: Path | None = None) -> bool:
    binary = bundled_tesseract_binary(root)
    tessdata = bundled_tessdata_dir(root)

    if not binary.exists() or not tessdata.is_dir():
        return False

    pytesseract.pytesseract.tesseract_cmd = str(binary)
    os.environ["TESSDATA_PREFIX"] = str(tessdata)

    lib_dir = binary.parent / "lib"
    if lib_dir.is_dir():
        env_var = "PATH" if sys.platform == "win32" else "DYLD_LIBRARY_PATH"
        current = os.environ.get(env_var)
        os.environ[env_var] = (
            f"{lib_dir}{os.pathsep}{current}" if current else str(lib_dir)
        )

    return True


def open_folder(path: str | Path) -> None:
    folder = Path(path)
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
