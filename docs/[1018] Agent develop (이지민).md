# [1018] Agent Pipeline (이지민)

- [ ]  `metrics` 폴더 및 파일 생성
- [ ]  `streamlit_app.py` 업데이트 (디자인 완성 x)
- [ ]  `requirements.txt` 업데이트 (streamlit module 추가)
- [ ]  `my_agent/utils/tools.py`에 구현되어 있던 몇 개의 함수들은 `my_agent/utils` 아래에 파일로 옮겼습니다
    - `prompt_builder` → `my_agent/utils/prompt_builder.py`
    - `memory` → `my_agent/utils/chat_history.py`
        - `chat_history` 폴더에 json으로 로그 저장됨
    - `postprocess` → `my_agent/utils/postprocess.py`
        
        

```bash
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