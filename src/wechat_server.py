#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版企业微信服务器
支持IPv4/IPv6双栈，处理企业微信回调
"""

import os
import sys
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional
import urllib.parse as urlparse
from datetime import datetime

from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.enterprise import parse_message
from wechatpy.enterprise.replies import TextReply

from .config import get_config
from .logger import get_logger
from .user_session import get_session_manager, MessageType
from .message_processor import get_message_processor


class DualStackHTTPServer(HTTPServer):
    """支持IPv4和IPv6双栈的HTTP服务器（简化版）"""
    
    address_family = socket.AF_INET6
    
    def __init__(self, address, handler_class):
        self.dualstack_ipv6 = True
        super().__init__(address, handler_class)
    
    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except:
            pass  # 如果设置失败，继续使用默认配置
        return super().server_bind()


class WeChatCallbackHandler(BaseHTTPRequestHandler):
    """企业微信回调处理器（简化版）"""
    
    def __init__(self, *args, **kwargs):
        self.config = get_config()
        self.logger = get_logger("WeChatServer")
        self.session_manager = get_session_manager()
        self.message_processor = get_message_processor()
        
        # 初始化加密实例
        self.crypto = WeChatCrypto(
            self.config.wechat_callback_token,
            self.config.wechat_encoding_aes_key,
            self.config.wechat_corpid
        )
        
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """重写日志方法"""
        self.logger.info(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        """处理GET请求（企业微信服务器验证）"""
        try:
            # 解析查询参数
            parsed_url = urlparse.urlparse(self.path)
            query_params = urlparse.parse_qs(parsed_url.query)
            
            # 提取参数
            msg_signature = query_params.get('msg_signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            echostr = query_params.get('echostr', [''])[0]
            
            self.logger.info(f"收到GET验证请求: msg_signature={msg_signature[:10]}..., timestamp={timestamp}, nonce={nonce}")
            
            if not all([msg_signature, timestamp, nonce, echostr]):
                self.logger.error("GET请求缺少必要参数")
                self.send_error(400, "Missing required parameters")
                return
            
            # 验证签名并解密echostr
            try:
                decrypted_echostr = self.crypto.check_signature(
                    msg_signature,
                    timestamp,
                    nonce,
                    echostr
                )
                
                self.logger.info("GET验证成功")
                
                # 返回解密后的echostr
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(decrypted_echostr.encode('utf-8'))
                
            except Exception as e:
                self.logger.error(f"GET验证失败: {e}")
                self.send_error(400, "Signature verification failed")
                
        except Exception as e:
            self.logger.error(f"处理GET请求时出错: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def do_POST(self):
        """处理POST请求（接收企业微信消息）"""
        try:
            # 解析查询参数
            parsed_url = urlparse.urlparse(self.path)
            query_params = urlparse.parse_qs(parsed_url.query)
            
            # 提取参数
            msg_signature = query_params.get('msg_signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            
            self.logger.info(f"收到POST消息请求: msg_signature={msg_signature[:10]}..., timestamp={timestamp}, nonce={nonce}")
            
            if not all([msg_signature, timestamp, nonce]):
                self.logger.error("POST请求缺少必要参数")
                self.send_error(400, "Missing required parameters")
                return
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            request_body = self.rfile.read(content_length).decode('utf-8')
            
            self.logger.debug(f"POST请求体长度: {len(request_body)}")
            
            if not request_body:
                self.logger.error("POST请求体为空")
                self.send_error(400, "Empty request body")
                return
            
            # 解密消息
            try:
                decrypted_xml = self.crypto.decrypt_message(
                    request_body,
                    msg_signature,
                    timestamp,
                    nonce
                )
                
                self.logger.debug(f"解密后的XML: {decrypted_xml[:200]}...")
                
                # 解析消息
                message = parse_message(decrypted_xml)
                
                self.logger.info(f"解析消息: 类型={message.type}, 发送者={message.source}")
                
                # 处理消息
                response_xml = self._handle_message(message, nonce, timestamp)
                
                # 发送响应
                self.send_response(200)
                self.send_header('Content-Type', 'text/xml; charset=utf-8')
                self.end_headers()
                self.wfile.write(response_xml.encode('utf-8'))
                
                self.logger.info("POST请求处理完成")
                
            except Exception as e:
                self.logger.error(f"解密或处理消息失败: {e}")
                self.send_error(400, "Message processing failed")
                
        except Exception as e:
            self.logger.error(f"处理POST请求时出错: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def _handle_message(self, message, nonce: str, timestamp: str) -> str:
        """处理消息并返回响应XML"""
        try:
            user_id = message.source
            message_id = getattr(message, 'id', f"{int(time.time())}_{user_id}")
            
            # 只处理文本消息
            if message.type == 'text':
                content = message.content
                
                self.logger.info(f"收到文本消息来自 {user_id}: {content[:50]}...")
                
                # 添加到用户会话队列
                success = self.session_manager.add_message(
                    user_id=user_id,
                    message_id=message_id,
                    content=content,
                    message_type=MessageType.TEXT
                )
                
                if not success:
                    self.logger.error(f"添加消息到用户 {user_id} 的队列失败")
                
                # 企业微信要求：必须立即返回success，实际回复通过异步方式发送
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
                
            elif message.type == 'event':
                # 处理事件消息
                event_type = getattr(message, 'event', 'unknown')
                self.logger.info(f"收到事件消息: 事件类型={event_type}, 发送者={user_id}")
                
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
                self.logger.info(f"收到非文本消息，类型: {message.type}, 发送者: {user_id}")
                
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
            self.logger.error(f"处理消息时出错: {e}")
            
            # 出错时也返回success，避免企业微信重试
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


class WeChatServer:
    """企业微信服务器"""
    
    def __init__(self):
        """初始化服务器"""
        self.config = get_config()
        self.logger = get_logger("WeChatServer")
        self.server_config = self.config.get_server_config()
        
        self.httpd = None
        self.is_running = False
        
        self.logger.info(f"企业微信服务器初始化完成，监听地址: {self.server_config['host']}:{self.server_config['port']}")
    
    def start(self):
        """启动服务器"""
        if self.is_running:
            self.logger.warning("服务器已经在运行中")
            return
        
        server_address = (self.server_config['host'], self.server_config['port'])
        
        try:
            # 尝试使用双栈服务器
            self.httpd = DualStackHTTPServer(server_address, WeChatCallbackHandler)
            server_type = "双栈服务器 (IPv4 + IPv6)"
        except Exception as e:
            self.logger.warning(f"双栈服务器初始化失败，回退到标准HTTPServer: {e}")
            self.httpd = HTTPServer(server_address, WeChatCallbackHandler)
            server_type = "标准服务器 (IPv4)"
        
        # 解析主机地址显示信息
        host = self.server_config['host']
        if host == '::':
            display_host = ':: (所有IPv6地址，同时支持IPv4)'
        elif host == '0.0.0.0':
            display_host = '0.0.0.0 (所有IPv4地址)'
        elif ':' in host:
            display_host = f'{host} (IPv6地址)'
        else:
            display_host = f'{host} (IPv4地址)'
        
        self.logger.info(f"""
        ========================================
            企业微信回调服务器启动
        ========================================
        
        服务器配置：
        服务器类型: {server_type}
        监听地址: {display_host}
        监听端口: {self.server_config['port']}
        
        回调URL配置：
        企业微信回调URL: http://你的域名或IP:{self.server_config['port']}/callback
        Token: {self.config.wechat_callback_token[:10]}...
        EncodingAESKey: {self.config.wechat_encoding_aes_key[:10]}...
        
        按 Ctrl+C 停止服务器
        """)
        
        self.is_running = True
        
        # 启动服务器
        try:
            self.logger.info(f"服务器正在启动，监听 {host}:{self.server_config['port']}...")
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            self.logger.info("\n收到停止信号，正在关闭服务器...")
            self.stop()
        except Exception as e:
            self.logger.error(f"服务器运行出错: {e}")
            self.stop()
    
    def stop(self):
        """停止服务器"""
        self.is_running = False
        
        if self.httpd:
            self.httpd.server_close()
        
        self.logger.info("服务器已关闭")


def run_wechat_server():
    """运行企业微信服务器"""
    server = WeChatServer()
    server.start()


if __name__ == "__main__":
    # 测试服务器
    print("测试企业微信服务器...")
    
    # 设置测试配置
    os.environ["DEEPSEEK_API_KEY"] = "test_key"
    os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
    os.environ["WECHAT_WORK_CORPSECRET"] = "test_secret"
    os.environ["WECHAT_WORK_AGENTID"] = "1000002"
    os.environ["WECHAT_WORK_CALLBACK_TOKEN"] = "test_token"
    os.environ["WECHAT_WORK_ENCODING_AES_KEY"] = "test_aes_key"
    
    # 使用本地地址和测试端口
    os.environ["SERVER_HOST"] = "127.0.0.1"
    os.environ["SERVER_PORT"] = "8888"
    
    server = WeChatServer()
    
    # 在新线程中启动服务器
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    
    print("服务器已启动，按 Ctrl+C 停止...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止服务器...")
        server.stop()