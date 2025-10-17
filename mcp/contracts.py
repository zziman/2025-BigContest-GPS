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

class WebSearchInput(TypedDict, total=False):
    query: str
    top_k: int
    recency_days: int
    deep_search: bool
    rewrite_query: bool
    rerank: Literal["cosine", "sbert", "cross"]
    debug: bool

class WebDoc(TypedDict, total=False):
    title: str
    url: str
    snippet: str
    source: str          # domain
    published_at: str    # ISO8601 or ""
    score: float         # 정규화 가중치

class WebSearchOutput(TypedDict):
    success: bool
    provider_used: str
    count: int
    docs: List[WebDoc]
    error: Optional[str]


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
    if not (1 <= top_k <= 25):
        return False, "top_k must be 1~25"
    recency_days = int(data.get("recency_days", 60))
    if recency_days < 0:
        return False, "recency_days must be >= 0"
    rerank = data.get("rerank", "cosine")
    if rerank not in {"cosine", "sbert", "cross"}:
        return False, "rerank must be one of: cosine/sbert/cross"
    return True, None

