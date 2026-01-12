#!/usr/bin/env python3
"""
Frederica - 企业微信聊天机器人主程序
支持回调服务器模式
"""

import sys
import os
import argparse
from dotenv import load_dotenv

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.wechat_bot import get_bot
from src.callback_server import run_callback_server
from src.logger import get_logger


def check_environment():
    """检查环境配置"""
    load_dotenv()
    
    required_vars = ['DEEPSEEK_API_KEY', 'WECHAT_WORK_CORPID', 'WECHAT_WORK_CORPSECRET', 'WECHAT_WORK_AGENTID']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger = get_logger()
        logger.error("错误：缺少必要的环境变量：")
        for var in missing_vars:
            logger.error(f"  - {var}")
        logger.error("\n请检查.env文件或设置环境变量。")
        logger.error("企业微信配置说明：")
        logger.error("1. 登录企业微信管理后台")
        logger.error("2. 进入'应用管理' -> '自建应用'")
        logger.error("3. 创建或选择应用，获取以下信息：")
        logger.error("   - WECHAT_WORK_CORPID: 企业ID")
        logger.error("   - WECHAT_WORK_CORPSECRET: 应用Secret")
        logger.error("   - WECHAT_WORK_AGENTID: 应用ID")
        return False
    
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Frederica - 企业微信聊天机器人')
    parser.add_argument('--check', action='store_true', help='检查环境配置')
    parser.add_argument('--status', action='store_true', help='显示机器人状态')
    parser.add_argument('--clear-memory', metavar='USER_ID', help='清除指定用户的记忆')
    parser.add_argument('--memory-summary', metavar='USER_ID', help='显示用户的记忆摘要')
    parser.add_argument('--send-test', metavar='USER_ID', help='发送测试消息到指定用户')
    parser.add_argument('--callback', action='store_true', help='启动回调服务器（默认模式）')
    parser.add_argument('--host', default='0.0.0.0', help='回调服务器监听地址（默认: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=8080, help='回调服务器监听端口（默认: 8080）')
    
    args = parser.parse_args()
    
    # 检查环境
    if not check_environment():
        sys.exit(1)
    
    if args.check:
        logger = get_logger()
        logger.info("环境检查通过！")
        logger.info(f"DeepSeek API Key: {'已设置' if os.getenv('DEEPSEEK_API_KEY') else '未设置'}")
        logger.info(f"API Base: {os.getenv('DEEPSEEK_API_BASE', '默认')}")
        logger.info(f"模型: {os.getenv('MODEL', '默认')}")
        logger.info(f"企业ID: {os.getenv('WECHAT_WORK_CORPID', '未设置')}")
        logger.info(f"应用ID: {os.getenv('WECHAT_WORK_AGENTID', '未设置')}")
        logger.info(f"应用Secret: {'已设置' if os.getenv('WECHAT_WORK_CORPSECRET') else '未设置'}")
        return
    
    # 获取机器人实例
    bot = get_bot()
    
    if args.status:
        status = bot.get_status()
        logger = get_logger()
        logger.info("机器人状态：")
        logger.info(f"  运行状态: {'运行中' if status['is_running'] else '已停止'}")
        logger.info(f"  待处理消息: {status['queue_size']}")
        logger.info(f"  待发送响应: {status['response_queue_size']}")
        logger.info(f"  活跃用户: {status['active_users']}")
        logger.info(f"  已处理消息: {status['processed_messages']}")
        return
    
    if args.clear_memory:
        from src.memory import get_memory_system
        memory = get_memory_system()
        memory.clear_user_memories(args.clear_memory)
        logger = get_logger()
        logger.info(f"已清除用户 {args.clear_memory} 的记忆")
        return
    
    if args.memory_summary:
        from src.memory import get_memory_system
        memory = get_memory_system()
        summary = memory.get_memory_summary(args.memory_summary)
        logger = get_logger()
        logger.info(f"用户 {args.memory_summary} 的记忆摘要：")
        logger.info(summary)
        return
    
    if args.send_test:
        success = bot.send_test_message(args.send_test, "这是一条测试消息，用于验证企业微信机器人连接。")
        logger = get_logger()
        if success:
            logger.info(f"测试消息已发送到用户: {args.send_test}")
        else:
            logger.error(f"发送测试消息失败，请检查配置")
        return
    
    # 启动回调服务器（默认模式）
    logger = get_logger()
    logger.info("""
    ========================================
        Frederica - 企业微信聊天机器人
    ========================================
    
    功能特性：
    1. 基于企业微信官方API
    2. 异步对话处理
    3. 长期记忆存储
    4. 智能上下文理解
    5. 自然语言交互
    
    使用说明：
    1. 确保已正确配置企业微信应用
    2. 启动回调服务器接收企业微信消息
    3. 在企业微信管理后台配置回调URL
    4. 支持文本消息的智能回复
    5. 按 Ctrl+C 停止服务器
    
    配置要求：
    1. DeepSeek API密钥
    2. 企业微信企业ID、应用Secret和应用ID
    3. 企业微信应用需要配置消息回调URL
    
    回调URL配置：
    1. 在企业微信管理后台配置回调URL
    2. URL格式: http://你的域名或IP:端口/callback
    3. Token: FREDERICATOKEN
    4. EncodingAESKey: norTzT7trWzPklIJEBILTG7UMzMXuibpzlAVaS4zag0
    5. 消息加解密方式: 安全模式
    
    注意：企业微信消息接收必须使用回调模式
          轮询模式已被废弃，不再支持
    """)
    
    try:
        # 启动回调服务器
        run_callback_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
