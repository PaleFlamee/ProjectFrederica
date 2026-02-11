#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
delete_file_or_folder_tool.py
供LLM使用的文件/文件夹删除工具
支持通过tool_call调用，删除指定的文件或文件夹
"""

import os
import json
import shutil
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

def delete_file_or_folder(path: str, force: bool = False) -> str:
    """
    删除指定的文件或文件夹
    
    Args:
        path: 要删除的文件或文件夹路径（相对路径，相对于根目录）
        force: 是否强制删除非空文件夹，默认为False
        
    Returns:
        str: 成功时返回成功信息，失败时返回错误信息
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
        
        # 检查是否为根目录（防止误删整个根目录）
        if os.path.normpath(abs_path) == os.path.normpath(BASE_PATH):
            return "错误：不能删除根目录"
        
        # 判断是文件还是文件夹
        is_file = os.path.isfile(abs_path)
        is_dir = os.path.isdir(abs_path)
        
        if is_file:
            # 删除文件
            file_size = os.path.getsize(abs_path)
            os.remove(abs_path)
            
            # 验证文件是否删除成功
            if not os.path.exists(abs_path):
                return f"成功：已删除文件 '{path}'（原大小：{file_size}字节）"
            else:
                return f"错误：文件删除失败"
                
        elif is_dir:
            # 检查文件夹是否为空
            is_empty = len(os.listdir(abs_path)) == 0
            
            if is_empty:
                # 删除空文件夹
                os.rmdir(abs_path)
                
                # 验证文件夹是否删除成功
                if not os.path.exists(abs_path):
                    return f"成功：已删除空文件夹 '{path}'"
                else:
                    return f"错误：空文件夹删除失败"
            else:
                # 非空文件夹，需要force参数
                if not force:
                    item_count = len(os.listdir(abs_path))
                    return f"错误：文件夹 '{path}' 非空（包含 {item_count} 个项目），如需删除请设置 force=true"
                
                # 使用shutil.rmtree递归删除非空文件夹
                shutil.rmtree(abs_path)
                
                # 验证文件夹是否删除成功
                if not os.path.exists(abs_path):
                    return f"成功：已强制删除非空文件夹 '{path}'"
                else:
                    return f"错误：非空文件夹删除失败"
        else:
            # 既不是文件也不是文件夹（可能是符号链接等）
            return f"错误：'{path}' 不是常规文件或文件夹"
            
    except PermissionError:
        return f"错误：没有权限删除路径 '{path}'"
    except shutil.Error as e:
        return f"错误：删除文件夹时发生异常 - {str(e)}"
    except Exception as e:
        return f"错误：删除操作时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "delete_file_or_folder",
        "description": "删除指定的文件或文件夹。支持相对路径（相对于根目录，根目录由环境变量LLM_ROOT_DIRECTORY指定，默认为'brain'）。禁止使用父目录(..)。注意：删除非空文件夹需要设置force=true参数。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要删除的文件或文件夹路径（相对路径，相对于根目录）"
                },
                "force": {
                    "type": "boolean",
                    "description": "是否强制删除非空文件夹。默认为false（仅删除空文件夹或文件）"
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
                    "name": "delete_file_or_folder",
                    "arguments": "{\"path\": \"test.txt\", \"force\": false}"
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
        if function_name != "delete_file_or_folder":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        force = arguments.get("force", False)
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        
        # 验证force参数类型
        if not isinstance(force, bool):
            return f"错误：参数 'force' 必须是布尔值，收到 '{force}'"
        
        # 执行工具
        return delete_file_or_folder(path, force)
        
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
    print("=== 文件/文件夹删除工具基本演示 ===\n")
    
    # 首先创建一些测试文件
    test_dir = os.path.join(BASE_PATH, "test_delete_demo")
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "test_file.txt")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("这是一个测试文件")
    
    test_subdir = os.path.join(test_dir, "subfolder")
    os.makedirs(test_subdir, exist_ok=True)
    
    test_subfile = os.path.join(test_subdir, "nested_file.txt")
    with open(test_subfile, 'w', encoding='utf-8') as f:
        f.write("嵌套文件")
    
    print("1. 测试删除文件:")
    rel_path = os.path.relpath(test_file, BASE_PATH)
    result = delete_file_or_folder(rel_path)
    print(f"   删除文件 '{rel_path}': {result}\n")
    
    print("2. 测试删除空文件夹（不带force参数）:")
    empty_dir = os.path.join(test_dir, "empty_folder")
    os.makedirs(empty_dir, exist_ok=True)
    rel_empty_dir = os.path.relpath(empty_dir, BASE_PATH)
    result = delete_file_or_folder(rel_empty_dir)
    print(f"   删除空文件夹 '{rel_empty_dir}': {result}\n")
    
    print("3. 测试删除非空文件夹（不带force参数）:")
    rel_subdir = os.path.relpath(test_subdir, BASE_PATH)
    result = delete_file_or_folder(rel_subdir)
    print(f"   删除非空文件夹 '{rel_subdir}': {result}\n")
    
    print("4. 测试删除非空文件夹（带force=true参数）:")
    result = delete_file_or_folder(rel_subdir, force=True)
    print(f"   强制删除非空文件夹 '{rel_subdir}': {result}\n")
    
    print("5. 测试删除不存在的路径:")
    result = delete_file_or_folder("non_existent_path.txt")
    print(f"   删除不存在的路径: {result}\n")
    
    print("6. 测试删除根目录（应该失败）:")
    result = delete_file_or_folder(".")
    print(f"   尝试删除根目录: {result}\n")
    
    # 清理剩余的测试目录
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    print("7. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "delete_file_or_folder",
            "arguments": json.dumps({
                "path": "test_delete_demo/test_file.txt",
                "force": False
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果: {result}")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()