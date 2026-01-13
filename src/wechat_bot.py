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
        
        # 微信客服相关状态
        self.kf_token = None
        self.kf_open_kfid = None
        self.kf_cursor = None  # 用于增量拉取消息
        
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
        
        # 生成响应（允许LLM主动决定是否保持沉默）
        self.logger.info(f"为 {user_name} 生成响应...")
        response = self.llm.generate_response(llm_messages, context, allow_silent=True)
        
        if response['success']:
            reply_content = response['content']
            is_silent = response.get('is_silent', False)
            
            # 检查是否是沉默响应
            if is_silent or reply_content == "[SILENT]":
                self.logger.info(f"LLM决定对用户 {user_name} 保持沉默")
                # 从历史记录中移除用户的这条消息，因为LLM决定不回应
                # 这样可以避免沉默响应影响后续对话
                if session['history'] and session['history'][-1]['role'] == 'user':
                    session['history'].pop()
                return
            
            # 添加到响应队列，传递原始消息的所有相关参数
            response_data = {
                'user_id': user_id,
                'user_name': user_name,
                'content': reply_content,
                'msg_id': message['msg_id']
            }
            
            # 传递客服相关参数（如果存在）
            if 'is_kf_event' in message:
                response_data['is_kf_event'] = message['is_kf_event']
            if 'open_kfid' in message:
                response_data['open_kfid'] = message['open_kfid']
            
            self.response_queue.put(response_data)
            
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
            
            # 检查是否是客服消息
            is_kf_event = response.get('is_kf_event', False)
            open_kfid = response.get('open_kfid', self.kf_open_kfid)
            
            if is_kf_event and open_kfid:
                # 发送微信客服消息
                self._send_kf_message(user_id, open_kfid, content)
            else:
                # 发送普通企业微信消息
                self._send_work_message(user_id, content)
            
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
    
    def _send_work_message(self, user_id: str, content: str):
        """发送普通企业微信消息"""
        try:
            # 获取有效的客户端
            client = self._get_client_with_token()
            
            # 发送文本消息到企业微信
            # 注意：需要根据接收者类型（用户、部门、标签）使用不同的API
            client.message.send_text(self.agentid, user_id, content)
            
            self.logger.info(f"已发送企业微信消息给 {user_id}: {content[:50]}...")
            
        except WeChatException as e:
            self.logger.error(f"发送企业微信消息失败: {e}")
            # 如果是token问题，尝试刷新
            if "access_token" in str(e):
                self.logger.warning("检测到token问题，尝试刷新...")
                self.token_manager._refresh_token()
        except Exception as e:
            self.logger.error(f"发送企业微信消息失败: {e}")
    
    def _send_kf_message(self, external_userid: str, open_kfid: str, content: str):
        """发送微信客服消息"""
        # 在方法开头导入requests，避免在异常处理中引用未定义的变量
        import requests
        
        try:
            # 参数验证
            if not external_userid or not isinstance(external_userid, str):
                self.logger.error(f"无效的external_userid: {external_userid}")
                raise ValueError(f"无效的external_userid: {external_userid}")
            
            if not open_kfid or not isinstance(open_kfid, str):
                self.logger.error(f"无效的open_kfid: {open_kfid}")
                raise ValueError(f"无效的open_kfid: {open_kfid}")
            
            if not content or not isinstance(content, str):
                self.logger.error(f"无效的消息内容: {content}")
                raise ValueError(f"无效的消息内容: {content}")
            
            self.logger.info(f"准备发送微信客服消息: 用户={external_userid}, 客服账号={open_kfid}, 内容长度={len(content)}")
            
            # 获取access_token
            access_token = self.token_manager.get_token()
            
            # 构建请求URL
            url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg?access_token={access_token}"
            
            # 构建请求体
            request_data = {
                "touser": external_userid,
                "open_kfid": open_kfid,
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
            
            self.logger.debug(f"微信客服API请求数据: {request_data}")
            
            # 发送POST请求
            response = requests.post(url, json=request_data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("errcode") != 0:
                error_code = result.get("errcode")
                error_msg = result.get("errmsg")
                
                # 记录错误信息
                self.logger.error(f"发送微信客服消息失败: 错误代码={error_code}, 错误信息={error_msg}")
                self.logger.error(f"请求参数: external_userid={external_userid}, open_kfid={open_kfid}")
                self.logger.error(f"响应结果: {result}")
                
                raise Exception(f"微信客服API错误 {error_code}: {error_msg}")
            
            self.logger.info(f"已成功发送微信客服消息给 {external_userid}: {content[:50]}...")
            self.logger.debug(f"API响应: {result}")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"网络请求失败: {e}")
            self.logger.error(f"请求URL: {url if 'url' in locals() else '未知'}")
            raise Exception(f"网络请求失败: {e}")
        except ValueError as e:
            self.logger.error(f"参数验证失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"发送微信客服消息失败: {e}", exc_info=True)
            raise
    
    def start(self, blocking: bool = True):
        """
        启动机器人
        
        Args:
            blocking: 是否阻塞运行（True: 运行主循环，适合独立运行；False: 只启动线程后返回，适合集成到其他服务中）
        """
        if self.is_running:
            self.logger.warning("机器人已经在运行中")
            return
        
        self.logger.info("启动企业微信聊天机器人...")
        
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
        
        if blocking:
            self.logger.info("按 Ctrl+C 停止机器人")
            
            # 主循环，保持程序运行（阻塞模式）
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
        else:
            # 非阻塞模式，只启动线程后返回
            self.logger.info("机器人以非阻塞模式启动，线程已在后台运行")
    
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
                    
                    # 首先尝试直接解析XML，因为wechatpy可能无法识别kf_msg_or_event事件
                    root = ET.fromstring(decrypted_xml)
                    
                    # 提取MsgType和Event
                    msg_type_elem = root.find('MsgType')
                    event_elem = root.find('Event')
                    
                    msg_type = msg_type_elem.text if msg_type_elem is not None else None
                    event_type = event_elem.text if event_elem is not None else None
                    
                    self.logger.info(f"直接解析XML: MsgType={msg_type}, Event={event_type}")
                    
                    # 解析消息对象（用于其他字段）
                    message = parse_message(decrypted_xml)
                    self.logger.info(f"wechatpy解析: 类型={message.type}, 发送者={message.source}")
                    
                    # 处理不同类型的消息
                    if msg_type == 'text':
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
                    
                    elif msg_type == 'event' and event_type == 'kf_msg_or_event':
                        # 处理客服消息事件
                        self.logger.info(f"处理客服消息事件 (kf_msg_or_event)")
                        
                        try:
                            # 提取Token和OpenKfId
                            token = None
                            open_kfid = None
                            
                            # 提取Token
                            token_field = root.find('Token')
                            if token_field is not None:
                                token = token_field.text
                                self.logger.debug(f"提取到Token: {token[:20]}...")
                            
                            # 提取OpenKfId
                            open_kfid_field = root.find('OpenKfId')
                            if open_kfid_field is not None:
                                open_kfid = open_kfid_field.text
                                self.logger.debug(f"提取到OpenKfId: {open_kfid}")
                            
                            # 保存到实例变量
                            if token and open_kfid:
                                self.kf_token = token
                                self.kf_open_kfid = open_kfid
                                
                                self.logger.info(f"客服事件已接收，Token: {token[:20]}..., OpenKfId: {open_kfid}")
                                
                                # 在新线程中拉取消息，避免阻塞回调响应
                                threading.Thread(
                                    target=self._fetch_kf_messages,
                                    args=(token, open_kfid),
                                    daemon=True
                                ).start()
                                
                                self.logger.info(f"已启动消息拉取线程")
                            else:
                                self.logger.warning(f"无法从事件消息中提取Token或OpenKfId")
                                self.logger.debug(f"Token: {token}, OpenKfId: {open_kfid}")
                            
                        except Exception as e:
                            self.logger.error(f"解析客服事件失败: {e}")
                            self.logger.debug(f"原始XML: {decrypted_xml}")
                        
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
                    
                    elif msg_type == 'event':
                        # 其他类型的事件消息
                        self.logger.info(f"收到其他事件消息: Event={event_type}")
                        
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
                    
                    else:
                        # 其他类型的消息（图片、语音等）
                        self.logger.info(f"收到非文本消息，类型: {msg_type}")
                        
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
    
    def _fetch_kf_messages(self, token: str, open_kfid: str) -> None:
        """
        拉取微信客服消息
        
        Args:
            token: 回调事件返回的token，10分钟内有效
            open_kfid: 客服账号ID
        """
        try:
            self.logger.info(f"开始拉取微信客服消息，open_kfid: {open_kfid}")
            
            # 获取access_token
            access_token = self.token_manager.get_token()
            
            # 构建请求URL
            url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg?access_token={access_token}"
            
            # 构建请求体
            request_data = {
                "token": token,
                "open_kfid": open_kfid,
                "limit": 1000,
                "voice_format": 0
            }
            
            # 如果有cursor，添加到请求中
            if self.kf_cursor:
                request_data["cursor"] = self.kf_cursor
            
            # 发送POST请求
            import requests
            response = requests.post(url, json=request_data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("errcode") != 0:
                self.logger.error(f"拉取微信客服消息失败: {result.get('errmsg')}")
                return
            
            # 更新cursor
            self.kf_cursor = result.get("next_cursor")
            
            # 处理消息列表
            msg_list = result.get("msg_list", [])
            self.logger.info(f"拉取到 {len(msg_list)} 条客服消息")
            
            for msg in msg_list:
                self._process_kf_message(msg)
            
            # 如果还有更多消息，继续拉取
            if result.get("has_more") == 1:
                self.logger.info("还有更多消息，继续拉取...")
                # 为了避免阻塞，可以在新线程中继续拉取
                threading.Thread(target=self._fetch_kf_messages, args=(token, open_kfid), daemon=True).start()
                
        except Exception as e:
            self.logger.error(f"拉取微信客服消息时出错: {e}", exc_info=True)
    
    def _process_kf_message(self, msg: Dict[str, Any]) -> None:
        """
        处理单条客服消息
        
        Args:
            msg: 消息数据
        """
        try:
            msg_type = msg.get("msgtype")
            origin = msg.get("origin", 0)
            
            # 只处理微信客户发送的消息（origin=3）
            if origin != 3:
                self.logger.debug(f"跳过非客户消息，origin: {origin}")
                return
            
            # 获取用户ID和消息内容
            external_userid = msg.get("external_userid")
            open_kfid = msg.get("open_kfid")
            
            if not external_userid:
                self.logger.warning("消息缺少external_userid，跳过处理")
                return
            
            # 根据消息类型处理内容
            content = ""
            if msg_type == "text":
                text_data = msg.get("text", {})
                content = text_data.get("content", "")
            elif msg_type in ["image", "voice", "video", "file"]:
                # 媒体文件消息，暂时处理为文本提示
                content = f"[收到{msg_type}消息]"
            else:
                self.logger.info(f"跳过不支持的消息类型: {msg_type}")
                return
            
            if not content:
                self.logger.warning("消息内容为空，跳过处理")
                return
            
            self.logger.info(f"处理客服消息: 用户={external_userid}, 内容={content[:50]}...")
            
            # 生成消息ID
            msg_id = msg.get("msgid", f"kf_{int(time.time())}_{external_userid}")
            
            # 添加到消息队列进行处理
            self.message_queue.put({
                'type': 'text',
                'user_id': external_userid,
                'user_name': external_userid,  # 暂时使用external_userid作为用户名
                'content': content,
                'msg_id': msg_id,
                'timestamp': datetime.now().isoformat(),
                'is_callback': True,
                'is_kf_event': True,
                'open_kfid': open_kfid
            })
            
            self.logger.info(f"客服消息已添加到处理队列，当前队列大小: {self.message_queue.qsize()}")
            
        except Exception as e:
            self.logger.error(f"处理客服消息时出错: {e}", exc_info=True)
    
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
            
            # 生成响应（允许LLM主动决定是否保持沉默）
            self.logger.info(f"为 {user_id} 生成同步响应...")
            response = self.llm.generate_response(llm_messages, context, allow_silent=True)
            
            if response['success']:
                reply_content = response['content']
                is_silent = response.get('is_silent', False)
                
                # 检查是否是沉默响应
                if is_silent or reply_content == "[SILENT]":
                    self.logger.info(f"LLM决定对用户 {user_id} 保持沉默")
                    # 从历史记录中移除用户的这条消息，因为LLM决定不回应
                    if session['history'] and session['history'][-1]['role'] == 'user':
                        session['history'].pop()
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
