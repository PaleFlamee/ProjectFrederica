#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
duckduckgo_search_tool.py
供LLM使用的DuckDuckGo网络搜索工具
支持通过tool_call调用，进行网络搜索并返回格式化的搜索结果
"""

import json
import time
from typing import Dict, Any, List
from ddgs import DDGS

def duckduckgo_search(query: str, max_results: int = 5) -> str:
    """
    使用DuckDuckGo进行网络搜索
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认为5，范围1-10
    
    Returns:
        str: 格式化的搜索结果或错误信息
    """
    try:
        # 验证参数
        if not query or not query.strip():
            return "错误：搜索关键词不能为空"
        
        query = query.strip()
        
        # 验证max_results范围
        if not isinstance(max_results, int):
            return f"错误：max_results必须是整数，收到 '{type(max_results).__name__}'"
        
        if max_results < 1:
            return f"错误：max_results必须大于0，收到 {max_results}"
        
        if max_results > 10:
            return f"错误：max_results不能超过10，收到 {max_results}"
        
        # 执行搜索（带重试机制）
        max_retries = 2
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                with DDGS() as ddgs:
                    # 使用text方法进行搜索
                    results = list(ddgs.text(query, max_results=max_results))
                break  # 成功则跳出循环
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return f"错误：搜索执行失败（尝试{max_retries}次） - {str(e)}"
        
        # 检查是否有结果
        if not results:
            return f"信息：未找到关于 '{query}' 的搜索结果"
        
        # 格式化结果
        formatted_results = []
        formatted_results.append(f"搜索结果（共找到 {len(results)} 条）：")
        
        for i, result in enumerate(results, 1):
            title = result.get('title', '无标题')
            url = result.get('href', '无链接')
            body = result.get('body', '无摘要')
            
            # 限制摘要长度
            if body and len(body) > 200:
                body = body[:200] + "..."
            
            formatted_results.append(f"{i}. 标题：{title}")
            formatted_results.append(f"   URL：{url}")
            formatted_results.append(f"   摘要：{body}")
            
            # 如果不是最后一条结果，添加空行分隔
            if i < len(results):
                formatted_results.append("")
        
        return "\n".join(formatted_results)
        
    except ImportError:
        return "错误：未安装duckduckgo-search库，请运行 'pip install duckduckgo-search>=3.9.0'"
    except Exception as e:
        return f"错误：搜索过程中发生异常 - {str(e)}"

# 工具定义（符合OpenAI工具调用规范）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "duckduckgo_search",
        "description": "使用DuckDuckGo进行网络搜索。返回包含标题、URL和摘要的格式化搜索结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数。默认为5，最小为1，最大为10",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
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
                    "name": "duckduckgo_search",
                    "arguments": "{\"query\": \"Python编程\", \"max_results\": 5}"
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
        if function_name != "duckduckgo_search":
            return f"错误：未知的工具 '{function_name}'"
        
        # 提取参数
        query = arguments.get("query")
        max_results = arguments.get("max_results", 5)
        
        # 验证必要参数
        if not query:
            return "错误：缺少必要参数 'query'"
        
        # 验证max_results参数类型
        if not isinstance(max_results, int):
            return f"错误：参数 'max_results' 必须是整数，收到 '{type(max_results).__name__}'"
        
        # 执行工具
        return duckduckgo_search(query, max_results)
        
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
    print("=== DuckDuckGo搜索工具基本演示 ===\n")
    
    # 测试1：基本搜索
    print("1. 基本搜索（查询'Python编程'，默认5条结果）:")
    result = duckduckgo_search("Python编程")
    print(f"   结果前300字符:\n{result[:300]}...\n")
    
    # 测试2：限制结果数量
    print("2. 限制结果数量（查询'人工智能'，3条结果）:")
    result = duckduckgo_search("人工智能", max_results=3)
    print(f"   结果前300字符:\n{result[:300]}...\n")
    
    # 测试3：空查询
    print("3. 测试空查询:")
    result = duckduckgo_search("")
    print(f"   结果: {result}\n")
    
    # 测试4：无效的max_results
    print("4. 测试无效的max_results（查询'test'，max_results=0）:")
    result = duckduckgo_search("test", max_results=0)
    print(f"   结果: {result}\n")
    
    # 测试5：工具调用
    print("5. 模拟工具调用:")
    tool_call = {
        "id": "call_demo_001",
        "type": "function",
        "function": {
            "name": "duckduckgo_search",
            "arguments": json.dumps({
                "query": "机器学习",
                "max_results": 2
            })
        }
    }
    result = execute_tool_call(tool_call)
    print(f"   工具调用结果前400字符:\n{result[:400]}...\n")
    
    print("=== 演示完成 ===")

if __name__ == "__main__":
    # 运行基本演示
    demo_basic_usage()