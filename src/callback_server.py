#!/usr/bin/env python3
"""
企业微信回调服务器
提供HTTP接口处理企业微信的回调请求
支持IPv4和IPv6双栈
"""

import os
import sys
import socket
from typing import Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import urllib.parse as urlparse
from dotenv import load_dotenv

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.wechat_bot import get_bot
from src.logger import get_logger


class DualStackHTTPServer(HTTPServer):
    """支持IPv4和IPv6双栈的HTTP服务器"""
    
    address_family = socket.AF_INET6  # 使用IPv6地址族
    allow_reuse_address = True  # 允许地址重用
    
    def __init__(self, address, handler_class):
        # 设置双栈支持
        self.dualstack_ipv6 = True
        super().__init__(address, handler_class)
    
    def server_bind(self):
        # 设置socket选项以支持双栈
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        return super().server_bind()


class WeChatCallbackHandler(BaseHTTPRequestHandler):
    """企业微信回调HTTP处理器"""
    
    def __init__(self, *args, **kwargs):
        self.bot = get_bot()
        self.logger = get_logger()
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """重写日志方法，使用项目日志器"""
        self.logger.info(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        """处理GET请求（企业微信服务器验证）"""
        try:
            # 解析URL和查询参数
            parsed_url = urlparse.urlparse(self.path)
            query_params = urlparse.parse_qs(parsed_url.query)
            
            # 转换参数格式（从列表转换为字符串）
            simple_params: Dict[str, str] = {}
            for key, value in query_params.items():
                if value:
                    simple_params[key] = value[0]
            
            self.logger.info(f"收到GET请求: {self.path}")
            self.logger.info(f"查询参数: {simple_params}")
            self.logger.debug(f"原始查询参数: {query_params}")
            self.logger.debug(f"解析后的URL: {parsed_url}")
            
            # 记录详细的参数信息
            for param_name, param_value in simple_params.items():
                self.logger.debug(f"参数 {param_name}: {param_value} (长度: {len(param_value)})")
            
            # 处理回调请求
            self.logger.debug("开始处理GET回调请求...")
            response = self.bot.handle_callback_request('GET', simple_params)
            
            # 发送响应
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
            self.logger.info(f"GET请求处理完成，响应长度: {len(response)}")
            self.logger.debug(f"响应内容: {response}")
            
            # 记录响应头
            self.logger.debug(f"响应状态: 200 OK")
            self.logger.debug(f"响应Content-Type: text/plain; charset=utf-8")
            
        except Exception as e:
            self.logger.error(f"处理GET请求时出错: {e}", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}: {str(e)}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def do_POST(self):
        """处理POST请求（接收企业微信消息）"""
        try:
            # 解析URL和查询参数
            parsed_url = urlparse.urlparse(self.path)
            query_params = urlparse.parse_qs(parsed_url.query)
            
            # 转换参数格式
            simple_params: Dict[str, str] = {}
            for key, value in query_params.items():
                if value:
                    simple_params[key] = value[0]
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            request_body = self.rfile.read(content_length).decode('utf-8')
            
            self.logger.info(f"收到POST请求: {self.path}")
            self.logger.info(f"查询参数: {simple_params}")
            self.logger.info(f"请求体长度: {len(request_body)}")
            self.logger.debug(f"原始查询参数: {query_params}")
            self.logger.debug(f"解析后的URL: {parsed_url}")
            self.logger.debug(f"请求头: {dict(self.headers)}")
            self.logger.debug(f"Content-Length: {content_length}")
            
            # 记录详细的参数信息
            for param_name, param_value in simple_params.items():
                self.logger.debug(f"参数 {param_name}: {param_value} (长度: {len(param_value)})")
            
            # 记录请求体详细信息
            if request_body:
                self.logger.debug(f"请求体前500字符: {request_body[:500]}")
                self.logger.debug(f"请求体MD5: {hash(request_body)}")
                self.logger.debug(f"请求体是否包含XML: {'<?xml' in request_body[:100]}")
            else:
                self.logger.warning("请求体为空")
            
            # 处理回调请求
            self.logger.debug("开始处理POST回调请求...")
            response = self.bot.handle_callback_request('POST', simple_params, request_body)
            
            # 发送响应
            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
            self.logger.info(f"POST请求处理完成，响应长度: {len(response)}")
            self.logger.debug(f"响应内容前500字符: {response[:500] if response else '空响应'}")
            self.logger.debug(f"响应是否包含XML: {'<?xml' in response[:100] if response else False}")
            
            # 记录响应头
            self.logger.debug(f"响应状态: 200 OK")
            self.logger.debug(f"响应Content-Type: text/xml; charset=utf-8")
            
        except Exception as e:
            self.logger.error(f"处理POST请求时出错: {e}", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}: {str(e)}")
            self.logger.debug(f"请求路径: {self.path}")
            self.logger.debug(f"请求参数: {simple_params}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def do_HEAD(self):
        """处理HEAD请求（健康检查）"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
    
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检）"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def run_callback_server(host: str = '::', port: int = 8080):
    """
    启动回调服务器（支持IPv4和IPv6双栈）
    
    Args:
        host: 监听地址（默认: '::' 表示所有IPv6地址，也支持IPv4）
        port: 监听端口
    """
    load_dotenv()
    
    logger = get_logger()
    
    # 检查必要的环境变量
    required_vars = ['WECHAT_WORK_CORPID', 'WECHAT_WORK_CORPSECRET', 'WECHAT_WORK_AGENTID']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error("错误：缺少必要的环境变量：")
        for var in missing_vars:
            logger.error(f"  - {var}")
        logger.error("\n请检查.env文件或设置环境变量。")
        return
    
    # 初始化机器人（确保配置正确）
    try:
        bot = get_bot()
        logger.info("机器人初始化成功")
    except Exception as e:
        logger.error(f"机器人初始化失败: {e}")
        return
    
    server_address = (host, port)
    
    # 根据主机地址选择服务器类型
    try:
        # 尝试使用双栈服务器（支持IPv6和IPv4）
        httpd = DualStackHTTPServer(server_address, WeChatCallbackHandler)
        server_type = "双栈服务器 (IPv4 + IPv6)"
    except Exception as e:
        logger.warning(f"双栈服务器初始化失败，回退到标准HTTPServer: {e}")
        # 回退到标准HTTPServer
        httpd = HTTPServer(server_address, WeChatCallbackHandler)
        server_type = "标准服务器 (IPv4)"
    
    # 解析主机地址的显示名称
    if host == '::':
        display_host = ':: (所有IPv6地址，同时支持IPv4)'
        access_info = '允许所有网络接口访问（IPv4和IPv6）'
    elif host == '0.0.0.0':
        display_host = '0.0.0.0 (所有IPv4地址)'
        access_info = '允许所有IPv4网络接口访问'
    elif host in ['127.0.0.1', 'localhost']:
        display_host = f'{host} (本机IPv4地址)'
        access_info = '只允许本机IPv4访问'
    elif host == '::1':
        display_host = '::1 (本机IPv6地址)'
        access_info = '只允许本机IPv6访问'
    elif ':' in host:  # IPv6地址
        display_host = f'{host} (IPv6地址)'
        access_info = f'只允许特定IPv6网络接口访问: {host}'
    else:  # IPv4地址
        display_host = f'{host} (IPv4地址)'
        access_info = f'只允许特定IPv4网络接口访问: {host}'
    
    logger.info(f"""
    ========================================
        企业微信回调服务器启动
    ========================================
    
    服务器配置：
    服务器类型: {server_type}
    监听地址: {display_host}
    监听端口: {port}
    
    网络访问说明：
    {access_info}
    
    支持的协议：
    - IPv4: {'是' if server_type == '双栈服务器 (IPv4 + IPv6)' or host != '::1' else '否'}
    - IPv6: {'是' if server_type == '双栈服务器 (IPv4 + IPv6)' or host == '::' or host == '::1' or ':' in host else '否'}
    
    回调URL配置：
    IPv4访问URL: http://{host if host not in ['::', '0.0.0.0'] else 'localhost'}:{port}/callback
    IPv6访问URL: http://[{host if host != '::' else '::1'}]:{port}/callback
    
    重要提示：
    1. 如果监听地址是 '::'，服务器同时支持IPv4和IPv6
    2. 如果监听地址是 '0.0.0.0'，只支持IPv4
    3. 如果监听地址是 '127.0.0.1' 或 'localhost'，只支持本机IPv4访问
    4. 如果监听地址是 '::1'，只支持本机IPv6访问
    5. 生产环境建议使用域名和HTTPS
    
    企业微信配置要求：
    1. 在企业微信管理后台配置回调URL
    2. 使用以下参数：
       - URL: http://tx6p.paleflame.top/callback (根据实际域名调整)
       - Token: FREDERICATOKEN
       - EncodingAESKey: norTzT7trWzPklIJEBILTG7UMzMXuibpzlAVaS4zag0
       - 消息加解密方式: 安全模式
    
    按 Ctrl+C 停止服务器
    """)
    
    try:
        logger.info(f"服务器正在启动，监听 {host}:{port}...")
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在关闭服务器...")
        httpd.server_close()
        logger.info("服务器已关闭")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")
        httpd.server_close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='企业微信回调服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='监听端口 (默认: 8080)')
    parser.add_argument('--test', action='store_true', help='测试回调功能')
    
    args = parser.parse_args()
    
    if args.test:
        # 测试回调功能
        logger = get_logger()
        logger.info("测试回调功能...")
        
        try:
            bot = get_bot()
            
            # 测试GET验证
            test_params = {
                'msg_signature': 'test_signature',
                'timestamp': '1234567890',
                'nonce': 'test_nonce',
                'echostr': 'test_echostr'
            }
            
            logger.info("测试GET验证...")
            result = bot.handle_callback_request('GET', test_params)
            logger.info(f"GET测试结果: {result}")
            
            # 测试同步消息处理
            logger.info("测试同步消息处理...")
            reply = bot.process_callback_message_sync('test_user', '你好')
            logger.info(f"同步消息处理结果: {reply}")
            
            logger.info("回调功能测试完成")
            
        except Exception as e:
            logger.error(f"测试失败: {e}", exc_info=True)
    else:
        # 启动服务器
        run_callback_server(args.host, args.port)
