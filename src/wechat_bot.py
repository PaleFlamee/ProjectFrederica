import time
import threading
import queue
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from wechatpy.enterprise import WeChatClient
from wechatpy.enterprise.exceptions import WeChatException
from wechatpy.enterprise.crypto import WeChatCrypto

from src.llm import get_llm_client
from src.memory import get_memory_system


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
            print(f"企业微信Access Token刷新成功，有效期至: {datetime.fromtimestamp(self.expires_at)}")
        except Exception as e:
            print(f"刷新企业微信Access Token失败: {e}")
            raise


class WeChatWorkBot:
    """企业微信聊天机器人"""
    
    def __init__(self):
        load_dotenv()
        
        # 初始化企业微信配置
        self.corpid = os.getenv('WECHAT_WORK_CORPID')
        self.corpsecret = os.getenv('WECHAT_WORK_CORPSECRET')
        self.agentid = int(os.getenv('WECHAT_WORK_AGENTID', 0))
        self.polling_interval = int(os.getenv('WECHAT_WORK_POLLING_INTERVAL', 5))
        
        if not all([self.corpid, self.corpsecret, self.agentid]):
            raise ValueError("请配置企业微信相关环境变量: WECHAT_WORK_CORPID, WECHAT_WORK_CORPSECRET, WECHAT_WORK_AGENTID")
        
        # 初始化企业微信客户端
        self.token_manager = WeChatWorkTokenManager(self.corpid, self.corpsecret)
        self.client = WeChatClient(self.corpid, self.corpsecret)
        
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
        self.polling_thread = None
        
        print(f"企业微信机器人初始化完成，应用ID: {self.agentid}")
    
    def _get_client_with_token(self) -> WeChatClient:
        """获取带有有效token的客户端"""
        # 确保token有效
        self.token_manager.get_token()
        return self.client
    
    def _poll_messages(self):
        """轮询企业微信消息"""
        while self.is_running:
            try:
                # 获取最新的消息
                self._fetch_and_process_messages()
                
                # 清理过期的已处理消息ID
                if len(self.processed_msg_ids) > self.max_processed_ids:
                    # 保留最近的一半
                    self.processed_msg_ids = set(list(self.processed_msg_ids)[-self.max_processed_ids//2:])
                
                # 等待下一次轮询
                time.sleep(self.polling_interval)
                
            except Exception as e:
                print(f"轮询消息时出错: {e}")
                time.sleep(self.polling_interval * 2)  # 出错时等待更长时间
    
    def _fetch_and_process_messages(self):
        """获取并处理消息"""
        try:
            client = self._get_client_with_token()
            
            # 获取企业微信消息（这里使用主动拉取模式）
            # 注意：企业微信API需要配置回调或使用其他方式接收消息
            # 这里我们假设使用"获取聊天记录"API或类似功能
            # 实际实现可能需要根据企业微信的具体API调整
            
            # 由于企业微信的消息接收通常需要回调配置，
            # 这里我们提供一个简化的实现，实际使用时需要根据具体需求调整
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检查新消息...")
            
            # 这里可以添加实际的消息获取逻辑
            # 例如：使用企业微信的"获取聊天记录"API
            
        except WeChatException as e:
            print(f"企业微信API调用失败: {e}")
            # 如果是token过期，强制刷新
            if "access_token" in str(e):
                print("检测到token过期，尝试刷新...")
                self.token_manager._refresh_token()
        except Exception as e:
            print(f"获取消息时出错: {e}")
    
    def _process_incoming_message(self, msg_data: Dict[str, Any]):
        """处理收到的消息"""
        try:
            # 提取消息信息（根据企业微信消息格式调整）
            msg_id = msg_data.get('MsgId', '')
            user_id = msg_data.get('FromUserName', '')
            user_name = msg_data.get('User', {}).get('NickName', '未知用户')
            content = msg_data.get('Text', '')
            msg_type = msg_data.get('MsgType', 'text')
            
            # 检查是否已处理过该消息
            if msg_id in self.processed_msg_ids:
                return
            
            # 只处理文本消息
            if msg_type != 'text':
                print(f"跳过非文本消息类型: {msg_type}")
                return
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到消息来自 {user_name}: {content[:50]}...")
            
            # 标记为已处理
            self.processed_msg_ids.add(msg_id)
            
            # 添加到消息队列
            self.message_queue.put({
                'type': 'text',
                'user_id': user_id,
                'user_name': user_name,
                'content': content,
                'msg_id': msg_id,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"处理消息时出错: {e}")
    
    def _process_messages(self):
        """处理消息队列中的消息"""
        while self.is_running:
            try:
                # 从队列获取消息（非阻塞）
                try:
                    message = self.message_queue.get(timeout=0.5)
                except queue.Empty:
                    time.sleep(0.1)
                    continue
                
                # 处理消息
                self._process_single_message(message)
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except Exception as e:
                print(f"处理消息时出错: {e}")
                time.sleep(1)
    
    def _process_single_message(self, message: Dict[str, Any]):
        """处理单个消息"""
        user_id = message['user_id']
        user_name = message['user_name']
        content = message['content']
        
        # 检查是否需要回复
        if not self.llm.should_respond(content):
            print(f"跳过回复用户 {user_name} 的消息: {content[:30]}...")
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
        print(f"为 {user_name} 生成响应...")
        response = self.llm.generate_response(llm_messages, context)
        
        if response['success']:
            reply_content = response['content']
            
            # 检查是否是沉默响应
            if reply_content == "[SILENT]":
                print(f"对用户 {user_name} 保持沉默")
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
            
            print(f"为 {user_name} 生成响应完成")
        else:
            print(f"生成响应失败: {response.get('error', '未知错误')}")
    
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
                print(f"发送响应时出错: {e}")
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
            
            print(f"已发送消息给 {response['user_name']}: {content[:50]}...")
            
        except WeChatException as e:
            print(f"发送企业微信消息失败: {e}")
            # 如果是token问题，尝试刷新
            if "access_token" in str(e):
                print("检测到token问题，尝试刷新...")
                self.token_manager._refresh_token()
        except Exception as e:
            print(f"发送消息失败: {e}")
    
    def start(self):
        """启动机器人"""
        if self.is_running:
            print("机器人已经在运行中")
            return
        
        print("启动企业微信聊天机器人...")
        
        # 测试企业微信连接
        try:
            client = self._get_client_with_token()
            print("企业微信连接测试成功")
        except Exception as e:
            print(f"企业微信连接测试失败: {e}")
            print("请检查企业微信配置是否正确")
            return
        
        # 设置运行状态
        self.is_running = True
        
        # 启动处理线程
        self.processing_thread = threading.Thread(target=self._process_messages, daemon=True)
        self.response_thread = threading.Thread(target=self._send_responses, daemon=True)
        self.polling_thread = threading.Thread(target=self._poll_messages, daemon=True)
        
        self.processing_thread.start()
        self.response_thread.start()
        self.polling_thread.start()
        
        print("机器人已启动，开始处理消息...")
        print("按 Ctrl+C 停止机器人")
        
        # 主循环，保持程序运行
        try:
            while self.is_running:
                # 检查线程状态
                threads_alive = all([
                    self.processing_thread.is_alive(),
                    self.response_thread.is_alive(),
                    self.polling_thread.is_alive()
                ])
                
                if not threads_alive:
                    print("检测到线程异常，尝试重启...")
                    self._restart_threads()
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n收到停止信号...")
            self.stop()
        except Exception as e:
            print(f"主循环出错: {e}")
            self.stop()
    
    def _restart_threads(self):
        """重启线程"""
        if self.processing_thread and not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(target=self._process_messages, daemon=True)
            self.processing_thread.start()
            print("处理线程已重启")
        
        if self.response_thread and not self.response_thread.is_alive():
            self.response_thread = threading.Thread(target=self._send_responses, daemon=True)
            self.response_thread.start()
            print("响应线程已重启")
        
        if self.polling_thread and not self.polling_thread.is_alive():
            self.polling_thread = threading.Thread(target=self._poll_messages, daemon=True)
            self.polling_thread.start()
            print("轮询线程已重启")
    
    def stop(self):
        """停止机器人"""
        print("停止企业微信聊天机器人...")
        
        self.is_running = False
        
        # 等待线程结束
        threads = [self.processing_thread, self.response_thread, self.polling_thread]
        for thread in threads:
            if thread:
                thread.join(timeout=5)
        
        print("机器人已停止")
    
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
            print(f"测试消息发送成功: {user_id} - {content}")
            return True
        except Exception as e:
            print(f"发送测试消息失败: {e}")
            return False


# 全局机器人实例
_bot_instance = None

def get_bot() -> WeChatWorkBot:
    """获取机器人实例"""
    global _bot_instance
    
    if _bot_instance is None:
        _bot_instance = WeChatWorkBot()
    
    return _bot_instance
