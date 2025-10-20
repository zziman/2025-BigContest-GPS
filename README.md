# [1020] 2025 BigContest – AI 비밀상담소 (PoC)

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
<<<<<<< Updated upstream
│     ├─ metrics/         
│     │  ├─ general_metrics.py  # 폭넓게 사용할 수 있는 지표나 데이터 불러오는 파일
│     │  ├─ issue_metrics.py  # issue 노드에서 사용해야 하는 issue만의 주요 지표를 불러오고 이상지표 탐지
│     │  ├─ main_metrics.py  # 모든 노드에서 사용될 주요 지표 데이터에서 불러오는 파일
│     │  ├─ revisit_metrics.py  # revisit 노드에서 사용해야 하는 revisit만의 주요 지표를 불러오고 이상지표 탐지
│     │  ├─ sns_metrics.py  # sns 노드에서 사용해야 하는 sns만의 주요 지표를 불러오고 이상지표 탐지
│     │  └─ strategy_metrics.py  # 전략을 낼 때 참고해야 할 전략 강도 지표 불러오는 파일
=======
│     ├─ metrics/        
│     │  ├─ general_metrics.py 
│     │  ├─ issue_metrics.py  
│     │  ├─ main_metrics.py 
│     │  ├─ revisit_metrics.py 
│     │  ├─ sns_metrics.py 
│     │  └─ strategy_metrics.py  
>>>>>>> Stashed changes
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
│  ├─ franchise_data_addmetrics.csv
│  ├─ biz_area_addmetrics.csv
<<<<<<< Updated upstream
│  └─ admin_dong.csv
=======
│  ├─ admin_dong.csv
│  ├─ label_encoder_store.pkl
│  └─ preprocessed_df.csv
>>>>>>> Stashed changes
│
├─ assets/
│
├─ docs/
│
├─ AutogluonModels/
│
├─ time_series.py   
├─ dashboard.py           
├─ streamlit_app.py                    
├─ 디버깅.py
├─ .streamlit/
<<<<<<< Updated upstream
│  └─ secrets.toml                                                   
└─ requirements.txt                              
=======
│  └─ secrets.toml                                                  
└─ requirements.txt                                 
>>>>>>> Stashed changes
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
CONFIRM_ON_MULTI = 1
LLM_MODEL = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.2
ENABLE_RELEVANCE_CHECK = true
ENABLE_MEMORY = true

# 4) 앱 실행 (Streamlit)
uv run streamlit run streamlit_app.py

```



