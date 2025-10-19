# [1019] 2025 BigContest – AI 비밀상담소 (PoC)

소상공인 가맹점 데이터를 기반으로 전략 초안을 자동 생성하는 에이전트.
LangGraph로 멀티턴·분기·재시도를 제어하고, MCP 툴로 CSV 데이터를 조회한다.

<br>

## 폴더 구조

```
2025-BigContest/
├─ my_agent/
│  ├─ __init__.py
│  ├─ agent.py                         
│  └─ utils/
│     ├─ __init__.py
│     ├─ config.py                     
│     ├─ state.py
│     ├─ prompt_builder.py
│     ├─ postprocess.py
│     ├─ chat_history.py                      
│     ├─ tools.py                      
│     └─ nodes/
│        ├─ router.py                  
│        ├─ sns.py                     
│        ├─ revisit.py                 
│        ├─ issue.py                  
│        ├─ general.py                 
│        └─ web_augment.py             
│
├─ mcp/
│  ├─ server.py
│  ├─ tools.py
│  ├─ tools_web.py                     
│  ├─ contracts.py                     
│  └─ adapter_client.py
│
├─ data/
│  ├─ franchise_data.csv
│  ├─ biz_area.csv
│  └─ admin_dong.csv
│
├─ assets/
│
├─ dashboard.py           
├─ streamlit_app.py                    
├─ local_test.py
├─ .streamlit/
│  └─ secrets.toml                     
├─ .env                                
└─ requirements.txt                  
```

<br>

## 설치 및 실행(uv)
```bash
# 1) 저장소 클론
git clone https://github.com/zziman/2025-BigContest.git
cd 2025-BigContest

# 2) 가상환경 + 의존성 설치
uv venv
source .venv/bin/activate    # Windows: .\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt

# 3) 시크릿(secrets.toml) 생성 — 권장 방식
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'TOML'
# --- API Keys ---
GOOGLE_API_KEY = "your_key"                 
NAVER_CLIENT_ID = "your_naver_client_id"
NAVER_CLIENT_SECRET = "your_naver_secret"
TAVILY_API_KEY = "your_key"                         

# --- 검색 파라미터 ---
SEARCH_TIMEOUT = 12
SEARCH_TOPK = 5
SEARCH_RECENCY_DAYS = 60

# --- 정책/토글 ---
MCP_ENABLED = 1
CONFIRM_ON_MULTI = 0
LLM_MODEL = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.2
ENABLE_RELEVANCE_CHECK = true
ENABLE_MEMORY = true

# 4) 앱 실행 (Streamlit)
uv run streamlit run streamlit_app.py

```



