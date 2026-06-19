import socket
import sys
import threading
from contextlib import closing
from pathlib import Path
from werkzeug.serving import make_server

from app import app, configure_runtime, ensure_runtime_configured, set_output_folder
from invoice_renamer.runtime import (
    APP_NAME,
    desktop_dir,
    webview_storage_path,
    write_desktop_log,
    write_exception_log,
)


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class FlaskServer:
    def __init__(self, port: int):
        self.server = make_server("127.0.0.1", port, app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)


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
        self.folder_picker = folder_picker or select_folder_with_tk

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
            return {
                "selected": False,
                "output_folder": app.config["PROCESSED_FOLDER"],
            }

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
    import webview

    write_desktop_log(f"Starting {APP_NAME} desktop app")
    configure_runtime(desktop=True)
    port = find_free_port()
    server = FlaskServer(port)
    server.start()
    api = DesktopApi()

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
    webview.start(private_mode=False, storage_path=str(webview_storage_path()))


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
