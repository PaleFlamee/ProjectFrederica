#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
read_file_tool.py
供LLM使用的文件读取工具
支持通过tool_call调用，读取指定文件的内容
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

def read_file(path: str) -> str:
    """
    读取指定文件的内容
    
    Args:
        path: 相对路径（相对于根目录）
    
    Returns:
        str: 成功时返回文件内容，失败时返回错误信息
    """
    try:
        # 验证路径安全性
        if not validate_path(path):
            return "错误：路径包含不安全元素（如..）或格式不正确"
        
        # 构建基于根目录的绝对路径
        abs_path = os.path.join(BASE_PATH, path)
        
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"错误：文件 '{path}' 不存在"
        
        # 检查是否为文件
        if not os.path.isfile(abs_path):
            return f"错误：'{path}' 不是文件"
        
        # 检查文件大小（防止读取过大文件）
        file_size = os.path.getsize(abs_path)
        if file_size > 10 * 1024 * 1024:  # 10MB限制
            return f"错误：文件 '{path}' 过大（{file_size}字节），超过10MB限制"
        
        # 读取文件内容
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 返回文件内容
        return content
        
    except PermissionError:
        return f"错误：没有权限读取文件 '{path}'"
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(abs_path, 'r', encoding='gbk') as f:
                content = f.read()
            return content
        except:
            return f"错误：无法解码文件 '{path}' 的内容（尝试了UTF-8和GBK编码）"
    except Exception as e:
        return f"错误：读取文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取指定文件的内容并返回全文。支持相对路径（相对于根目录，根目录由环境变量LLM_ROOT_DIRECTORY指定，默认为'brain'）。禁止使用父目录(..)。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径（相对路径，相对于根目录）"
                }
            },
            "required": ["path"]
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
                    "name": "read_file",
                    "arguments": "{\"path\": \"example.md\"}"
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
        if function_name != "read_file":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        
        # 执行工具
        return read_file(path)
        
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
    print("=== 文件读取工具基本演示 ===\n")
    
    # 测试读取现有文件
    print("1. 读取 example.md 文件:")
    result = read_file("example.md")
    print(f"   前200字符: {result[:200]}...")
    print(f"   文件大小: {len(result)} 字符\n")
    
    # 测试读取不存在的文件
    print("2. 读取不存在的文件:")
    result = read_file("不存在的文件.txt")
    print(f"   结果: {result}\n")
    
    # 测试工具调用
    print("3. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "read_file",
            "arguments": json.dumps({"path": "example.md"})
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果前200字符: {result[:200]}...")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()