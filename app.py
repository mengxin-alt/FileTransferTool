# -*- coding: utf-8 -*-
import sys
import os

# 打包后自动识别路径（必须加）
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS  # 打包后路径
    else:
        return os.path.abspath(".")  # 开发时路径

base_path = get_base_path()

import uuid
import time
import psutil
import socket
import json
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import argparse
import qrcode
from PIL import Image, ImageTk
import logging
from logging.handlers import RotatingFileHandler
import webbrowser

# 仅在需要时导入Flask相关模块
if len(sys.argv) > 1 and sys.argv[1] == '--run-server':
    from flask import Flask, request, jsonify, send_from_directory, render_template
    from flask_cors import CORS

# 确保在导入Flask之前创建必要的全局变量
app = None
CORS = lambda x: x  # 默认定义一个空的CORS函数，避免NameError

# 打包后获取exe所在目录，解决资源路径问题
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

# app = Flask(__name__,
#             template_folder=os.path.join(base_path, "templates"),
#             static_folder=os.path.join(base_path, "static"))


# 如果是服务器模式，初始化Flask应用
if len(sys.argv) > 1 and sys.argv[1] == '--run-server':
    app = Flask(
        __name__,
        template_folder=os.path.join(base_path, "templates"),
        static_folder=os.path.join(base_path, "static")
    )
    CORS(app)

# 设置日志配置
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 配置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建日志文件处理器（按大小轮换）
log_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'file_transfer.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'  # 显式指定使用UTF-8编码
)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)

# 添加处理器到记录器
logger.addHandler(log_handler)

# 创建专门的访问日志记录器
access_logger = logging.getLogger('access')
access_logger.setLevel(logging.INFO)

# 创建访问日志文件处理器
access_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'access.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)

# 设置访问日志格式：时间、客户端IP、请求方法、URL、状态码、响应大小、响应时间
access_formatter = logging.Formatter(
    '%(asctime)s - %(remote_addr)s - %(method)s - %(url)s - %(status)s - %(content_length)s - %(response_time)sms'
)
access_handler.setFormatter(access_formatter)

# 添加处理器到访问日志记录器
access_logger.addHandler(access_handler)

# 配置文件路径
CONFIG_FILE = 'config.json'
SERVER_PROCESS = None

# 加载配置
logger.info('程序启动，开始加载配置...')
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    logger.info('配置加载成功: %s', CONFIG_FILE)
except Exception as e:
    logger.error('配置加载失败: %s', str(e))
    # 使用默认配置
    config = {
        'port': 8000,
        'upload_folder': 'uploads',
        'max_content_length': 1000,
        'debug': False
    }
    logger.info('使用默认配置: %s', config)

# 设置上传目录
UPLOAD_FOLDER = config['upload_folder']
logger.info('检查上传目录: %s', UPLOAD_FOLDER)
if not os.path.exists(UPLOAD_FOLDER):
    logger.info('上传目录不存在，开始创建: %s', UPLOAD_FOLDER)
    try:
        os.makedirs(UPLOAD_FOLDER)
        logger.info('上传目录创建成功: %s', UPLOAD_FOLDER)
    except Exception as e:
        logger.error('上传目录创建失败: %s', str(e))
        # 使用默认上传目录
        UPLOAD_FOLDER = 'uploads'
        logger.info('使用默认上传目录: %s', UPLOAD_FOLDER)
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            logger.info('默认上传目录创建成功: %s', UPLOAD_FOLDER)

# 仅在服务器模式下配置Flask应用
if app is not None:
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = config['max_content_length'] * 1024 * 1024  # 限制文件大小

# 仅在服务器模式下定义Flask路由和装饰器
if app is not None:
    # 请求开始时间记录
    @app.before_request
    def before_request():
        request.start_time = time.time()

    # 访问日志记录
    @app.after_request
    def after_request(response):
        # 计算响应时间
        response_time = (time.time() - request.start_time) * 1000
        
        # 获取客户端IP
        remote_addr = request.remote_addr
        
        # 获取请求信息
        method = request.method
        url = request.url
        
        # 获取响应信息
        status = response.status_code
        content_length = response.content_length or 0
        
        # 记录访问日志
        access_logger.info(
            '',
            extra={
                'remote_addr': remote_addr,
                'method': method,
                'url': url,
                'status': status,
                'content_length': content_length,
                'response_time': round(response_time, 2)
            }
        )
        
        return response

    # 主页路由
    @app.route('/')
    def index():
        return render_template('index.html', colors=config.get('colors', {}))

    # 获取文件列表（支持搜索）
    @app.route('/files', methods=['GET'])
    def get_files():
        query = request.args.get('query', '').lower()
        files = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                # 搜索功能：如果有查询参数，只显示包含查询字符串的文件
                if query and query not in filename.lower():
                    continue
                
                filesize = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)
                files.append({
                    'name': filename,
                    'original_name': filename.split('_', 1)[1] if '_' in filename else filename,
                    'size': filesize,
                    'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                })
        # 按修改时间倒序排列
        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({'files': files})

    # 上传文件
    @app.route('/upload', methods=['POST'])
    def upload_file():
        logger.info('收到文件上传请求')
        if 'file' not in request.files:
            logger.warning('文件上传请求中没有文件部分')
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # 生成唯一文件名，避免重名
        unique_filename = str(uuid.uuid4()) + '_' + file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        logger.info('文件上传成功: {} -> {}'.format(file.filename, unique_filename))
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': unique_filename,
            'original_name': file.filename
        }), 201

    # 下载文件
    @app.route('/download/<filename>', methods=['GET'])
    def download_file(filename):
        logger.info('收到文件下载请求: {}'.format(filename))
        try:
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        except FileNotFoundError:
            logger.warning('文件不存在: {}'.format(filename))
            return jsonify({'error': 'File not found'}), 404

    # 删除文件
    @app.route('/delete/<filename>', methods=['DELETE'])
    def delete_file(filename):
        logger.info('收到文件删除请求: {}'.format(filename))
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info('文件删除成功: {}'.format(filename))
            return jsonify({'message': 'File deleted successfully'}), 200
        else:
            logger.warning('文件不存在: {}'.format(filename))
            return jsonify({'error': 'File not found'}), 404




    # 仪表盘路由
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html', colors=config.get('colors', {}))



    # 启动服务器
    @app.route('/api/server/start', methods=['POST'])
    def start_server():
        logger.info('收到服务器启动请求')
        global SERVER_PROCESS, config
        
        if SERVER_PROCESS is not None and SERVER_PROCESS.poll() is None:
            logger.warning('服务器已经在运行，无法重复启动')
            return jsonify({'error': '服务器已经在运行'}), 400
        
        try:
            # 重新加载最新配置
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            # 启动服务器进程
            SERVER_PROCESS = subprocess.Popen([
                sys.executable, 'app.py', '--run-server'
            ])
            
            logger.info('服务器启动成功')
            return jsonify({'message': '服务器启动成功'})
        except Exception as e:
            logger.error('服务器启动失败: {}'.format(str(e)))
            return jsonify({'error': str(e)}), 500

    # 停止服务器
    @app.route('/api/server/stop', methods=['POST'])
    def stop_server():
        logger.info('收到服务器停止请求')
        global SERVER_PROCESS
        
        if SERVER_PROCESS is None or SERVER_PROCESS.poll() is not None:
            logger.warning('服务器未在运行，无法停止')
            return jsonify({'error': '服务器未在运行'}), 400
        
        try:
            logger.info('开始终止服务器进程及其子进程...')
            logger.info('主进程PID: {}'.format(SERVER_PROCESS.pid))
            
            # 使用psutil终止进程及其所有子进程
            parent = psutil.Process(SERVER_PROCESS.pid)
            children = parent.children(recursive=True)  # 获取所有子进程
            
            logger.info('找到 {} 个子进程'.format(len(children)))
            for child in children:
                logger.info('终止子进程: PID={}, 名称={}'.format(child.pid, child.name()))
                child.terminate()  # 终止所有子进程
            
            # 等待子进程终止
            logger.info('等待子进程终止...')
            terminated, still_alive = psutil.wait_procs(children, timeout=3)
            
            logger.info('已终止 {} 个子进程，仍有 {} 个子进程存活'.format(len(terminated), len(still_alive)))
            for child in still_alive:
                logger.warning('子进程 {} 仍在运行，将强制终止'.format(child.pid))
                child.kill()
            
            # 终止主进程
            logger.info('终止主进程: PID={}'.format(SERVER_PROCESS.pid))
            SERVER_PROCESS.terminate()
            
            logger.info('等待主进程终止...')
            try:
                SERVER_PROCESS.wait(timeout=5)
                logger.info('主进程已成功终止')
            except subprocess.TimeoutExpired:
                logger.warning('主进程超时未终止，将强制终止')
                parent.kill()
            
            # 验证进程是否已终止
            try:
                psutil.Process(parent.pid)
                logger.warning('警告: 进程 {} 仍在运行'.format(parent.pid))
            except psutil.NoSuchProcess:
                logger.info('进程 {} 已完全终止'.format(parent.pid))
            
            # 清除进程引用
            SERVER_PROCESS = None
            
            logger.info('服务器停止成功')
            return jsonify({'message': '服务器停止成功'})
        except subprocess.TimeoutExpired:
            # 超时后强制终止所有进程
            logger.warning('服务器停止超时，开始强制终止...')
            if SERVER_PROCESS and SERVER_PROCESS.poll() is None:
                try:
                    parent = psutil.Process(SERVER_PROCESS.pid)
                    children = parent.children(recursive=True)
                    logger.info('强制终止 {} 个子进程'.format(len(children)))
                    for child in children:
                        logger.info('强制终止子进程: PID={}'.format(child.pid))
                        child.kill()
                    logger.info('强制终止主进程: PID={}'.format(parent.pid))
                    parent.kill()
                except psutil.NoSuchProcess:
                    logger.info('进程已不存在')
            
            # 清除进程引用
            SERVER_PROCESS = None
            
            logger.info('服务器强制停止成功')
            return jsonify({'message': '服务器强制停止成功'})
        except Exception as e:
            logger.error('服务器停止失败: {}'.format(str(e)))
            # 发生异常时也清除进程引用
            SERVER_PROCESS = None
            return jsonify({'error': str(e)}), 500

    # 获取配置
    @app.route('/api/config', methods=['GET'])
    def get_config():
        logger.info('收到配置获取请求')
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return jsonify(config)

    # 保存配置
    @app.route('/api/config', methods=['POST'])
    def save_config():
        logger.info('收到配置保存请求')
        global config
        new_config = request.json
        
        try:
            # 验证配置
            if not isinstance(new_config['port'], int) or new_config['port'] < 1 or new_config['port'] > 65535:
                logger.warning('配置验证失败: 端口号必须在1-65535之间')
                return jsonify({'error': '端口号必须在1-65535之间'}), 400
                
            if not new_config['upload_folder'].strip():
                logger.warning('配置验证失败: 上传目录不能为空')
                return jsonify({'error': '上传目录不能为空'}), 400
                
            if not isinstance(new_config['max_content_length'], int) or new_config['max_content_length'] < 1:
                logger.warning('配置验证失败: 最大文件大小必须大于0')
                return jsonify({'error': '最大文件大小必须大于0'}), 400
                
            # 更新应用配置
            app.config['MAX_CONTENT_LENGTH'] = new_config['max_content_length'] * 1024 * 1024
            
            # 保存到文件
            with open(CONFIG_FILE, 'w') as f:
                json.dump(new_config, f, indent=2)
            
            # 更新全局配置变量
            config = new_config
            
            logger.info('配置保存成功')
            return jsonify({'message': '配置保存成功'})
        except Exception as e:
            logger.error('配置保存失败: {}'.format(str(e)))
            return jsonify({'error': str(e)}), 500

    # 获取服务器状态信息
    @app.route('/status')
    def get_server_status():
        try:
            # 获取CPU信息
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count(logical=True)
            
            # 获取内存信息
            memory = psutil.virtual_memory()
            
            # 获取磁盘信息
            disk = psutil.disk_usage('/')
            
            # 获取文件统计信息
            upload_folder = app.config['UPLOAD_FOLDER']
            total_files = 0
            total_size = 0
            
            for root_dir, dirs, files in os.walk(upload_folder):
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    total_files += 1
                    total_size += os.path.getsize(file_path)
            
            # 获取网络信息
            network_interfaces = []
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        network_interfaces.append({
                            'name': interface,
                            'ip': addr.address,
                            'netmask': addr.netmask
                        })
            
            # 构建响应数据
            status_data = {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'total': memory.total,
                    'used': memory.used,
                    'free': memory.free,
                    'percent': memory.percent
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'storage': {
                    'total_files': total_files,
                    'total_size': total_size
                },
                'network': network_interfaces
            }
            
            return jsonify(status_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("文件传输服务器 - 控制面板")
        self.root.geometry("480x600")  # 增加窗口高度，确保所有内容可见
        self.root.resizable(False, False)
        
        # 定义固定主题颜色方案
        self.themes = {
            "default": {
                "primary": "#3498db",
                "secondary": "#95a5a6",
                "background": "#f5f7fa",
                "text": "#333",
                "card": "white"
            },
            "dark": {
                "primary": "#2c3e50",
                "secondary": "#7f8c8d",
                "background": "#1a2530",
                "text": "#ecf0f1",
                "card": "#2c3e50"
            },
            "vibrant": {
                "primary": "#e74c3c",
                "secondary": "#f39c12",
                "background": "#fef9e7",
                "text": "#2c3e50",
                "card": "white"
            },
            "minimal": {
                "primary": "#7f8c8d",
                "secondary": "#bdc3c7",
                "background": "#ecf0f1",
                "text": "#2c3e50",
                "card": "white"
            },
            "pastel": {
                "primary": "#b39ddb",
                "secondary": "#81d4fa",
                "background": "#f3e5f5",
                "text": "#455a64",
                "card": "white"
            }
        }
        
        # 创建顶部菜单栏
        self.create_menu()
        
        # 主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(self.main_frame, text="📁 文件传输服务器", font=('Arial', 12, 'bold'))
        title_label.pack(pady=5)
        
        # 创建标签页控件
        self.notebook = ttk.Notebook(self.main_frame, padding=3)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建控制面板
        self.control_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.control_frame, text="服务控制")
        
        # 创建配置面板
        self.config_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.config_frame, text="配置")
        
        # 创建日志面板
        self.log_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.log_frame, text="日志")
        self.init_log_panel()
        

        
        # 初始化控制面板
        self.init_control_panel()
        
        # 初始化配置面板
        self.init_config_panel()
        
        # 加载当前配置
        self.load_config()
        
        # 服务器状态变量
        self.server_process = None
        self.server_running = False
    
    def create_menu(self):
        # 创建菜单栏
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # 服务控制菜单
        server_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="服务控制", menu=server_menu)
        server_menu.add_command(label="服务控制界面", command=self.show_service_control)
        server_menu.add_command(label="启动服务", command=self.start_server)
        server_menu.add_command(label="停止服务", command=self.stop_server)
        server_menu.add_separator()
        server_menu.add_command(label="退出", command=self.on_program_close)
        
        # 帮助菜单
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def show_logs(self):
        # 切换到日志面板
        self.notebook.select(self.log_frame)
    

    
    def show_service_control(self):
        # 显示标签页控件
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
    

    

    

    

    
    def init_log_panel(self):
        # 日志类型选择区域
        type_frame = ttk.Frame(self.log_frame)
        type_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(type_frame, text="日志类型: ").pack(side=tk.LEFT, padx=5)
        
        # 创建日志类型变量
        self.log_type_var = tk.StringVar()
        self.log_type_var.set("operation")  # 默认显示操作日志
        
        # 创建单选按钮组
        operation_rb = ttk.Radiobutton(type_frame, text="操作日志", variable=self.log_type_var, value="operation")
        operation_rb.pack(side=tk.LEFT, padx=5)
        
        access_rb = ttk.Radiobutton(type_frame, text="访问日志", variable=self.log_type_var, value="access")
        access_rb.pack(side=tk.LEFT, padx=5)
        
        # 日志级别过滤区域
        level_frame = ttk.Frame(self.log_frame)
        level_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(level_frame, text="日志级别: ").pack(side=tk.LEFT, padx=5)
        
        # 创建日志级别变量
        self.log_level_var = tk.StringVar()
        self.log_level_var.set("all")  # 默认显示所有级别
        
        # 创建单选按钮组
        level_all = ttk.Radiobutton(level_frame, text="全部", variable=self.log_level_var, value="all")
        level_all.pack(side=tk.LEFT, padx=5)
        
        level_info = ttk.Radiobutton(level_frame, text="信息", variable=self.log_level_var, value="info")
        level_info.pack(side=tk.LEFT, padx=5)
        
        level_warning = ttk.Radiobutton(level_frame, text="警告", variable=self.log_level_var, value="warning")
        level_warning.pack(side=tk.LEFT, padx=5)
        
        level_error = ttk.Radiobutton(level_frame, text="错误", variable=self.log_level_var, value="error")
        level_error.pack(side=tk.LEFT, padx=5)
        
        # 时间过滤区域
        time_frame = ttk.Frame(self.log_frame)
        time_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(time_frame, text="时间范围: ").pack(side=tk.LEFT, padx=5)
        
        # 创建时间变量和输入框
        self.start_time_var = tk.StringVar()
        self.end_time_var = tk.StringVar()
        
        # 设置默认时间为当天开始和结束
        from datetime import datetime, timedelta
        today = datetime.now()
        start_of_day = today.strftime("%Y-%m-%d %H:%M:%S")
        end_of_day = (today + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        ttk.Label(time_frame, text="开始: ").pack(side=tk.LEFT, padx=5)
        self.start_time_entry = ttk.Entry(time_frame, textvariable=self.start_time_var, width=20, font=('Courier New', 10))
        self.start_time_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(time_frame, text="结束: ").pack(side=tk.LEFT, padx=5)
        self.end_time_entry = ttk.Entry(time_frame, textvariable=self.end_time_var, width=20, font=('Courier New', 10))
        self.end_time_entry.pack(side=tk.LEFT, padx=5)
        
        # 时间过滤按钮
        self.time_filter_btn = ttk.Button(time_frame, text="时间过滤", command=self.on_time_filter)
        self.time_filter_btn.pack(side=tk.LEFT, padx=5)
        
        # 清除时间过滤按钮
        self.clear_time_filter_btn = ttk.Button(time_frame, text="清除时间过滤", command=self.on_clear_time_filter)
        self.clear_time_filter_btn.pack(side=tk.LEFT, padx=5)
        
        # 日志搜索区域
        search_frame = ttk.Frame(self.log_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="搜索: ").pack(side=tk.LEFT, padx=5)
        
        # 创建搜索变量和输入框
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 搜索按钮
        self.search_btn = ttk.Button(search_frame, text="搜索", command=self.on_search)
        self.search_btn.pack(side=tk.LEFT, padx=5)
        
        # 清除搜索按钮
        self.clear_search_btn = ttk.Button(search_frame, text="清除", command=self.on_clear_search)
        self.clear_search_btn.pack(side=tk.LEFT, padx=5)
        
        # 清空日志按钮
        self.clear_log_btn = ttk.Button(search_frame, text="清空日志", command=self.on_clear_log)
        self.clear_log_btn.pack(side=tk.LEFT, padx=5)
        
        # 导出日志按钮
        self.export_log_btn = ttk.Button(search_frame, text="导出日志", command=self.on_export_log)
        self.export_log_btn.pack(side=tk.LEFT, padx=5)
        
        # 日志内容显示区域
        log_content_frame = ttk.LabelFrame(self.log_frame, text="日志内容")
        log_content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(log_content_frame, orient=tk.VERTICAL)
        h_scrollbar = ttk.Scrollbar(log_content_frame, orient=tk.HORIZONTAL)
        
        # 创建文本控件并关联滚动条
        self.log_text = tk.Text(log_content_frame, wrap=tk.NONE, font=('Courier New', 11),
                               yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set,
                               spacing1=2, spacing2=0, spacing3=2, padx=10, pady=5,
                               bg="#f8f8f8")
        # 设置只读模式
        self.log_text.config(state=tk.NORMAL)
        
        # 配置滚动条命令
        v_scrollbar.config(command=self.log_text.yview)
        h_scrollbar.config(command=self.log_text.xview)
        
        # 打包顺序：先滚动条，再文本框
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 定义日志级别颜色标签
        self.log_text.tag_config("INFO", foreground="green")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        # 定义搜索结果高亮标签
        self.log_text.tag_config("SEARCH", background="yellow", foreground="black")
        # 定义交替行背景色标签
        self.log_text.tag_config("EVEN", background="#f8f8f8")
        self.log_text.tag_config("ODD", background="#ffffff")
        
        # 日志切换事件处理
        def on_log_change():
            self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                                  self.search_var.get(), self.start_time_var.get(), self.end_time_var.get())
        
        # 跟踪日志类型和级别变化
        self.log_type_var.trace_add('write', lambda *args: on_log_change())
        self.log_level_var.trace_add('write', lambda *args: on_log_change())
        
        # 搜索按钮事件处理
        def on_search():
            self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                                  self.search_var.get(), self.start_time_var.get(), self.end_time_var.get())
        
        # 清除搜索按钮事件处理
        def on_clear_search():
            self.search_var.set('')
            self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                                  '', self.start_time_var.get(), self.end_time_var.get())
        
        # 绑定Enter键搜索
        self.search_entry.bind('<Return>', lambda event: on_search())
        self.search_entry.bind('<KP_Enter>', lambda event: on_search())
        
        # 自动刷新功能
        def auto_refresh():
            # 保存当前滚动位置
            scroll_pos = self.log_text.yview()[1]
            # 加载日志（包含搜索关键词和时间过滤）
            self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                                  self.search_var.get(), self.start_time_var.get(), self.end_time_var.get())
            # 如果之前滚动到底部，则保持在底部
            if scroll_pos > 0.95:
                self.log_text.see(tk.END)
            # 继续定时刷新
            self.log_refresh_id = self.root.after(2000, auto_refresh)  # 2秒刷新一次
        
        # 初始加载日志（包含搜索关键词和时间过滤）
        self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                              self.search_var.get(), self.start_time_var.get(), self.end_time_var.get())
        
        # 启动自动刷新
        self.log_refresh_id = self.root.after(2000, auto_refresh)  # 2秒刷新一次
        
        # 程序关闭时停止自动刷新
        self.root.protocol("WM_DELETE_WINDOW", self.on_program_close)
    
    def on_program_close(self):
        logger.info('程序开始关闭...')
        # 关闭程序前检查并停止服务器
        if self.server_process and self.server_running:
            try:
                self.stop_server()
            except Exception as e:
                logger.error('关闭程序时停止服务器发生错误: %s', str(e))
        
        # 取消日志刷新定时器
        if hasattr(self, 'log_refresh_id'):
            self.root.after_cancel(self.log_refresh_id)
        
        logger.info('程序已关闭')
        self.root.quit()
    
    def load_logs_to_text(self, log_text, log_type="operation", log_level="all", search_keyword="", start_time="", end_time=""):
        # 根据日志类型选择不同的日志文件
        if log_type == "access":
            log_file_path = os.path.join(LOG_DIR, 'access.log')
        else:
            log_file_path = os.path.join(LOG_DIR, 'file_transfer.log')
        
        # 清空文本控件
        log_text.delete(1.0, tk.END)
        
        try:
            if os.path.exists(log_file_path):
                # 尝试使用不同的编码读取日志文件
                encodings = ['utf-8', 'gbk', 'latin-1']
                for encoding in encodings:
                    try:
                        with open(log_file_path, 'r', encoding=encoding) as f:
                            log_lines = f.readlines()
                            
                        # 如果成功读取，退出循环
                        break
                    except UnicodeDecodeError:
                        # 如果当前编码失败，尝试下一个编码
                        continue
                else:
                    # 如果所有编码都失败
                    log_text.insert(tk.END, "无法解码日志文件，请检查文件编码")
                    return
                
                # 根据日志级别、搜索关键词和时间范围过滤内容
                filtered_lines = []
                from datetime import datetime
                
                # 解析用户输入的时间范围
                try:
                    start_datetime = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
                except ValueError:
                    start_datetime = None
                
                try:
                    end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None
                except ValueError:
                    end_datetime = None
                
                for line in log_lines:
                    # 日志时间过滤
                    time_match = True
                    try:
                        # 解析日志行中的时间戳 (格式: 2023-05-15 14:30:45)
                        if len(line) >= 19 and line[10] == ' ' and line[4] == '-' and line[7] == '-':
                            log_datetime_str = line[:19]
                            log_datetime = datetime.strptime(log_datetime_str, "%Y-%m-%d %H:%M:%S")
                            
                            # 检查是否在时间范围内
                            if start_datetime and log_datetime < start_datetime:
                                time_match = False
                            if end_datetime and log_datetime > end_datetime:
                                time_match = False
                    except ValueError:
                        # 如果无法解析时间戳，默认不过滤
                        pass
                    
                    # 日志级别过滤
                    level_match = False
                    if log_level == "all":
                        level_match = True
                    elif log_level == "info" and "INFO" in line:
                        level_match = True
                    elif log_level == "warning" and "WARNING" in line:
                        level_match = True
                    elif log_level == "error" and "ERROR" in line:
                        level_match = True
                    
                    # 搜索关键词过滤
                    search_match = False
                    if not search_keyword:
                        search_match = True
                    elif search_keyword.lower() in line.lower():
                        search_match = True
                    
                    # 同时满足时间、级别和搜索条件才添加
                    if time_match and level_match and search_match:
                        filtered_lines.append(line)
                
                # 将过滤后的内容逐行插入到文本控件中，并应用颜色标签
                line_count = 0
                for line in filtered_lines:
                    # 获取当前行的起始位置
                    line_start = log_text.index(tk.END)
                    log_text.insert(tk.END, line)
                    line_end = log_text.index(tk.END)
                    
                    # 应用交替行背景色
                    if line_count % 2 == 0:
                        log_text.tag_add("EVEN", line_start, line_end)
                    else:
                        log_text.tag_add("ODD", line_start, line_end)
                    
                    # 根据日志级别应用颜色标签
                    if "[INFO]" in line or "INFO -" in line:
                        log_text.tag_add("INFO", line_start, line_end)
                    elif "[WARNING]" in line or "WARNING -" in line:
                        log_text.tag_add("WARNING", line_start, line_end)
                    elif "[ERROR]" in line or "ERROR -" in line:
                        log_text.tag_add("ERROR", line_start, line_end)
                    
                    line_count += 1
                    
                    # 高亮搜索关键词（如果存在）
                    if search_keyword:
                        keyword_len = len(search_keyword)
                        # 转换为小写进行不区分大小写的搜索
                        line_lower = line.lower()
                        keyword_lower = search_keyword.lower()
                        
                        # 找到所有匹配的位置并应用高亮
                        pos = 0
                        while True:
                            pos = line_lower.find(keyword_lower, pos)
                            if pos == -1:
                                break
                            
                            # 计算在文本控件中的实际位置
                            match_start = "{}+{}c".format(line_start, pos)
                            match_end = "{}+{}c".format(match_start, keyword_len)
                            
                            # 应用搜索高亮标签
                            log_text.tag_add("SEARCH", match_start, match_end)
                            
                            # 继续搜索下一个匹配
                            pos += keyword_len
            else:
                log_text.insert(tk.END, "暂无日志内容...")
        except Exception as e:
            log_text.insert(tk.END, "加载日志失败: {}".format(str(e)))
    
    def clear_logs(self, log_text, log_type="operation"):
        # 根据日志类型选择不同的日志文件
        if log_type == "access":
            log_file_path = os.path.join(LOG_DIR, 'access.log')
        else:
            log_file_path = os.path.join(LOG_DIR, 'file_transfer.log')
        
        try:
            if os.path.exists(log_file_path):
                open(log_file_path, 'w').close()  # 清空文件内容
                log_text.delete(1.0, tk.END)
                log_text.insert(tk.END, "日志已清空")
            else:
                log_text.delete(1.0, tk.END)
                log_text.insert(tk.END, "暂无日志内容")
        except Exception as e:
            log_text.insert(tk.END, "清空日志失败: {}".format(str(e)))
    
    def on_search(self):
        # 搜索按钮点击事件处理
        self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                              self.search_var.get(), self.start_time_var.get(), self.end_time_var.get())
    
    def on_clear_search(self):
        # 清除搜索按钮点击事件处理
        self.search_var.set('')
        self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), 
                              '', self.start_time_var.get(), self.end_time_var.get())
    
    def on_time_filter(self):
        # 时间过滤按钮点击事件处理
        self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), self.search_var.get(),
                              self.start_time_var.get(), self.end_time_var.get())
    
    def on_clear_time_filter(self):
        # 清除时间过滤按钮点击事件处理
        self.start_time_var.set('')
        self.end_time_var.set('')
        self.load_logs_to_text(self.log_text, self.log_type_var.get(), self.log_level_var.get(), self.search_var.get(), '', '')
    
    def on_clear_log(self):
        # 清空日志按钮点击事件处理
        log_type_name = '访问' if self.log_type_var.get() == 'access' else '操作'
        if messagebox.askyesno("确认", "确定要清空{}日志吗？".format(log_type_name)):
            self.clear_logs(self.log_text, self.log_type_var.get())
    
    def on_export_log(self):
        # 导出日志按钮点击事件处理
        # 获取当前过滤条件
        log_type = self.log_type_var.get()
        log_level = self.log_level_var.get()
        search_keyword = self.search_var.get()
        start_time = self.start_time_var.get()
        end_time = self.end_time_var.get()
        
        # 根据日志类型选择不同的日志文件
        if log_type == "access":
            log_file_path = os.path.join(LOG_DIR, 'access.log')
            default_filename = 'access.log'
        else:
            log_file_path = os.path.join(LOG_DIR, 'file_transfer.log')
            default_filename = 'file_transfer.log'
        
        try:
            if os.path.exists(log_file_path):
                # 尝试使用不同的编码读取日志文件
                encodings = ['utf-8', 'gbk', 'latin-1']
                for encoding in encodings:
                    try:
                        with open(log_file_path, 'r', encoding=encoding) as f:
                            log_lines = f.readlines()
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    messagebox.showerror("错误", "无法解码日志文件，请检查文件编码")
                    return
                
                # 根据过滤条件筛选日志
                from datetime import datetime
                filtered_lines = []
                
                # 解析用户输入的时间范围
                try:
                    start_datetime = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
                except ValueError:
                    start_datetime = None
                
                try:
                    end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None
                except ValueError:
                    end_datetime = None
                
                for line in log_lines:
                    # 日志时间过滤
                    time_match = True
                    try:
                        if len(line) >= 19 and line[10] == ' ' and line[4] == '-' and line[7] == '-':
                            log_datetime_str = line[:19]
                            log_datetime = datetime.strptime(log_datetime_str, "%Y-%m-%d %H:%M:%S")
                            if start_datetime and log_datetime < start_datetime:
                                time_match = False
                            if end_datetime and log_datetime > end_datetime:
                                time_match = False
                    except ValueError:
                        pass
                    
                    # 日志级别过滤
                    level_match = False
                    if log_level == "all":
                        level_match = True
                    elif log_level == "info" and "INFO" in line:
                        level_match = True
                    elif log_level == "warning" and "WARNING" in line:
                        level_match = True
                    elif log_level == "error" and "ERROR" in line:
                        level_match = True
                    
                    # 搜索关键词过滤
                    search_match = False
                    if not search_keyword:
                        search_match = True
                    elif search_keyword.lower() in line.lower():
                        search_match = True
                    
                    # 同时满足时间、级别和搜索条件才添加
                    if time_match and level_match and search_match:
                        filtered_lines.append(line)
                
                # 让用户选择导出文件路径
                export_filename = filedialog.asksaveasfilename(
                    defaultextension=".log",
                    initialfile=default_filename,
                    filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
                    title="导出日志"
                )
                
                if export_filename:
                    # 导出过滤后的日志内容
                    with open(export_filename, 'w', encoding='utf-8') as f:
                        f.writelines(filtered_lines)
                    
                    messagebox.showinfo("成功", "日志已导出到: {}".format(export_filename))
            else:
                messagebox.showwarning("警告", "暂无日志内容可导出")
        except Exception as e:
            messagebox.showerror("错误", "导出日志失败: {}".format(str(e)))
    

    
    def show_about(self):
        # 跳转到dashboard.html界面
        # 前置检查：dashboard 由 Flask 的 /dashboard 路由提供，必须先启动服务
        if not self.server_running or self.server_process is None:
            messagebox.showwarning(
                "提示",
                "服务器尚未启动，无法打开监控面板。\n请先在「服务控制」标签页点击「启动服务」。"
            )
            self.notebook.select(self.control_frame)
            return

        try:
            port = int(self.port_display_var.get())
            config['port'] = port
            # 获取所有本地IP地址，为空时用 127.0.0.1 兜底，避免 url 未定义导致崩溃
            local_ips = self.get_all_local_ips()
            main_ip = local_ips[0] if local_ips else '127.0.0.1'
            url = "http://{}:{}/dashboard".format(main_ip, port)
            webbrowser.open(url)
        except ValueError:
            messagebox.showerror("错误", "端口号无效，无法打开监控面板！")
        except Exception as e:
            logger.error("打开监控面板失败: %s", str(e))
            messagebox.showerror("错误", "打开监控面板失败: {}".format(str(e)))
        
    def show_config(self):
        # 切换到配置标签页
        self.notebook.select(self.config_frame)
        
    def init_control_panel(self):
        # 服务器控制框架
        control_box = ttk.LabelFrame(self.control_frame, text="服务控制", padding="10")
        control_box.pack(fill=tk.X, pady=5)
        
        # 端口配置区域
        port_frame = ttk.Frame(control_box)
        port_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(port_frame, text="端口: ", font=('Arial', 9, 'bold'), width=6).pack(side=tk.LEFT, padx=5)
        
        # 端口输入框
        self.port_display_var = tk.StringVar()
        self.port_display_var.set("{}".format(config['port']))
        self.port_entry = ttk.Entry(port_frame, textvariable=self.port_display_var, width=10, font=('Courier New', 10))
        self.port_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 控制按钮
        button_frame = ttk.Frame(port_frame)
        button_frame.pack(side=tk.LEFT, padx=10)
        
        self.start_btn = ttk.Button(button_frame, text="启动服务", command=self.start_server, width=10)
        self.start_btn.pack(side=tk.LEFT, padx=2)
        
        self.stop_btn = ttk.Button(button_frame, text="停止服务", command=self.stop_server, width=10, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        
        # 状态显示区域
        status_frame = ttk.Frame(control_box)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="状态: ", font=('Arial', 9, 'bold'), width=6).pack(side=tk.LEFT, padx=5)
        
        # 状态文字
        self.status_var = tk.StringVar()
        self.status_var.set("未运行")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, font=('Arial', 10, 'bold'), foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # 访问地址区域
        access_frame = ttk.LabelFrame(self.control_frame, text="访问地址", padding="10")
        access_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 说明文字
        info_label = ttk.Label(access_frame, text="手机或其他电脑可通过访问以下地址（或扫码）互传文件:", 
                             font=('Arial', 8), wraplength=400, justify=tk.CENTER)
        info_label.pack(fill=tk.X, pady=5)
        
        # 二维码和地址显示
        content_frame = ttk.Frame(access_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=2, padx=2)
        
        # 二维码区域 - 居中对齐
        qr_frame = ttk.Frame(content_frame)
        qr_frame.pack(side=tk.LEFT, padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        self.qr_label = ttk.Label(qr_frame, text="服务器未启动，无法生成二维码", font=('Arial', 9, 'italic'))
        self.qr_label.pack(fill=tk.BOTH, expand=True, anchor=tk.CENTER)
        
        # 地址区域 - 居中对齐
        addr_frame = ttk.Frame(content_frame)
        addr_frame.pack(side=tk.LEFT, padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        # 访问地址显示
        self.address_var = tk.StringVar()
        self.address_var.set("服务器未启动")
        self.address_label = ttk.Label(addr_frame, textvariable=self.address_var, font=('Courier New', 9, 'bold'), 
                                     foreground="blue", relief=tk.SUNKEN, borderwidth=1, padding=5, 
                                     wraplength=180, justify=tk.CENTER)
        self.address_label.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # 复制地址按钮
        copy_frame = ttk.Frame(addr_frame)
        copy_frame.pack(fill=tk.X, pady=5)
        self.copy_btn = ttk.Button(copy_frame, text="复制地址", command=self.copy_address, state=tk.DISABLED, width=10)
        self.copy_btn.pack(anchor=tk.CENTER)
    

    
    def init_config_panel(self):
        # 配置框架
        config_box = ttk.LabelFrame(self.config_frame, text="服务器配置", padding="10")
        config_box.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 端口配置
        ttk.Label(config_box, text="服务器端口: ", width=12, font=('Arial', 9, 'bold')).grid(row=0, column=0, padx=8, pady=5, sticky=tk.W)
        self.port_var = tk.StringVar()
        port_entry = ttk.Entry(config_box, textvariable=self.port_var, width=25, font=('Arial', 9))
        port_entry.grid(row=0, column=1, padx=8, pady=5, sticky=tk.W+tk.E)
        
        # 上传目录配置
        ttk.Label(config_box, text="上传目录: ", width=12, font=('Arial', 9, 'bold')).grid(row=1, column=0, padx=8, pady=5, sticky=tk.W)
        self.upload_folder_var = tk.StringVar()
        upload_entry = ttk.Entry(config_box, textvariable=self.upload_folder_var, state='readonly', width=25, font=('Arial', 9))
        upload_entry.grid(row=1, column=1, padx=8, pady=5, sticky=tk.W+tk.E)
        
        # 添加选择目录按钮
        select_folder_btn = ttk.Button(config_box, text="选择目录", command=self.select_upload_folder, width=10)
        select_folder_btn.grid(row=1, column=2, padx=8, pady=5, sticky=tk.E)
        
        # 最大文件大小配置
        ttk.Label(config_box, text="最大文件大小 (MB): ", width=15, font=('Arial', 9, 'bold')).grid(row=2, column=0, padx=8, pady=5, sticky=tk.W)
        self.max_size_var = tk.StringVar()
        size_entry = ttk.Entry(config_box, textvariable=self.max_size_var, width=25, font=('Arial', 9))
        size_entry.grid(row=2, column=1, padx=8, pady=5, sticky=tk.W+tk.E)
        
        # 调试模式配置
        ttk.Label(config_box, text="调试模式: ", width=12, font=('Arial', 9, 'bold')).grid(row=3, column=0, padx=8, pady=5, sticky=tk.W)
        self.debug_var = tk.BooleanVar()
        debug_check = ttk.Checkbutton(config_box, variable=self.debug_var)
        debug_check.grid(row=3, column=1, padx=8, pady=5, sticky=tk.W)
        
        # 配置列权重，使输入框自适应宽度
        config_box.columnconfigure(1, weight=1)
        
        # 颜色配置
        colors_frame = ttk.LabelFrame(self.config_frame, text="网站颜色配置", padding="10")
        colors_frame.pack(fill=tk.BOTH, pady=5)
        
        # 主题选择区域
        ttk.Label(colors_frame, text="选择主题: ", width=12, font=('Arial', 9, 'bold')).grid(row=0, column=0, padx=8, pady=5, sticky=tk.W)
        
        # 创建主题变量
        self.theme_var = tk.StringVar(value="default")
        
        # 创建主题单选框组
        for i, (theme_name, theme_colors) in enumerate(self.themes.items()):
            # 将主题名称转换为中文显示
            theme_display_name = {
                "default": "默认主题",
                "dark": "深色主题",
                "vibrant": "活力主题",
                "minimal": "简约主题",
                "pastel": "柔和主题"
            }.get(theme_name, theme_name)
            
            # 创建单选按钮
            theme_radio = ttk.Radiobutton(
                colors_frame,
                text=theme_display_name,
                variable=self.theme_var,
                value=theme_name
            )
            theme_radio.grid(row=i, column=1, padx=8, pady=2, sticky=tk.W)
        
        # 配置列权重
        colors_frame.columnconfigure(1, weight=1)
        
        # 保存按钮
        save_frame = ttk.Frame(self.config_frame, padding="10")
        save_frame.pack(fill=tk.X, pady=5)
        
        self.save_btn = ttk.Button(save_frame, text="保存配置", command=self.save_config, width=12)
        self.save_btn.pack(side=tk.RIGHT, padx=5)
        
    def load_config(self):
        # 加载配置
        global config
        self.port_var.set(str(config.get('port', 5000)))
        self.upload_folder_var.set(config.get('upload_folder', 'uploads'))
        self.max_size_var.set(str(config.get('max_content_length', 100)))
        self.debug_var.set(config.get('debug', False))
        
        # 加载颜色配置并选择对应的主题
        current_colors = config.get('colors', {})
        
        # 默认使用default主题
        selected_theme = "default"
        
        # 查找匹配的主题
        for theme_name, theme_colors in self.themes.items():
            match = True
            for color_key, color_value in theme_colors.items():
                if current_colors.get(color_key) != color_value:
                    match = False
                    break
            if match:
                selected_theme = theme_name
                break
        
        # 设置选中的主题
        self.theme_var.set(selected_theme)
    
    def select_upload_folder(self):
        # 打开文件选择对话框选择上传目录
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            # 设置选择的目录到变量中
            self.upload_folder_var.set(folder_selected)
    
    def save_config(self):
        # 保存配置
        try:
            # 获取选中的主题
            selected_theme = self.theme_var.get()
            
            new_config = {
                'port': int(self.port_var.get()),
                'upload_folder': self.upload_folder_var.get(),
                'max_content_length': int(self.max_size_var.get()),
                'debug': self.debug_var.get(),
                'colors': self.themes.get(selected_theme, self.themes['default'])
            }
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(new_config, f, indent=2)
            
            # 更新全局配置
            global config, UPLOAD_FOLDER
            config = new_config
            UPLOAD_FOLDER = config['upload_folder']
            
            # 只有在服务器模式下（app不为None）才更新Flask配置
            if app is not None:
                app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
                app.config['MAX_CONTENT_LENGTH'] = config['max_content_length'] * 1024 * 1024
            
            messagebox.showinfo("成功", "配置已保存！")
        except Exception as e:
            messagebox.showerror("错误", "保存配置失败: {}".format(str(e)))
    
    def generate_qr_code(self, url):
        # 生成二维码
        try:
            # 创建二维码对象
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=5,  # 适合当前界面的方块大小
                border=1,     # 合适的边框
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            # 生成图片
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 调整二维码图片尺寸以适应优化后的界面
            img = img.resize((120, 120), Image.LANCZOS)
            
            # 转换为Tkinter可用的图片格式
            self.qr_img = ImageTk.PhotoImage(img)
            
            # 更新二维码显示
            self.qr_label.config(image=self.qr_img, text="")
            self.qr_label.image = self.qr_img  # 保持引用
            
        except Exception as e:
            messagebox.showerror("错误", "生成二维码失败: {}".format(str(e)))
    
    def get_all_local_ips(self):
        # 获取所有本地IP地址
        ips = []
        try:
            # 方法1: 使用psutil获取所有网络接口的IP地址（更可靠）
            import psutil
            
            # 获取所有网络接口的信息
            net_if_addrs = psutil.net_if_addrs()
            
            for interface, addresses in net_if_addrs.items():
                # 过滤出IPv4地址
                for addr in addresses:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        # 排除环回地址和私有保留地址
                        if ip != '127.0.0.1' and not ip.startswith('169.254.'):
                            ips.append(ip)
            
            # 方法2: 如果psutil获取失败，使用传统方法作为备用
            if not ips:
                hostname = socket.gethostname()
                addresses = socket.getaddrinfo(hostname, None)
                
                for addr in addresses:
                    ip = addr[4][0]
                    if addr[0] == socket.AF_INET and ip != '127.0.0.1':
                        ips.append(ip)
            
            # 方法3: 尝试获取当前网络接口的IP（通过连接外部服务器）
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                current_ip = s.getsockname()[0]
                s.close()
                
                if current_ip and current_ip not in ips:
                    ips.append(current_ip)
            except:
                pass
            
            # 去重并按优先级排序（当前网络IP优先）
            ips = list(set(ips))
            
            # 如果有current_ip，将其移到列表开头
            if 'current_ip' in locals() and current_ip in ips:
                ips.remove(current_ip)
                ips.insert(0, current_ip)
            
        except Exception as e:
            print("获取本地IP地址失败: {}".format(str(e)))
        
        return ips
    
    def start_server(self):
        # 启动服务器
        try:
            # 读取端口输入
            port = int(self.port_display_var.get())
            
            # 检查端口是否为特权端口（1-1023）
            if 1 <= port <= 1023:
                # 提示用户需要管理员权限
                result = messagebox.askyesno("警告", "您正在使用特权端口（1-1023），需要管理员权限才能启动服务器。\n\n继续启动吗？")
                if not result:
                    return
            
            # 更新配置
            global config
            config['port'] = port
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            # 确保上传目录存在
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            
            # 启动服务器进程，确保使用相同的Python解释器
            python_path = sys.executable
            self.server_process = subprocess.Popen([
                python_path, __file__, '--run-server'
            ])
            logger.info('已启动服务器进程，PID: %s, Python路径: %s', self.server_process.pid, python_path)
            
            self.server_running = True
            self.status_var.set("运行中")
            self.status_label.config(foreground="green")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.port_entry.config(state='readonly')
            
            # 获取所有本地IP地址
            local_ips = self.get_all_local_ips()
            
            # 更新访问地址
            if local_ips:
                main_ip = local_ips[0]
                url = "http://{}:{}".format(main_ip, port)
                self.address_var.set(url)
                
                # 生成二维码
                self.generate_qr_code(url)
            
            # 启用复制按钮
            self.copy_btn.config(state=tk.NORMAL)
            
            messagebox.showinfo("成功", "服务器已启动！")
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的端口号！")
        except Exception as e:
            messagebox.showerror("错误", "启动服务器失败: {}".format(str(e)))
    
    def stop_server(self):
        # 停止服务器
        if self.server_process and self.server_running:
            try:
                logger.info("=== 开始停止服务器进程 ===")
                logger.info("主进程PID: %s", self.server_process.pid)
                
                # 尝试获取父进程对象，添加进程存在性检查
                try:
                    parent = psutil.Process(self.server_process.pid)
                except psutil.NoSuchProcess:
                    logger.warning("进程 %s 已不存在", self.server_process.pid)
                    # 直接清理状态并返回
                    self.server_running = False
                    self.server_process = None
                    self.status_var.set("未运行")
                    self.status_label.config(foreground="red")
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    self.port_entry.config(state='normal')
                    self.qr_label.config(image="", text="服务器未启动，无法生成二维码")
                    self.address_var.set("服务器未启动")
                    self.copy_btn.config(state=tk.DISABLED)
                    messagebox.showinfo("信息", "服务器进程已不存在，可能已被手动终止")
                    return
                
                # 获取并终止所有子进程
                try:
                    children = parent.children(recursive=True)  # 获取所有子进程
                    logger.info("找到 %s 个子进程", len(children))
                    for child in children:
                        try:
                            logger.info("终止子进程: PID=%s, 名称=%s", child.pid, child.name())
                            child.terminate()  # 终止所有子进程
                        except psutil.NoSuchProcess:
                            logger.info("子进程 %s 已不存在", child.pid)
                    
                    # 等待子进程终止
                    logger.info("等待子进程终止...")
                    terminated, still_alive = psutil.wait_procs(children, timeout=3)
                    
                    logger.info("已终止 %s 个子进程，仍有 %s 个子进程存活", len(terminated), len(still_alive))
                    for child in still_alive:
                        try:
                            logger.warning("子进程 %s 仍在运行，将强制终止", child.pid)
                            child.kill()
                        except psutil.NoSuchProcess:
                            logger.info("子进程 %s 已不存在", child.pid)
                except psutil.NoSuchProcess:
                    logger.warning("父进程 %s 已不存在，无法管理子进程", self.server_process.pid)
                
                # 终止主进程
                logger.info("终止主进程: PID=%s", self.server_process.pid)
                try:
                    self.server_process.terminate()
                    
                    logger.info("等待主进程终止...")
                    try:
                        self.server_process.wait(timeout=5)
                        logger.info("主进程已成功终止")
                    except subprocess.TimeoutExpired:
                        logger.warning("主进程超时未终止，将强制终止")
                        try:
                            parent = psutil.Process(self.server_process.pid)
                            parent.kill()
                        except psutil.NoSuchProcess:
                            logger.info("主进程 %s 已不存在", self.server_process.pid)
                except OSError as e:
                    logger.warning("终止主进程失败: %s", str(e))
                
                # 再次检查并终止可能遗漏的进程
                logger.info("再次检查并终止可能遗漏的进程...")
                try:
                    parent = psutil.Process(self.server_process.pid)
                    # 如果进程仍然存在，再次尝试终止
                    logger.info("再次终止主进程: PID=%s", parent.pid)
                    parent.kill()
                except psutil.NoSuchProcess:
                    logger.info("进程 %s 已不存在", self.server_process.pid)
                
                # 验证进程是否已终止
                process_terminated = False
                try:
                    psutil.Process(self.server_process.pid)
                    logger.warning("警告: 进程 %s 仍在运行", self.server_process.pid)
                except psutil.NoSuchProcess:
                    logger.info("进程 %s 已完全终止", self.server_process.pid)
                    process_terminated = True
                
                # 查找并终止所有监听指定端口的进程（解决Flask工作进程未终止的问题）
                logger.info("查找并终止所有监听端口 %s 的进程...", config['port'])
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        # 使用connections()方法获取连接信息，而不是在attrs中指定
                        for conn in proc.net_connections(kind='inet'):
                            if conn.laddr.port == config['port']:
                                logger.info("发现进程 %s (%s) 正在监听端口 %s，准备终止", proc.pid, proc.name(), conn.laddr.port)
                                if proc.pid != os.getpid():  # 不要终止当前进程
                                    proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                        continue
                
                logger.info("端口 %s 的进程清理完成", config['port'])
                
                self.server_running = False
                self.status_var.set("未运行")
                self.status_label.config(foreground="red")
                self.start_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.DISABLED)
                self.port_entry.config(state='normal')
                
                # 重置二维码显示
                self.qr_label.config(image="", text="服务器未启动，无法生成二维码")
                
                # 重置地址显示
                self.address_var.set("服务器未启动")
                
                # 禁用复制按钮
                self.copy_btn.config(state=tk.DISABLED)
                
                # 清除进程引用
                self.server_process = None
                
                messagebox.showinfo("成功", "服务器已停止！")
                print("=== 服务器停止完成 ===")
                
            except subprocess.TimeoutExpired:
                # 超时后强制终止所有进程
                logger.info("\n=== 服务器停止超时，开始强制终止 ===")
                try:
                    parent = psutil.Process(self.server_process.pid)
                    logger.warning("强制终止主进程: PID=%s", parent.pid)
                    parent.kill()
                    
                    # 强制终止所有子进程
                    children = parent.children(recursive=True)
                    logger.warning("强制终止 %s 个子进程", len(children))
                    for child in children:
                        try:
                            logger.warning("强制终止子进程: PID=%s", child.pid)
                            child.kill()
                        except psutil.NoSuchProcess:
                            logger.info("子进程 %s 已不存在", child.pid)
                except psutil.NoSuchProcess:
                    logger.info("进程已不存在")
                except Exception as e:
                    logger.error("强制终止进程时发生错误: %s", str(e))
                
                # 查找并终止所有监听指定端口的进程（解决Flask工作进程未终止的问题）
                logger.info("查找并终止所有监听端口 %s 的进程...", config['port'])
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        # 使用net_connections()方法获取连接信息，而不是在attrs中指定
                        for conn in proc.net_connections(kind='inet'):
                            if conn.laddr.port == config['port']:
                                logger.info("发现进程 %s (%s) 正在监听端口 %s，准备终止", proc.pid, proc.name(), conn.laddr.port)
                                if proc.pid != os.getpid():  # 不要终止当前进程
                                    proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                        continue
                
                logger.info("端口 %s 的进程清理完成", config['port'])
                
                # 清除进程引用
                self.server_process = None
                self.server_running = False
                self.status_var.set("未运行")
                self.status_label.config(foreground="red")
                self.start_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.DISABLED)
                self.port_entry.config(state='normal')
                self.qr_label.config(image="", text="服务器未启动，无法生成二维码")
                self.address_var.set("服务器未启动")
                self.copy_btn.config(state=tk.DISABLED)
                
                messagebox.showinfo("成功", "服务器已强制停止！")
                
            except Exception as e:
                print("\n=== 停止服务器失败: {} ===".format(str(e)))
                messagebox.showerror("错误", "停止服务器失败: {}".format(str(e)))
                # 即使发生异常，也要清除进程引用
                self.server_process = None
                self.server_running = False
    
    def copy_address(self):
        # 复制当前地址到剪贴板
        try:
            # 获取当前地址
            current_address = self.address_var.get()
            
            # 检查地址是否有效
            if current_address != "服务器未启动":
                # 复制到剪贴板
                self.root.clipboard_clear()
                self.root.clipboard_append(current_address)
                self.root.update()  # 保持剪贴板内容
                
                messagebox.showinfo("成功", "已复制地址: {}".format(current_address))
            
        except Exception as e:
            messagebox.showerror("错误", "复制地址失败: {}".format(str(e)))
    
    def restart_server(self):
        # 重启服务器
        self.stop_server()
        time.sleep(1)
        self.start_server()

if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='文件传输服务器')
    parser.add_argument('--run-server', action='store_true', help='以实际文件传输服务器模式运行')
    args = parser.parse_args()
    
    if args.run_server:
        # 以实际文件传输服务器模式运行
        # 获取本地IP地址
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        
        print("\n文件传输服务器启动成功！")
        print("访问地址: http://{}:{}".format(local_ip, config['port']))
        print("在手机或其他设备上访问上述地址即可进行文件传输")
        print("按 Ctrl+C 停止服务器\n")
        
        app.run(host='0.0.0.0', port=config['port'], debug=config['debug'])
    else:
        # 以GUI模式运行
        print("\n启动服务器GUI控制面板...")
        root = tk.Tk()
        server_gui = ServerGUI(root)
        root.mainloop()
