# mcp/contracts.py

# -*- coding: utf-8 -*-
"""
MCP 툴 I/O 계약 정의 + 경량 검증
"""
from typing import TypedDict, Optional, List, Literal, Tuple


class MerchantSearchInput(TypedDict):
    merchant_name: str


class MerchantSearchOutput(TypedDict):
    found: bool
    message: str
    count: int
    merchants: List[dict]


class LoadStoreDataInput(TypedDict):
    store_id: str


class LoadStoreDataOutput(TypedDict):
    success: bool
    data: Optional[dict]
    error: Optional[str]


class ResolveRegionInput(TypedDict):
    district: str


class ResolveRegionOutput(TypedDict):
    success: bool
    admin_dong_code: Optional[str]
    error: Optional[str]


class LoadAreaDataInput(TypedDict):
    admin_dong_code: str


class LoadAreaDataOutput(TypedDict):
    success: bool
    data: Optional[dict]
    error: Optional[str]


class LoadRegionDataInput(TypedDict):
    admin_dong_code: str


class LoadRegionDataOutput(TypedDict):
    success: bool
    data: Optional[dict]
    error: Optional[str]


class CooperationCandidatesInput(TypedDict):
    area_geo: str
    industry: str
    main_customers: List[str]
    limit: Optional[int]


class CooperationCandidatesOutput(TypedDict):
    success: bool
    count: int
    candidates: List[dict]
    error: Optional[str]


class WebSearchInput(TypedDict, total=False):
    query: str
    top_k: int
    rewrite_query: bool
    debug: bool
    
class WebDoc(TypedDict, total=False):
    title: str
    url: str
    snippet: str
    raw_content: str
    source: str
    published_at: str
    
class WebSearchOutput(TypedDict):
    success: bool
    provider_used: str
    count: int
    docs: List[WebDoc]
    query: str
    query_used: str
    meta: dict


class WeatherForecastInput(TypedDict):
    lat: float
    lon: float
    days: int

class WeatherForecastOutput(TypedDict):
    success: bool
    count: int
    data: list
    message: str


def validate_merchant_search_input(data: dict) -> Tuple[bool, Optional[str]]:
    if not isinstance(data.get("merchant_name"), str):
        return False, "merchant_name must be string"
    if not data["merchant_name"].strip():
        return False, "merchant_name cannot be empty"
    return True, None

def validate_store_id_input(data: dict) -> Tuple[bool, Optional[str]]:
    if not data.get("store_id"):
        return False, "store_id required"
    return True, None

def validate_web_search_input(data: dict) -> Tuple[bool, Optional[str]]:
    q = data.get("query")
    if not isinstance(q, str) or not q.strip():
        return False, "query must be non-empty string"

    top_k = int(data.get("top_k", 5))
    if not (1 <= top_k <= 20):
        return False, "top_k must be between 1 and 20"

    if "rewrite_query" in data and not isinstance(data["rewrite_query"], bool):
        return False, "rewrite_query must be boolean"

    if "debug" in data and not isinstance(data["debug"], bool):
        return False, "debug must be boolean"

    return True, None

