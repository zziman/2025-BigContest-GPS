#### 길 잃은 사장님의 마케팅 방향을 찾아드립니다. 
# Good Profit Sterategy, GPS
설명 설명 설명

<br>

## 사용법
- [Google Drive – BigContest Data & Models](https://drive.google.com/drive/folders/1PHuQ0MktQrNGLxbpdMhAsIu1dLTfrc56?usp=sharing)에서 `data` 폴더와 `AutogluonModels` 폴더 다운로드 후 프로젝트의 투트 (최상위 디렉토리)에 위치시키기
- [Naver 개발자 센터](https://developers.naver.com/main/)에서 회원가입 후 API key 발급 후 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`에 복사
- [SERPER](https://serper.dev/?utm_term=google%20search%20api&gad_source=1&gad_campaignid=18303173259&gbraid=0AAAAAo4ZGoFTAeI1fAA-lanHIZ6WQlowT&gclid=CjwKCAjwgeLHBhBuEiwAL5gNEfzLIWpKg1JLqHiADvDkkEgYntLfZAJOmEG0Xs3UkvmsNrPQwX7_pBoCYV4QAvD_BwE)에서 회원가입 후 API key 발급 후 `SERPER_API_KEY`에 복사
- [기상청 API허브 4.3 단기예보조회](https://apihub.kma.go.kr/)에서 API 신청 후 API Key 복사 후 `WEATHER_API_KEY`에 복사

## 설치 및 실행(uv)
```bash
# 1) 저장소 클론
git clone https://github.com/zziman/2025-BigContest.git
cd 2025-BigContest

# 2) 가상환경 + 의존성 설치
uv venv
source .venv/bin/activate    # Windows: .\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
uv venv --python 3.10

# 3) 시크릿(secrets.toml) 생성 — 권장 방식
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'TOML'
# --- API Keys ---
GOOGLE_API_KEY = "your_key"                 
NAVER_CLIENT_ID = "your_naver_client_id"
NAVER_CLIENT_SECRET = "your_naver_secret"
SERPER_API_KEY = "your_key"                         
WEATHER_API_KEY = 'your_key'

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

## 폴더 구조
```
GPS/
├─ my_agent/
│  ├─ __init__.py
│  ├─ agent.py
│  ├─ utils/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ state.py
│  │  ├─ prompt_builder.py
│  │  ├─ postprocess.py
│  │  ├─ chat_history.py
│  │  └─ tools.py
│  ├─ metrics/
│  │  ├─ general_metrics.py
│  │  ├─ issue_metrics.py
│  │  ├─ main_metrics.py
│  │  ├─ revisit_metrics.py
│  │  ├─ sns_metrics.py
│  │  ├─ season_metrics.py
│  │  ├─ cooperation_metrics.py
│  │  └─ strategy_metrics.py
│  └─ nodes/
│     ├─ router.py
│     ├─ sns.py
│     ├─ revisit.py
│     ├─ issue.py
│     ├─ general.py
│     ├─ relevance_check.py
│     ├─ season.py
│     ├─ cooperation.py
│     └─ web_augment.py
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
│  ├─ admin_dong.csv
│  ├─ label_encoder_store.pkl
│  ├─ preprocessed_df.csv
│  └─ data.duckdb
│
├─ scripts/
│  └─ build_duckdb.py
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
├─ .streamlit/
│  └─ secrets.toml
└─ requirements.txt                                                                                                              
```                                                 


<br>