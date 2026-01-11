import os
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv
import tiktoken


class DeepSeekClient:
    """DeepSeek API客户端"""
    
    def __init__(self):
        load_dotenv()
        
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.api_base = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com')
        self.model = os.getenv('MODEL', 'deepseek-chat')
        self.max_tokens = int(os.getenv('MAX_TOKENS', 4096))
        self.temperature = float(os.getenv('TEMPERATURE', 0.7))
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )
        
        # 初始化tokenizer
        try:
            self.encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except:
            self.encoder = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return len(self.encoder.encode(text))
    
    def truncate_messages(self, messages: List[Dict[str, str]], max_tokens: int = None) -> List[Dict[str, str]]:
        """截断消息以确保不超过token限制"""
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        total_tokens = 0
        truncated_messages = []
        
        # 从最新的消息开始处理
        for message in reversed(messages):
            content = message.get('content', '')
            tokens = self.count_tokens(content)
            
            if total_tokens + tokens > max_tokens:
                # 如果添加这条消息会超过限制，则跳过
                continue
            
            total_tokens += tokens
            truncated_messages.insert(0, message)  # 保持原始顺序
        
        return truncated_messages
    
    def generate_response(self, 
                         messages: List[Dict[str, str]], 
                         context: Optional[str] = None,
                         use_memory: bool = True) -> Dict[str, Any]:
        """生成响应"""
        
        # 准备系统消息
        system_message = {
            "role": "system",
            "content": """你是一个名为Frederica的微信聊天机器人。你友好、热情、乐于助人。
请用中文回复，保持自然、友好的对话风格。
如果用户的问题需要更多上下文，可以询问澄清。
如果用户发送的内容不明确或无法理解，可以礼貌地请求解释。
保持对话流畅自然，避免过于机械的回答。"""
        }
        
        # 如果有上下文，添加到系统消息中
        if context:
            system_message["content"] += f"\n\n相关上下文：\n{context}"
        
        # 构建完整的消息列表
        full_messages = [system_message] + messages
        
        # 截断消息以确保不超过token限制
        truncated_messages = self.truncate_messages(full_messages, self.max_tokens - 500)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=truncated_messages,
                temperature=self.temperature,
                max_tokens=min(1000, self.max_tokens - self.count_tokens(
                    " ".join([msg.get('content', '') for msg in truncated_messages])
                )),
                stream=False
            )
            
            result = {
                "success": True,
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else None,
                "model": response.model
            }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": "抱歉，我遇到了一些技术问题，请稍后再试。"
            }
    
    def generate_silent_response(self) -> str:
        """生成沉默响应（用于异步对话中的无响应情况）"""
        return "[SILENT]"  # 特殊标记表示沉默
    
    def should_respond(self, message: str) -> bool:
        """判断是否应该回复消息"""
        # 简单的启发式规则：如果消息太短或看起来像命令/系统消息，可能不需要回复
        message_lower = message.lower().strip()
        
        # 不需要回复的情况
        no_response_patterns = [
            'ok', '好的', '收到', '谢谢', '感谢', 
            '拜拜', '再见', '晚安', '早安',
            '哈哈', '呵呵', '嘿嘿',
            '[图片]', '[文件]', '[语音]'
        ]
        
        for pattern in no_response_patterns:
            if pattern in message_lower:
                return False
        
        # 如果消息太短（少于2个字符）
        if len(message_lower) < 2:
            return False
        
        return True


# 单例模式
_llm_instance = None

def get_llm_client() -> DeepSeekClient:
    """获取LLM客户端实例"""
    global _llm_instance
    
    if _llm_instance is None:
        _llm_instance = DeepSeekClient()
    
    return _llm_instance
