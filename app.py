import os
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from invoice_renamer.extractor import extract_amount
from invoice_renamer.processor import process_pdf_file
from invoice_renamer.runtime import (
    configure_tesseract,
    ensure_work_folders,
    open_folder,
    resource_path,
)


app = Flask(
    __name__,
    template_folder=str(resource_path("templates")),
    static_folder=str(resource_path("static")),
)
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024


def configure_runtime() -> None:
    upload_dir, processed_dir = ensure_work_folders()
    app.config["UPLOAD_FOLDER"] = str(upload_dir)
    app.config["PROCESSED_FOLDER"] = str(processed_dir)
    app.config["TESSERACT_BUNDLED"] = configure_tesseract()
    app.config["DESKTOP_MODE"] = False
    app.config["OUTPUT_FOLDER_SELECTED"] = False


def temporary_upload_name(original_filename: str) -> str:
    safe_name = secure_filename(original_filename)
    if safe_name:
        return safe_name
    return f"{uuid.uuid4().hex}.pdf"


def set_output_folder(folder: str | Path) -> str:
    output_dir = Path(folder).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    app.config["PROCESSED_FOLDER"] = str(output_dir)
    app.config["OUTPUT_FOLDER_SELECTED"] = True
    return str(output_dir)


configure_runtime()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/app-info")
def app_info():
    desktop_mode = bool(app.config.get("DESKTOP_MODE", False))
    output_selected = bool(app.config.get("OUTPUT_FOLDER_SELECTED", False))
    return jsonify(
        {
            "desktop": desktop_mode,
            "output_folder": app.config["PROCESSED_FOLDER"]
            if not desktop_mode or output_selected
            else "",
            "output_folder_selected": output_selected,
            "tesseract_bundled": bool(app.config.get("TESSERACT_BUNDLED", False)),
        }
    )


@app.route("/upload", methods=["POST"])
def upload_files():
    if "files" not in request.files:
        return jsonify({"error": "没有选择文件"}), 400

    files = request.files.getlist("files")
    if not files or all(file.filename == "" for file in files):
        return jsonify({"error": "没有选择文件"}), 400
    if app.config.get("DESKTOP_MODE") and not app.config.get("OUTPUT_FOLDER_SELECTED"):
        return jsonify({"error": "请先选择输出文件夹"}), 400

    results = []
    processed_count = 0
    total_amount = 0.0

    with tempfile.TemporaryDirectory(prefix="invoice-renamer-") as upload_dir:
        for file in files:
            original_filename = file.filename
            if file and original_filename.lower().endswith(".pdf"):
                try:
                    file_path = os.path.join(
                        upload_dir,
                        temporary_upload_name(original_filename),
                    )
                    file.save(file_path)

                    result = process_pdf_file(
                        file_path,
                        original_filename,
                        app.config["PROCESSED_FOLDER"],
                    )
                    results.append(result)

                    if result["success"]:
                        processed_count += 1
                        total_amount += result.get("amount", 0.0)
                except Exception as exc:
                    results.append(
                        {
                            "success": False,
                            "error": f"处理错误: {exc}",
                            "original_filename": original_filename,
                        }
                    )
            else:
                results.append(reject_non_pdf(original_filename))

    return jsonify(
        {
            "total_files": len(files),
            "processed_files": processed_count,
            "total_amount": round(total_amount, 2),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }
    )


def reject_non_pdf(original_filename: str) -> dict:
    return {
        "success": False,
        "error": "仅支持PDF文件，未保存",
        "original_filename": original_filename,
    }


@app.route("/download/<filename>")
def download_file(filename):
    try:
        file_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        return jsonify({"error": "文件不存在"}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/processed-files")
def list_processed_files():
    try:
        files = []
        for filename in os.listdir(app.config["PROCESSED_FOLDER"]):
            if not filename.lower().endswith(".pdf"):
                continue
            file_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
            file_stat = os.stat(file_path)
            amount = extract_amount(file_path)
            files.append(
                {
                    "name": filename,
                    "size": file_stat.st_size,
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    "amount": float(amount) if amount else 0.0,
                }
            )
        files.sort(key=lambda item: item["amount"])
        return jsonify({"files": files})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/open-output-folder", methods=["POST"])
def open_output_folder():
    try:
        if app.config.get("DESKTOP_MODE") and not app.config.get("OUTPUT_FOLDER_SELECTED"):
            return jsonify({"error": "请先选择输出文件夹"}), 400
        os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)
        open_folder(app.config["PROCESSED_FOLDER"])
        return jsonify({"message": "已打开输出文件夹"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/download-all")
def download_all():
    zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
    try:
        with zipfile.ZipFile(os.fdopen(zip_fd, "wb"), "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in os.listdir(app.config["PROCESSED_FOLDER"]):
                file_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
                if os.path.isfile(file_path):
                    zf.write(file_path, arcname=filename)
        return send_file(zip_path, as_attachment=True, download_name="renamed_invoices.zip")
    finally:
        threading.Thread(
            target=lambda: (time.sleep(5), os.remove(zip_path)),
            daemon=True,
        ).start()


if __name__ == "__main__":
    print("PDF重命名工具启动成功")
    print(f"数据目录: {Path(app.config['UPLOAD_FOLDER']).parent}")
    print("访问地址: http://127.0.0.1:5000")
    app.run(debug=True)
