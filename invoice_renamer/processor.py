import os
import re
import shutil

from invoice_renamer.extractor import extract_amount


def unique_filename(folder: str, filename: str) -> str:
    name, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{name}({counter}){ext}"
        counter += 1
    return candidate


def save_to_folder(file_path: str, folder: str, filename: str) -> str:
    os.makedirs(folder, exist_ok=True)
    dest_name = unique_filename(folder, filename)
    dest_path = os.path.join(folder, dest_name)
    shutil.copyfile(file_path, dest_path)
    return dest_name


def is_already_renamed(filename: str) -> bool:
    return re.match(r"^\d+\.\d{2}(?:\(\d+\))?\.pdf$", filename.lower()) is not None


def process_pdf_file(file_path: str, original_filename: str, processed_folder: str) -> dict:
    try:
        amount = extract_amount(file_path)

        if is_already_renamed(original_filename):
            name_amount_match = re.match(r"^(\d+\.\d{2})", original_filename)
            name_amount = name_amount_match.group(1) if name_amount_match else None
            if amount and amount == name_amount:
                new_filename = save_to_folder(file_path, processed_folder, original_filename)
                return {
                    "success": True,
                    "amount": float(amount),
                    "new_filename": new_filename,
                    "original_filename": original_filename,
                    "message": "文件名金额已校验",
                }

        if amount:
            new_filename = save_to_folder(file_path, processed_folder, f"{amount}.pdf")
            return {
                "success": True,
                "amount": float(amount),
                "new_filename": new_filename,
                "original_filename": original_filename,
            }

        new_filename = save_to_folder(file_path, processed_folder, original_filename)
        return {
            "success": False,
            "error": "未找到金额信息",
            "original_filename": original_filename,
            "new_filename": new_filename,
        }
    except Exception as exc:
        try:
            dest_name = save_to_folder(file_path, processed_folder, original_filename)
        except Exception:
            dest_name = None
        return {
            "success": False,
            "error": f"处理错误: {exc}",
            "original_filename": original_filename,
            "new_filename": dest_name or original_filename,
        }
