# -*- coding: utf-8 -*-
"""
FastMCP 서버: 모든 툴 노출
"""
from fastmcp.server import FastMCP
from mcp.tools import (
    search_merchant,
    load_store_data,
    resolve_region,
    load_area_data,
    load_region_data
)

mcp = FastMCP(
    "BigContestMCPServer",
    instructions="""
    신한카드 빅콘테스트 2025 - 소상공인 마케팅 상담 MCP 서버
    제공 툴:
    - search_merchant: 가맹점명 검색
    - load_store_data: 가맹점 데이터 조회
    - resolve_region: 지역→행정동코드 변환
    - load_area_data: 상권 데이터 조회
    - load_region_data: 행정동 인구 데이터 조회
    """
)

# 툴 등록
mcp.tool()(search_merchant)
mcp.tool()(load_store_data)
mcp.tool()(resolve_region)
mcp.tool()(load_area_data)
mcp.tool()(load_region_data)

if __name__ == "__main__":
    mcp.run()