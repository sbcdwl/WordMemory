"""
主窗口 - 核心学习界面
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QProgressBar,
    QMessageBox, QApplication, QTextEdit, QLineEdit,
    QStackedWidget, QShortcut, QMenuBar, QMenu, QAction,
    QStatusBar, QCheckBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.controllers.scheduler import Scheduler
from src.models.database import db
from src.models.word import Word
from src.models.review_record import ReviewRecord


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化调度器（稍后设置词书）
        self.scheduler = None
        self.current_queue = []  # 当前学习队列
        self.current_index = 0   # 当前学习进度
        self.current_word = None
        self.current_record = None
        self.current_type = None  # 'review' 或 'new'
        self.is_answer_shown = False  # 是否已显示答案
        self.settings = self._load_settings()
        self._review_processed = False  # 防止重复处理
        
        # 初始化UI
        self.init_ui()
        
        # 加载默认词书
        self._load_default_book()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("WordMemory - 背单词")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(self._get_styles())
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 10, 20, 10)
        
        # 1. 菜单栏
        self._create_menu_bar()
        
        # 2. 顶部信息栏
        self._create_top_bar(main_layout)
        
        # 3. 单词卡片（核心区域）
        self._create_card_area(main_layout)
        
        # 4. 操作按钮（评分按钮）
        self._create_action_buttons(main_layout)
        
        # 5. 导航栏
        self._create_navigation(main_layout)
        
        # 6. 状态栏
        self._create_status_bar()
        
        # 7. 快捷键
        self._setup_shortcuts()
        
        # 初始显示空状态或加载单词
        self._update_display()
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        import_action = QAction("导入词书(&I)...", self)
        import_action.triggered.connect(self._on_import)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        
        settings_action = QAction("设置(&S)...", self)
        settings_action.triggered.connect(self._on_settings)
        tools_menu.addAction(settings_action)
        
        stats_action = QAction("统计(&D)...", self)
        stats_action.triggered.connect(self._on_stats)
        tools_menu.addAction(stats_action)
        
        tools_menu.addSeparator()
        
        reset_action = QAction("重置今日进度(&R)", self)
        reset_action.triggered.connect(self._on_reset_today)
        tools_menu.addAction(reset_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _create_top_bar(self, parent_layout):
        """创建顶部信息栏"""
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # 词书名称
        self.book_label = QLabel("词书: 未选择")
        self.book_label.setFont(QFont("", 11, QFont.Bold))
        top_layout.addWidget(self.book_label)
        
        top_layout.addStretch()
        
        # 进度标签
        self.progress_label = QLabel("进度: 0%")
        self.progress_label.setFont(QFont("", 10))
        top_layout.addWidget(self.progress_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFixedHeight(18)
        top_layout.addWidget(self.progress_bar)
        
        parent_layout.addWidget(top_widget)
        
        # 今日统计
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        
        self.today_stats_label = QLabel("今日: 复习 0 词 | 新词 0 词")
        self.today_stats_label.setFont(QFont("", 9))
        stats_layout.addWidget(self.today_stats_label)
        
        stats_layout.addStretch()
        
        self.total_stats_label = QLabel("总计: 0/0")
        self.total_stats_label.setFont(QFont("", 9))
        stats_layout.addWidget(self.total_stats_label)
        
        parent_layout.addWidget(stats_widget)
    
    def _create_card_area(self, parent_layout):
        """创建单词卡片区域"""
        # 卡片容器
        self.card_frame = QFrame()
        self.card_frame.setObjectName("card_frame")
        self.card_frame.setMinimumHeight(300)
        
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setSpacing(15)
        card_layout.setContentsMargins(30, 30, 30, 30)
        
        # 单词显示（堆叠：看词想义模式 vs 拼写模式）
        self.card_stack = QStackedWidget()
        
        # 页面1: 看词想义模式
        self.card_show_page = QWidget()
        show_layout = QVBoxLayout(self.card_show_page)
        show_layout.setSpacing(15)
        
        # 单词/音标
        self.word_label = QLabel("")
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setFont(QFont("", 28, QFont.Bold))
        show_layout.addWidget(self.word_label)
        
        self.phonetic_label = QLabel("")
        self.phonetic_label.setAlignment(Qt.AlignCenter)
        self.phonetic_label.setFont(QFont("", 14))
        self.phonetic_label.setStyleSheet("color: #666;")
        show_layout.addWidget(self.phonetic_label)
        
        show_layout.addStretch()
        
        # 释义（初始隐藏）
        self.meaning_label = QLabel("")
        self.meaning_label.setAlignment(Qt.AlignCenter)
        self.meaning_label.setFont(QFont("", 18))
        self.meaning_label.setWordWrap(True)
        self.meaning_label.hide()
        show_layout.addWidget(self.meaning_label)
        
        # 显示答案按钮
        self.show_answer_btn = QPushButton("👁 显示答案")
        self.show_answer_btn.setFont(QFont("", 12, QFont.Bold))
        self.show_answer_btn.clicked.connect(self._on_show_answer)
        self.show_answer_btn.setFixedHeight(40)
        show_layout.addWidget(self.show_answer_btn)
        
        # 例句（初始隐藏）
        self.example_label = QLabel("")
        self.example_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.example_label.setFont(QFont("", 10))
        self.example_label.setWordWrap(True)
        self.example_label.setStyleSheet("color: #555; padding: 10px; background: #f5f5f5; border-radius: 5px;")
        self.example_label.hide()
        show_layout.addWidget(self.example_label)
        
        # 扩展信息（折叠，初始隐藏）
        self.extra_label = QLabel("")
        self.extra_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.extra_label.setFont(QFont("", 9))
        self.extra_label.setWordWrap(True)
        self.extra_label.setStyleSheet("color: #777; padding: 10px; background: #fafafa; border-radius: 5px;")
        self.extra_label.hide()
        show_layout.addWidget(self.extra_label)
        
        self.card_stack.addWidget(self.card_show_page)
        
        # 页面2: 拼写模式
        self.card_type_page = QWidget()
        type_layout = QVBoxLayout(self.card_type_page)
        type_layout.setSpacing(15)
        
        # 中文释义（题目）
        self.type_question_label = QLabel("")
        self.type_question_label.setAlignment(Qt.AlignCenter)
        self.type_question_label.setFont(QFont("", 20, QFont.Bold))
        type_layout.addWidget(self.type_question_label)
        
        self.type_phonetic_label = QLabel("")
        self.type_phonetic_label.setAlignment(Qt.AlignCenter)
        self.type_phonetic_label.setFont(QFont("", 14))
        self.type_phonetic_label.setStyleSheet("color: #666;")
        type_layout.addWidget(self.type_phonetic_label)
        
        type_layout.addStretch()
        
        # 输入框
        self.type_input = QLineEdit()
        self.type_input.setPlaceholderText("请输入英文拼写...")
        self.type_input.setFont(QFont("", 16))
        self.type_input.setFixedHeight(50)
        self.type_input.returnPressed.connect(self._on_type_submit)
        self.type_input.setEnabled(False)
        type_layout.addWidget(self.type_input)
        
        # 提交按钮
        self.type_submit_btn = QPushButton("提交")
        self.type_submit_btn.setFont(QFont("", 12, QFont.Bold))
        self.type_submit_btn.clicked.connect(self._on_type_submit)
        self.type_submit_btn.setFixedHeight(40)
        self.type_submit_btn.setEnabled(False)
        type_layout.addWidget(self.type_submit_btn)
        
        # 结果显示
        self.type_result_label = QLabel("")
        self.type_result_label.setAlignment(Qt.AlignCenter)
        self.type_result_label.setFont(QFont("", 14))
        self.type_result_label.setWordWrap(True)
        self.type_result_label.hide()
        type_layout.addWidget(self.type_result_label)
        
        # 继续按钮（错误后显示）
        self.type_continue_btn = QPushButton("继续 →")
        self.type_continue_btn.setFont(QFont("", 12, QFont.Bold))
        self.type_continue_btn.clicked.connect(self._on_type_continue)
        self.type_continue_btn.setFixedHeight(40)
        self.type_continue_btn.hide()
        type_layout.addWidget(self.type_continue_btn)
        
        self.card_stack.addWidget(self.card_type_page)
        
        card_layout.addWidget(self.card_stack)
        
        # 当前进度
        self.progress_counter = QLabel("第 0 / 0 词")
        self.progress_counter.setAlignment(Qt.AlignCenter)
        self.progress_counter.setFont(QFont("", 10))
        self.progress_counter.setStyleSheet("color: #888;")
        card_layout.addWidget(self.progress_counter)
        
        parent_layout.addWidget(self.card_frame)
    
    def _create_action_buttons(self, parent_layout):
        """创建操作按钮（评分按钮）"""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setSpacing(10)
        
        # 评分按钮
        self.btn_forgot = QPushButton("忘记")
        self.btn_forgot.setObjectName("btn_forgot")
        self.btn_forgot.clicked.connect(lambda: self._on_review(0))
        self.btn_forgot.setEnabled(False)
        button_layout.addWidget(self.btn_forgot)
        
        self.btn_hard = QPushButton("困难")
        self.btn_hard.setObjectName("btn_hard")
        self.btn_hard.clicked.connect(lambda: self._on_review(2))
        self.btn_hard.setEnabled(False)
        button_layout.addWidget(self.btn_hard)
        
        self.btn_good = QPushButton("记住")
        self.btn_good.setObjectName("btn_good")
        self.btn_good.clicked.connect(lambda: self._on_review(3))
        self.btn_good.setEnabled(False)
        button_layout.addWidget(self.btn_good)
        
        self.btn_easy = QPushButton("容易")
        self.btn_easy.setObjectName("btn_easy")
        self.btn_easy.clicked.connect(lambda: self._on_review(4))
        self.btn_easy.setEnabled(False)
        button_layout.addWidget(self.btn_easy)
        
        self.btn_very_easy = QPushButton("非常容易")
        self.btn_very_easy.setObjectName("btn_very_easy")
        self.btn_very_easy.clicked.connect(lambda: self._on_review(5))
        self.btn_very_easy.setEnabled(False)
        button_layout.addWidget(self.btn_very_easy)
        
        parent_layout.addWidget(button_widget)
    
    def _create_navigation(self, parent_layout):
        """创建导航栏"""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setSpacing(10)
        
        nav_layout.addStretch()
        
        self.btn_prev = QPushButton("⏪ 上一词")
        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_prev.setEnabled(False)
        nav_layout.addWidget(self.btn_prev)
        
        self.btn_next = QPushButton("下一词 ⏩")
        self.btn_next.clicked.connect(self._on_next)
        self.btn_next.setEnabled(False)
        nav_layout.addWidget(self.btn_next)
        
        self.btn_stats = QPushButton("📊 统计")
        self.btn_stats.clicked.connect(self._on_stats)
        nav_layout.addWidget(self.btn_stats)
        
        nav_layout.addStretch()
        
        parent_layout.addWidget(nav_widget)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def _update_display(self):
        """更新显示（加载单词或显示空状态）"""
        if self.current_queue and self.current_index < len(self.current_queue):
            self._show_word(self.current_index)
        elif self.current_queue:
            self._show_complete()
        else:
            self._show_empty_state()
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        # 空格键：显示答案
        self.shortcut_space = QShortcut(QKeySequence("Space"), self)
        self.shortcut_space.activated.connect(self._on_show_answer)
        
        # 左右箭头：切换单词
        self.shortcut_left = QShortcut(QKeySequence("Left"), self)
        self.shortcut_left.activated.connect(self._on_prev)
        
        self.shortcut_right = QShortcut(QKeySequence("Right"), self)
        self.shortcut_right.activated.connect(self._on_next)
        
        # 数字键：评分
        self.shortcut_1 = QShortcut(QKeySequence("1"), self)
        self.shortcut_1.activated.connect(lambda: self._on_review(0))
        
        self.shortcut_2 = QShortcut(QKeySequence("2"), self)
        self.shortcut_2.activated.connect(lambda: self._on_review(2))
        
        self.shortcut_3 = QShortcut(QKeySequence("3"), self)
        self.shortcut_3.activated.connect(lambda: self._on_review(3))
        
        self.shortcut_4 = QShortcut(QKeySequence("4"), self)
        self.shortcut_4.activated.connect(lambda: self._on_review(4))
        
        self.shortcut_5 = QShortcut(QKeySequence("5"), self)
        self.shortcut_5.activated.connect(lambda: self._on_review(5))
    
    def _load_settings(self):
        """加载设置"""
        return {
            'review_mode': db.get_setting('review_mode', 'show_then_check'),
            'show_phonetic': db.get_setting('show_phonetic', 'true') == 'true',
            'max_examples': int(db.get_setting('max_examples_display', '2')),
            'daily_new_words': int(db.get_setting('daily_new_words', '20'))
        }
    
    def _load_default_book(self):
        """加载默认词书"""
        from src.models.book import Book
        books = Book.get_all(active_only=True)
        if books:
            book = books[0]
            self.scheduler = Scheduler(book.book_id)
            self._update_info()
            self._load_today_queue()
        else:
            # 没有词书，显示空状态
            self._show_empty_state()
    
    def _load_today_queue(self):
        """加载今日学习队列"""
        if not self.scheduler:
            return
        
        review_words, new_words = self.scheduler.get_daily_words()
        
        # 构建队列
        self.current_queue = []
        
        # 复习词
        for word in review_words:
            record = ReviewRecord.get_by_word_id(word.id)
            self.current_queue.append({
                'word': word,
                'type': 'review',
                'record': record
            })
        
        # 新词
        for word in new_words:
            record = ReviewRecord.get_by_word_id(word.id)
            self.current_queue.append({
                'word': word,
                'type': 'new',
                'record': record
            })
        
        self.current_index = 0
        
        if self.current_queue:
            self._show_word(0)
        else:
            self._show_complete()
    
    def _show_word(self, index):
        """显示指定索引的单词"""
        if not self.current_queue or index >= len(self.current_queue):
            self._show_complete()
            return
        
        item = self.current_queue[index]
        self.current_word = item['word']
        self.current_record = item['record']
        self.current_type = item['type']
        self.is_answer_shown = False
        self._review_processed = False
        
        # 更新显示模式
        mode = db.get_setting('review_mode', 'show_then_check')
        if mode == 'type_answer':
            self.card_stack.setCurrentIndex(1)  # 拼写模式
            self._show_type_mode()
        else:
            self.card_stack.setCurrentIndex(0)  # 看词想义模式
            self._show_show_mode()
        
        # 更新进度
        self.progress_counter.setText(f"第 {index + 1} / {len(self.current_queue)} 词")
        self.progress_bar.setValue(int((index + 1) / len(self.current_queue) * 100))
        
        # 更新导航按钮
        self.btn_prev.setEnabled(index > 0)
        self.btn_next.setEnabled(index < len(self.current_queue) - 1)
        
        # 更新状态栏
        if self.current_type == 'review':
            self.status_bar.showMessage(f"复习词 {index + 1}/{len(self.current_queue)}")
        else:
            self.status_bar.showMessage(f"新词 {index + 1}/{len(self.current_queue)}")
    
    def _show_show_mode(self):
        """显示看词想义模式"""
        word = self.current_word
        
        # 显示单词
        self.word_label.setText(word.word)
        self.word_label.show()
        
        # 显示音标
        if self.settings.get('show_phonetic', True):
            phonetic = ""
            if word.us_phone:
                phonetic += f"美 /{word.us_phone}/ "
            if word.uk_phone:
                phonetic += f"英 /{word.uk_phone}/"
            self.phonetic_label.setText(phonetic.strip())
            self.phonetic_label.show()
        else:
            self.phonetic_label.hide()
        
        # 隐藏释义
        self.meaning_label.hide()
        
        # 显示答案按钮
        self.show_answer_btn.show()
        self.show_answer_btn.setEnabled(True)
        
        # 隐藏例句
        self.example_label.hide()
        self.extra_label.hide()
        
        # 禁用评分按钮
        self._set_review_buttons_enabled(False)
    
    def _show_type_mode(self):
        """显示拼写模式"""
        word = self.current_word
        
        # 显示中文释义
        self.type_question_label.setText(word.translation)
        
        # 显示音标（提示）
        if self.settings.get('show_phonetic', True):
            phonetic = ""
            if word.us_phone:
                phonetic += f"美 /{word.us_phone}/ "
            if word.uk_phone:
                phonetic += f"英 /{word.uk_phone}/"
            self.type_phonetic_label.setText(phonetic.strip())
            self.type_phonetic_label.show()
        else:
            self.type_phonetic_label.hide()
        
        # 清空输入框
        self.type_input.clear()
        self.type_input.setEnabled(True)
        self.type_input.setFocus()
        
        # 启用提交按钮
        self.type_submit_btn.setEnabled(True)
        
        # 隐藏结果
        self.type_result_label.hide()
        self.type_continue_btn.hide()
        
        # 禁用评分按钮
        self._set_review_buttons_enabled(False)
    
    def _on_show_answer(self):
        """显示答案（看词想义模式）"""
        if not self.current_word or self.is_answer_shown:
            return
        
        word = self.current_word
        self.is_answer_shown = True
        
        # 显示释义
        self.meaning_label.setText(word.translation)
        self.meaning_label.show()
        
        # 显示答案按钮
        self.show_answer_btn.setEnabled(False)
        
        # 显示例句（最多设置的数量）
        examples = word.get_examples()
        if examples and self.settings.get('max_examples', 2) > 0:
            max_display = min(len(examples), self.settings.get('max_examples', 2))
            example_text = "📖 例句:\n"
            for i in range(max_display):
                example_text += f"  • {examples[i]['en']}\n    {examples[i]['cn']}\n"
            if len(examples) > max_display:
                example_text += f"  ... 还有 {len(examples) - max_display} 条"
            self.example_label.setText(example_text.strip())
            self.example_label.show()
        else:
            self.example_label.hide()
        
        # 显示扩展信息（短语/同义词/同根词）- 简化显示
        extra_parts = []
        phrases = word.get_phrases()
        if phrases:
            extra_parts.append(f"📝 短语: {', '.join([p['phrase'] for p in phrases[:3]])}")
        synonyms = word.get_synonyms()
        if synonyms:
            extra_parts.append(f"🔗 同义: {', '.join([s.get('tran', '') for s in synonyms[:2]])}")
        if extra_parts:
            self.extra_label.setText("\n".join(extra_parts))
            self.extra_label.show()
        else:
            self.extra_label.hide()
        
        # 启用评分按钮
        self._set_review_buttons_enabled(True)
    
    def _on_type_submit(self):
        """提交拼写答案"""
        if not self.current_word or self.is_answer_shown:
            return
        
        user_input = self.type_input.text().strip()
        if not user_input:
            return
        
        word = self.current_word
        self.is_answer_shown = True
        
        # 不区分大小写比较
        is_correct = user_input.lower() == word.word.lower()
        
        if is_correct:
            # 拼写正确
            self.type_result_label.setText("✅ 完全正确！")
            self.type_result_label.setStyleSheet("color: green; font-weight: bold;")
            self.type_result_label.show()
            
            # 禁用输入和提交
            self.type_input.setEnabled(False)
            self.type_submit_btn.setEnabled(False)
            
            # 自动跳转（延迟1秒）
            QTimer.singleShot(1000, lambda: self._on_review(4, from_type=True))
        else:
            # 拼写错误
            self.type_result_label.setText(f"❌ 正确拼写: {word.word}")
            self.type_result_label.setStyleSheet("color: red; font-weight: bold;")
            self.type_result_label.show()
            
            # 禁用输入和提交
            self.type_input.setEnabled(False)
            self.type_submit_btn.setEnabled(False)
            
            # 显示继续按钮
            self.type_continue_btn.show()
    
    def _on_type_continue(self):
        """拼写错误后继续"""
        # 记录为"忘记" (quality=0)
        self._on_review(0, from_type=True)
    
    def _on_review(self, quality, from_type=False):
        """处理复习评分"""
        if not self.current_record:
            return
        
        # 如果已经处理过，防止重复
        if self._review_processed:
            return
        self._review_processed = True
        
        # 执行复习
        self.current_record.review(quality)
        
        # 更新进度
        self._update_stats()
        
        # 移动到下一个词
        self._review_processed = False
        if self.current_index < len(self.current_queue) - 1:
            self.current_index += 1
            self._show_word(self.current_index)
        else:
            self._show_complete()
    
    def _set_review_buttons_enabled(self, enabled):
        """启用/禁用评分按钮"""
        self.btn_forgot.setEnabled(enabled)
        self.btn_hard.setEnabled(enabled)
        self.btn_good.setEnabled(enabled)
        self.btn_easy.setEnabled(enabled)
        self.btn_very_easy.setEnabled(enabled)
    
    def _show_empty_state(self):
        """显示空状态"""
        self.word_label.setText("📚 还没有词书")
        self.word_label.setFont(QFont("", 16))
        self.phonetic_label.setText("点击菜单「文件 → 导入词书」开始学习")
        self.phonetic_label.setStyleSheet("color: #888;")
        self.meaning_label.hide()
        self.show_answer_btn.hide()
        self._set_review_buttons_enabled(False)
        self.progress_counter.setText("")
        
        # 清空堆栈
        self.card_stack.setCurrentIndex(0)
    
    def _show_complete(self):
        """显示今日学习完成"""
        self.word_label.setText("🎉 今日学习完成！")
        self.word_label.setFont(QFont("", 18, QFont.Bold))
        self.phonetic_label.setText("明天再来吧，或者导入更多单词")
        self.phonetic_label.setStyleSheet("color: #888;")
        self.meaning_label.hide()
        self.show_answer_btn.hide()
        self._set_review_buttons_enabled(False)
        self.progress_counter.setText("已完成所有单词")
        
        # 清空堆栈
        self.card_stack.setCurrentIndex(0)
    
    def _on_import(self):
        """导入词书"""
        from .import_dialog import ImportDialog
        dialog = ImportDialog(self)
        if dialog.exec_():
            # 导入成功，刷新
            imported_book_id = dialog.get_imported_book_id()
            if imported_book_id:
                self.scheduler = Scheduler(imported_book_id)
                self._update_info()
                self._load_today_queue()
                QMessageBox.information(self, "成功", "词书导入成功！")
    
    def _on_settings(self):
        """打开设置"""
        QMessageBox.information(self, "提示", "设置功能开发中...")
    
    def _on_stats(self):
        """打开统计"""
        QMessageBox.information(self, "提示", "统计功能开发中...")
    
    def _on_reset_today(self):
        """重置今日进度"""
        reply = QMessageBox.question(
            self, "确认重置",
            "重置今日进度将清除当前学习队列，确定继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._load_today_queue()
    
    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(
            self,
            "关于 WordMemory",
            "WordMemory v1.0\n\n"
            "基于艾宾浩斯遗忘曲线的背单词软件\n"
            "使用 Python + PyQt5 开发\n\n"
            "© 2026"
        )
    
    def _on_prev(self):
        """上一词"""
        if self.current_index > 0:
            self.current_index -= 1
            self._show_word(self.current_index)
    
    def _on_next(self):
        """下一词（跳过当前）"""
        if self.current_index < len(self.current_queue) - 1:
            self.current_index += 1
            self._show_word(self.current_index)
    
    def _update_info(self):
        """更新顶部信息"""
        if not self.scheduler:
            return
        
        from src.models.book import Book
        book = Book.get_by_id(self.scheduler.book_id)
        if book:
            self.book_label.setText(f"词书: {book.book_name}")
        
        # 更新进度
        stats = self.scheduler.get_stats()
        self.progress_label.setText(f"进度: {stats['progress']:.1f}%")
        self.progress_bar.setValue(int(stats['progress']))
        
        # 更新统计
        today_stats = self.scheduler.get_today_stats()
        self.today_stats_label.setText(
            f"今日: 复习 {today_stats['review_count']} 词 | 新词 {today_stats['new_count']} 词"
        )
        self.total_stats_label.setText(
            f"总计: {stats['learned_words']}/{stats['total_words']}"
        )
    
    def _update_stats(self):
        """更新统计数据"""
        self._update_info()
        
        # 更新进度条
        if self.current_queue:
            progress = (self.current_index + 1) / len(self.current_queue) * 100
            self.progress_bar.setValue(int(progress))
    
    def _get_styles(self):
        """获取样式表"""
        return """
            QMainWindow {
                background-color: #f7f9fc;
            }
            QFrame#card_frame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e5ec;
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
            QPushButton#btn_forgot {
                background-color: #fee2e2;
                border-color: #fca5a5;
                color: #b91c1c;
            }
            QPushButton#btn_forgot:hover {
                background-color: #fecaca;
            }
            QPushButton#btn_hard {
                background-color: #fef3c7;
                border-color: #fcd34d;
                color: #92400e;
            }
            QPushButton#btn_hard:hover {
                background-color: #fde68a;
            }
            QPushButton#btn_good {
                background-color: #dbeafe;
                border-color: #93c5fd;
                color: #1e40af;
            }
            QPushButton#btn_good:hover {
                background-color: #bfdbfe;
            }
            QPushButton#btn_easy {
                background-color: #d1fae5;
                border-color: #6ee7b7;
                color: #065f46;
            }
            QPushButton#btn_easy:hover {
                background-color: #a7f3d0;
            }
            QPushButton#btn_very_easy {
                background-color: #d1fae5;
                border-color: #34d399;
                color: #065f46;
            }
            QPushButton#btn_very_easy:hover {
                background-color: #a7f3d0;
            }
            QPushButton[enabled="false"] {
                opacity: 0.5;
            }
            QProgressBar {
                border: 1px solid #d0d7e2;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f2f5;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 4px;
            }
        """
    
    def closeEvent(self, event):
        """关闭事件"""
        # 可以在这里保存状态
        event.accept()