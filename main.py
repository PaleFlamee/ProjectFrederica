#!/usr/bin/env python3
"""
Frederica - 企业微信聊天机器人主程序
"""

import sys
import os
import argparse
from dotenv import load_dotenv

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.wechat_bot import get_bot


def check_environment():
    """检查环境配置"""
    load_dotenv()
    
    required_vars = ['DEEPSEEK_API_KEY', 'WECHAT_WORK_CORPID', 'WECHAT_WORK_CORPSECRET', 'WECHAT_WORK_AGENTID']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("错误：缺少必要的环境变量：")
        for var in missing_vars:
            print(f"  - {var}")
        print("\n请检查.env文件或设置环境变量。")
        print("企业微信配置说明：")
        print("1. 登录企业微信管理后台")
        print("2. 进入'应用管理' -> '自建应用'")
        print("3. 创建或选择应用，获取以下信息：")
        print("   - WECHAT_WORK_CORPID: 企业ID")
        print("   - WECHAT_WORK_CORPSECRET: 应用Secret")
        print("   - WECHAT_WORK_AGENTID: 应用ID")
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
    
    args = parser.parse_args()
    
    # 检查环境
    if not check_environment():
        sys.exit(1)
    
    if args.check:
        print("环境检查通过！")
        print(f"DeepSeek API Key: {'已设置' if os.getenv('DEEPSEEK_API_KEY') else '未设置'}")
        print(f"API Base: {os.getenv('DEEPSEEK_API_BASE', '默认')}")
        print(f"模型: {os.getenv('MODEL', '默认')}")
        print(f"企业ID: {os.getenv('WECHAT_WORK_CORPID', '未设置')}")
        print(f"应用ID: {os.getenv('WECHAT_WORK_AGENTID', '未设置')}")
        print(f"应用Secret: {'已设置' if os.getenv('WECHAT_WORK_CORPSECRET') else '未设置'}")
        return
    
    # 获取机器人实例
    bot = get_bot()
    
    if args.status:
        status = bot.get_status()
        print("机器人状态：")
        print(f"  运行状态: {'运行中' if status['is_running'] else '已停止'}")
        print(f"  待处理消息: {status['queue_size']}")
        print(f"  待发送响应: {status['response_queue_size']}")
        print(f"  活跃用户: {status['active_users']}")
        print(f"  已处理消息: {status['processed_messages']}")
        return
    
    if args.clear_memory:
        from src.memory import get_memory_system
        memory = get_memory_system()
        memory.clear_user_memories(args.clear_memory)
        print(f"已清除用户 {args.clear_memory} 的记忆")
        return
    
    if args.memory_summary:
        from src.memory import get_memory_system
        memory = get_memory_system()
        summary = memory.get_memory_summary(args.memory_summary)
        print(f"用户 {args.memory_summary} 的记忆摘要：")
        print(summary)
        return
    
    if args.send_test:
        success = bot.send_test_message(args.send_test, "这是一条测试消息，用于验证企业微信机器人连接。")
        if success:
            print(f"测试消息已发送到用户: {args.send_test}")
        else:
            print(f"发送测试消息失败，请检查配置")
        return
    
    # 启动机器人
    print("""
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
    2. 机器人将自动轮询并处理消息
    3. 支持文本消息的智能回复
    4. 按 Ctrl+C 停止机器人
    
    配置要求：
    1. DeepSeek API密钥
    2. 企业微信企业ID、应用Secret和应用ID
    3. 企业微信应用需要配置消息接收权限
    
    注意：企业微信消息接收需要配置回调或使用其他接收方式
          当前实现使用主动轮询模式，可能需要根据实际需求调整
    """)
    
    try:
        bot.start()
    except KeyboardInterrupt:
        print("\n收到停止信号，正在关闭机器人...")
        bot.stop()
    except Exception as e:
        print(f"机器人运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
