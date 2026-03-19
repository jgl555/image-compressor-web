"""
🖼️ Image Compressor Web - Flask Backend
在线图片压缩工具后端API
"""

import os
import uuid
import io
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, after_this_request
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 清理过期文件
def cleanup_old_files():
    """删除1小时前的上传文件"""
    now = datetime.now()
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if now - file_time > timedelta(hours=1):
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted old file: {filename}")
                except Exception as e:
                    logger.error(f"Error deleting {filename}: {e}")

@app.route('/')
def index():
    """返回前端页面"""
    return send_file('index.html')

@app.route('/api/compress', methods=['POST'])
def compress_image():
    """
    图片压缩API
    
    请求参数:
    - file: 图片文件
    - quality: 压缩质量 (1-100), 默认85
    - format: 输出格式 (jpeg, png, webp), 默认保持原格式
    
    返回:
    - compressed_image: 压缩后的图片
    - original_size: 原始大小(bytes)
    - compressed_size: 压缩后大小(bytes)
    - compression_ratio: 压缩率(%)
    - format: 输出格式
    """
    # 清理旧文件
    cleanup_old_files()
    
    # 检查文件
    if 'file' not in request.files:
        return jsonify({'error': '请上传图片文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    # 检查文件类型
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'不支持的文件类型: {ext}'}), 400
    
    # 获取参数
    quality = request.form.get('quality', type=int, default=85)
    quality = max(1, min(100, quality))  # 限制在1-100之间
    output_format = request.form.get('format', '').lower()
    
    # 读取原始图片
    original_size = len(file.read())
    file.seek(0)  # 重置文件指针
    
    if original_size > MAX_FILE_SIZE:
        return jsonify({'error': f'文件太大,最大支持{MAX_FILE_SIZE/1024/1024}MB'}), 400
    
    try:
        img = Image.open(file)
        
        # 保持Exif信息
        exif_data = img.info.get('exif')
        
        # 确定输出格式
        if output_format and output_format in ALLOWED_EXTENSIONS:
            save_format = output_format.upper()
        else:
            save_format = img.format or 'JPEG'
        
        # 处理透明度
        if save_format == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
            # 转换为RGB
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        # 压缩图片
        output = io.BytesIO()
        
        if save_format == 'JPEG':
            img.save(output, format='JPEG', quality=quality, optimize=True)
        elif save_format == 'PNG':
            # PNG压缩: quality表示压缩级别
            compress_level = int((100 - quality) / 11)  # 转换为0-9
            img.save(output, format='PNG', optimize=True, compress_level=compress_level)
        elif save_format == 'WEBP':
            img.save(output, format='WEBP', quality=quality, method=6)
        else:
            img.save(output, format=save_format, quality=quality)
        
        compressed_size = output.tell()
        output.seek(0)
        
        # 计算压缩率
        compression_ratio = round((1 - compressed_size / original_size) * 100, 2) if original_size > 0 else 0
        
        # 生成唯一文件名
        filename = f"{uuid.uuid4()}.{save_format.lower()}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # 保存文件
        with open(filepath, 'wb') as f:
            f.write(output.getvalue())
        
        # 返回压缩后的图片
        output.seek(0)
        
        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.error(f"Error removing file: {e}")
            return response
        
        return send_file(
            output,
            mimetype=f'image/{save_format.lower()}',
            as_attachment=True,
            download_name=f'compressed_{filename}'
        )
        
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return jsonify({'error': f'压缩失败: {str(e)}'}), 500

@app.route('/api/info', methods=['POST'])
def get_image_info():
    """获取图片信息"""
    if 'file' not in request.files:
        return jsonify({'error': '请上传图片文件'}), 400
    
    file = request.files['file']
    
    try:
        img = Image.open(file)
        info = {
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode,
            'size_bytes': len(file.read())
        }
        file.seek(0)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
