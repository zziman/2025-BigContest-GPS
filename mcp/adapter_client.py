# mcp/adapter_client.py

# -*- coding: utf-8 -*-
"""
MCP 툴 직접 호출 (Python 내부에서 바로 사용 가능)
"""
from typing import List
from mcp.tools import (
    search_merchant,
    load_store_data,
    load_bizarea_data,
    load_region_data
)
from mcp.tools_web import web_search


def get_mcp_tools() -> List:
    """
    MCP 툴 리스트 반환 (현재 미사용)
    """
    return [] # 빈 리스트 반환


def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    """
    MCP 툴 직접 호출 (adapter 없이 Python에서 직접 호출할 경우)
    """
    tools_map = {
        "search_merchant": search_merchant,
        "load_store_data": load_store_data,
        "load_bizarea_data": load_bizarea_data,
        "load_region_data": load_region_data,
        "web_search": web_search
    }
    tool_func = tools_map.get(tool_name)
    if not tool_func:
        raise ValueError(f"Tool '{tool_name}' not found. Available: {list(tools_map.keys())}")

    return tool_func(**kwargs)