#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_file_tool.py
供LLM使用的文件列表工具
支持通过tool_call调用，列出指定目录的文件
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

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

def list_files(path: str, recursive: bool = False) -> str:
    """
    列出指定目录的文件和文件夹
    
    Args:
        path: 相对路径（相对于根目录）
        recursive: 是否递归列出子目录内容，默认为False
    
    Returns:
        str: 成功时返回文件列表字符串，失败时返回错误信息
    """
    try:
        # 验证路径安全性
        if not validate_path(path):
            return "错误：路径包含不安全元素（如..）或格式不正确"
        
        # 构建基于根目录的绝对路径
        abs_path = os.path.join(BASE_PATH, path)
        
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"错误：路径 '{path}' 不存在"
        
        # 检查是否为目录
        if not os.path.isdir(abs_path):
            return f"错误：'{path}' 不是目录"
        
        # 列出文件
        if recursive:
            result_lines = []
            for root, dirs, files in os.walk(abs_path):
                # 计算相对于根目录的路径
                rel_root = os.path.relpath(root, BASE_PATH)
                
                # 添加目录信息
                if rel_root == '.':
                    result_lines.append(f"目录: .")
                else:
                    result_lines.append(f"目录: {rel_root}")
                
                # 添加子目录（如果有）
                if dirs:
                    dirs_sorted = sorted(dirs)
                    result_lines.append(f"  子目录: {', '.join(dirs_sorted)}")
                
                # 添加文件
                if files:
                    files_sorted = sorted(files)
                    result_lines.append(f"  文件: {', '.join(files_sorted)}")
                
                result_lines.append("")  # 空行分隔
            
            return "\n".join(result_lines).strip()
        else:
            # 非递归模式
            items = os.listdir(abs_path)
            
            # 分离目录和文件
            dirs = []
            files = []
            for item in items:
                item_path = os.path.join(abs_path, item)
                if os.path.isdir(item_path):
                    dirs.append(item + "/")
                else:
                    files.append(item)
            
            # 排序
            dirs_sorted = sorted(dirs)
            files_sorted = sorted(files)
            
            # 构建结果
            result_lines = [f"目录: {path}"]
            if dirs_sorted:
                result_lines.append(f"  子目录: {', '.join(dirs_sorted)}")
            if files_sorted:
                result_lines.append(f"  文件: {', '.join(files_sorted)}")
            
            return "\n".join(result_lines)
            
    except PermissionError:
        return f"错误：没有权限访问路径 '{path}'"
    except Exception as e:
        return f"错误：列出文件时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "列出指定目录中的文件和文件夹。支持相对路径（相对于根目录，根目录由环境变量LLM_ROOT_DIRECTORY指定，默认为'brain'）。禁止使用父目录(..)。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要列出文件的目录路径（相对路径，相对于根目录）"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出子目录内容。默认为false（仅列出当前目录）"
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
                    "name": "list_files",
                    "arguments": "{\"path\": \".\", \"recursive\": false}"
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
        if function_name != "list_files":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        recursive = arguments.get("recursive", False)
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        
        # 执行工具
        return list_files(path, recursive)
        
    except json.JSONDecodeError:
        return "错误：无法解析工具参数（无效的JSON格式）"
    except KeyError as e:
        return f"错误：工具调用格式不正确 - 缺少字段: {str(e)}"
    except Exception as e:
        return f"错误：执行工具时发生异常 - {str(e)}"

def demo_llm_interaction():
    """
    演示LLM如何调用此工具
    """
    print("=== LLM文件列表工具演示 ===\n")
    
    # 模拟LLM的工具调用请求
    tool_calls = [
        {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "list_files",
                "arguments": json.dumps({"path": "."})
            }
        },
        {
            "id": "call_002",
            "type": "function",
            "function": {
                "name": "list_files",
                "arguments": json.dumps({"path": ".", "recursive": True})
            }
        },
        {
            "id": "call_003",
            "type": "function",
            "function": {
                "name": "list_files",
                "arguments": json.dumps({"path": "不存在的路径"})
            }
        }
    ]
    
    # 执行每个工具调用
    for i, tool_call in enumerate(tool_calls, 1):
        print(f"演示 {i}:")
        print(f"  工具调用: {tool_call['function']['name']}({tool_call['function']['arguments']})")
        result = execute_tool_call(tool_call)
        print(f"  执行结果:\n{result}")
        print("-" * 50)
    
    print("\n=== 工具定义（供LLM使用）===")
    print(json.dumps(TOOL_DEFINITION, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # 运行演示
    demo_llm_interaction()