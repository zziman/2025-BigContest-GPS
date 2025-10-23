# time_series.py

import streamlit as st
import joblib
import pandas as pd
from autogluon.tabular import TabularPredictor

st.set_page_config(page_title="Next Month Sales Prediction", layout="centered")
st.title("🛒 다음달 매출 예상")

# 모델 및 데이터 로드
@st.cache_data
def load_predictor():
    return TabularPredictor.load("AutogluonModels/ag-20251018_185635")

@st.cache_data
def load_label_encoder():
    return joblib.load("data/label_encoder_store.pkl")

@st.cache_data
def load_data():
    return pd.read_csv("data/preprocessed_df.csv")

predictor = load_predictor()
label_encoder = load_label_encoder()
df = load_data()

label_map = {
    0: "90%초과(하위 10% 이하)",
    1: "75-90%",
    2: "50-75%",
    3: "25-50%",
    4: "10-25%",
    5: "10%이하"
}

# 예측 함수
def predict_next_month(store_id):
    try:
        encoded_store_id = label_encoder.transform([store_id])[0]
    except ValueError:
        st.error(f"[Error] store_id '{store_id}'는 학습 데이터에 존재하지 않습니다.")
        return None

    store_df = df[df["가맹점_구분번호"] == encoded_store_id].sort_values("기준년월")
    if store_df.empty:
        st.error(f"[Error] store_id {store_id} 데이터가 없습니다.")
        return None

    latest_row = store_df.iloc[-1:].copy()
    drop_cols = ['매출금액_구간', '매핑용_상권명', '매핑용_업종', '기준년월']
    latest_row = latest_row.drop(columns=drop_cols, errors='ignore')

    pred_class = predictor.predict(latest_row).iloc[0]
    pred_proba_df = predictor.predict_proba(latest_row).iloc[0]

    pred_label = label_map[int(pred_class)]
    pred_prob = float(pred_proba_df[int(pred_class)])

    return {
        "predicted_class": int(pred_class),
        "predicted_label": pred_label,
        "predicted_probability": pred_prob
    }

# Streamlit UI
store_id_input = st.text_input("Store ID를 입력해주세요:", "")
if st.button("입력"):
    if store_id_input.strip() == "":
        st.warning("Store ID를 입력해주세요.")
    else:
        result = predict_next_month(store_id_input.strip())
        if result:
            st.subheader(f"Store ID: {store_id_input}")
            st.metric(label="예상매출구간", value=result['predicted_label'],
                      delta=f"{result['predicted_probability']*100:.2f}% 확률")
