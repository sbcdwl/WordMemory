"""
导入对话框 - 选择 JSON 文件导入单词
"""

import os
import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QFrame,
    QProgressBar, QTextEdit, QMessageBox, QGroupBox,
    QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.controllers.importer import Importer


class ImportWorker(QThread):
    """导入工作线程（避免UI卡顿）"""
    
    # 信号：进度更新、完成、错误
    progress = pyqtSignal(int, str)  # 进度值, 状态文字
    finished = pyqtSignal(dict)      # 统计结果
    error = pyqtSignal(str)          # 错误信息
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        """执行导入"""
        try:
            self.progress.emit(0, "正在解析 JSON 文件...")
            
            importer = Importer()
            stats = importer.import_from_file(self.file_path)
            
            self.progress.emit(100, "导入完成！")
            self.finished.emit(stats)
            
        except Exception as e:
            self.error.emit(str(e))


class ImportDialog(QDialog):
    """导入对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.imported_book_id = None
        
        self.init_ui()
        self._apply_styles()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("导入词书")
        self.setMinimumSize(600, 450)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # ===== 标题 =====
        title_label = QLabel("📂 导入词书")
        title_label.setFont(QFont("", 16, QFont.Bold))
        layout.addWidget(title_label)
        
        # ===== 文件选择区域 =====
        file_group = QGroupBox("选择 JSON 文件")
        file_layout = QVBoxLayout(file_group)
        
        # 文件路径行
        path_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("请选择 JSON 文件...")
        self.file_path_edit.setReadOnly(True)
        path_layout.addWidget(self.file_path_edit)
        
        self.browse_btn = QPushButton("📁 浏览...")
        self.browse_btn.clicked.connect(self._on_browse)
        self.browse_btn.setFixedWidth(100)
        path_layout.addWidget(self.browse_btn)
        
        file_layout.addLayout(path_layout)
        layout.addWidget(file_group)
        
        # ===== 预览区域 =====
        self.preview_group = QGroupBox("📋 预览信息")
        self.preview_group.setVisible(False)
        preview_layout = QGridLayout(self.preview_group)
        preview_layout.setSpacing(8)
        
        # 词书ID
        preview_layout.addWidget(QLabel("词书ID:"), 0, 0)
        self.preview_book_id = QLabel("-")
        self.preview_book_id.setStyleSheet("font-weight: bold; color: #2563eb;")
        preview_layout.addWidget(self.preview_book_id, 0, 1)
        
        # 词书名称
        preview_layout.addWidget(QLabel("词书名称:"), 1, 0)
        self.preview_book_name = QLabel("-")
        preview_layout.addWidget(self.preview_book_name, 1, 1)
        
        # 单词数量
        preview_layout.addWidget(QLabel("单词数量:"), 2, 0)
        self.preview_word_count = QLabel("-")
        preview_layout.addWidget(self.preview_word_count, 2, 1)
        
        # 格式
        preview_layout.addWidget(QLabel("格式:"), 3, 0)
        self.preview_format = QLabel("-")
        preview_layout.addWidget(self.preview_format, 3, 1)
        
        layout.addWidget(self.preview_group)
        
        # ===== 进度条 =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # ===== 状态信息 =====
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # ===== 导入结果 =====
        self.result_group = QGroupBox("📊 导入结果")
        self.result_group.setVisible(False)
        result_layout = QVBoxLayout(self.result_group)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(100)
        self.result_text.setStyleSheet("background: #f8fafc; border-radius: 4px;")
        result_layout.addWidget(self.result_text)
        
        layout.addWidget(self.result_group)
        
        # ===== 按钮 =====
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.import_btn = QPushButton("📥 导入")
        self.import_btn.setObjectName("import_btn")
        self.import_btn.setFixedWidth(120)
        self.import_btn.setFixedHeight(40)
        self.import_btn.clicked.connect(self._on_import)
        self.import_btn.setEnabled(False)
        button_layout.addWidget(self.import_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setFixedWidth(100)
        self.close_btn.setFixedHeight(40)
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _on_browse(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 JSON 词库文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
            self._preview_file(file_path)
            self.import_btn.setEnabled(True)
    
    def _preview_file(self, file_path):
        """预览文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 判断格式
            if isinstance(data, dict):
                # 单个单词
                book_id = data.get('bookId', '未知')
                head_word = data.get('headWord', '未知')
                self.preview_book_id.setText(book_id)
                self.preview_book_name.setText(f"单词语料 (含 {head_word})")
                self.preview_word_count.setText("1 个单词")
                self.preview_format.setText("单个单词 (JSON 对象)")
                
            elif isinstance(data, list) and len(data) > 0:
                # 多个单词
                book_id = data[0].get('bookId', '未知')
                word_count = len(data)
                self.preview_book_id.setText(book_id)
                self.preview_book_name.setText(f"词书 (共 {word_count} 个单词)")
                self.preview_word_count.setText(f"{word_count} 个单词")
                self.preview_format.setText("单词列表 (JSON 数组)")
                
            else:
                self.preview_book_id.setText("无法解析")
                self.preview_book_name.setText("格式不支持")
                self.preview_word_count.setText("-")
                self.preview_format.setText("未知格式")
            
            self.preview_group.setVisible(True)
            self.status_label.setText(f"✅ 文件解析成功，准备导入")
            self.status_label.setStyleSheet("color: #16a34a;")
            
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "解析错误", f"JSON 格式错误:\n{str(e)}")
            self.preview_group.setVisible(False)
            self.import_btn.setEnabled(False)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"读取文件失败:\n{str(e)}")
            self.preview_group.setVisible(False)
            self.import_btn.setEnabled(False)
    
    def _on_import(self):
        """执行导入"""
        file_path = self.file_path_edit.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "请选择有效的 JSON 文件")
            return
        
        # 确认导入
        reply = QMessageBox.question(
            self,
            "确认导入",
            f"确定要导入以下词书吗？\n\n{self.preview_book_id.text()}\n{self.preview_book_name.text()}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        # 禁用按钮
        self.import_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        
        # 显示进度
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.result_group.setVisible(False)
        self.status_label.setText("⏳ 正在导入，请稍候...")
        self.status_label.setStyleSheet("color: #2563eb;")
        
        # 启动工作线程
        self.worker = ImportWorker(file_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_import_finished)
        self.worker.error.connect(self._on_import_error)
        self.worker.start()
    
    def _on_progress(self, value, text):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.status_label.setText(f"⏳ {text}")
    
    def _on_import_finished(self, stats):
        """导入完成"""
        self.progress_bar.setValue(100)
        
        # 显示结果
        self.result_group.setVisible(True)
        result_text = f"""
📊 导入统计

总计单词: {stats['total']}
✅ 成功导入: {stats['success']}
⏭️ 已跳过: {stats['skipped']}
❌ 错误: {stats['errors']}
        """
        
        if stats['error_messages']:
            result_text += f"\n\n⚠️ 错误详情:\n" + "\n".join(stats['error_messages'][:5])
            if len(stats['error_messages']) > 5:
                result_text += f"\n... 还有 {len(stats['error_messages']) - 5} 条错误"
        
        self.result_text.setText(result_text)
        
        # 更新状态
        if stats['success'] > 0:
            self.status_label.setText(f"✅ 导入成功！共导入 {stats['success']} 个单词")
            self.status_label.setStyleSheet("color: #16a34a;")
            # 保存导入的词书ID
            if hasattr(self.worker, 'importer') and self.worker.importer.get_book():
                self.imported_book_id = self.worker.importer.get_book().book_id
        else:
            if stats['skipped'] > 0 and stats['errors'] == 0:
                self.status_label.setText(f"⏭️ 所有单词已存在，无需导入")
                self.status_label.setStyleSheet("color: #f59e0b;")
            else:
                self.status_label.setText(f"❌ 导入失败，请检查文件")
                self.status_label.setStyleSheet("color: #dc2626;")
        
        # 恢复按钮
        self.import_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.import_btn.setText("✅ 已完成")
        self.import_btn.setEnabled(False)
    
    def _on_import_error(self, error_msg):
        """导入错误"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ {error_msg}")
        self.status_label.setStyleSheet("color: #dc2626;")
        
        QMessageBox.critical(self, "导入失败", f"导入过程中发生错误:\n{error_msg}")
        
        # 恢复按钮
        self.import_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
    
    def _apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #d0d7e2;
                background-color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f0f2f5;
                border-color: #b0b8c4;
            }
            QPushButton#import_btn {
                background-color: #2563eb;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton#import_btn:hover {
                background-color: #1d4ed8;
            }
            QPushButton#import_btn:disabled {
                background-color: #93c5fd;
            }
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #d0d7e2;
                border-radius: 6px;
                background-color: white;
            }
            QLineEdit:disabled {
                background-color: #f1f5f9;
            }
            QProgressBar {
                border: 1px solid #d0d7e2;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f2f5;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)
    
    def get_imported_book_id(self):
        """获取导入的词书ID"""
        return self.imported_book_id