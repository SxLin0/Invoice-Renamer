import socket
import sys
import threading
from contextlib import closing

import webview
from werkzeug.serving import make_server

from app import app, configure_runtime, set_output_folder
from invoice_renamer.runtime import write_desktop_log, write_exception_log


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


class DesktopApi:
    def __init__(self, window=None):
        self.window = window

    def bind_window(self, window) -> None:
        self.window = window

    def select_output_folder(self) -> dict:
        if self.window is None:
            return {
                "selected": False,
                "output_folder": app.config["PROCESSED_FOLDER"],
            }

        selected = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        if not selected:
            return {
                "selected": False,
                "output_folder": app.config["PROCESSED_FOLDER"],
            }

        output_folder = set_output_folder(selected[0])
        return {"selected": True, "output_folder": output_folder}


def main() -> None:
    write_desktop_log("Starting Invoice Renamer desktop app")
    configure_runtime()
    app.config["DESKTOP_MODE"] = True
    port = find_free_port()
    server = FlaskServer(port)
    server.start()
    api = DesktopApi()

    window = webview.create_window(
        "冰冰发票改名器",
        f"http://127.0.0.1:{port}",
        width=1120,
        height=820,
        min_size=(880, 620),
        js_api=api,
    )
    api.bind_window(window)
    window.events.closed += server.stop
    webview.start()


def show_startup_error(log_path: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"冰冰发票改名器启动失败。\n\n错误日志：\n{log_path}",
            "冰冰发票改名器",
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
