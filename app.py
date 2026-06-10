import os
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from invoice_renamer.extractor import extract_amount
from invoice_renamer.processor import process_pdf_file, unique_filename


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["PROCESSED_FOLDER"] = "processed"


def ensure_work_folders() -> None:
    for folder in [app.config["UPLOAD_FOLDER"], app.config["PROCESSED_FOLDER"]]:
        os.makedirs(folder, exist_ok=True)


def temporary_upload_name(original_filename: str) -> str:
    safe_name = secure_filename(original_filename)
    if safe_name:
        return safe_name
    return f"{uuid.uuid4().hex}.pdf"


ensure_work_folders()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_files():
    if "files" not in request.files:
        return jsonify({"error": "没有选择文件"}), 400

    files = request.files.getlist("files")
    if not files or all(file.filename == "" for file in files):
        return jsonify({"error": "没有选择文件"}), 400

    results = []
    processed_count = 0
    total_amount = 0.0

    for file in files:
        original_filename = file.filename
        if file and original_filename.lower().endswith(".pdf"):
            try:
                file_path = os.path.join(
                    app.config["UPLOAD_FOLDER"],
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
            results.append(save_non_pdf(file, original_filename))

    return jsonify(
        {
            "total_files": len(files),
            "processed_files": processed_count,
            "total_amount": round(total_amount, 2),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }
    )


def save_non_pdf(file, original_filename: str) -> dict:
    try:
        dest_name = unique_filename(app.config["PROCESSED_FOLDER"], original_filename)
        dest_path = os.path.join(app.config["PROCESSED_FOLDER"], dest_name)
        file.stream.seek(0)
        with open(dest_path, "wb") as dst:
            shutil.copyfileobj(file.stream, dst)
        return {
            "success": False,
            "error": "仅支持PDF文件，已原样收纳",
            "original_filename": original_filename,
            "new_filename": dest_name,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"非PDF保存失败: {exc}",
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


@app.route("/clear-files", methods=["POST"])
def clear_files():
    try:
        for folder in [app.config["UPLOAD_FOLDER"], app.config["PROCESSED_FOLDER"]]:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        return jsonify({"message": "文件已清空"})
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
    print("访问地址: http://127.0.0.1:5000")
    app.run(debug=True)
