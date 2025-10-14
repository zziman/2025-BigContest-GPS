# -*- coding: utf-8 -*-
"""
MCP 툴 직접 호출 (어댑터 우회)
"""
from typing import List
from mcp.tools import (
    search_merchant,
    load_store_data,
    resolve_region,
    load_area_data,
    load_region_data
)


def get_mcp_tools() -> List:
    """
    MCP 툴 리스트 반환 (어댑터 없이 직접 사용)
    """
    return []  # 빈 리스트 반환 (사용 안 함)


def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    """
    MCP 툴 직접 호출
    """
    tools_map = {
        "search_merchant": search_merchant,
        "load_store_data": load_store_data,
        "resolve_region": resolve_region,
        "load_area_data": load_area_data,
        "load_region_data": load_region_data,
    }
    
    tool_func = tools_map.get(tool_name)
    if not tool_func:
        raise ValueError(f"Tool {tool_name} not found")
    
    return tool_func(**kwargs)