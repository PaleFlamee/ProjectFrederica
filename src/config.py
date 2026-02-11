#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import os
from typing import Optional
from dotenv import load_dotenv


class Config:
    """配置管理类"""
    
    def __init__(self):
        """初始化配置，加载环境变量"""
        load_dotenv()
        
        # DeepSeek API配置
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        # 企业微信配置
        self.wechat_corpid = os.getenv("WECHAT_WORK_CORPID")
        self.wechat_corpsecret = os.getenv("WECHAT_WORK_CORPSECRET")
        self.wechat_agentid = os.getenv("WECHAT_WORK_AGENTID")
        self.wechat_callback_token = os.getenv("WECHAT_WORK_CALLBACK_TOKEN")
        self.wechat_encoding_aes_key = os.getenv("WECHAT_WORK_ENCODING_AES_KEY")
        
        # 日志配置
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_to_file = os.getenv("LOG_TO_FILE", "true").lower() == "true"
        self.log_to_console = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
        self.log_dir = os.getenv("LOG_DIR", "./logs")
        self.max_log_file_size = int(os.getenv("MAX_LOG_FILE_SIZE", "10485760"))
        self.log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        
        # 消息处理配置
        self.message_batch_timeout = int(os.getenv("MESSAGE_BATCH_TIMEOUT", "40"))
        self.conversation_timeout = int(os.getenv("CONVERSATION_TIMEOUT", "3600"))
        self.max_users = int(os.getenv("MAX_USERS", "10"))
        
        # 服务器配置
        self.server_host = os.getenv("SERVER_HOST", "::")  # IPv4/IPv6双栈
        self.server_port = int(os.getenv("SERVER_PORT", "8080"))
    
    def validate(self) -> bool:
        """验证必要配置是否完整"""
        missing_configs = []
        
        # 检查DeepSeek API配置
        if not self.deepseek_api_key:
            missing_configs.append("DEEPSEEK_API_KEY")
        
        # 检查企业微信配置
        if not self.wechat_corpid:
            missing_configs.append("WECHAT_WORK_CORPID")
        if not self.wechat_corpsecret:
            missing_configs.append("WECHAT_WORK_CORPSECRET")
        if not self.wechat_agentid:
            missing_configs.append("WECHAT_WORK_AGENTID")
        if not self.wechat_callback_token:
            missing_configs.append("WECHAT_WORK_CALLBACK_TOKEN")
        if not self.wechat_encoding_aes_key:
            missing_configs.append("WECHAT_WORK_ENCODING_AES_KEY")
        
        if missing_configs:
            print(f"错误：缺少必要的配置项：{', '.join(missing_configs)}")
            print("请检查.env文件或设置环境变量")
            return False
        
        return True
    
    def get_wechat_config(self) -> dict:
        """获取企业微信配置字典"""
        return {
            "corpid": self.wechat_corpid,
            "corpsecret": self.wechat_corpsecret,
            "agentid": self.wechat_agentid,
            "callback_token": self.wechat_callback_token,
            "encoding_aes_key": self.wechat_encoding_aes_key
        }
    
    def get_log_config(self) -> dict:
        """获取日志配置字典"""
        return {
            "level": self.log_level,
            "to_file": self.log_to_file,
            "to_console": self.log_to_console,
            "dir": self.log_dir,
            "max_file_size": self.max_log_file_size,
            "backup_count": self.log_backup_count
        }
    
    def get_message_config(self) -> dict:
        """获取消息处理配置字典"""
        return {
            "batch_timeout": self.message_batch_timeout,
            "conversation_timeout": self.conversation_timeout,
            "max_users": self.max_users
        }
    
    def get_server_config(self) -> dict:
        """获取服务器配置字典"""
        return {
            "host": self.server_host,
            "port": self.server_port
        }


# 全局配置实例
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """获取配置实例（单例模式）"""
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config()
    
    return _config_instance


def setup_config() -> Config:
    """设置并验证配置"""
    config = get_config()
    
    if not config.validate():
        raise ValueError("配置验证失败")
    
    return config


if __name__ == "__main__":
    # 测试配置加载
    config = setup_config()
    print("配置加载成功：")
    print(f"DeepSeek API Key: {'已设置' if config.deepseek_api_key else '未设置'}")
    print(f"企业微信企业ID: {config.wechat_corpid}")
    print(f"企业微信应用ID: {config.wechat_agentid}")
    print(f"消息批量超时: {config.message_batch_timeout}秒")
    print(f"对话超时: {config.conversation_timeout}秒")
    print(f"最大用户数: {config.max_users}")