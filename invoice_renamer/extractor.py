import re
from decimal import Decimal, InvalidOperation

import pdfplumber
import pytesseract


AMOUNT_TOKEN = r"[0-9]+(?:[\.,．，][0-9]{2})"
CHINESE_TOTAL = r"[零〇壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整正]+"


def normalize_amount(raw_amount: str) -> str:
    cleaned = re.sub(r"\s+", "", raw_amount)
    cleaned = cleaned.replace("，", ".").replace(",", ".").replace("．", ".")
    try:
        return f"{Decimal(cleaned):.2f}"
    except InvalidOperation:
        return raw_amount


def _amounts_in(text: str) -> list[str]:
    return [normalize_amount(match.group(0)) for match in re.finditer(AMOUNT_TOKEN, text)]


def _extract_from_total_context(text: str) -> str | None:
    text = text.replace("\u00a0", " ")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Most reliable for electronic invoices whose extracted layout puts the
    # label and amount on separate lines: "壹拾伍圆捌角壹分 ¥15.81".
    chinese_amount_pattern = rf"{CHINESE_TOTAL}\s*(?:[￥¥Yy]\s*)?({AMOUNT_TOKEN})"
    for line in lines:
        if match := re.search(chinese_amount_pattern, line):
            return normalize_amount(match.group(1))

    for line in lines:
        compact = re.sub(r"\s+", "", line)
        if "价税合计" in compact and "小写" in compact and (amounts := _amounts_in(line)):
            return amounts[-1]

    for match in re.finditer(r"价\s*税\s*合\s*计", text):
        window = text[match.start() : match.start() + 180]
        if "小写" in re.sub(r"\s+", "", window) and (amounts := _amounts_in(window)):
            return amounts[-1]

    for line in lines:
        compact = re.sub(r"\s+", "", line)
        if "票价" in compact and (amounts := _amounts_in(line)):
            return amounts[-1]

    return None


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _extract_ocr_text(pdf_path: str) -> str:
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            image = page.to_image(resolution=300)
            parts.append(pytesseract.image_to_string(image.original, lang="chi_sim+eng"))
    return "\n".join(parts)


def extract_amount(pdf_path: str) -> str | None:
    try:
        text = _extract_text(pdf_path)
        if amount := _extract_from_total_context(text):
            return amount

        ocr_text = _extract_ocr_text(pdf_path)
        if amount := _extract_from_total_context(ocr_text):
            return amount

        amounts = _amounts_in(text) or _amounts_in(ocr_text)
        return amounts[-1] if amounts else None
    except Exception as exc:
        print(f"提取金额错误: {exc}")
        return None
