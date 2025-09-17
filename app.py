from flask import Flask, request, jsonify, render_template, send_file
import os
import re
import uuid
from werkzeug.utils import secure_filename
import pdfplumber
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'

# 创建必要的目录
for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def extract_amount(pdf_path):
    """
    从PDF发票中提取金额,支持铁路电子发票和普通电子发票
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() + '\n'
            
            # 首先尝试普通发票
            regular_match = re.search(r'小写[）)]?\s*[：:]\s*¥?([0-9]+\.[0-9]{2})', text)
            if regular_match:
                return regular_match.group(1)
            
            # 尝试提取价税合计金额
            total_match = re.search(r'价税合计.*?([0-9]+\.[0-9]{2})', text, re.DOTALL)
            if total_match:
                return total_match.group(1)
            
            # 尝试直接匹配金额模式
            amount_match = re.search(r'¥?\s*([0-9]+\.[0-9]{2})', text)
            if amount_match:
                return amount_match.group(1)
            
            return None
    except Exception as e:
        print(f"提取金额错误: {e}")
        return None

def is_already_renamed(filename):
    """
    检查文件名是否已经是金额格式(如40.00.pdf)
    """
    pattern = r'^\d+\.\d{2}(?:_\d+)?\.pdf$'
    return re.match(pattern, filename.lower()) is not None

def process_pdf_file(file_path, original_filename):
    try:
        # 检查是否已经是金额格式
        if is_already_renamed(original_filename):
            try:
                amount_float = float(original_filename.split('.')[0])
            except ValueError:
                amount_float = 0.0
            return {
                'success': True,
                'amount': amount_float,
                'new_filename': original_filename,
                'original_filename': original_filename,
                'message': '文件已是金额格式'
            }

        amount = extract_amount(file_path)
        if amount:
            new_filename = f'{amount}.pdf'
            new_filepath = os.path.join(app.config['PROCESSED_FOLDER'], new_filename)
            counter = 1
            while os.path.exists(new_filepath):
                name, ext = os.path.splitext(new_filename)
                new_filename = f"{name}_{counter}{ext}"
                new_filepath = os.path.join(app.config['PROCESSED_FOLDER'], new_filename)
                counter += 1
            with open(file_path, 'rb') as src, open(new_filepath, 'wb') as dst:
                dst.write(src.read())
            return {
                'success': True,
                'amount': float(amount),
                'new_filename': new_filename,
                'original_filename': original_filename
            }
        else:
            return {
                'success': False,
                'error': '未找到金额信息',
                'original_filename': original_filename
            }
    except Exception as e:
        return {
            'success': False,
            'error': f'处理错误: {str(e)}',
            'original_filename': original_filename
        }

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """处理多文件上传"""
    if 'files' not in request.files:
        return jsonify({'error': '没有选择文件'}), 400
    
    files = request.files.getlist('files')
    if len(files) == 0 or all(file.filename == '' for file in files):
        return jsonify({'error': '没有选择文件'}), 400
    
    results = []
    processed_count = 0
    total_amount = 0.0
    
    for file in files:
        if file and file.filename.lower().endswith('.pdf'):
            try:
                # 安全处理文件名
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # 保存原始文件
                file.save(file_path)
                
                # 处理PDF文件
                result = process_pdf_file(file_path, filename)
                results.append(result)
                
                if result['success']:
                    processed_count += 1
                    if 'amount' in result:
                        total_amount += result['amount']
                
            except Exception as e:
                results.append({
                    'success': False,
                    'error': f'处理错误: {str(e)}',
                    'original_filename': file.filename
                })
        else:
            results.append({
                'success': False,
                'error': '仅支持PDF文件',
                'original_filename': file.filename
            })
    
    return jsonify({
        'total_files': len(files),
        'processed_files': processed_count,
        'total_amount': round(total_amount, 2),
        'results': results,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/download/<filename>')
def download_file(filename):
    """下载处理后的文件"""
    try:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/processed-files')
def list_processed_files():
    """获取已处理文件列表"""
    try:
        files = []
        for filename in os.listdir(app.config['PROCESSED_FOLDER']):
            if filename.endswith('.pdf'):
                file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
                file_stat = os.stat(file_path)
                files.append({
                    'name': filename,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    'amount': float(filename.split('_')[0].replace('.pdf', ''))
                })
        # 按金额排序
        files.sort(key=lambda x: x['amount'])
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear-files', methods=['POST'])
def clear_files():
    """清空处理过的文件"""
    try:
        for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        return jsonify({'message': '文件已清空'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("💰PDF重命名工具启动成功！")
    print("访问地址: http://127.0.0.1:5000")
    print("功能: 提取PDF发票金额并重命名文件")
    app.run(debug=True)