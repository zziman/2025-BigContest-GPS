# -*- coding: utf-8 -*-
"""
MCP 툴 I/O 계약 정의 + 경량 검증
"""
from typing import TypedDict, Optional, List, Any


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


def validate_merchant_search_input(data: dict) -> tuple[bool, Optional[str]]:
    """search_merchant 입력 검증"""
    if not isinstance(data.get("merchant_name"), str):
        return False, "merchant_name must be string"
    if not data["merchant_name"].strip():
        return False, "merchant_name cannot be empty"
    return True, None


def validate_store_id_input(data: dict) -> tuple[bool, Optional[str]]:
    """store_id 입력 검증"""
    if not data.get("store_id"):
        return False, "store_id required"
    return True, None