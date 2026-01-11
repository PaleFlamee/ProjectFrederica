import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import hashlib
import re


class MemorySystem:
    """简单的记忆库系统，使用SQLite存储对话记忆"""
    
    def __init__(self, db_path: str = "./data/memory.db", max_items: int = 100):
        self.db_path = db_path
        self.max_items = max_items
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建记忆表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                embedding TEXT,
                metadata TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON memories (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON memories (timestamp)')
        
        conn.commit()
        conn.close()
    
    def add_memory(self, user_id: str, content: str, metadata: Optional[Dict] = None):
        """添加新的记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 如果记忆数量超过限制，删除最旧的记忆
        cursor.execute('SELECT COUNT(*) FROM memories WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        
        if count >= self.max_items:
            cursor.execute('''
                DELETE FROM memories 
                WHERE user_id = ? 
                AND id IN (
                    SELECT id FROM memories 
                    WHERE user_id = ? 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                )
            ''', (user_id, user_id, count - self.max_items + 1))
        
        # 插入新记忆
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute('''
            INSERT INTO memories (user_id, content, metadata)
            VALUES (?, ?, ?)
        ''', (user_id, content, metadata_json))
        
        conn.commit()
        conn.close()
    
    def get_recent_memories(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, content, timestamp, metadata
            FROM memories
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        memories = []
        for row in rows:
            memory = dict(row)
            if memory['metadata']:
                memory['metadata'] = json.loads(memory['metadata'])
            memories.append(memory)
        
        return memories
    
    def search_memories(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """基于文本相似度搜索记忆"""
        all_memories = self.get_recent_memories(user_id, limit=50)
        
        # 简单的文本相似度计算（基于关键词匹配）
        query_words = set(re.findall(r'\w+', query.lower()))
        
        scored_memories = []
        for memory in all_memories:
            content = memory['content'].lower()
            content_words = set(re.findall(r'\w+', content))
            
            # 计算Jaccard相似度
            if query_words and content_words:
                intersection = len(query_words.intersection(content_words))
                union = len(query_words.union(content_words))
                similarity = intersection / union if union > 0 else 0
            else:
                similarity = 0
            
            scored_memories.append((similarity, memory))
        
        # 按相似度排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        # 返回最相关的记忆
        return [memory for similarity, memory in scored_memories[:limit] if similarity > 0.1]
    
    def clear_user_memories(self, user_id: str):
        """清除用户的所有记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM memories WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_memory_summary(self, user_id: str) -> str:
        """生成记忆摘要"""
        memories = self.get_recent_memories(user_id, limit=20)
        
        if not memories:
            return "暂无历史对话记忆。"
        
        summary_parts = []
        for memory in memories[:10]:  # 只取最近的10条
            content = memory['content']
            # 截断过长的内容
            if len(content) > 100:
                content = content[:97] + "..."
            summary_parts.append(f"- {content}")
        
        return "最近的对话记忆：\n" + "\n".join(summary_parts)


# 单例模式
_memory_instance = None

def get_memory_system(db_path: str = None) -> MemorySystem:
    """获取记忆系统实例"""
    global _memory_instance
    
    if _memory_instance is None:
        if db_path is None:
            from dotenv import load_dotenv
            load_dotenv()
            db_path = os.getenv('MEMORY_DB_PATH', './data/memory.db')
        
        _memory_instance = MemorySystem(db_path)
    
    return _memory_instance
