#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replace_in_file_tool.py
供LLM使用的文件内容替换工具
支持通过tool_call调用，在指定文件中搜索并替换文本内容
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

def replace_in_file(path: str, search_text: str, replace_text: str, replace_all: bool = False) -> str:
    """
    在指定文件中搜索并替换文本内容
    
    Args:
        path: 文件路径（相对路径，相对于根目录）
        search_text: 要搜索的文本内容（精确匹配，区分大小写）
        replace_text: 要替换成的文本内容
        replace_all: 是否替换所有匹配项，默认为False（只替换第一个）
    
    Returns:
        str: 成功时返回替换统计信息，失败时返回错误信息
    """
    try:
        # 验证路径安全性
        if not validate_path(path):
            return "错误：路径包含不安全元素（如..）或格式不正确"
        
        # 验证搜索文本
        if not search_text or not search_text.strip():
            return "错误：搜索文本不能为空"
        
        search_text = search_text.strip()
        
        # 构建基于根目录的绝对路径
        abs_path = os.path.join(BASE_PATH, path)
        
        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return f"错误：文件 '{path}' 不存在"
        
        # 检查是否为文件
        if not os.path.isfile(abs_path):
            return f"错误：'{path}' 不是文件"
        
        # 检查文件大小（10MB限制）
        file_size = os.path.getsize(abs_path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            return f"错误：文件 '{path}' 过大（{file_size}字节），超过10MB限制"
        
        # 读取文件内容
        content = None
        try:
            # 尝试UTF-8编码
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试GBK编码
            try:
                with open(abs_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except:
                return f"错误：无法解码文件 '{path}' 的内容（不支持的文件编码）"
        except Exception as e:
            return f"错误：读取文件 '{path}' 失败 - {str(e)}"
        
        # 统计原始匹配次数
        original_count = content.count(search_text)
        
        if original_count == 0:
            return f"信息：在文件 '{path}' 中未找到搜索文本 '{search_text}'"
        
        # 执行替换
        if replace_all:
            # 替换所有匹配项
            new_content = content.replace(search_text, replace_text)
            replaced_count = original_count
        else:
            # 只替换第一个匹配项
            new_content = content.replace(search_text, replace_text, 1)
            replaced_count = 1
        
        # 检查替换后内容是否有变化
        if content == new_content:
            return f"信息：文件 '{path}' 内容未发生变化（可能搜索文本与替换文本相同）"
        
        # 写入文件
        try:
            # 使用原始编码写入
            original_encoding = 'utf-8'
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    f.read()
            except UnicodeDecodeError:
                original_encoding = 'gbk'
            
            with open(abs_path, 'w', encoding=original_encoding) as f:
                f.write(new_content)
            
            # 验证写入
            if os.path.exists(abs_path):
                # 构建成功信息
                mode_desc = "全部替换" if replace_all else "替换第一个匹配项"
                result = [
                    f"成功：在文件 '{path}' 中替换了 {replaced_count} 处匹配",
                    f"搜索文本：'{search_text}'",
                    f"替换文本：'{replace_text}'",
                    f"替换模式：{mode_desc}",
                    f"文件大小：{file_size}字节"
                ]
                
                # 如果未替换所有匹配项，显示剩余匹配数
                if not replace_all and original_count > 1:
                    result.append(f"提示：文件中还有 {original_count - 1} 处匹配未替换")
                
                return "\n".join(result)
            else:
                return f"错误：文件 '{path}' 写入失败"
                
        except PermissionError:
            return f"错误：没有权限写入文件 '{path}'"
        except Exception as e:
            return f"错误：写入文件 '{path}' 时发生异常 - {str(e)}"
            
    except PermissionError:
        return f"错误：没有权限访问文件 '{path}'"
    except Exception as e:
        return f"错误：替换文件内容时发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "replace_in_file",
        "description": "在指定文件中搜索并替换文本内容。支持相对路径（相对于根目录，根目录由环境变量LLM_ROOT_DIRECTORY指定，默认为'brain'）。精确匹配，区分大小写。禁止使用父目录(..)。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要操作的文件路径（相对路径，相对于根目录）"
                },
                "search_text": {
                    "type": "string",
                    "description": "要搜索的文本内容（精确匹配，区分大小写）"
                },
                "replace_text": {
                    "type": "string",
                    "description": "要替换成的文本内容"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "是否替换所有匹配项。默认为false（只替换第一个匹配项）"
                }
            },
            "required": ["path", "search_text", "replace_text"]
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
                    "name": "replace_in_file",
                    "arguments": "{\"path\": \"test.txt\", \"search_text\": \"old\", \"replace_text\": \"new\"}"
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
        if function_name != "replace_in_file":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        path = arguments.get("path")
        search_text = arguments.get("search_text")
        replace_text = arguments.get("replace_text")
        replace_all = arguments.get("replace_all", False)
        
        # 验证必要参数
        if not path:
            return "错误：缺少必要参数 'path'"
        if not search_text:
            return "错误：缺少必要参数 'search_text'"
        if replace_text is None:
            return "错误：缺少必要参数 'replace_text'"
        
        # 验证replace_all参数类型
        if not isinstance(replace_all, bool):
            return f"错误：参数 'replace_all' 必须是布尔值，收到 '{type(replace_all).__name__}'"
        
        # 执行工具
        return replace_in_file(path, search_text, replace_text, replace_all)
        
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
    print("=== 文件内容替换工具基本演示 ===\n")
    
    # 创建测试文件
    test_content = """这是测试文件的第一行。
这是第二行，包含测试文本。
这是第三行，也包含测试文本。
这是第四行，没有匹配的文本。
这是第五行，包含Test文本（注意大小写）。"""
    
    test_file = "test_replace.txt"
    
    # 写入测试文件
    try:
        with open(os.path.join(BASE_PATH, test_file), 'w', encoding='utf-8') as f:
            f.write(test_content)
        print(f"1. 已创建测试文件: {test_file}")
    except Exception as e:
        print(f"1. 创建测试文件失败: {e}")
        return
    
    # 测试1：替换第一个匹配项
    print("\n2. 测试替换第一个匹配项:")
    result = replace_in_file(test_file, "测试文本", "替换后的文本", replace_all=False)
    print(f"   结果: {result}")
    
    # 测试2：替换所有匹配项
    print("\n3. 测试替换所有匹配项:")
    result = replace_in_file(test_file, "替换后的文本", "新的文本", replace_all=True)
    print(f"   结果: {result}")
    
    # 测试3：搜索不存在的文本
    print("\n4. 测试搜索不存在的文本:")
    result = replace_in_file(test_file, "不存在的文本", "新内容", replace_all=False)
    print(f"   结果: {result}")
    
    # 测试4：区分大小写测试
    print("\n5. 测试区分大小写（搜索'Test'而不是'test'）:")
    result = replace_in_file(test_file, "Test", "TEST", replace_all=False)
    print(f"   结果: {result}")
    
    # 测试5：工具调用
    print("\n6. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "arguments": json.dumps({
                "path": test_file,
                "search_text": "新的文本",
                "replace_text": "最终文本",
                "replace_all": True
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果: {result}")
    
    # 读取最终文件内容
    print("\n7. 最终文件内容:")
    try:
        with open(os.path.join(BASE_PATH, test_file), 'r', encoding='utf-8') as f:
            final_content = f.read()
        print("   " + final_content.replace("\n", "\n   "))
    except Exception as e:
        print(f"   读取最终文件失败: {e}")
    
    # 清理测试文件
    print("\n8. 清理测试文件:")
    try:
        os.remove(os.path.join(BASE_PATH, test_file))
        print(f"   已删除: {test_file}")
    except Exception as e:
        print(f"   删除测试文件失败: {e}")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()