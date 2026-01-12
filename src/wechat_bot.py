import time
import threading
import queue
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from wechatpy.enterprise import WeChatClient
from wechatpy.enterprise.exceptions import WeChatException
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.enterprise import parse_message
from wechatpy.enterprise.replies import TextReply

from src.llm import get_llm_client
from src.memory import get_memory_system
from src.logger import get_logger


class WeChatWorkTokenManager:
    """企业微信Access Token管理器"""
    
    def __init__(self, corpid: str, corpsecret: str):
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.access_token = None
        self.expires_at = 0
        self.client = WeChatClient(corpid, corpsecret)
    
    def get_token(self) -> str:
        """获取有效的access_token"""
        current_time = time.time()
        
        # 如果token不存在或即将过期，刷新token
        if not self.access_token or current_time >= self.expires_at - 300:  # 提前5分钟刷新
            self._refresh_token()
        
        return self.access_token
    
    def _refresh_token(self):
        """刷新access_token"""
        try:
            # 使用wechatpy客户端获取token
            self.client.fetch_access_token()
            self.access_token = self.client.access_token
            # 企业微信token有效期为2小时（7200秒）
            self.expires_at = time.time() + 7200
            logger = get_logger()
            logger.info(f"企业微信Access Token刷新成功，有效期至: {datetime.fromtimestamp(self.expires_at)}")
        except Exception as e:
            logger = get_logger()
            logger.error(f"刷新企业微信Access Token失败: {e}")
            raise


class WeChatWorkBot:
    """企业微信聊天机器人"""
    
    def __init__(self):
        load_dotenv()
        
        # 初始化企业微信配置
        self.corpid = os.getenv('WECHAT_WORK_CORPID')
        self.corpsecret = os.getenv('WECHAT_WORK_CORPSECRET')
        self.agentid = int(os.getenv('WECHAT_WORK_AGENTID', 0))
        
        # 回调配置（从用户提供的参数中获取）
        self.callback_token = os.getenv('WECHAT_WORK_CALLBACK_TOKEN', 'FREDERICATOKEN')
        self.encoding_aes_key = os.getenv('WECHAT_WORK_ENCODING_AES_KEY', 'norTzT7trWzPklIJEBILTG7UMzMXuibpzlAVaS4zag0')
        
        if not all([self.corpid, self.corpsecret, self.agentid]):
            raise ValueError("请配置企业微信相关环境变量: WECHAT_WORK_CORPID, WECHAT_WORK_CORPSECRET, WECHAT_WORK_AGENTID")
        
        # 初始化企业微信客户端
        self.token_manager = WeChatWorkTokenManager(self.corpid, self.corpsecret)
        self.client = WeChatClient(self.corpid, self.corpsecret)
        
        # 初始化加密实例
        self.crypto = WeChatCrypto(
            self.callback_token,
            self.encoding_aes_key,
            self.corpid
        )
        
        # 初始化LLM和记忆系统
        self.llm = get_llm_client()
        self.memory = get_memory_system()
        
        # 消息队列用于异步处理
        self.message_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
        # 用户会话状态
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        
        # 已处理消息ID缓存（避免重复处理）
        self.processed_msg_ids = set()
        self.max_processed_ids = 1000  # 最大缓存消息ID数量
        
        # 配置
        self.max_history = 20  # 最大历史消息数
        
        # 运行状态
        self.is_running = False
        self.processing_thread = None
        self.response_thread = None
        
        # 初始化日志器
        self.logger = get_logger()
        
        self.logger.info(f"企业微信机器人初始化完成，应用ID: {self.agentid}")
        self.logger.info(f"回调配置: Token={self.callback_token[:10]}..., AESKey={self.encoding_aes_key[:10]}...")
    
    def _get_client_with_token(self) -> WeChatClient:
        """获取带有有效token的客户端"""
        # 确保token有效
        self.token_manager.get_token()
        return self.client
    
    
    def _process_messages(self):
        """处理消息队列中的消息"""
        process_count = 0
        while self.is_running:
            try:
                # 从队列获取消息（非阻塞）
                try:
                    message = self.message_queue.get(timeout=0.5)
                    process_count += 1
                    self.logger.debug(f"开始处理第 {process_count} 条消息: {message.get('msg_id', '未知ID')}")
                except queue.Empty:
                    # 每10次空队列检查记录一次日志，避免日志过多
                    if process_count % 10 == 0:
                        self.logger.debug(f"消息队列为空，等待中... (已处理 {process_count} 条消息)")
                    time.sleep(0.1)
                    continue
                
                # 处理消息
                self._process_single_message(message)
                
                # 标记任务完成
                self.message_queue.task_done()
                self.logger.debug(f"第 {process_count} 条消息处理完成")
                
            except Exception as e:
                self.logger.error(f"处理消息时出错: {e}", exc_info=True)
                time.sleep(1)
    
    def _process_single_message(self, message: Dict[str, Any]):
        """处理单个消息"""
        user_id = message['user_id']
        user_name = message['user_name']
        content = message['content']
        
        # 检查是否需要回复
        if not self.llm.should_respond(content):
            self.logger.debug(f"跳过回复用户 {user_name} 的消息: {content[:30]}...")
            return
        
        # 获取用户会话
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'history': [],
                'last_active': datetime.now(),
                'user_name': user_name
            }
        
        session = self.user_sessions[user_id]
        session['last_active'] = datetime.now()
        
        # 添加到历史记录
        session['history'].append({
            'role': 'user',
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # 限制历史记录长度
        if len(session['history']) > self.max_history * 2:
            session['history'] = session['history'][-self.max_history * 2:]
        
        # 获取相关记忆
        relevant_memories = self.memory.search_memories(user_id, content, limit=3)
        context = None
        
        if relevant_memories:
            memory_texts = [f"- {mem['content']}" for mem in relevant_memories]
            context = "相关历史对话：\n" + "\n".join(memory_texts)
        
        # 准备消息给LLM
        llm_messages = []
        for msg in session['history'][-10:]:
            llm_messages.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        # 生成响应
        self.logger.info(f"为 {user_name} 生成响应...")
        response = self.llm.generate_response(llm_messages, context)
        
        if response['success']:
            reply_content = response['content']
            
            # 检查是否是沉默响应
            if reply_content == "[SILENT]":
                self.logger.info(f"对用户 {user_name} 保持沉默")
                return
            
            # 添加到响应队列
            self.response_queue.put({
                'user_id': user_id,
                'user_name': user_name,
                'content': reply_content,
                'msg_id': message['msg_id']
            })
            
            # 添加到历史记录
            session['history'].append({
                'role': 'assistant',
                'content': reply_content,
                'timestamp': datetime.now().isoformat()
            })
            
            # 保存到记忆库
            self.memory.add_memory(
                user_id=user_id,
                content=f"用户: {content}\nFrederica: {reply_content}",
                metadata={
                    'type': 'conversation',
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            self.logger.info(f"为 {user_name} 生成响应完成")
        else:
            self.logger.error(f"生成响应失败: {response.get('error', '未知错误')}")
    
    def _send_responses(self):
        """发送响应队列中的消息"""
        while self.is_running:
            try:
                # 从队列获取响应（非阻塞）
                try:
                    response = self.response_queue.get(timeout=0.5)
                except queue.Empty:
                    time.sleep(0.1)
                    continue
                
                # 发送响应
                self._send_single_response(response)
                
                # 标记任务完成
                self.response_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"发送响应时出错: {e}")
                time.sleep(1)
    
    def _send_single_response(self, response: Dict[str, Any]):
        """发送单个响应到企业微信"""
        try:
            user_id = response['user_id']
            content = response['content']
            
            # 获取有效的客户端
            client = self._get_client_with_token()
            
            # 发送文本消息到企业微信
            # 注意：需要根据接收者类型（用户、部门、标签）使用不同的API
            client.message.send_text(self.agentid, user_id, content)
            
            self.logger.info(f"已发送消息给 {response['user_name']}: {content[:50]}...")
            
        except WeChatException as e:
            self.logger.error(f"发送企业微信消息失败: {e}")
            # 如果是token问题，尝试刷新
            if "access_token" in str(e):
                self.logger.warning("检测到token问题，尝试刷新...")
                self.token_manager._refresh_token()
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
    
    def start(self):
        """启动机器人（回调模式）"""
        if self.is_running:
            self.logger.warning("机器人已经在运行中")
            return
        
        self.logger.info("启动企业微信聊天机器人（回调模式）...")
        
        # 测试企业微信连接
        try:
            client = self._get_client_with_token()
            self.logger.info("企业微信连接测试成功")
        except Exception as e:
            self.logger.error(f"企业微信连接测试失败: {e}")
            self.logger.error("请检查企业微信配置是否正确")
            return
        
        # 设置运行状态
        self.is_running = True
        
        # 启动处理线程（只启动消息处理和响应发送线程）
        self.processing_thread = threading.Thread(target=self._process_messages, daemon=True)
        self.response_thread = threading.Thread(target=self._send_responses, daemon=True)
        
        self.processing_thread.start()
        self.response_thread.start()
        
        self.logger.info("机器人已启动，等待回调消息...")
        self.logger.info("按 Ctrl+C 停止机器人")
        
        # 主循环，保持程序运行
        try:
            while self.is_running:
                # 检查线程状态
                threads_alive = all([
                    self.processing_thread.is_alive(),
                    self.response_thread.is_alive()
                ])
                
                if not threads_alive:
                    self.logger.warning("检测到线程异常，尝试重启...")
                    self._restart_threads()
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("\n收到停止信号...")
            self.stop()
        except Exception as e:
            self.logger.error(f"主循环出错: {e}")
            self.stop()
    
    def _restart_threads(self):
        """重启线程"""
        if self.processing_thread and not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(target=self._process_messages, daemon=True)
            self.processing_thread.start()
            self.logger.info("处理线程已重启")
        
        if self.response_thread and not self.response_thread.is_alive():
            self.response_thread = threading.Thread(target=self._send_responses, daemon=True)
            self.response_thread.start()
            self.logger.info("响应线程已重启")
    
    def stop(self):
        """停止机器人"""
        self.logger.info("停止企业微信聊天机器人...")
        
        self.is_running = False
        
        # 等待线程结束
        threads = [self.processing_thread, self.response_thread]
        for thread in threads:
            if thread:
                thread.join(timeout=5)
        
        self.logger.info("机器人已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取机器人状态"""
        return {
            'is_running': self.is_running,
            'queue_size': self.message_queue.qsize(),
            'response_queue_size': self.response_queue.qsize(),
            'active_users': len(self.user_sessions),
            'processed_messages': len(self.processed_msg_ids),
            'memory_stats': {
                'total_users': len(set([key for key in self.user_sessions.keys()]))
            }
        }
    
    def send_test_message(self, user_id: str, content: str = "测试消息") -> bool:
        """发送测试消息（用于调试）"""
        try:
            client = self._get_client_with_token()
            client.message.send_text(self.agentid, user_id, content)
            self.logger.info(f"测试消息发送成功: {user_id} - {content}")
            return True
        except Exception as e:
            self.logger.error(f"发送测试消息失败: {e}")
            return False
    
    def handle_callback_request(self, request_method: str, query_params: Dict[str, str], request_body: Optional[str] = None) -> str:
        """
        处理企业微信回调请求
        
        Args:
            request_method: HTTP请求方法 ('GET' 或 'POST')
            query_params: URL查询参数
            request_body: POST请求的原始请求体
            
        Returns:
            响应内容
        """
        try:
            self.logger.info(f"处理回调请求: 方法={request_method}, 参数={query_params}")
            self.logger.debug(f"请求方法: {request_method}")
            self.logger.debug(f"完整查询参数: {query_params}")
            self.logger.debug(f"请求体长度: {len(request_body) if request_body else 0}")
            
            # 验证必要的参数
            msg_signature = query_params.get('msg_signature', '')
            timestamp = query_params.get('timestamp', '')
            nonce = query_params.get('nonce', '')
            
            self.logger.debug(f"msg_signature: {msg_signature[:20]}... (长度: {len(msg_signature)})")
            self.logger.debug(f"timestamp: {timestamp}")
            self.logger.debug(f"nonce: {nonce}")
            
            if not all([msg_signature, timestamp, nonce]):
                self.logger.error(f"缺少必要的回调参数: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")
                self.logger.debug("缺少必要参数，返回错误响应")
                return "Missing required parameters"
            
            if request_method == 'GET':
                # GET请求：验证服务器有效性
                echostr = query_params.get('echostr', '')
                if not echostr:
                    self.logger.error("GET请求缺少echostr参数")
                    return "Missing echostr parameter"
                
                self.logger.info(f"处理GET验证请求，echostr: {echostr}")
                
                # 验证签名并解密echostr
                try:
                    # 企业微信要求：验证签名，然后返回解密后的echostr
                    decrypted_echostr = self.crypto.check_signature(
                        msg_signature,
                        timestamp,
                        nonce,
                        echostr
                    )
                    self.logger.info(f"验证成功，返回解密后的echostr: {decrypted_echostr}")
                    return decrypted_echostr
                except Exception as e:
                    self.logger.error(f"验证签名失败: {e}")
                    return "Signature verification failed"
            
            elif request_method == 'POST':
                # POST请求：处理消息
                if not request_body:
                    self.logger.error("POST请求缺少请求体")
                    return "Missing request body"
                
                self.logger.info(f"处理POST消息请求，请求体长度: {len(request_body)}")
                
                try:
                    # 解密消息
                    decrypted_xml = self.crypto.decrypt_message(
                        request_body,
                        msg_signature,
                        timestamp,
                        nonce
                    )
                    
                    self.logger.debug(f"解密后的XML: {decrypted_xml}")
                    
                    # 解析XML消息
                    message = parse_message(decrypted_xml)
                    self.logger.info(f"收到消息: 类型={message.type}, 发送者={message.source}")
                    
                    # 处理不同类型的消息
                    if message.type == 'text':
                        # 文本消息
                        content = message.content
                        user_id = message.source
                        
                        self.logger.info(f"收到文本消息来自 {user_id}: {content[:50]}...")
                        
                        # 生成消息ID（如果没有）
                        msg_id = getattr(message, 'id', f"{int(time.time())}_{user_id}")
                        
                        # 添加到消息队列进行处理
                        self.message_queue.put({
                            'type': 'text',
                            'user_id': user_id,
                            'user_name': user_id,  # 暂时使用user_id作为用户名
                            'content': content,
                            'msg_id': msg_id,
                            'timestamp': datetime.now().isoformat(),
                            'is_callback': True  # 标记为回调消息
                        })
                        
                        self.logger.info(f"消息已添加到处理队列，当前队列大小: {self.message_queue.qsize()}")
                        
                        # 企业微信要求：必须立即返回success，否则会重试
                        # 实际回复将通过异步方式发送
                        reply = TextReply(
                            content="",  # 空内容，表示已接收
                            message=message
                        )
                        
                        # 加密回复
                        encrypted_reply = self.crypto.encrypt_message(
                            reply.render(),
                            nonce,
                            timestamp
                        )
                        
                        return encrypted_reply
                    
                    else:
                        # 其他类型的消息（图片、语音等）
                        self.logger.info(f"收到非文本消息，类型: {message.type}")
                        
                        # 返回success表示已接收
                        reply = TextReply(
                            content="",
                            message=message
                        )
                        
                        encrypted_reply = self.crypto.encrypt_message(
                            reply.render(),
                            nonce,
                            timestamp
                        )
                        
                        return encrypted_reply
                        
                except Exception as e:
                    self.logger.error(f"处理POST消息失败: {e}", exc_info=True)
                    return "Error processing message"
            
            else:
                self.logger.error(f"不支持的请求方法: {request_method}")
                return "Unsupported request method"
                
        except Exception as e:
            self.logger.error(f"处理回调请求时出错: {e}", exc_info=True)
            return "Internal server error"
    
    def process_callback_message_sync(self, user_id: str, content: str) -> str:
        """
        同步处理回调消息（用于测试和直接调用）
        
        Args:
            user_id: 用户ID
            content: 消息内容
            
        Returns:
            回复内容
        """
        try:
            self.logger.info(f"同步处理消息: 用户={user_id}, 内容={content}")
            
            # 检查是否需要回复
            if not self.llm.should_respond(content):
                self.logger.debug(f"跳过回复用户 {user_id} 的消息: {content[:30]}...")
                return ""
            
            # 获取用户会话
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {
                    'history': [],
                    'last_active': datetime.now(),
                    'user_name': user_id
                }
            
            session = self.user_sessions[user_id]
            session['last_active'] = datetime.now()
            
            # 添加到历史记录
            session['history'].append({
                'role': 'user',
                'content': content,
                'timestamp': datetime.now().isoformat()
            })
            
            # 限制历史记录长度
            if len(session['history']) > self.max_history * 2:
                session['history'] = session['history'][-self.max_history * 2:]
            
            # 获取相关记忆
            relevant_memories = self.memory.search_memories(user_id, content, limit=3)
            context = None
            
            if relevant_memories:
                memory_texts = [f"- {mem['content']}" for mem in relevant_memories]
                context = "相关历史对话：\n" + "\n".join(memory_texts)
            
            # 准备消息给LLM
            llm_messages = []
            for msg in session['history'][-10:]:
                llm_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
            
            # 生成响应
            self.logger.info(f"为 {user_id} 生成同步响应...")
            response = self.llm.generate_response(llm_messages, context)
            
            if response['success']:
                reply_content = response['content']
                
                # 检查是否是沉默响应
                if reply_content == "[SILENT]":
                    self.logger.info(f"对用户 {user_id} 保持沉默")
                    return ""
                
                # 添加到历史记录
                session['history'].append({
                    'role': 'assistant',
                    'content': reply_content,
                    'timestamp': datetime.now().isoformat()
                })
                
                # 保存到记忆库
                self.memory.add_memory(
                    user_id=user_id,
                    content=f"用户: {content}\nFrederica: {reply_content}",
                    metadata={
                        'type': 'conversation',
                        'timestamp': datetime.now().isoformat()
                    }
                )
                
                self.logger.info(f"为 {user_id} 生成同步响应完成")
                return reply_content
            else:
                self.logger.error(f"生成响应失败: {response.get('error', '未知错误')}")
                return "抱歉，我遇到了一些技术问题，请稍后再试。"
                
        except Exception as e:
            self.logger.error(f"同步处理消息时出错: {e}", exc_info=True)
            return "处理消息时出现错误"


# 全局机器人实例
_bot_instance = None

def get_bot() -> WeChatWorkBot:
    """获取机器人实例"""
    global _bot_instance
    
    if _bot_instance is None:
        _bot_instance = WeChatWorkBot()
    
    return _bot_instance
