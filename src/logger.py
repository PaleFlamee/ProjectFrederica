#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统模块
支持时间-级别-模块-信息格式
"""

import os
import sys
import logging
import logging.handlers
from typing import Optional
from datetime import datetime

from .config import get_config


class WeChatLogger:
    """企业微信服务日志器"""
    
    # 日志级别映射
    LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    def __init__(self, name: str = "WeChatServer"):
        """初始化日志器"""
        self.name = name
        self.config = get_config()
        self.log_config = self.config.get_log_config()
        
        # 创建日志器
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.LEVELS.get(self.log_config['level'], logging.INFO))
        
        # 清除现有的处理器
        self.logger.handlers.clear()
        
        # 创建格式化器（时间-级别-模块-信息）
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 添加文件处理器
        if self.log_config['to_file']:
            # 确保日志目录存在
            os.makedirs(self.log_config['dir'], exist_ok=True)
            
            log_file = os.path.join(self.log_config['dir'], f'{self.name.lower()}.log')
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=self.log_config['max_file_size'],
                backupCount=self.log_config['backup_count'],
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(self.LEVELS.get(self.log_config['level'], logging.INFO))
            self.logger.addHandler(file_handler)
        
        # 添加控制台处理器
        if self.log_config['to_console']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(self.LEVELS.get(self.log_config['level'], logging.INFO))
            self.logger.addHandler(console_handler)
        
        # 记录初始化日志
        self.info(f"日志系统初始化完成，级别: {self.log_config['level']}")
    
    def debug(self, message: str, *args, **kwargs):
        """记录DEBUG级别日志"""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """记录INFO级别日志"""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """记录WARNING级别日志"""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """记录ERROR级别日志"""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """记录CRITICAL级别日志"""
        self.logger.critical(message, *args, **kwargs)
    
    def log_user_message(self, user_id: str, message_type: str, content: str):
        """记录用户消息日志"""
        truncated_content = content[:100] + "..." if len(content) > 100 else content
        self.info(f"用户消息 - 用户ID: {user_id}, 类型: {message_type}, 内容: {truncated_content}")
    
    def log_llm_call(self, user_id: str, prompt_length: int, response_length: int):
        """记录LLM调用日志"""
        self.debug(f"LLM调用 - 用户ID: {user_id}, 提示长度: {prompt_length}, 响应长度: {response_length}")
    
    def log_queue_status(self, user_id: str, queue_size: int, last_message_time: Optional[datetime]):
        """记录队列状态日志"""
        last_time_str = last_message_time.strftime("%Y-%m-%d %H:%M:%S") if last_message_time else "无"
        self.debug(f"队列状态 - 用户ID: {user_id}, 队列大小: {queue_size}, 最后消息时间: {last_time_str}")
    
    def log_tool_call(self, user_id: str, tool_name: str, success: bool):
        """记录工具调用日志"""
        status = "成功" if success else "失败"
        self.info(f"工具调用 - 用户ID: {user_id}, 工具: {tool_name}, 状态: {status}")


# 全局日志器实例
_logger_instance: Optional[WeChatLogger] = None


def get_logger(name: str = "WeChatServer") -> WeChatLogger:
    """获取日志器实例（单例模式）"""
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = WeChatLogger(name=name)
    
    return _logger_instance


def setup_logger(name: str = "WeChatServer") -> WeChatLogger:
    """设置并获取日志器"""
    global _logger_instance
    
    _logger_instance = WeChatLogger(name=name)
    return _logger_instance


# 便捷函数
def debug(message: str, *args, **kwargs):
    """全局DEBUG日志"""
    logger = get_logger()
    logger.debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs):
    """全局INFO日志"""
    logger = get_logger()
    logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs):
    """全局WARNING日志"""
    logger = get_logger()
    logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs):
    """全局ERROR日志"""
    logger = get_logger()
    logger.error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs):
    """全局CRITICAL日志"""
    logger = get_logger()
    logger.critical(message, *args, **kwargs)


if __name__ == "__main__":
    # 测试日志系统
    logger = setup_logger("TestLogger")
    
    logger.debug("这是一条DEBUG消息")
    logger.info("这是一条INFO消息")
    logger.warning("这是一条WARNING消息")
    logger.error("这是一条ERROR消息")
    logger.critical("这是一条CRITICAL消息")
    
    # 测试专用日志方法
    logger.log_user_message("test_user", "text", "这是一条测试消息，用于验证日志系统的工作情况。")
    logger.log_llm_call("test_user", 150, 200)
    logger.log_queue_status("test_user", 3, datetime.now())
    logger.log_tool_call("test_user", "read_file", True)