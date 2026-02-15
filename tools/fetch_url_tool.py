#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_url_tool.py
供LLM使用的网页内容获取工具
使用Jina Reader API获取网页内容并转换为Markdown格式
"""

import json
import time
import re
from typing import Dict, Any
from urllib.parse import urlparse
import requests

# Jina Reader API配置 - 从环境变量读取
# 环境变量名: JINA_API_BASE, JINA_API_KEY

def fetch_url(url: str, output_format: str = "markdown", max_length: int = 1000) -> str:
    """
    使用Jina Reader API获取网页内容
    
    Args:
        url: 要获取的网页URL
        output_format: 输出格式，默认为"markdown"，可选"text"或"html"
        max_length: 最大返回长度，默认为1000字符
    
    Returns:
        str: 提取的网页内容或错误信息
    """
    try:
        # 验证参数
        if not url or not url.strip():
            return "错误：URL不能为空"
        
        url = url.strip()
        
        # 验证URL格式
        if not _is_valid_url(url):
            return f"错误：无效的URL格式 '{url}'，仅支持http/https协议"
        
        # 验证output_format参数
        valid_formats = ["markdown", "text", "html"]
        if output_format not in valid_formats:
            return f"错误：无效的输出格式 '{output_format}'，可选值: {', '.join(valid_formats)}"
        
        # 验证max_length参数
        if not isinstance(max_length, int):
            return f"错误：max_length必须是整数，收到 '{type(max_length).__name__}'"
        
        if max_length < 1:
            return f"错误：max_length必须大于0，收到 {max_length}"
        
        if max_length > 10000:
            return f"错误：max_length不能超过10000，收到 {max_length}"
        
        # 获取API配置
        import os
        api_base = os.getenv("JINA_API_BASE", "https://r.jina.ai")
        api_key = os.getenv("JINA_API_KEY")
        
        if not api_key:
            return "错误：未设置Jina API密钥，请设置JINA_API_KEY环境变量"
        
        # 构建Jina Reader API URL
        # Jina Reader API格式: {api_base}/{url}?format={format}&max-length={max_length}
        encoded_url = requests.utils.quote(url, safe='')
        api_url = f"{api_base}/{encoded_url}"
        
        # 构建查询参数
        params = {
            "format": output_format,
            "max-length": max_length
        }
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # 执行API调用（带重试机制）
        max_retries = 2
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    api_url,
                    params=params,
                    headers=headers,
                    timeout=30,  # 30秒超时
                    allow_redirects=True
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    content = response.text
                    
                    # 检查内容是否为空
                    if not content or not content.strip():
                        return f"信息：获取到的网页内容为空，URL: {url}"
                    
                    # 限制内容长度
                    if len(content) > max_length:
                        content = content[:max_length] + "..."
                    
                    # 添加来源信息
                    result = f"{content}\n\n[来源: {url}]"
                    return result
                    
                elif response.status_code == 401:
                    return "错误：Jina API密钥无效或已过期"
                elif response.status_code == 403:
                    return "错误：访问被拒绝，请检查API密钥权限"
                elif response.status_code == 404:
                    return f"错误：网页不存在或无法访问，URL: {url}"
                elif response.status_code == 429:
                    return "错误：API请求过于频繁，请稍后重试"
                elif 500 <= response.status_code < 600:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return f"错误：Jina API服务器错误 (HTTP {response.status_code})"
                else:
                    return f"错误：获取网页内容失败 (HTTP {response.status_code})"
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return "错误：请求超时，请检查网络连接或稍后重试"
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return "错误：网络连接失败，请检查网络连接"
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return f"错误：请求异常 - {str(e)}"
        
        return "错误：获取网页内容失败，请稍后重试"
        
    except Exception as e:
        return f"错误：获取网页内容过程中发生异常 - {str(e)}"

def _is_valid_url(url: str) -> bool:
    """
    验证URL格式
    
    Args:
        url: 要验证的URL
    
    Returns:
        bool: 是否有效的URL
    """
    try:
        result = urlparse(url)
        
        # 检查协议
        if result.scheme not in ['http', 'https']:
            return False
        
        # 检查网络位置
        if not result.netloc:
            return False
        
        # 基本格式检查
        if not re.match(r'^https?://', url):
            return False
        
        return True
    except:
        return False

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "使用Jina Reader API获取网页内容并转换为Markdown格式。返回提取的网页内容，包含标题和主要内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要获取的网页URL（必须包含http://或https://）"
                },
                "output_format": {
                    "type": "string",
                    "description": "输出格式。默认为'markdown'，可选'text'（纯文本）或'html'（原始HTML）",
                    "enum": ["markdown", "text", "html"],
                    "default": "markdown"
                },
                "max_length": {
                    "type": "integer",
                    "description": "最大返回长度（字符数）。默认为1000，最小为1，最大为10000",
                    "minimum": 1,
                    "maximum": 10000,
                    "default": 1000
                }
            },
            "required": ["url"]
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
                    "name": "fetch_url",
                    "arguments": "{\"url\": \"https://example.com\", \"max_length\": 1000}"
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
        if function_name != "fetch_url":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        url = arguments.get("url")
        output_format = arguments.get("output_format", "markdown")
        max_length = arguments.get("max_length", 1000)
        
        # 验证必要参数
        if not url:
            return "错误：缺少必要参数 'url'"
        
        # 验证max_length参数类型
        if not isinstance(max_length, int):
            return f"错误：参数 'max_length' 必须是整数，收到 '{type(max_length).__name__}'"
        
        # 验证output_format参数
        valid_formats = ["markdown", "text", "html"]
        if output_format not in valid_formats:
            return f"错误：参数 'output_format' 必须是 {valid_formats} 之一，收到 '{output_format}'"
        
        # 执行工具
        return fetch_url(url, output_format, max_length)
        
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
    print("=== 网页内容获取工具基本演示 ===\n")
    
    # 测试1：基本获取
    print("1. 基本获取（获取Python官网，默认Markdown格式，1000字符）:")
    result = fetch_url("https://www.python.org")
    if result.startswith("#") or result.startswith("错误"):
        print(f"   结果前200字符:\n{result[:200]}...\n")
    else:
        print(f"   结果: {result}\n")
    
    # 测试2：纯文本格式
    print("2. 纯文本格式（获取示例网站，text格式，500字符）:")
    result = fetch_url("https://example.com", output_format="text", max_length=500)
    if result.startswith("Example Domain") or result.startswith("错误"):
        print(f"   结果前200字符:\n{result[:200]}...\n")
    else:
        print(f"   结果: {result}\n")
    
    # 测试3：无效URL
    print("3. 测试无效URL:")
    result = fetch_url("invalid-url")
    print(f"   结果: {result}\n")
    
    # 测试4：无效的max_length
    print("4. 测试无效的max_length（URL: test.com, max_length=0）:")
    result = fetch_url("https://test.com", max_length=0)
    print(f"   结果: {result}\n")
    
    # 测试5：工具调用
    print("5. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "fetch_url",
            "arguments": json.dumps({
                "url": "https://news.ycombinator.com",
                "output_format": "markdown",
                "max_length": 800
            })
        }
    }
    result = execute_tool_call(tool_call)
    if result.startswith("#") or result.startswith("错误"):
        print(f"   工具调用结果前300字符:\n{result[:300]}...\n")
    else:
        print(f"   结果: {result}\n")
    
    print("=== 演示完成 ===")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()