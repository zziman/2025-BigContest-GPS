# mcp/server.py

# -*- coding: utf-8 -*-
"""
FastMCP 서버: 데이터 조회 툴 제공
"""

from fastmcp.server import FastMCP
from mcp.tools import (
    search_merchant,
    load_store_data,
    load_bizarea_data, 
    find_cooperation_candidates
)
from mcp.tools_web import web_search 
from mcp.tools_weather import get_weather_forecast 

mcp = FastMCP(
    "BigContestMCPServer",
    instructions="""
    신한카드 빅콘테스트 2025 - 소상공인 마케팅 상담 MCP 서버
    제공 툴:
    - search_merchant: 가맹점명 검색
    - load_store_data: 가맹점 데이터 조회
    - load_bizarea_data: 상권 데이터 조회
    - find_cooperation_candidates: 협업 후보 조회
    - web_search: 외부 검색 웹 정보 수집
    """
)

# 툴 등록
mcp.tool()(search_merchant)
mcp.tool()(load_store_data)
mcp.tool()(load_bizarea_data)
mcp.tool()(find_cooperation_candidates)
mcp.tool()(web_search)
mcp.tool()(get_weather_forecast)

if __name__ == "__main__":
    mcp.run()
