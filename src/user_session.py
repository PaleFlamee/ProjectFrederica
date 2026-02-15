#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户会话管理模块
负责管理用户会话、消息队列和状态持久化
"""

import os
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

from .config import get_config
from .logger import get_logger


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"


@dataclass
class UserMessage:
    """用户消息数据类"""
    message_id: str
    user_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserMessage':
        """从字典创建"""
        return cls(
            message_id=data["message_id"],
            user_id=data["user_id"],
            content=data["content"],
            message_type=MessageType(data["message_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class UserSession:
    """用户会话数据类"""
    user_id: str
    message_queue: List[UserMessage] = field(default_factory=list)
    last_message_time: Optional[datetime] = None
    last_processed_time: Optional[datetime] = None
    is_processing: bool = False
    conversation_start_time: Optional[datetime] = None
    conversation_end_time: Optional[datetime] = None
    
    def add_message(self, message: UserMessage):
        """添加消息到队列"""
        self.message_queue.append(message)
        self.last_message_time = message.timestamp
        
        # 如果是第一条消息，设置对话开始时间
        if self.conversation_start_time is None:
            self.conversation_start_time = message.timestamp
        
        # 重置对话结束时间
        self.conversation_end_time = None
    
    def clear_queue(self):
        """清空消息队列"""
        self.message_queue.clear()
        self.last_processed_time = datetime.now()
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return len(self.message_queue)
    
    def should_process_batch(self, batch_timeout: int) -> bool:
        """检查是否应该处理批量消息"""
        if not self.message_queue:
            return False
        
        if self.is_processing:
            return False
        
        if self.last_message_time is None:
            return False
        
        # 检查是否超过批量处理超时时间
        time_since_last_message = (datetime.now() - self.last_message_time).total_seconds()
        return time_since_last_message >= batch_timeout
    
    def is_conversation_expired(self, conversation_timeout: int) -> bool:
        """检查对话是否已过期"""
        if self.conversation_start_time is None:
            return True
        
        if self.conversation_end_time is not None:
            return True
        
        # 检查是否超过对话超时时间
        if self.last_message_time is None:
            time_since_last_activity = (datetime.now() - self.conversation_start_time).total_seconds()
        else:
            time_since_last_activity = (datetime.now() - self.last_message_time).total_seconds()
        
        return time_since_last_activity >= conversation_timeout
    
    def end_conversation(self):
        """结束对话"""
        self.conversation_end_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "message_queue": [msg.to_dict() for msg in self.message_queue],
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "last_processed_time": self.last_processed_time.isoformat() if self.last_processed_time else None,
            "is_processing": self.is_processing,
            "conversation_start_time": self.conversation_start_time.isoformat() if self.conversation_start_time else None,
            "conversation_end_time": self.conversation_end_time.isoformat() if self.conversation_end_time else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """从字典创建"""
        session = cls(
            user_id=data["user_id"],
            is_processing=data["is_processing"]
        )
        
        # 恢复消息队列
        if data["message_queue"]:
            session.message_queue = [UserMessage.from_dict(msg) for msg in data["message_queue"]]
        
        # 恢复时间字段
        if data["last_message_time"]:
            session.last_message_time = datetime.fromisoformat(data["last_message_time"])
        if data["last_processed_time"]:
            session.last_processed_time = datetime.fromisoformat(data["last_processed_time"])
        if data["conversation_start_time"]:
            session.conversation_start_time = datetime.fromisoformat(data["conversation_start_time"])
        if data["conversation_end_time"]:
            session.conversation_end_time = datetime.fromisoformat(data["conversation_end_time"])
        
        return session


class UserSessionManager:
    """用户会话管理器"""
    
    def __init__(self):
        """初始化用户会话管理器"""
        self.config = get_config()
        self.logger = get_logger("UserSessionManager")
        self.message_config = self.config.get_message_config()
        
        # 用户会话字典
        self.user_sessions: Dict[str, UserSession] = {}
        
        # 线程锁
        self.lock = threading.RLock()
        
        # 持久化目录
        self.persistence_dir = os.path.join("data", "sessions")
        os.makedirs(self.persistence_dir, exist_ok=True)
        
        self.logger.info(f"用户会话管理器初始化完成，最大用户数: {self.message_config['max_users']}")
    
    def get_session(self, user_id: str) -> UserSession:
        """获取用户会话，如果不存在则创建"""
        with self.lock:
            if user_id not in self.user_sessions:
                # 检查是否超过最大用户数
                if len(self.user_sessions) >= self.message_config['max_users']:
                    self.logger.warning(f"达到最大用户数限制，无法为新用户 {user_id} 创建会话")
                    raise ValueError(f"达到最大用户数限制: {self.message_config['max_users']}")
                
                # 创建新会话
                self.user_sessions[user_id] = UserSession(user_id=user_id)
                self.logger.info(f"为新用户 {user_id} 创建会话")
            
            return self.user_sessions[user_id]
    
    def add_message(self, user_id: str, message_id: str, content: str, message_type: MessageType = MessageType.TEXT) -> bool:
        """添加用户消息"""
        try:
            with self.lock:
                session = self.get_session(user_id)
                
                # 检查对话是否已过期
                if session.is_conversation_expired(self.message_config['conversation_timeout']):
                    self.logger.info(f"用户 {user_id} 的对话已过期，创建新对话")
                    # 保存旧对话并创建新会话
                    self._save_session_to_file(session)
                    self.user_sessions[user_id] = UserSession(user_id=user_id)
                    session = self.user_sessions[user_id]
                
                # 创建消息对象
                message = UserMessage(
                    message_id=message_id,
                    user_id=user_id,
                    content=content,
                    message_type=message_type
                )
                
                # 添加到队列
                session.add_message(message)
                
                # 记录日志
                self.logger.log_user_message(user_id, message_type.value, content)
                self.logger.log_queue_status(user_id, session.get_queue_size(), session.last_message_time)
                
                return True
                
        except Exception as e:
            self.logger.error(f"添加用户消息失败: {e}")
            return False
    
    def get_messages_for_processing(self, user_id: str) -> Optional[List[UserMessage]]:
        """获取待处理的消息（如果应该处理的话）"""
        with self.lock:
            if user_id not in self.user_sessions:
                return None
            
            session = self.user_sessions[user_id]
            
            # 检查是否应该处理批量消息
            if not session.should_process_batch(self.message_config['batch_timeout']):
                return None
            
            # 标记为正在处理
            session.is_processing = True
            
            # 返回消息副本
            return session.message_queue.copy()
    
    def mark_processing_complete(self, user_id: str, success: bool = True):
        """标记处理完成"""
        with self.lock:
            if user_id not in self.user_sessions:
                return
            
            session = self.user_sessions[user_id]
            session.is_processing = False
            
            if success:
                # 清空队列
                session.clear_queue()
                self.logger.info(f"用户 {user_id} 的消息处理完成，队列已清空")
            else:
                self.logger.warning(f"用户 {user_id} 的消息处理失败，队列保留")
    
    def get_batch_candidates(self) -> List[str]:
        """获取应该处理批量消息的用户ID列表"""
        with self.lock:
            candidates = []
            
            for user_id, session in self.user_sessions.items():
                if session.should_process_batch(self.message_config['batch_timeout']):
                    candidates.append(user_id)
            
            return candidates
    
    def cleanup_expired_sessions(self):
        """清理过期的会话"""
        with self.lock:
            expired_users = []
            
            for user_id, session in self.user_sessions.items():
                if session.is_conversation_expired(self.message_config['conversation_timeout']):
                    expired_users.append(user_id)
            
            for user_id in expired_users:
                session = self.user_sessions[user_id]
                session.end_conversation()
                self._save_session_to_file(session)
                del self.user_sessions[user_id]
                self.logger.info(f"清理过期会话: {user_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = {
                "total_users": len(self.user_sessions),
                "active_users": 0,
                "total_messages_in_queues": 0,
                "users_with_pending_messages": 0
            }
            
            for session in self.user_sessions.values():
                queue_size = session.get_queue_size()
                stats["total_messages_in_queues"] += queue_size
                
                if queue_size > 0:
                    stats["users_with_pending_messages"] += 1
                
                if not session.is_conversation_expired(self.message_config['conversation_timeout']):
                    stats["active_users"] += 1
            
            return stats
    
    def _save_session_to_file(self, session: UserSession):
        """保存会话到文件"""
        try:
            filename = f"session_{session.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.persistence_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"会话已保存到文件: {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存会话到文件失败: {e}")
    
    def shutdown(self):
        """关闭管理器，保存所有会话"""
        with self.lock:
            self.logger.info("正在关闭用户会话管理器...")
            
            for user_id, session in self.user_sessions.items():
                if session.get_queue_size() > 0 or session.conversation_start_time is not None:
                    self._save_session_to_file(session)
            
            self.logger.info(f"用户会话管理器已关闭，保存了 {len(self.user_sessions)} 个会话")


# 全局用户会话管理器实例
_session_manager_instance: Optional[UserSessionManager] = None


def get_session_manager() -> UserSessionManager:
    """获取用户会话管理器实例（单例模式）"""
    global _session_manager_instance
    
    if _session_manager_instance is None:
        _session_manager_instance = UserSessionManager()
    
    return _session_manager_instance


def setup_session_manager() -> UserSessionManager:
    """设置并获取用户会话管理器"""
    global _session_manager_instance
    
    _session_manager_instance = UserSessionManager()
    return _session_manager_instance


# if __name__ == "__main__":
#     # 测试用户会话管理器
#     import time
    
#     manager = setup_session_manager()
    
#     # 测试添加消息
#     print("测试添加消息...")
#     manager.add_message("user1", "msg1", "你好，这是第一条消息")
#     manager.add_message("user1", "msg2", "这是第二条消息")
#     manager.add_message("user2", "msg3", "用户2的消息")
    
#     # 测试获取统计信息
#     stats = manager.get_stats()
#     print(f"统计信息: {stats}")
    
#     # 测试批量处理候选
#     print("等待批量处理超时...")
#     time.sleep(2)  # 等待2秒
    
#     candidates = manager.get_batch_candidates()
#     print(f"批量处理候选: {candidates}")
    
#     # 测试获取待处理消息
#     for user_id in candidates:
#         messages = manager.get_messages_for_processing(user_id)
#         if messages:
#             print(f"用户 {user_id} 的待处理消息: {len(messages)} 条")
#             manager.mark_processing_complete(user_id, success=True)
    
#     # 测试清理过期会话
#     print("测试清理过期会话...")
#     manager.cleanup_expired_sessions()
    
#     # 关闭管理器
#     manager.shutdown()