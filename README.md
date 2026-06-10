# 发票改名器

把 PDF 发票拖到网页里，程序会识别发票总金额，并把文件改名为 `金额.pdf`，例如 `15.81.pdf`。

## 启动方法

1. 打开终端，进入项目文件夹。

2. 第一次使用先安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. 启动程序：

```bash
python app.py
```

4. 浏览器打开：

```text
http://127.0.0.1:5000
```

5. 上传 PDF 发票，处理完成后下载改名后的文件。

## 注意

如果发票是扫描图片，电脑需要安装 Tesseract OCR 才能识别。普通电子发票通常不需要额外安装。

处理过程中会自动创建：

- `uploads/`：临时上传文件
- `processed/`：处理后的文件
