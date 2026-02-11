#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_client.py
简易LLM聊天客户端
"""

import json
import os
import sys
from typing import Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入现有工具模块
try:
    from tools.list_file_tool import execute_tool_call as execute_list, TOOL_DEFINITION as LIST_TOOL
    from tools.read_file_tool import execute_tool_call as execute_read, TOOL_DEFINITION as READ_TOOL
    from tools.create_file_or_folder_tool import execute_tool_call as execute_create, TOOL_DEFINITION as CREATE_TOOL
    from tools.write_to_file_tool import execute_tool_call as execute_write, TOOL_DEFINITION as WRITE_TOOL
    from tools.search_files_tool import execute_tool_call as execute_search, TOOL_DEFINITION as SEARCH_TOOL
    from tools.delete_file_or_folder_tool import execute_tool_call as execute_delete, TOOL_DEFINITION as DELETE_TOOL
    
    print("✓ 成功导入所有工具模块")
except ImportError as e:
    print(f"✗ 导入工具模块失败: {e}")
    print("请确保所有工具文件都在当前目录中")
    sys.exit(1)

# 从环境变量配置API客户端
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not API_KEY:
    print("错误：未设置DEEPSEEK_API_KEY环境变量")
    print("请在.env文件中设置DEEPSEEK_API_KEY，或通过系统环境变量设置")
    sys.exit(1)

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

# 定义所有可用工具
TOOLS = [
    LIST_TOOL,
    READ_TOOL,
    CREATE_TOOL,
    WRITE_TOOL,
    SEARCH_TOOL,
    DELETE_TOOL
]

# 工具执行器映射
TOOL_EXECUTORS = {
    "list_files": execute_list,
    "read_file": execute_read,
    "create_file_or_folder": execute_create,
    "write_file": execute_write,
    "search_files": execute_search,
    "delete_file_or_folder": execute_delete
}

def load_soul_content() -> str:
    """
    读取brain/soul.md文件内容作为system prompt
    
    Returns:
        str: 文件内容，如果文件不存在或为空则返回空字符串
    """
    soul_path = os.path.join("brain", "soul.md")
    max_size = 10 * 1024  # 10KB限制
    
    try:
        # 检查文件是否存在且有内容
        if not os.path.exists(soul_path):
            return ""
        
        file_size = os.path.getsize(soul_path)
        if file_size == 0:
            return ""
        
        # 检查文件大小
        if file_size > max_size:
            print(f"警告：soul.md文件过大（{file_size}字节），超过{max_size}字节限制")
            return ""
        
        # 尝试UTF-8编码
        try:
            with open(soul_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return content if content else ""
        except UnicodeDecodeError:
            # 尝试GBK编码
            try:
                with open(soul_path, 'r', encoding='gbk') as f:
                    content = f.read().strip()
                    return content if content else ""
            except:
                return ""
    except Exception:
        # 任何其他错误都静默处理
        return ""
    
    return ""

def display_message(role: str, content: str, indent: int = 0):
    """
    显示格式化消息
    
    Args:
        role: 消息角色 (User, Assistant, Tool Call, Tool Result)
        content: 要写入的内容
        indent: 缩进级别
    """
    indent_str = " " * indent
    print(f"{indent_str}[{role}] > {content}")

def format_tool_call(tool_call: Any) -> str:
    """
    格式化工具调用信息
    
    Args:
        tool_call: 工具调用对象
        
    Returns:
        str: 格式化的工具调用字符串
    """
    try:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        return f"{function_name}({json.dumps(arguments, ensure_ascii=False)})"
    except Exception as e:
        return f"格式化工具调用失败: {e}"

def format_assistant_message(assistant_message: Any) -> Dict[str, Any]:
    """
    格式化助手消息，确保tool_calls字段正确
    
    Args:
        assistant_message: 助手消息对象
        
    Returns:
        Dict: 格式化的助手消息字典
    """
    message_dict = {
        "role": "assistant",
        "content": assistant_message.content or ""
    }
    
    if assistant_message.tool_calls:
        # 正确格式化tool_calls字段
        message_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            for tc in assistant_message.tool_calls
        ]
    
    return message_dict

def execute_tools(tool_calls: List[Any]) -> List[Dict[str, Any]]:
    """
    执行工具调用并返回结果
    
    Args:
        tool_calls: 工具调用列表
        
    Returns:
        List[Dict]: 工具执行结果列表
    """
    tool_results = []
    
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        
        # 显示工具调用
        display_message("Tool Call", format_tool_call(tool_call))
        
        # 转换为字典格式（与现有工具兼容）
        tool_call_dict = {
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": function_name,
                "arguments": tool_call.function.arguments
            }
        }
        
        # 执行工具
        if function_name in TOOL_EXECUTORS:
            try:
                result = TOOL_EXECUTORS[function_name](tool_call_dict)
                display_message("Tool Result", result, indent=2)
                
                # 添加到结果列表
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            except Exception as e:
                error_msg = f"执行工具 {function_name} 时发生错误: {e}"
                display_message("Tool Result", error_msg, indent=2)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": error_msg
                })
        else:
            error_msg = f"未知的工具: {function_name}"
            display_message("Tool Result", error_msg, indent=2)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": error_msg
            })
    
    return tool_results


def process_tool_calls_loop(initial_message, messages, client, tools, tool_executors):
    """
    处理工具调用循环，执行所有工具调用并获取最终回复
    
    Args:
        initial_message: 初始的助手消息（包含工具调用）
        messages: 当前的消息历史列表
        client: OpenAI客户端实例
        tools: 可用工具列表
        tool_executors: 工具执行器映射
        
    Returns:
        tuple: (current_message, messages) - 最终消息和更新后的消息历史
    """
    current_message = initial_message
    has_tool_calls = bool(current_message.tool_calls)
    
    while has_tool_calls:
        # 执行当前轮次的工具调用
        tool_results = execute_tools(current_message.tool_calls)
        
        # 将工具结果添加到消息历史
        messages.extend(tool_results)
        
        # 再次调用API获取新的回复
        next_response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        current_message = next_response.choices[0].message
        
        # 显示助手回复
        if current_message.content:
            display_message("Assistant", current_message.content)
        
        # 添加到消息历史（使用格式化函数确保tool_calls正确）
        messages.append(format_assistant_message(current_message))
        
        # 检查是否还有工具调用需要处理
        has_tool_calls = bool(current_message.tool_calls)
    
    return current_message, messages


def chat_loop():
    """
    主聊天循环
    """
    # 加载soul.md内容作为system prompt
    soul_content = load_soul_content()
    messages = []
    from datetime import datetime
    
    if soul_content:
        messages.append({"role": "system", "content": soul_content})
        print(f"[System] 已加载soul.md内容作为system prompt（{len(soul_content)}字符）")
    messages.append({"role": "system", "content": datetime.now().strftime("<time>%Y-%m-%d %H:%M:%S CST ") + "<channel>cli " + "<user_id>PaleFlame"})

    print("\n" + "="*60)
    print("简易LLM聊天客户端")
    print("="*60)
    print("可用工具:")
    for i, tool in enumerate(TOOLS, 1):
        print(f"  {i}. {tool['function']['name']} - {tool['function']['description'][:50]}...")
    print("\n输入 'quit' 或 'exit' 退出程序")
    print("="*60)
    
    while True:
        try:
            # 获取用户输入
            user_input = input("\n[User] > ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n感谢使用，再见！")
                break
            
            if not user_input:
                continue
            
            # 添加时间信息
            user_input

            # 添加到消息历史
            messages.append({"role": "user", "content": user_input})
            
            # 调用API
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto"
                )
                
                assistant_message = response.choices[0].message
                
                # 显示助手回复
                if assistant_message.content:
                    display_message("Assistant", assistant_message.content)
                
                # 添加到消息历史（使用格式化函数确保tool_calls正确）
                messages.append(format_assistant_message(assistant_message))
                
                # 处理工具调用 - 使用新封装的函数处理工具调用循环
                current_message, messages = process_tool_calls_loop(
                    initial_message=assistant_message,
                    messages=messages,
                    client=client,
                    tools=TOOLS,
                    tool_executors=TOOL_EXECUTORS
                )
                
                # 循环结束后，确保最后的消息格式正确
                if current_message.content and messages and messages[-1]["role"] == "assistant":
                    # 更新最后一条消息的tool_calls（如果有）
                    display_message("System", "CORRECTION TRIGGERED")
                    messages[-1]["tool_calls"] = current_message.tool_calls
                            
            except Exception as e:
                display_message("System", f"API调用失败: {e}")
                # 移除最后一条用户消息以便重试
                if messages and messages[-1]["role"] == "user":
                    messages.pop()
        
        except KeyboardInterrupt:
            print("\n\n检测到中断，退出程序...")
            break
        except Exception as e:
            display_message("System", f"发生错误: {e}")
    # 退出对话

def main():
    """
    主函数
    """
    print("LLM客户端启动...")
    
    # 显示菜单
    while True:
        print("\n请选择模式:")
        print("  1. 交互式聊天")
        print("  2. 退出")
        
        choice = input("请输入选择 (1-2): ").strip()
        
        if choice == "1":
            chat_loop()
        elif choice == "2":
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main()