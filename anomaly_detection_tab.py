import sys
import os
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QPushButton, QLabel, 
                             QTextEdit, QFileDialog, QMessageBox, 
                             QScrollArea, QFrame, QProgressBar, QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QPixmap, QFont
from utils.ssh_client_anomaly_detection import SSHClient
import tempfile
import shutil
import json

# 设置日志
logger = logging.getLogger(__name__)

class ImageProcessingThread(QThread):
    """图片处理线程"""
    finished = pyqtSignal(str, str, str)  # 处理完成信号，传递三个结果文件路径
    error = pyqtSignal(str)               # 错误信号
    progress = pyqtSignal(str)            # 进度信号
    
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        
    def run(self):
        try:
            self.progress.emit("正在连接远程服务器...")
            ssh_client = SSHClient()
            self.progress.emit("正在上传图片到远程服务器...")
            self.progress.emit("正在处理图片...")
            
            # 调用SSH客户端处理图片
            local_result_pre_image, local_result_heat_map, local_result_json = ssh_client.process_images(self.image_path)
            
            self.finished.emit(local_result_pre_image, local_result_heat_map, local_result_json)
            
        except Exception as e:
            error_msg = f"图片处理失败: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)

class AnomalyDetectionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.image_path = None  # 存储上传的图片路径
        self.current_results = None  # 当前处理结果文件路径
        self.processing_thread = None  # 处理线程
        
        self.init_ui()
        self.setup_logging()
        
    def init_ui(self):
        """初始化用户界面"""
        # 主布局 - 垂直分割
        main_layout = QVBoxLayout(self)
        
        # 创建上下分割器
        main_splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(main_splitter)
        
        # 上半部分 - 图片处理区域
        self.create_image_processing_area(main_splitter)
        
        # 下半部分 - 日志区域
        self.create_log_area(main_splitter)
        
        # 设置分割器比例
        main_splitter.setSizes([700, 200])
        
    def create_image_processing_area(self, parent_splitter):
        """创建图片处理区域"""
        # 创建上半部分容器
        image_frame = QFrame()
        image_frame.setFrameStyle(QFrame.StyledPanel)
        
        # 创建水平布局
        image_layout = QHBoxLayout(image_frame)
        
        # 创建左右分割器
        image_splitter = QSplitter(Qt.Horizontal)
        image_layout.addWidget(image_splitter)
        
        # 左侧 - 图片上传区域
        self.create_upload_area(image_splitter)
        
        # 右侧 - 图片展示区域
        self.create_display_area(image_splitter)
        
        # 设置左右分割比例
        image_splitter.setSizes([400, 1000])
        
        parent_splitter.addWidget(image_frame)
        
    def create_upload_area(self, parent_splitter):
        """创建图片上传区域"""
        # 左侧容器
        upload_frame = QFrame()
        upload_frame.setFrameStyle(QFrame.StyledPanel)
        upload_layout = QVBoxLayout(upload_frame)
        
        # 标题
        title_label = QLabel("图片上传区域")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        upload_layout.addWidget(title_label)
        
        # 上传按钮
        self.upload_btn = QPushButton("选择图片")
        self.upload_btn.clicked.connect(self.select_image)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        upload_layout.addWidget(self.upload_btn)
        
        # 当前图片显示区域
        image_info_frame = QFrame()
        image_info_frame.setFrameStyle(QFrame.StyledPanel)
        image_info_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
        """)
        image_info_layout = QVBoxLayout(image_info_frame)
        image_info_layout.setContentsMargins(10, 10, 10, 10)
        
        self.current_image_label = QLabel("当前图片:")
        self.current_image_label.setFont(QFont("Arial", 10, QFont.Bold))
        image_info_layout.addWidget(self.current_image_label)
        
        self.image_name_label = QLabel("未选择图片")
        self.image_name_label.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        self.image_name_label.setWordWrap(True)
        image_info_layout.addWidget(self.image_name_label)
        
        image_info_frame.setMaximumHeight(120)
        image_info_frame.setMinimumHeight(80)
        upload_layout.addWidget(image_info_frame)
        
        # 清空按钮
        self.clear_btn = QPushButton("清空图片")
        self.clear_btn.clicked.connect(self.clear_image)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
        """)
        upload_layout.addWidget(self.clear_btn)
        
        # 处理按钮
        self.process_btn = QPushButton("开始处理")
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover:enabled {
                background-color: #1976D2;
            }
            QPushButton:pressed:enabled {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        upload_layout.addWidget(self.process_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        upload_layout.addWidget(self.progress_bar)
        
        # 添加弹性空间
        upload_layout.addStretch()
        
        parent_splitter.addWidget(upload_frame)
        
    def create_display_area(self, parent_splitter):
        """创建图片展示区域"""
        # 右侧容器
        display_frame = QFrame()
        display_frame.setFrameStyle(QFrame.StyledPanel)
        display_layout = QVBoxLayout(display_frame)
        
        # 标题和刷新按钮
        header_layout = QHBoxLayout()
        title_label = QLabel("处理结果展示")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        header_layout.addWidget(title_label)
        
        self.refresh_btn = QPushButton("刷新页面")
        self.refresh_btn.clicked.connect(self.refresh_page)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
        """)
        header_layout.addWidget(self.refresh_btn)
        
        display_layout.addLayout(header_layout)
        
        # 创建标签页显示不同类型的结果
        self.result_tabs = QTabWidget()
        self.result_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                color: #333;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #2196F3;
                border-bottom: 2px solid #2196F3;
            }
            QTabBar::tab:hover {
                background-color: #e0e0e0;
            }
        """)
        
        # 预测结果标签页
        self.prediction_tab = self.create_image_tab("预测结果")
        self.result_tabs.addTab(self.prediction_tab, "预测结果")
        
        # 热力图标签页
        self.heatmap_tab = self.create_image_tab("热力图")
        self.result_tabs.addTab(self.heatmap_tab, "热力图")
        
        # JSON结果标签页
        self.json_tab = self.create_json_tab()
        self.result_tabs.addTab(self.json_tab, "JSON结果")
        
        display_layout.addWidget(self.result_tabs)
        
        parent_splitter.addWidget(display_frame)
        
    def create_image_tab(self, tab_name):
        """创建图片显示标签页"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # 图片显示区域
        image_display = QLabel()
        image_display.setAlignment(Qt.AlignCenter)
        image_display.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                color: #666;
                font-size: 14px;
            }
        """)
        image_display.setMinimumSize(400, 300)
        image_display.setText(f"暂无{tab_name}")
        
        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(image_display)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        return tab_widget
        
    def create_json_tab(self):
        """创建JSON结果显示标签页"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # JSON文本显示区域
        json_display = QTextEdit()
        json_display.setReadOnly(True)
        json_display.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                color: #333;
            }
        """)
        json_display.setMinimumSize(400, 300)
        json_display.setText("暂无JSON结果")
        layout.addWidget(json_display)
        
        return tab_widget
        
    def create_log_area(self, parent_splitter):
        """创建日志区域"""
        # 日志容器
        log_frame = QFrame()
        log_frame.setFrameStyle(QFrame.StyledPanel)
        log_layout = QVBoxLayout(log_frame)
        
        # 标题
        log_title = QLabel("系统日志")
        log_title.setFont(QFont("Arial", 12, QFont.Bold))
        log_layout.addWidget(log_title)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setMinimumHeight(150)
        log_layout.addWidget(self.log_text)
        
        parent_splitter.addWidget(log_frame)
        
    def setup_logging(self):
        """设置日志系统"""
        # 创建自定义日志处理器
        self.log_handler = LogHandler()
        self.log_handler.log_signal.connect(self.append_log)
        
        # 获取根日志器并添加处理器
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(logging.INFO)
        
        # 记录启动信息
        logger.info("异常检测系统启动")
        
    def select_image(self):
        """选择图片文件"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.gif *.tiff)"
        )
        
        if file_path:
            # 验证图片格式
            if self.validate_image_format(file_path):
                self.image_path = file_path
                self.image_name_label.setText(os.path.basename(file_path))
                self.image_name_label.setStyleSheet("color: black; font-weight: bold;")
                self.update_process_button_state()
                logger.info(f"选择了图片: {os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "格式错误", f"文件 {os.path.basename(file_path)} 不是有效的图片格式")
            
    def validate_image_format(self, file_path):
        """验证图片格式"""
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']
        _, ext = os.path.splitext(file_path.lower())
        return ext in valid_extensions
        
    def clear_image(self):
        """清空图片"""
        self.image_path = None
        self.image_name_label.setText("未选择图片")
        self.image_name_label.setStyleSheet("color: gray; font-style: italic;")
        self.update_process_button_state()
        logger.info("已清空图片")
        
    def update_process_button_state(self):
        """更新处理按钮状态"""
        if self.image_path is not None:
            self.process_btn.setEnabled(True)
            self.process_btn.setText("开始处理")
        else:
            self.process_btn.setEnabled(False)
            self.process_btn.setText("请先选择图片")
            
    def start_processing(self):
        """开始处理图片"""
        if self.image_path is None:
            QMessageBox.warning(self, "未选择图片", "请先选择一张图片")
            return
            
        # 禁用处理按钮
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        logger.info(f"开始处理图片: {os.path.basename(self.image_path)}")
        
        # 创建并启动处理线程
        self.processing_thread = ImageProcessingThread(self.image_path)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.error.connect(self.on_processing_error)
        self.processing_thread.progress.connect(self.on_processing_progress)
        self.processing_thread.start()
        
    def on_processing_finished(self, prediction_path, heatmap_path, json_path):
        """处理完成回调"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        
        # 保存结果路径
        self.current_results = {
            'prediction': prediction_path,
            'heatmap': heatmap_path,
            'json': json_path
        }
        
        # 显示结果
        self.display_results()
        
        logger.info(f"图片处理完成")
        logger.info(f"预测结果: {prediction_path}")
        logger.info(f"热力图: {heatmap_path}")
        logger.info(f"JSON结果: {json_path}")
        
    def on_processing_error(self, error_msg):
        """处理错误回调"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        
        logger.error(error_msg)
        QMessageBox.critical(self, "处理失败", error_msg)
        
    def on_processing_progress(self, progress_msg):
        """处理进度回调"""
        logger.info(progress_msg)
        
    def display_results(self):
        """显示处理结果"""
        if not self.current_results:
            return
            
        # 显示预测结果
        self.display_image_result(self.prediction_tab, self.current_results['prediction'], "预测结果")
        
        # 显示热力图
        self.display_image_result(self.heatmap_tab, self.current_results['heatmap'], "热力图")
        
        # 显示JSON结果
        self.display_json_result()
        
    def display_image_result(self, tab_widget, image_path, result_type):
        """显示图片结果"""
        try:
            if os.path.exists(image_path):
                # 获取标签页中的图片显示组件
                scroll_area = tab_widget.findChild(QScrollArea)
                if scroll_area:
                    image_display = scroll_area.widget()
                    if isinstance(image_display, QLabel):
                        pixmap = QPixmap(image_path)
                        if not pixmap.isNull():
                            # 缩放图片以适应显示区域
                            scaled_pixmap = pixmap.scaled(
                                image_display.size(), 
                                Qt.KeepAspectRatio, 
                                Qt.SmoothTransformation
                            )
                            image_display.setPixmap(scaled_pixmap)
                        else:
                            image_display.setText(f"无法加载{result_type}图片")
                    else:
                        image_display.setText(f"无法加载{result_type}图片")
            else:
                # 获取标签页中的图片显示组件
                scroll_area = tab_widget.findChild(QScrollArea)
                if scroll_area:
                    image_display = scroll_area.widget()
                    if isinstance(image_display, QLabel):
                        image_display.setText(f"{result_type}文件不存在")
        except Exception as e:
            logger.error(f"显示{result_type}失败: {str(e)}")
            
    def display_json_result(self):
        """显示JSON结果"""
        try:
            if self.current_results and os.path.exists(self.current_results['json']):
                with open(self.current_results['json'], 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                # 格式化JSON数据
                formatted_json = json.dumps(json_data, ensure_ascii=False, indent=2)
                
                # 获取JSON标签页中的文本显示组件
                json_display = self.json_tab.findChild(QTextEdit)
                if json_display:
                    json_display.setText(formatted_json)
            else:
                json_display = self.json_tab.findChild(QTextEdit)
                if json_display:
                    json_display.setText("暂无JSON结果")
        except Exception as e:
            logger.error(f"显示JSON结果失败: {str(e)}")
            json_display = self.json_tab.findChild(QTextEdit)
            if json_display:
                json_display.setText(f"JSON结果显示错误: {str(e)}")
            
    def refresh_page(self):
        """刷新页面"""
        # 清空图片
        self.clear_image()
        
        # 清空结果
        self.current_results = None
        
        # 清空结果显示
        self.clear_result_displays()
        
        logger.info("页面已刷新")
        
    def clear_result_displays(self):
        """清空结果显示"""
        # 清空预测结果
        self.clear_image_display(self.prediction_tab, "预测结果")
        
        # 清空热力图
        self.clear_image_display(self.heatmap_tab, "热力图")
        
        # 清空JSON结果
        json_display = self.json_tab.findChild(QTextEdit)
        if json_display:
            json_display.setText("暂无JSON结果")
            
    def clear_image_display(self, tab_widget, result_type):
        """清空图片显示"""
        scroll_area = tab_widget.findChild(QScrollArea)
        if scroll_area:
            image_display = scroll_area.widget()
            if isinstance(image_display, QLabel):
                image_display.clear()
                image_display.setText(f"暂无{result_type}")
        
    def append_log(self, message):
        """添加日志到界面"""
        self.log_text.append(message)
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 关闭日志处理器
        if hasattr(self, 'log_handler'):
            # 先从root logger中移除handler，避免atexit时的错误
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)
            self.log_handler.close()
        event.accept()

class LogHandler(logging.Handler, QObject):
    """自定义日志处理器，用于将日志显示在界面上"""
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self._closed = False
    
    def emit(self, record):
        if not self._closed:
            try:
                log_message = self.format(record)
                self.log_signal.emit(log_message)
            except RuntimeError:
                # Qt对象已被删除，忽略错误
                pass
    
    def close(self):
        """关闭处理器"""
        self._closed = True
        super().close()

def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("异常检测系统")
    window.setGeometry(100, 100, 1400, 900)
    
    # 创建中央部件
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    # 创建布局
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    
    # 添加异常检测组件
    anomaly_detection_widget = AnomalyDetectionWidget()
    layout.addWidget(anomaly_detection_widget)
    
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
