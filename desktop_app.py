import socket
import sys
import threading
import time
import urllib.request
from contextlib import closing
from pathlib import Path
from werkzeug.serving import make_server

from app import app, configure_runtime, ensure_runtime_configured, set_output_folder
from invoice_renamer.runtime import (
    APP_NAME,
    desktop_dir,
    user_data_dir,
    webview_storage_path,
    write_desktop_log,
    write_exception_log,
)

ERROR_ALREADY_EXISTS = 183
_SINGLE_INSTANCE = None


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class FlaskServer:
    def __init__(self, port: int):
        self.port = port
        self.server = make_server("127.0.0.1", port, app, threaded=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()
        self.wait_until_ready()

    def stop(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)

    def wait_until_ready(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        url = f"http://127.0.0.1:{self.port}/health"
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=0.3) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.05)
        raise TimeoutError("Local web server did not become ready in time")


class SingleInstance:
    def __init__(self, name: str):
        self.name = name
        self.handle = None
        self.lock_fd = None
        self.lock_path = None

    def acquire(self) -> bool:
        if sys.platform == "win32":
            return self._acquire_windows_mutex()
        return self._acquire_lock_file()

    def release(self) -> None:
        if sys.platform == "win32" and self.handle:
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(self.handle)
            finally:
                self.handle = None
            return

        if self.lock_fd is not None:
            try:
                import os

                os.close(self.lock_fd)
                if self.lock_path:
                    self.lock_path.unlink(missing_ok=True)
            finally:
                self.lock_fd = None
                self.lock_path = None

    def _acquire_windows_mutex(self) -> bool:
        import ctypes

        mutex_name = f"Local\\{self.name}"
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            return True
        self.handle = handle
        return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS

    def _acquire_lock_file(self) -> bool:
        import os

        lock_dir = user_data_dir()
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path = lock_dir / "app.lock"
        try:
            self.lock_fd = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
            )
            os.write(self.lock_fd, str(os.getpid()).encode("ascii"))
            return True
        except FileExistsError:
            return False


def show_already_running_message() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"{APP_NAME} 已经在运行。",
            APP_NAME,
            0x40,
        )
    except Exception:
        pass


def folder_picker_initial_dir(initial_dir: str) -> str:
    candidates = [Path(initial_dir)] if initial_dir else []
    candidates.append(desktop_dir())
    candidates.append(Path.home())
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return str(candidate)
        except OSError:
            continue
    return str(Path.home())


def select_folder_with_tk(initial_dir: str) -> str | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            initialdir=folder_picker_initial_dir(initial_dir),
            title="选择输出文件夹",
            mustexist=True,
        )
        return selected or None
    finally:
        root.destroy()


class DesktopApi:
    def __init__(self, window=None, folder_picker=None):
        self.window = window
        self.folder_picker = folder_picker

    def bind_window(self, window) -> None:
        self.window = window

    def select_output_folder(self) -> dict:
        ensure_runtime_configured()
        if self.folder_picker is not None:
            selected_folder = self.folder_picker(app.config["PROCESSED_FOLDER"])
            if not selected_folder:
                return {
                    "selected": False,
                    "output_folder": app.config["PROCESSED_FOLDER"],
                }

            output_folder = set_output_folder(selected_folder)
            return {"selected": True, "output_folder": output_folder}

        if self.window is None:
            selected_folder = select_folder_with_tk(app.config["PROCESSED_FOLDER"])
            if not selected_folder:
                return {
                    "selected": False,
                    "output_folder": app.config["PROCESSED_FOLDER"],
                }
            output_folder = set_output_folder(selected_folder)
            return {"selected": True, "output_folder": output_folder}

        import webview

        selected = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        if not selected:
            return {
                "selected": False,
                "output_folder": app.config["PROCESSED_FOLDER"],
            }

        output_folder = set_output_folder(selected[0])
        return {"selected": True, "output_folder": output_folder}


def main() -> None:
    global _SINGLE_INSTANCE
    import webview

    _SINGLE_INSTANCE = SingleInstance("InvoiceRenamerDesktop")
    if not _SINGLE_INSTANCE.acquire():
        write_desktop_log("Another desktop app instance is already running")
        show_already_running_message()
        return

    try:
        write_desktop_log(f"Starting {APP_NAME} desktop app")
        write_desktop_log("Configuring runtime")
        configure_runtime(desktop=True)
        port = find_free_port()
        write_desktop_log(f"Starting local server on port {port}")
        server = FlaskServer(port)
        server.start()
        write_desktop_log("Local server is ready")
        api = DesktopApi()

        write_desktop_log("Creating webview window")
        window = webview.create_window(
            APP_NAME,
            f"http://127.0.0.1:{port}",
            width=1120,
            height=820,
            min_size=(880, 620),
            js_api=api,
        )
        api.bind_window(window)
        window.events.closed += server.stop
        write_desktop_log("Starting webview event loop")
        webview.start(private_mode=False, storage_path=str(webview_storage_path()))
    finally:
        if _SINGLE_INSTANCE is not None:
            _SINGLE_INSTANCE.release()
            _SINGLE_INSTANCE = None


def show_startup_error(log_path: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"{APP_NAME} 启动失败。\n\n错误日志：\n{log_path}",
            APP_NAME,
            0x10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_path = write_exception_log(exc)
        show_startup_error(str(log_path))
        raise
