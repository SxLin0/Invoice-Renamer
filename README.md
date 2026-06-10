# Invoice Renamer

一个简单的 PDF 发票改名工具：上传发票后自动识别价税合计金额，并把文件重命名为 `金额.pdf`，例如 `15.81.pdf`。

## 功能

- 批量上传 PDF 发票
- 自动识别发票总金额
- 按金额生成新文件名
- 支持单个下载和打包下载
- 自动处理同名文件

## 环境要求

- Python 3.10 或更高版本
- 普通电子发票不需要额外软件
- 扫描版发票需要本机安装 Tesseract OCR

## 快速开始

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

启动后打开浏览器访问：

```text
http://127.0.0.1:5000
```

如果 `5000` 端口被占用，可以改用 Flask 命令指定端口：

```bash
python -m flask --app app run --host 127.0.0.1 --port 5001
```

## 使用方法

1. 打开网页。
2. 拖入或选择 PDF 发票。
3. 点击“开始处理”。
4. 下载改名后的文件，或点击“打包下载”。

## 项目结构

```text
.
├── app.py                  # Flask Web 服务
├── invoice_renamer/        # 金额识别和文件处理逻辑
├── templates/              # 前端页面
├── static/                 # 图标等静态资源
├── tests/                  # 自动化测试
├── requirements.txt        # Python 依赖
├── LICENSE                 # 开源许可证
└── README.md
```

运行时会自动创建：

- `uploads/`：临时上传文件
- `processed/`：处理后的文件

这两个目录不会提交到 Git。

## 测试

```bash
pytest
```

## 许可证

本项目基于 MIT License 开源，详见 [LICENSE](LICENSE)。
