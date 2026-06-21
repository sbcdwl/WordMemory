"""
数据库模块 - 负责数据库的连接、初始化和基础操作
所有数据持久化都通过此模块完成
"""

import sqlite3
import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    """数据库管理类（单例模式 + 线程安全）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化数据库配置"""
        if not hasattr(self, '_initialized'):
            self.db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data', 'word_memory.db'
            )
            # 确保 data 目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # 线程本地存储：每个线程有自己的连接
            self._local = threading.local()
            
            # 主线程初始化连接
            self._get_connection()
            
            # 创建所有表
            self._create_tables()
            
            # 初始化默认设置
            self._init_default_settings()
            
            self._initialized = True
    
    def _get_connection(self):
        """
        获取当前线程的数据库连接
        如果当前线程没有连接，创建一个新的
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 启用 WAL 模式
            conn.execute("PRAGMA journal_mode=WAL")
            # 启用外键约束
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.connection = conn
        return self._local.connection
    
    def get_connection(self):
        """获取当前线程的数据库连接"""
        return self._get_connection()
    
    def get_cursor(self):
        """获取当前线程的游标"""
        return self._get_connection().cursor()
    
    def commit(self):
        """提交当前线程的事务"""
        conn = self._get_connection()
        conn.commit()
    
    def close(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def close_all(self):
        """关闭所有线程的连接（程序退出时调用）"""
        # 只关闭当前线程的连接
        self.close()
    
    def _create_tables(self):
        """创建所有表（如果不存在）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. 词书表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT UNIQUE NOT NULL,
                book_name TEXT,
                word_count INTEGER DEFAULT 0,
                import_date TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # 2. 单词表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                us_phone TEXT,
                uk_phone TEXT,
                api_param TEXT,
                audio_local_path TEXT,
                example_json TEXT,
                phrase_json TEXT,
                synonym_json TEXT,
                root_json TEXT,
                raw_json TEXT,
                created_date TEXT NOT NULL,
                UNIQUE(book_id, word)
            )
        ''')
        
        # 3. 复习记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL,
                last_review_date TEXT NOT NULL,
                next_review_date TEXT NOT NULL,
                review_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                consecutive_correct INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                last_quality INTEGER,
                is_new INTEGER DEFAULT 1,
                FOREIGN KEY (word_id) REFERENCES words (id) ON DELETE CASCADE
            )
        ''')
        
        # 创建索引（提升查询性能）
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_next_review ON review_records(next_review_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_word_id ON review_records(word_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_book_id ON words(book_id)')
        
        # 4. 设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_date TEXT NOT NULL
            )
        ''')
        
        conn.commit()
    
    def _init_default_settings(self):
        """初始化默认设置（如果不存在）"""
        default_settings = {
            'daily_new_words': '20',
            'review_mode': 'show_then_check',
            'max_examples_display': '2',
            'show_phonetic': 'true',
            'ease_factor_min': '1.3',
            'ease_factor_max': '2.5',
            'wrong_penalty_factor': '0.15'
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        for key, value in default_settings.items():
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value, updated_date)
                VALUES (?, ?, ?)
            ''', (key, value, now))
        
        conn.commit()
    
    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        执行查询并返回字典列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def execute_update(self, sql: str, params: tuple = ()) -> int:
        """
        执行更新操作，返回受影响的行数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    
    def execute_insert(self, sql: str, params: tuple = ()) -> int:
        """
        执行插入操作，返回最后插入的ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """
        批量执行操作
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(sql, params_list)
        conn.commit()
        return cursor.rowcount
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        获取设置值
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return default
    
    def update_setting(self, key: str, value: Any):
        """
        更新设置值
        """
        now = datetime.now().isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_date)
            VALUES (?, ?, ?)
        ''', (key, str(value), now))
        conn.commit()


# 全局数据库实例
db = Database()