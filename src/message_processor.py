#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息处理器模块
负责批量处理消息、调用LLM、处理工具调用
"""

import os
import sys
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from openai import OpenAI

from .config import get_config
from .logger import get_logger
from .user_session import UserMessage, get_session_manager, MessageType
from .wechat_client import get_wechat_client

# 导入local_client中的工具调用相关函数
try:
    # 添加当前目录到Python路径，以便导入local_client
    # sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from local_client import (
        load_soul_content,
        format_assistant_message,
        execute_tools,
        process_tool_calls_loop,
        TOOLS as LOCAL_TOOLS,
        TOOL_EXECUTORS as LOCAL_TOOL_EXECUTORS
    )
    
    # 导入工具模块
    from tools.list_file_tool import TOOL_DEFINITION as LIST_TOOL
    from tools.read_file_tool import TOOL_DEFINITION as READ_TOOL
    from tools.create_file_or_folder_tool import TOOL_DEFINITION as CREATE_TOOL
    from tools.write_to_file_tool import TOOL_DEFINITION as WRITE_TOOL
    from tools.search_files_tool import TOOL_DEFINITION as SEARCH_TOOL
    from tools.delete_file_or_folder_tool import TOOL_DEFINITION as DELETE_TOOL
    from tools.replace_in_file_tool import TOOL_DEFINITION as REPLACE_TOOL
    from tools.duckduckgo_search_tool import TOOL_DEFINITION as DUCKDUCKGO_TOOL
    from tools.fetch_url_tool import TOOL_DEFINITION as FETCH_URL_TOOL
    
    TOOLS_AVAILABLE = True
    print("✓ 成功导入local_client和工具模块")
    
except ImportError as e:
    print(f"✗ 导入local_client或工具模块失败: {e}")
    TOOLS_AVAILABLE = False
    LOCAL_TOOLS = []
    LOCAL_TOOL_EXECUTORS = {}


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self):
        """初始化消息处理器"""
        self.config = get_config()
        self.logger = get_logger("MessageProcessor")
        self.session_manager = get_session_manager()
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.config.deepseek_api_key,
            base_url=self.config.deepseek_base_url
        )
        
        # 初始化企业微信客户端
        self.wechat_client = get_wechat_client()
        
        # 加载soul.md内容
        self.soul_content = load_soul_content() if TOOLS_AVAILABLE else ""
        if self.soul_content:
            self.logger.info(f"已加载soul.md内容作为system prompt（{len(self.soul_content)}字符）")
        else:
            self.logger.warning("soul.md内容加载失败或为空")
        
        # 工具调用支持
        self.tools_enabled = TOOLS_AVAILABLE
        if self.tools_enabled:
            self.logger.info(f"工具调用已启用，可用工具: {len(LOCAL_TOOLS)} 个")
        else:
            self.logger.warning("工具调用未启用，将只支持纯聊天")
        
        # 处理线程
        self.processing_thread = None
        self.is_running = False
        
        self.logger.info("消息处理器初始化完成")
    
    def start(self):
        """启动消息处理器"""
        if self.is_running:
            self.logger.warning("消息处理器已经在运行中")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("消息处理器已启动")
    
    def stop(self):
        """停止消息处理器"""
        self.is_running = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        self.logger.info("消息处理器已停止")
    
    def _processing_loop(self):
        """处理循环"""
        self.logger.info("开始消息处理循环")
        
        while self.is_running:
            try:
                # 获取需要批量处理的用户
                candidates = self.session_manager.get_batch_candidates()
                
                if candidates:
                    self.logger.debug(f"发现 {len(candidates)} 个需要处理的用户: {candidates}")
                    
                    # 处理每个用户的消息
                    for user_id in candidates:
                        self._process_user_messages(user_id)
                
                # 清理过期会话
                self.session_manager.cleanup_expired_sessions()
                
                # 休眠一段时间避免CPU占用过高
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"消息处理循环出错: {e}")
                time.sleep(5)  # 出错后等待更长时间
    
    def _process_user_messages(self, user_id: str):
        """处理单个用户的消息"""
        try:
            # 获取待处理的消息
            messages = self.session_manager.get_messages_for_processing(user_id)
            if not messages:
                return
            
            self.logger.info(f"开始处理用户 {user_id} 的 {len(messages)} 条消息")
            
            # 合并消息内容
            merged_content = self._merge_messages(messages)
            
            # 调用LLM处理
            success, response_content = self._call_llm(user_id, merged_content)
            
            if success and response_content:
                # 解析分段标记并发送（这里需要后续集成企业微信发送功能）
                self._handle_llm_response(user_id, response_content)
                
                # 标记处理成功
                self.session_manager.mark_processing_complete(user_id, success=True)
                self.logger.info(f"用户 {user_id} 的消息处理成功")
            else:
                # 标记处理失败
                self.session_manager.mark_processing_complete(user_id, success=False)
                self.logger.error(f"用户 {user_id} 的消息处理失败")
                
        except Exception as e:
            self.logger.error(f"处理用户 {user_id} 的消息时出错: {e}")
            self.session_manager.mark_processing_complete(user_id, success=False)
    
    def _merge_messages(self, messages: List[UserMessage]) -> str:
        """合并多条消息为一条消息内容"""
        merged_lines = []
        
        for i, message in enumerate(messages, 1):
            # 添加时间戳和消息内容
            time_str = message.timestamp.strftime("%H:%M:%S")
            merged_lines.append(f"[{time_str}] {message.content}")
            
            # 如果不是最后一条消息，添加分隔符
            if i < len(messages):
                merged_lines.append("<SEGMENTATION>")
        
        return "\n".join(merged_lines)
    
    def _call_llm(self, user_id: str, content: str) -> tuple[bool, Optional[str]]:
        """调用LLM处理消息"""
        try:
            # 构建消息列表
            messages = []
            
            # 添加system消息（soul.md内容）
            if self.soul_content:
                messages.append({
                    "role": "system",
                    "content": self.soul_content
                })
            
            # 添加时间、渠道和用户信息
            time_info = datetime.now().strftime("<time>%Y-%m-%d %H:%M:%S CST ")
            channel_info = "<channel>wechat "
            user_info = f"<user_id>{user_id}"
            
            messages.append({
                "role": "system",
                "content": time_info + channel_info + user_info
            })
            
            # 添加用户消息
            messages.append({
                "role": "user",
                "content": content
            })
            
            self.logger.log_llm_call(user_id, len(content), 0)
            
            # 调用LLM API
            if self.tools_enabled:
                # 使用工具调用
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    tools=LOCAL_TOOLS,
                    tool_choice="auto"
                )
            else:
                # 只使用纯聊天
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages
                )
            
            assistant_message = response.choices[0].message
            
            # 处理工具调用（如果有）
            if assistant_message.tool_calls and self.tools_enabled:
                self.logger.info(f"用户 {user_id} 的LLM响应包含工具调用")
                
                # 处理工具调用循环
                current_message, updated_messages = process_tool_calls_loop(
                    initial_message=assistant_message,
                    messages=messages,
                    client=self.client,
                    tools=LOCAL_TOOLS,
                    tool_executors=LOCAL_TOOL_EXECUTORS
                )
                
                # 获取最终回复内容
                final_content = current_message.content
                
                # 记录工具调用
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    self.logger.log_tool_call(user_id, tool_name, success=True)
            else:
                final_content = assistant_message.content
            
            # 记录响应长度
            response_length = len(final_content) if final_content else 0
            self.logger.log_llm_call(user_id, len(content), response_length)
            
            return True, final_content
            
        except Exception as e:
            self.logger.error(f"调用LLM API失败: {e}")
            return False, None
    
    def _handle_llm_response(self, user_id: str, response_content: str):
        """处理LLM响应"""
        try:
            # 解析<SEGMENTATION>标记
            segments = self._parse_segmentation(response_content)
            
            # 记录分段信息
            self.logger.info(f"用户 {user_id} 的LLM响应被分为 {len(segments)} 段")
            
            if not segments:
                self.logger.warning(f"用户 {user_id} 的LLM响应为空，无需发送")
                return
            
            # 发送消息给用户
            self.logger.info(f"开始发送 {len(segments)} 段消息给用户 {user_id}")
            
            # 使用企业微信客户端发送消息
            success = self.wechat_client.send_messages(user_id, segments)
            
            if success:
                self.logger.info(f"成功发送所有消息给用户 {user_id}")
                
                # 记录发送的详细信息（用于调试）
                for i, segment in enumerate(segments, 1):
                    truncated_segment = segment[:100] + "..." if len(segment) > 100 else segment
                    self.logger.debug(f"已发送第 {i} 段消息: {truncated_segment}")
            else:
                self.logger.error(f"发送消息给用户 {user_id} 失败")
                
        except Exception as e:
            self.logger.error(f"处理LLM响应失败: {e}")
    
    def _parse_segmentation(self, content: str) -> List[str]:
        """解析<SEGMENTATION>标记，将内容分段"""
        if not content:
            return []
        
        # 按<SEGMENTATION>标记分割
        segments = content.split("<SEGMENTATION>")
        
        # 清理每段内容
        cleaned_segments = []
        for segment in segments:
            cleaned = segment.strip()
            if cleaned:  # 只保留非空段
                cleaned_segments.append(cleaned)
        
        return cleaned_segments
    
    def process_message_immediately(self, user_id: str, message_id: str, content: str) -> bool:
        """立即处理单条消息（用于测试或特殊情况）"""
        try:
            self.logger.info(f"立即处理用户 {user_id} 的消息: {content[:50]}...")
            
            # 构建消息
            messages = []
            
            # 添加system消息
            if self.soul_content:
                messages.append({
                    "role": "system",
                    "content": self.soul_content
                })
            
            # 添加时间、渠道和用户信息
            time_info = datetime.now().strftime("<time>%Y-%m-%d %H:%M:%S CST ")
            channel_info = "<channel>wechat "
            user_info = f"<user_id>{user_id}"
            
            messages.append({
                "role": "system",
                "content": time_info + channel_info + user_info
            })
            
            # 添加用户消息（带时间戳）
            time_str = datetime.now().strftime("%H:%M:%S")
            formatted_content = f"[{time_str}] {content}"
            
            messages.append({
                "role": "user",
                "content": formatted_content
            })
            
            # 调用LLM
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages
            )
            
            response_content = response.choices[0].message.content
            self.logger.info(f"立即处理完成，响应长度: {len(response_content)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"立即处理消息失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            "is_running": self.is_running,
            "tools_enabled": self.tools_enabled,
            "soul_content_loaded": bool(self.soul_content),
            "session_stats": self.session_manager.get_stats()
        }


# 全局消息处理器实例
_message_processor_instance: Optional[MessageProcessor] = None


def get_message_processor() -> MessageProcessor:
    """获取消息处理器实例（单例模式）"""
    global _message_processor_instance
    
    if _message_processor_instance is None:
        _message_processor_instance = MessageProcessor()
    
    return _message_processor_instance


def setup_message_processor() -> MessageProcessor:
    """设置并获取消息处理器"""
    global _message_processor_instance
    
    _message_processor_instance = MessageProcessor()
    return _message_processor_instance


# if __name__ == "__main__":
#     # 测试消息处理器
#     import time
    
#     print("测试消息处理器...")
    
#     # 设置配置（使用测试配置）
#     os.environ["DEEPSEEK_API_KEY"] = "test_key"
#     os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
#     os.environ["WECHAT_WORK_CORPSECRET"] = "test_secret"
#     os.environ["WECHAT_WORK_AGENTID"] = "test_id"
    
#     processor = setup_message_processor()
    
#     # 测试状态
#     status = processor.get_status()
#     print(f"处理器状态: {status}")
    
#     # 测试合并消息
#     test_messages = [
#         UserMessage("msg1", "test_user", "第一条消息"),
#         UserMessage("msg2", "test_user", "第二条消息"),
#         UserMessage("msg3", "test_user", "第三条消息")
#     ]
    
#     merged = processor._merge_messages(test_messages)
#     print(f"合并后的消息:\n{merged}")
    
#     # 测试分段解析
#     test_response = "第一段内容<SEGMENTATION>第二段内容<SEGMENTATION>第三段内容"
#     segments = processor._parse_segmentation(test_response)
#     print(f"分段解析结果: {segments}")
    
#     # 测试立即处理（需要真实的API密钥）
#     # processor.process_message_immediately("test_user", "test_msg", "你好")
    
#     print("测试完成")