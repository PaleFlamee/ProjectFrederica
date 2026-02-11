#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
write_to_file_tool.py
供LLM使用的文件写入工具
支持通过tool_call调用，向指定文件写入内容
"""

import os
import json
from typing import Dict, Any

# 从环境变量获取根目录，默认为"brain"
ROOT_DIR = os.getenv("LLM_ROOT_DIRECTORY", "brain")
BASE_PATH = os.path.join(os.getcwd(), ROOT_DIR)

def validate_path(path: str) -> bool:
    """
    验证路径是否安全
    
    Args:
        path: 要验证的路径
        
    Returns:
        bool: 如果路径安全返回True，否则返回False
    """
    # 检查是否包含父目录引用
    if ".." in path:
        return False
    
    # 检查是否为绝对路径（Windows和Unix风格）
    if os.path.isabs(path):
        return False
    
    # 检查Unix风格的绝对路径（以/开头）
    if path.startswith('/'):
        return False
    
    # 检查Windows风格的绝对路径（包含盘符）
    if len(path) > 1 and path[1] == ':':
        return False
    
    # 检查其他不安全字符
    unsafe_chars = ["~", ":", "*", "?", "\"", "<", ">", "|"]
    for char in unsafe_chars:
        if char in path:
            return False
    
    return True

def write_file(path: str, content: str, mode: str = "write") -> str:
    """
    向指定文件写入内容
    
    Args:
        path: 文件路径（相对路径，相对于根目录）
        content: 要写入的内容
        mode: 写入模式，'write'（覆盖）或 'append'（追加），默认为'write'
    
    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
    """
    try:
        # 验证路径安全性
        if not validate_path(path):
            return "错误：路径包含不安全元素（如..）或格式不正确"
        
        # 构建基于根目录的绝对路径
        abs_path = os.path.join(BASE_PATH, path)
        
        # 检查内容大小（防止写入过大内容）
        content_size = len(content.encode('utf-8'))
        if content_size > 10 * 1024 * 1024:  # 10MB限制
            return f"错误：要写入的内容过大（{content_size}字节），超过10MB限制"
        
        # 确保父目录存在
        parent_dir = os.path.dirname(abs_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # 根据模式写入文件
        if mode == "write":
            # 覆盖模式
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 验证写入
            if os.path.exists(abs_path):
                file_size = os.path.getsize(abs_path)
                return f"成功：已写入文件 '{path}'（模式：覆盖，大小：{file_size}字节）"
            else:
                return f"错误：文件写入失败"
                
        elif mode == "append":
            # 追加模式
            file_exists = os.path.exists(abs_path)
            
            with open(abs_path, 'a', encoding='utf-8') as f:
                f.write(content)
            
            # 验证写入
            if os.path.exists(abs_path):
                file_size = os.path.getsize(abs_path)
                action = "追加到" if file_exists else "创建并写入"
                return f"成功：已{action}文件 '{path}'（模式：追加，大小：{file_size}字节）"
            else:
                return f"错误：文件追加失败"
        else:
            return f"错误：不支持的模式 '{mode}'，请使用 'write' 或 'append'"
            
    except PermissionError:
        return f"错误：没有权限写入文件 '{path}'"
    except Exception as e:
        return f"错误：写入文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "向指定文件写入内容。支持相对路径（相对于根目录，根目录由环境变量LLM_ROOT_DIRECTORY指定，默认为'brain'），自动创建父目录。禁止使用父目录(..)。支持覆盖和追加两种模式。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要写入的文件路径（相对路径，相对于根目录）"
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容"
                },
                "mode": {
                    "type": "string",
                    "description": "写入模式：'write'（覆盖）或 'append'（追加），默认为'write'",
                    "enum": ["write", "append"]
                }
            },
            "required": ["path", "content"]
        }
    }
}

def execute_tool_call(tool_call: Dict[str, Any]) -> str:
    """
    执行工具调用
    
    Args:
        tool_call: 包含工具调用信息的字典，格式为：
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": "{\"path\": \"test.txt\", \"content\": \"Hello World\"}"
                }
            }
    
    Returns:
        str: 工具执行结果
    """
    try:
        # 解析参数
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]
        arguments = json.loads(arguments_str)
        
        # 验证工具名称
        if function_name != "write_file":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        content = arguments.get("content")
        mode = arguments.get("mode", "write")
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        if content is None:
            return "错误：缺少必要参数 'content'"
        
        # 验证mode参数
        if mode not in ["write", "append"]:
            return f"错误：参数 'mode' 必须是 'write' 或 'append'，收到 '{mode}'"
        
        # 执行工具
        return write_file(path, content, mode)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"

def demo_basic_usage():
    """
    演示基本用法
    """
    print("=== 文件写入工具基本演示 ===\n")
    
    # 测试写入新文件
    print("1. 写入新文件 'test_write.txt':")
    result = write_file("test_write.txt", "这是写入的新内容\n第二行内容")
    print(f"   结果: {result}\n")
    
    # 测试追加模式
    print("2. 追加内容到文件:")
    result = write_file("test_write.txt", "\n这是追加的内容", mode="append")
    print(f"   结果: {result}\n")
    
    # 测试覆盖模式
    print("3. 覆盖文件内容:")
    result = write_file("test_write.txt", "这是覆盖后的新内容", mode="write")
    print(f"   结果: {result}\n")
    
    # 测试写入到子目录
    print("4. 写入到子目录文件:")
    result = write_file("subdir/test_subdir.txt", "子目录文件内容")
    print(f"   结果: {result}\n")
    
    # 测试工具调用
    print("5. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "write_file",
            "arguments": json.dumps({
                "path": "demo_tool.txt",
                "content": "通过工具调用写入的内容",
                "mode": "write"
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果: {result}")
    
    # 清理测试文件
    print("\n6. 清理测试文件:")
    test_files = ["test_write.txt", "demo_tool.txt", "subdir/test_subdir.txt"]
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"   已删除: {file}")
    
    # 清理测试目录
    if os.path.exists("subdir") and os.path.isdir("subdir"):
        os.rmdir("subdir")
        print(f"   已删除: subdir/")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()