# 曹姐发票改名器

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

桌面版由 GitHub Actions 自动打包，用户不需要安装 Python、依赖库或 Tesseract OCR。

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

### 桌面开发模式

```bash
python desktop_app.py
```

这会启动本地 Flask 服务，并用系统 WebView 打开桌面窗口。开发模式如果要识别扫描版发票，仍需要本机安装 Tesseract OCR；正式桌面包会内置 OCR 运行时。

### 桌面版自动构建

推送到 `dev` 分支或手动运行 `Build Desktop Apps` GitHub Actions workflow 后，会生成以下构建产物：

```text
InvoiceRenamerSetup.exe
InvoiceRenamer-macos.dmg
```

Windows 用户下载 `InvoiceRenamerSetup.exe` 后双击安装。macOS 用户下载 `InvoiceRenamer-macos.dmg` 后打开，并把 App 拖到“应用程序”里。当前 macOS 包未做 Developer ID 签名和公证，首次打开如果被系统拦截，可以右键 App 后选择“打开”。

构建流程会安装 Tesseract OCR，收集 `tesseract` 可执行文件、动态库和 `eng` / `chi_sim` 语言包，然后使用 PyInstaller 打包桌面应用。

运行时上传文件和处理后文件保存在用户数据目录中：

```text
Windows: %LOCALAPPDATA%\曹姐发票改名器
macOS: ~/Library/Application Support/曹姐发票改名器
Linux: ~/.local/share/曹姐发票改名器
```

## 使用方法

1. 打开网页。
2. 拖入或选择 PDF 发票。
3. 点击“开始处理”。
4. 下载改名后的文件，或点击“打包下载”。

桌面版中，首次处理前会让用户选择输出文件夹。处理后的 PDF 会直接保存到该文件夹，处理完成后点击“打开输出文件夹”即可查看改名后的文件。“清空列表”只清空当前窗口里的待处理文件和结果记录，不会删除用户的源文件，也不会删除已经输出的 PDF。

## 项目结构

```text
.
├── app.py                  # Flask Web 服务
├── desktop_app.py          # 桌面 App 入口
├── InvoiceRenamer.spec     # PyInstaller 打包配置
├── invoice_renamer/        # 金额识别和文件处理逻辑
├── scripts/                # 构建辅助脚本
├── templates/              # 前端页面
├── static/                 # 图标等静态资源
├── tests/                  # 自动化测试
├── requirements.txt        # Python 依赖
├── LICENSE                 # 开源许可证
└── README.md
```

运行时会在用户数据目录自动创建：

- `uploads/`：临时上传文件
- `processed/`：处理后的文件

这两个目录不会提交到 Git。

## 测试

```bash
pytest
```

## 许可证

本项目基于 MIT License 开源，详见 [LICENSE](LICENSE)。
