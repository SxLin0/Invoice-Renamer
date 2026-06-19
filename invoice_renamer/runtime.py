import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import pytesseract


APP_NAME = "曹姐发票改名器"
WINDOWS_DESKTOP_FOLDER_ID = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"


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


def windows_known_folder_path(folder_id: str) -> Path | None:
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

            def __init__(self, value: str):
                guid = uuid.UUID(value)
                data4 = (ctypes.c_ubyte * 8).from_buffer_copy(guid.bytes[8:])
                super().__init__(guid.time_low, guid.time_mid, guid.time_hi_version, data4)

        path_ptr = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(GUID(folder_id)),
            0,
            None,
            ctypes.byref(path_ptr),
        )
        if result != 0 or not path_ptr.value:
            return None
        try:
            return Path(path_ptr.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
    except Exception:
        return None


def desktop_dir() -> Path:
    if sys.platform == "win32":
        known_desktop = windows_known_folder_path(WINDOWS_DESKTOP_FOLDER_ID)
        if known_desktop is not None:
            return known_desktop
        if user_profile := os.environ.get("USERPROFILE"):
            return Path(user_profile) / "Desktop"
    return Path.home() / "Desktop"


def ensure_work_folders(base_dir: Path | None = None) -> tuple[Path, Path]:
    root = base_dir or user_data_dir()
    upload_dir = root / "uploads"
    processed_dir = root / "processed"
    upload_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir, processed_dir


def default_output_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None or os.environ.get("INVOICE_RENAMER_DATA_DIR"):
        output_dir = (base_dir or user_data_dir()) / "Output"
    elif sys.platform == "win32":
        output_dir = desktop_dir() / APP_NAME
    else:
        output_dir = user_data_dir() / "Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def normalize_output_dir(folder: str | Path) -> Path:
    raw_folder = os.fspath(folder).strip().strip('"')
    raw_folder = re.sub(
        r"%([^%]+)%",
        lambda match: os.environ.get(match.group(1), match.group(0)),
        raw_folder,
    )
    expanded = os.path.expandvars(raw_folder)
    if not expanded:
        raise ValueError("请选择输出文件夹")

    output_dir = Path(expanded).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise NotADirectoryError(f"{output_dir} 不是文件夹")

    try:
        return output_dir.resolve(strict=False)
    except OSError:
        return output_dir.absolute()


def ensure_writable_dir(folder: str | Path) -> Path:
    output_dir = normalize_output_dir(folder)
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".invoice-renamer-",
            suffix=".tmp",
            dir=output_dir,
            delete=True,
        ):
            pass
    except OSError as exc:
        raise PermissionError(f"输出文件夹不可写：{output_dir}") from exc
    return output_dir


def desktop_log_path() -> Path:
    return user_data_dir() / "logs" / "desktop.log"


def webview_storage_path() -> Path:
    path = user_data_dir() / "webview"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
        os.startfile(str(folder))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
