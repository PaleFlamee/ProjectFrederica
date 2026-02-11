#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_file_or_folder_tool.py
供LLM使用的文件/文件夹创建工具
支持通过tool_call调用，创建空文件或空文件夹
"""

import os
import json
import re
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

def validate_name(name: str) -> tuple[bool, str]:
    """
    验证文件/文件夹名称的合法性
    
    Args:
        name: 要验证的名称
    
    Returns:
        tuple[bool, str]: (是否有效, 错误信息)
    """
    # 检查是否为空
    if not name or not name.strip():
        return False, "名称不能为空"
    
    # 去除首尾空格
    name = name.strip()
    
    # 检查长度
    if len(name) > 255:
        return False, "名称长度不能超过255个字符"
    
    # 检查非法字符（Windows文件系统限制）
    illegal_chars = r'[<>:"/\\|?*]'
    if re.search(illegal_chars, name):
        return False, f"名称包含非法字符：<>:\"/\\|?*"
    
    # 检查保留名称（Windows）
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    if name.upper() in reserved_names:
        return False, f"'{name}' 是系统保留名称"
    
    # 检查以点开头或结尾
    if name.startswith('.') or name.endswith('.'):
        return False, "名称不能以点开头或结尾"
    
    # 检查连续空格
    if '  ' in name:
        return False, "名称不能包含连续空格"
    
    return True, name

def create_file_or_folder(name: str, type: str = "file", path: str = ".") -> str:
    """
    创建空文件或空文件夹
    
    Args:
        name: 文件或文件夹名称
        type: 创建类型，'file'（文件）或 'folder'（文件夹）
        path: 创建路径（相对路径，相对于根目录）
    
    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
    """
    try:
        # 验证名称
        is_valid, validation_result = validate_name(name)
        if not is_valid:
            return f"错误：{validation_result}"
        
        # 验证路径安全性
        if not validate_path(path):
            return "错误：路径包含不安全元素（如..）或格式不正确"
        
        # 构建基于根目录的目标路径
        if path == ".":
            target_dir = BASE_PATH
        else:
            target_dir = os.path.join(BASE_PATH, path)
        
        # 确保目标目录存在（递归创建）
        os.makedirs(target_dir, exist_ok=True)
        
        # 构建完整路径
        full_path = os.path.join(target_dir, name)
        
        # 检查是否已存在
        if os.path.exists(full_path):
            existing_type = "文件" if os.path.isfile(full_path) else "文件夹"
            return f"错误：'{name}' 已存在（{existing_type}）"
        
        # 根据类型创建
        if type == "file":
            # 创建空文件
            with open(full_path, 'w', encoding='utf-8') as f:
                pass  # 创建空文件
            
            # 验证文件是否创建成功
            if os.path.exists(full_path) and os.path.isfile(full_path):
                file_size = os.path.getsize(full_path)
                return f"成功：已创建空文件 '{name}'（大小：{file_size}字节）"
            else:
                return f"错误：文件创建失败"
                
        elif type == "folder":
            # 创建文件夹
            os.makedirs(full_path, exist_ok=True)
            
            # 验证文件夹是否创建成功
            if os.path.exists(full_path) and os.path.isdir(full_path):
                return f"成功：已创建空文件夹 '{name}'"
            else:
                return f"错误：文件夹创建失败"
        else:
            return f"错误：不支持的类型 '{type}'，请使用 'file' 或 'folder'"
            
    except PermissionError:
        return f"错误：没有权限在路径 '{path}' 创建{type}"
    except Exception as e:
        return f"错误：创建{type}时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "create_file_or_folder",
        "description": "创建空文件或空文件夹。支持相对路径（相对于根目录，根目录由环境变量LLM_ROOT_DIRECTORY指定，默认为'brain'），自动创建父目录。禁止使用父目录(..)。注意：名称应该是纯文件名（不含路径），路径通过 `path` 参数指定。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "要创建的文件或文件夹名称（纯名称，不含路径）"
                },
                "type": {
                    "type": "string",
                    "description": "创建类型：'file'（文件）或 'folder'（文件夹），默认为'file'",
                    "enum": ["file", "folder"]
                },
                "path": {
                    "type": "string",
                    "description": "可选，创建路径（相对路径，相对于根目录），默认为当前目录。例如：要在文件夹 'myfolder' 内创建文件，设置 path='myfolder'"
                }
            },
            "required": ["name"]
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
                    "name": "create_file_or_folder",
                    "arguments": "{\"name\": \"test.txt\", \"type\": \"file\"}"
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
        if function_name != "create_file_or_folder":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        name = arguments.get("name")
        type = arguments.get("type", "file")
        path = arguments.get("path", ".")
        
        # 验证必要参数
        if not name:
            return "错误：缺少必要参数 'name'"
        
        # 验证type参数
        if type not in ["file", "folder"]:
            return f"错误：参数 'type' 必须是 'file' 或 'folder'，收到 '{type}'"
        
        # 执行工具
        return create_file_or_folder(name, type, path)
        
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
    print("=== 文件/文件夹创建工具基本演示 ===\n")
    
    # 测试创建文件
    print("1. 创建空文件 'test_file.txt':")
    result = create_file_or_folder("test_file.txt", "file")
    print(f"   结果: {result}\n")
    
    # 测试创建文件夹
    print("2. 创建空文件夹 'test_folder':")
    result = create_file_or_folder("test_folder", "folder")
    print(f"   结果: {result}\n")
    
    # 测试名称验证
    print("3. 测试非法名称验证:")
    test_names = [
        ("", "空名称"),
        ("test<file>.txt", "包含非法字符"),
        ("CON", "系统保留名称"),
        ("  test  ", "前后空格"),
    ]
    
    for name, description in test_names:
        is_valid, msg = validate_name(name)
        print(f"   '{name}' ({description}): {'有效' if is_valid else '无效'} - {msg}")
    
    print()
    
    # 测试工具调用
    print("4. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "create_file_or_folder",
            "arguments": json.dumps({
                "name": "demo_file.txt",
                "type": "file",
                "path": "."
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果: {result}")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()