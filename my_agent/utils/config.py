# -*- coding: utf-8 -*-
"""
중앙 설정 관리: Streamlit secrets.toml + .env 지원
"""
import os
from pathlib import Path
from typing import Literal

# ═══════════════════════════════════════════════════════════
# 프로젝트 경로
# ═══════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MCP_DIR = PROJECT_ROOT / "mcp"

# ═══════════════════════════════════════════════════════════
# 설정 소스 우선순위: Streamlit secrets > .env > 기본값
# ═══════════════════════════════════════════════════════════
def _get_config(key: str, default=None):
    """
    설정 값 가져오기 (우선순위: Streamlit > .env)
    """
    # 1. Streamlit secrets (Streamlit 실행 시)
    try:
        import streamlit as st
        value = st.secrets.get(key)
        if value is not None:
            return value
    except (ImportError, FileNotFoundError, KeyError):
        pass
    
    # 2. 환경변수 (.env 또는 시스템)
    value = os.environ.get(key)
    if value is not None:
        return value
    
    # 3. 기본값
    return default


# ═══════════════════════════════════════════════════════════
# API Keys
# ═══════════════════════════════════════════════════════════
GOOGLE_API_KEY = _get_config("GOOGLE_API_KEY")

# ═══════════════════════════════════════════════════════════
# 데이터 경로
# ═══════════════════════════════════════════════════════════
FRANCHISE_CSV = _get_config(
    "FRANCHISE_CSV",
    (DATA_DIR / "franchise_data.csv").as_posix()
)
BIZ_AREA_CSV = _get_config(
    "BIZ_AREA_CSV",
    (DATA_DIR / "biz_area.csv").as_posix()
)
ADMIN_DONG_CSV = _get_config(
    "ADMIN_DONG_CSV",
    (DATA_DIR / "admin_dong.csv").as_posix()
)

# ═══════════════════════════════════════════════════════════
# MCP 설정
# ═══════════════════════════════════════════════════════════
MCP_ENABLED = str(_get_config("MCP_ENABLED", "1")) == "1"
MCP_SERVER_PATH = (MCP_DIR / "server.py").as_posix()

# ═══════════════════════════════════════════════════════════
# LLM 설정
# ═══════════════════════════════════════════════════════════
LLM_MODEL = _get_config("LLM_MODEL", "gemini-2.5-flash")
LLM_TEMPERATURE = float(_get_config("LLM_TEMPERATURE", "0.2"))
LLM_MAX_RETRIES = int(_get_config("LLM_MAX_RETRIES", "2"))

# ═══════════════════════════════════════════════════════════
# 정책 토글
# ═══════════════════════════════════════════════════════════
CONFIRM_ON_MULTI = str(_get_config("CONFIRM_ON_MULTI", "0")) == "1"
ENABLE_RELEVANCE_CHECK = str(_get_config("ENABLE_RELEVANCE_CHECK", "1")) == "1"
ENABLE_MEMORY = str(_get_config("ENABLE_MEMORY", "1")) == "1"

# ═══════════════════════════════════════════════════════════
# 체크포인트 설정
# ═══════════════════════════════════════════════════════════
CHECKPOINT_DIR = PROJECT_ROOT / ".checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

IntentType = Literal["SNS", "REVISIT", "ISSUE", "GENERAL"]