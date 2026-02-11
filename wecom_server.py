#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信LLM交互服务端 - 主程序入口
"""

import os
import sys
import signal
import threading
import time
from typing import Dict, Any

# 添加src目录到Python路径
# sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config import setup_config, get_config
from src.logger import setup_logger, get_logger
from src.user_session import setup_session_manager, get_session_manager
from src.message_processor import setup_message_processor, get_message_processor
from src.wechat_client import setup_wechat_client, get_wechat_client
from src.wechat_server import WeChatServer


class WeChatLLMServer:
    """企业微信LLM交互服务端主类"""
    
    def __init__(self):
        """初始化服务端"""
        self.is_running = False
        self.components = {}
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"收到信号 {signum}，正在关闭服务...")
        self.stop()
    
    def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            self.logger = get_logger("Main")
            self.logger.info("开始初始化企业微信LLM交互服务端...")
            
            # 1. 初始化配置
            self.logger.info("初始化配置...")
            self.config = setup_config()
            self.components['config'] = self.config
            
            # 2. 初始化日志系统
            self.logger.info("初始化日志系统...")
            self.logger = setup_logger("WeChatLLMServer")
            self.components['logger'] = self.logger
            
            # 3. 初始化用户会话管理器
            self.logger.info("初始化用户会话管理器...")
            self.session_manager = setup_session_manager()
            self.components['session_manager'] = self.session_manager
            
            # 4. 初始化消息处理器
            self.logger.info("初始化消息处理器...")
            self.message_processor = setup_message_processor()
            self.components['message_processor'] = self.message_processor
            
            # 5. 初始化企业微信服务器
            self.logger.info("初始化企业微信服务器...")
            self.wechat_server = WeChatServer()
            self.components['wechat_server'] = self.wechat_server
            
            self.logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            print(f"初始化失败: {e}")
            return False
    
    def start(self):
        """启动服务端"""
        if self.is_running:
            self.logger.warning("服务端已经在运行中")
            return
        
        try:
            self.logger.info("启动企业微信LLM交互服务端...")
            
            # 1. 启动消息处理器
            self.logger.info("启动消息处理器...")
            self.message_processor.start()
            
            # 2. 在企业微信服务器线程中启动
            self.logger.info("启动企业微信服务器...")
            self.wechat_server_thread = threading.Thread(
                target=self.wechat_server.start,
                daemon=True
            )
            self.wechat_server_thread.start()
            
            self.is_running = True
            
            # 显示启动信息
            self._display_startup_info()
            
            # 主循环
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"启动服务端失败: {e}")
            self.stop()
    
    def _display_startup_info(self):
        """显示启动信息"""
        config = self.config
        
        self.logger.info(f"""
        ========================================
            企业微信LLM交互服务端启动成功
        ========================================
        
        服务配置：
        服务器地址: {config.server_host}:{config.server_port}
        最大用户数: {config.max_users}
        消息批量超时: {config.message_batch_timeout}秒
        对话超时: {config.conversation_timeout}秒
        
        LLM配置：
        API提供商: DeepSeek
        基础URL: {config.deepseek_base_url}
        
        企业微信配置：
        企业ID: {config.wechat_corpid[:10]}...
        应用ID: {config.wechat_agentid}
        
        日志配置：
        日志级别: {config.log_level}
        日志目录: {config.log_dir}
        
        ========================================
        服务已启动，按 Ctrl+C 停止服务
        ========================================
        """)
    
    def _main_loop(self):
        """主循环"""
        self.logger.info("进入主循环...")
        
        try:
            while self.is_running:
                # 定期显示状态信息
                self._display_status()
                
                # 休眠一段时间
                time.sleep(10)
                
        except KeyboardInterrupt:
            self.logger.info("收到键盘中断信号")
        except Exception as e:
            self.logger.error(f"主循环出错: {e}")
        finally:
            self.stop()
    
    def _display_status(self):
        """显示状态信息"""
        try:
            # 获取会话统计信息
            session_stats = self.session_manager.get_stats()
            
            # 获取消息处理器状态
            processor_status = self.message_processor.get_status()
            
            self.logger.info(f"""
            服务状态：
            运行状态: {'运行中' if self.is_running else '已停止'}
            服务器状态: {'运行中' if self.wechat_server.is_running else '已停止'}
            消息处理器: {'运行中' if processor_status['is_running'] else '已停止'}
            
            用户统计：
            总用户数: {session_stats['total_users']}
            活跃用户: {session_stats['active_users']}
            待处理消息用户: {session_stats['users_with_pending_messages']}
            队列中总消息数: {session_stats['total_messages_in_queues']}
            
            功能状态：
            工具调用: {'已启用' if processor_status['tools_enabled'] else '未启用'}
            soul.md加载: {'成功' if processor_status['soul_content_loaded'] else '失败'}
            """)
            
        except Exception as e:
            self.logger.error(f"获取状态信息失败: {e}")
    
    def stop(self):
        """停止服务端"""
        if not self.is_running:
            return
        
        self.logger.info("正在停止企业微信LLM交互服务端...")
        self.is_running = False
        
        try:
            # 1. 停止企业微信服务器
            if hasattr(self, 'wechat_server') and self.wechat_server:
                self.logger.info("停止企业微信服务器...")
                self.wechat_server.stop()
            
            # 2. 停止消息处理器
            if hasattr(self, 'message_processor') and self.message_processor:
                self.logger.info("停止消息处理器...")
                self.message_processor.stop()
            
            # 3. 关闭用户会话管理器
            if hasattr(self, 'session_manager') and self.session_manager:
                self.logger.info("关闭用户会话管理器...")
                self.session_manager.shutdown()
            
            self.logger.info("企业微信LLM交互服务端已停止")
            
        except Exception as e:
            self.logger.error(f"停止服务端时出错: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取服务端状态"""
        if not self.is_running:
            return {"status": "stopped"}
        
        try:
            session_stats = self.session_manager.get_stats()
            processor_status = self.message_processor.get_status()
            
            return {
                "status": "running",
                "server": {
                    "is_running": self.is_running,
                    "wechat_server_running": self.wechat_server.is_running,
                    "message_processor_running": processor_status['is_running']
                },
                "users": session_stats,
                "features": {
                    "tools_enabled": processor_status['tools_enabled'],
                    "soul_content_loaded": processor_status['soul_content_loaded']
                },
                "config": {
                    "max_users": self.config.max_users,
                    "message_batch_timeout": self.config.message_batch_timeout,
                    "conversation_timeout": self.config.conversation_timeout,
                    "server_host": self.config.server_host,
                    "server_port": self.config.server_port
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


def main():
    """主函数"""
    print("""
    ========================================
        企业微信LLM交互服务端
    ========================================
    
    版本: 1.0.0
    描述: 与local_client平行的企业微信LLM交互服务端
    作者: AI Assistant
    
    """)
    
    # 创建服务端实例
    server = WeChatLLMServer()
    
    # 初始化
    if not server.initialize():
        print("初始化失败，请检查配置和依赖")
        return 1
    
    # 启动服务端
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭...")
    except Exception as e:
        print(f"服务端运行出错: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())