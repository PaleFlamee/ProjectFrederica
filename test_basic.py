#!/usr/bin/env python3
"""
基本功能测试
"""

import sys
import os
from dotenv import load_dotenv

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_memory_system():
    """测试记忆系统"""
    print("测试记忆系统...")
    
    from src.memory import get_memory_system
    
    memory = get_memory_system()
    
    # 测试添加记忆
    test_user = "test_user_123"
    memory.add_memory(test_user, "用户说：你好，我是测试用户")
    memory.add_memory(test_user, "用户问：今天天气怎么样？")
    memory.add_memory(test_user, "Frederica回答：今天天气晴朗，适合外出")
    
    # 测试获取记忆
    memories = memory.get_recent_memories(test_user, limit=5)
    print(f"获取到 {len(memories)} 条记忆")
    
    for i, mem in enumerate(memories, 1):
        print(f"{i}. {mem['content'][:50]}...")
    
    # 测试搜索记忆
    search_results = memory.search_memories(test_user, "天气", limit=2)
    print(f"\n搜索'天气'找到 {len(search_results)} 条相关记忆")
    
    # 测试记忆摘要
    summary = memory.get_memory_summary(test_user)
    print(f"\n记忆摘要：\n{summary[:100]}...")
    
    # 清理测试数据
    memory.clear_user_memories(test_user)
    print("\n记忆系统测试完成！")
    
    return True


def test_llm_client():
    """测试LLM客户端"""
    print("\n测试LLM客户端...")
    
    from src.llm import get_llm_client
    
    try:
        llm = get_llm_client()
        
        # 测试token计数
        test_text = "你好，这是一个测试消息"
        token_count = llm.count_tokens(test_text)
        print(f"Token计数测试: '{test_text}' -> {token_count} tokens")
        
        # 测试是否应该回复
        should_respond = llm.should_respond("你好")
        print(f"是否应该回复'你好': {should_respond}")
        
        should_not_respond = llm.should_respond("好的")
        print(f"是否应该回复'好的': {should_not_respond}")
        
        # 测试沉默响应
        silent_response = llm.generate_silent_response()
        print(f"沉默响应: {silent_response}")
        
        print("LLM客户端测试完成！")
        return True
        
    except Exception as e:
        print(f"LLM客户端测试失败: {e}")
        return False


def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    
    try:
        from src.memory import MemorySystem
        from src.llm import DeepSeekClient
        from src.wechat_bot import WeChatWorkBot
        
        print("所有模块导入成功！")
        return True
    except ImportError as e:
        print(f"模块导入失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 50)
    print("Frederica 微信聊天机器人 - 基本功能测试")
    print("=" * 50)
    
    # 加载环境变量
    load_dotenv()
    
    # 检查API密钥
    if not os.getenv('DEEPSEEK_API_KEY'):
        print("警告: DEEPSEEK_API_KEY 未设置，部分测试可能失败")
        print("请设置环境变量或编辑.env文件")
    
    tests = [
        ("模块导入", test_imports),
        ("记忆系统", test_memory_system),
        ("LLM客户端", test_llm_client),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*30}")
        print(f"运行测试: {test_name}")
        print(f"{'='*30}")
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"测试异常: {e}")
            results.append((test_name, False))
    
    # 显示测试结果
    print(f"\n{'='*50}")
    print("测试结果汇总:")
    print(f"{'='*50}")
    
    all_passed = True
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{test_name:20} {status}")
        if not success:
            all_passed = False
    
    print(f"\n{'='*50}")
    if all_passed:
        print("所有测试通过！")
        print("可以运行 main.py 启动机器人")
    else:
        print("部分测试失败，请检查以上错误信息")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
