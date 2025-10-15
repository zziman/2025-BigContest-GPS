# -*- coding: utf-8 -*-
"""
Adapter: streamlit_app.py가 기대하는 대시보드 API를 제공
- dashboard_viz.py 에 있는 코드/데이터를 활용하여 필요한 함수만 노출
"""
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ───────── 유틸 ─────────
def to_month_robust(s):
    if pd.isna(s): return pd.NaT
    if isinstance(s, (pd.Timestamp, datetime)):
        return pd.Timestamp(s).to_period('M').to_timestamp()
    s = str(s).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 6:
        y = int(digits[:4]); m = int(digits[4:6])
        if 1 <= m <= 12:
            return pd.Timestamp(y, m, 1)
    dt = pd.to_datetime(s, errors="coerce")
    return (pd.Timestamp(dt).to_period('M').to_timestamp()
            if pd.notna(dt) else pd.NaT)

def ensure_dt(df):
    if "기준년월" not in df.columns:
        raise KeyError("CSV에 '기준년월' 컬럼이 없습니다.")
    df = df.copy()
    df["dt"] = df["기준년월"].apply(to_month_robust)
    if df["dt"].notna().sum() == 0:
        def hard(s):
            s = str(s)
            ds = "".join(ch for ch in s if ch.isdigit())
            if len(ds) >= 6:
                y, m = int(ds[:4]), int(ds[4:6])
                if 1<=m<=12: return pd.Timestamp(y, m, 1)
            return pd.NaT
        df["dt"] = df["기준년월"].apply(hard)
    return df

def parse_bin_mid(v):
    if pd.isna(v): return np.nan
    if isinstance(v, (int,float,np.number)): return float(v)
    s = str(v).strip()
    m = re.search(r"(\d+)\s*-\s*(\d+)", s)
    if not m: return np.nan
    return (float(m.group(1)) + float(m.group(2))) / 2.0

def get_num(row, col, bin_col=None):
    v = row.get(col, np.nan)
    if pd.notna(v):
        try: return float(v)
        except: pass
    if bin_col:
        return parse_bin_mid(row.get(bin_col))
    return np.nan

def pick_latest_row(df, dt_target, upjong=None, key_col=None, key_val=None):
    q = df.copy()
    if upjong is not None and "업종" in q.columns:
        q = q[q["업종"].astype(str) == str(upjong)]
    if key_col and (key_col in q.columns):
        q = q[q[key_col].astype(str) == str(key_val)]
    if q.empty:
        return pd.Series(), "no_match_condition"
    same = q[q["dt"] == dt_target]
    if not same.empty:
        return same.sort_values("dt").iloc[-1], "match_same_dt"
    past = q[q["dt"] < dt_target]
    if not past.empty:
        return past.sort_values("dt").iloc[-1], "fallback_past_dt"
    latest = q.sort_values("dt").iloc[-1]
    return latest, "fallback_latest_any"

def pick_peers(df, dt_target, upjong, trade_key):
    base = df[(df["업종"].astype(str)==str(upjong)) & (df["상권_지리"].astype(str)==str(trade_key))]
    if base.empty: return base, "peer_no_key_match"
    p = base[base["dt"] == dt_target]
    if not p.empty: return p, "peer_same_dt"
    p = base[base["dt"] < dt_target]
    if not p.empty: return p.sort_values("dt").tail(9999), "peer_past_dt"
    return base.sort_values("dt").tail(9999), "peer_latest_any"

# ───────── 필수 API ─────────
def load_all_data(fr_path, bz_path, ad_path):
    fr = ensure_dt(pd.read_csv(fr_path, low_memory=False))
    bz = ensure_dt(pd.read_csv(bz_path, low_memory=False))
    ad = ensure_dt(pd.read_csv(ad_path, low_memory=False))
    if "가맹점_구분번호" not in fr.columns:
        raise KeyError("franchise_data.csv 에 '가맹점_구분번호'가 없습니다.")
    fr["MCT_KEY"] = fr["가맹점_구분번호"].astype(str).str.strip()
    # 텍스트 정리
    for df in (fr, bz, ad):
        for c in ("업종","상권_지리","행정동","행정동_코드_명"):
            if c in df.columns:
                df[c] = df[c].astype(str).str.replace("\u200b","").str.strip()
    # 행정동 정규화
    fr["행정동_norm"] = fr.get("행정동", pd.Series(index=fr.index, dtype=object)).astype(str).str.split().str[-1]
    if "행정동_코드_명" in ad.columns:
        ad["행정동_norm"] = ad["행정동_코드_명"].astype(str).str.split().str[-1]
    elif "행정동" in ad.columns:
        ad["행정동_norm"] = ad["행정동"].astype(str).str.split().str[-1]
    else:
        ad["행정동_norm"] = np.nan
    return fr, bz, ad

def compute_context(fr, bz, ad, store_id):
    dfm = fr[fr["MCT_KEY"] == str(store_id)].copy()
    if dfm.empty:
        raise ValueError(f"선택한 가맹점({store_id}) 데이터가 없습니다.")
    latest_dt = dfm["dt"].dropna().max()
    cand = dfm[dfm["dt"]==latest_dt]
    if cand.empty:
        cand = dfm.sort_values("dt").tail(1)
    row_now = cand.iloc[0]
    upjong    = str(row_now.get("업종",""))
    trade_key = str(row_now.get("상권_지리",""))
    dong_key  = str(row_now.get("행정동_norm",""))
    peers, _  = pick_peers(fr, row_now["dt"], upjong, trade_key)
    tr_row, _ = pick_latest_row(bz, row_now["dt"], upjong, "상권_지리", trade_key)
    dn_row, _ = pick_latest_row(ad, row_now["dt"], upjong, "행정동_norm", dong_key)
    return dfm, row_now, peers, tr_row, dn_row

# ───────── 시각화 ─────────
def build_kpi_figs(row_now, dfm, peers):
    figs = []
    items = [
        ("총매출금액", get_num(row_now,"총매출금액","매출금액_구간"), "원"),
        ("객단가",     get_num(row_now,"객단가","객단가_구간") or 
                       (get_num(row_now,"총매출금액","매출금액_구간") /
                        max(get_num(row_now,"총매출건수","매출건수_구간") or 1, 1)), "원"),
        ("재방문 고객 비중", row_now.get("재방문_고객_비중", np.nan), "%"),
        ("취소율", row_now.get("취소율", np.nan) if "취소율" in row_now.index else np.nan, "%"),
        ("배달매출비율", row_now.get("배달매출금액_비율", np.nan), "%"),
    ]
    # 전월 비교
    prev_dt = row_now["dt"] - pd.offsets.MonthBegin(1) if pd.notna(row_now["dt"]) else row_now["dt"]
    prev = dfm[dfm["dt"]==prev_dt]
    prev_row = prev.iloc[0] if not prev.empty else row_now
    for title, cur, unit in items:
        if pd.isna(cur): 
            continue
        ref = cur
        if title=="총매출금액":
            ref = get_num(prev_row,"총매출금액","매출금액_구간") or cur
        elif title=="객단가":
            ref = get_num(prev_row,"객단가","객단가_구간") or cur
        elif title=="재방문 고객 비중":
            ref = prev_row.get("재방문_고객_비중", cur)
        elif title=="취소율":
            ref = (prev_row.get("취소율", np.nan) if "취소율" in prev_row.index else np.nan) or cur
        elif title=="배달매출비율":
            ref = prev_row.get("배달매출금액_비율", cur)

        fig = go.Figure(go.Indicator(
            mode="number+delta", value=float(cur),
            number={"valueformat": ",.0f", "suffix": f" {unit}"},
            delta={"reference": float(ref), "relative": False, "valueformat": ",.0f"},
            title={"text": title}
        ))
        fig.update_layout(height=100, margin=dict(l=10,r=10,t=30,b=10))
        figs.append(fig)
    return figs

def build_pyramid(row_now, dn_row):
    age_order = ["≤20","30","40","50","60+"]
    male_vals = [row_now.get("남성_20대이하_고객_비중",0), row_now.get("남성_30대_고객_비중",0),
                 row_now.get("남성_40대_고객_비중",0),   row_now.get("남성_50대_고객_비중",0),
                 row_now.get("남성_60대이상_고객_비중",0)]
    fem_vals  = [row_now.get("여성_20대이하_고객_비중",0), row_now.get("여성_30대_고객_비중",0),
                 row_now.get("여성_40대_고객_비중",0),   row_now.get("여성_50대_고객_비중",0),
                 row_now.get("여성_60대이상_고객_비중",0)]
    fig = go.Figure()
    fig.add_bar(x=-np.array(male_vals, dtype=float), y=age_order, name="남성", orientation="h")
    fig.add_bar(x= np.array(fem_vals,  dtype=float), y=age_order, name="여성", orientation="h")
    fig.update_layout(barmode="relative", height=520, margin=dict(l=20,r=20,t=20,b=20),
                      xaxis=dict(title_text="비중(%)", tickformat=".0f"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

def build_radar_and_minibars(row_now, peers):
    def pct_rank(series, val):
        s = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
        if s.empty or pd.isna(val): return np.nan
        return (s < float(val)).mean() * 100
    def peer_series(col, fallback=None):
        if peers is None or peers.empty: return None
        if col in peers.columns and not peers[col].isna().all():
            return pd.to_numeric(peers[col], errors="coerce")
        if fallback and fallback in peers.columns:
            return peers[fallback].map(parse_bin_mid)
        return None

    axes = [
        ("거래건수(상위 %)", "총매출건수", "매출건수_구간"),
        ("객단가(상위 %)",   "객단가",     "객단가_구간"),
        ("재방문(%)",        "재방문_고객_비중", None),
        ("취소율(%)",        "취소율",     "취소율_구간"),
        ("배달비율(%)",      "배달매출금액_비율", None),
        ("매출금액(상위 %)", "총매출금액", "매출금액_구간"),
    ]
    mini_rows = []
    for title, col, bin_col in axes:
        v = get_num(row_now, col, bin_col)
        p = pct_rank(peer_series(col, bin_col), v)
        if "상위" in title:
            mini_rows.append({"지표": title, "값": (100 - p) if pd.notna(p) else 0})
    mini_df = pd.DataFrame(mini_rows)
    mini = px.bar(mini_df, x="값", y="지표", orientation="h", text="값", range_x=[0,100])
    mini.update_traces(texttemplate='%{text:.1f}%', textposition="outside")
    mini.update_layout(height=210, margin=dict(l=20,r=20,t=10,b=10), xaxis_title="", yaxis_title="")

    # 간단 레이더(동일 척도 0~100)
    radar_labels = [r["지표"] for r in mini_rows]
    radar_vals   = [r["값"]  for r in mini_rows]
    radar = go.Figure()
    if radar_labels:
        radar.add_trace(go.Scatterpolar(r=radar_vals, theta=radar_labels, fill="toself", name="매장"))
        radar.update_layout(height=360, polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                            margin=dict(l=40,r=40,t=40,b=40))
    return radar, mini

def build_trend_24m(dfm):
    d = dfm.sort_values("dt").tail(24).copy()
    if "객단가" not in d.columns or d["객단가"].isna().all():
        if "객단가_구간" in d.columns:
            d["객단가"] = d["객단가_구간"].map(parse_bin_mid)
    if "총매출금액" not in d.columns or d["총매출금액"].isna().all():
        if "매출금액_구간" in d.columns:
            d["총매출금액"] = d["매출금액_구간"].map(parse_bin_mid)

    fig = go.Figure()
    if "총매출금액" in d.columns and not d["총매출금액"].isna().all():
        fig.add_trace(go.Scatter(x=d["dt"], y=d["총매출금액"], mode="lines+markers", name="총매출금액(구간)"))
    if "객단가" in d.columns and not d["객단가"].isna().all():
        fig.add_trace(go.Scatter(x=d["dt"], y=d["객단가"], mode="lines", name="객단가", yaxis="y2", line=dict(dash="dot")))
    if "재방문_고객_비중" in d.columns and not d["재방문_고객_비중"].isna().all():
        fig.add_trace(go.Scatter(x=d["dt"], y=d["재방문_고객_비중"], mode="lines", name="재방문(%)", yaxis="y3", line=dict(dash="dash")))
    fig.update_layout(
        height=380, margin=dict(l=20,r=20,t=20,b=20),
        yaxis=dict(title="매출(원, 또는 구간중간값)"),
        yaxis2=dict(title="객단가(원)", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(title="재방문(%)", overlaying="y", side="right", position=0.92, showgrid=False),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom")
    )
    return fig

def build_gap_bar(row_now, peers):
    def peer_mean(col, bin_col=None):
        if peers is None or peers.empty: return np.nan
        s = peers[col] if (col in peers.columns) else None
        if s is None or pd.Series(s).isna().all():
            if bin_col and (bin_col in peers.columns):
                s = peers[bin_col].map(parse_bin_mid)
        if s is None: return np.nan
        s = pd.to_numeric(s, errors="coerce").dropna()
        return s.mean() if not s.empty else np.nan

    items = [
        ("객단가", get_num(row_now,"객단가","객단가_구간"), peer_mean("객단가","객단가_구간")),
        ("재방문(%)", row_now.get("재방문_고객_비중", np.nan), peer_mean("재방문_고객_비중")),
        ("취소율(%)", row_now.get("취소율", np.nan), peer_mean("취소율","취소율_구간")),
        ("배달비율(%)", row_now.get("배달매출금액_비율", np.nan), peer_mean("배달매출금액_비율")),
    ]
    df = pd.DataFrame([{"지표":k, "격차":(s-a) if (pd.notna(s) and pd.notna(a)) else np.nan}
                       for k,s,a in items]).dropna()
    if df.empty:
        return go.Figure()
    fig = px.bar(df, x="격차", y="지표", orientation="h", color="격차",
                 color_continuous_scale=["#d73027","#fdae61","#eeeeee","#a6d96a","#1a9850"],
                 color_continuous_midpoint=0)
    fig.update_traces(texttemplate='%{x:+.1f}', textposition="outside")
    fig.update_layout(height=220, coloraxis_showscale=False, margin=dict(l=20,r=20,t=10,b=10),
                      xaxis_title="매장 - 피어 평균", yaxis_title="")
    return fig

def build_age_dev(row_now, dn_row):
    age_labels = ["≤20","30","40","50","60+"]
    store_age_map = {
        "≤20": (row_now.get("남성_20대이하_고객_비중",0) + row_now.get("여성_20대이하_고객_비중",0)),
        "30":  (row_now.get("남성_30대_고객_비중",0)    + row_now.get("여성_30대_고객_비중",0)),
        "40":  (row_now.get("남성_40대_고객_비중",0)    + row_now.get("여성_40대_고객_비중",0)),
        "50":  (row_now.get("남성_50대_고객_비중",0)    + row_now.get("여성_50대_고객_비중",0)),
        "60+": (row_now.get("남성_60대이상_고객_비중",0) + row_now.get("여성_60대이상_고객_비중",0)),
    }
    if dn_row is not None and not isinstance(dn_row, pd.Series):
        dn_row = pd.Series(dn_row)
    if dn_row is None or dn_row.empty:
        x_region = [0,0,0,0,0]
    else:
        age_counts = {
            "≤20": (dn_row.get("연령대_10_상주인구_수",0) or 0) + (dn_row.get("연령대_20_상주인구_수",0) or 0),
            "30":  dn_row.get("연령대_30_상주인구_수",0) or 0,
            "40":  dn_row.get("연령대_40_상주인구_수",0) or 0,
            "50":  dn_row.get("연령대_50_상주인구_수",0) or 0,
            "60+": dn_row.get("연령대_60_이상_상주인구_수",0) or 0,
        }
        tot = float(np.nansum(list(age_counts.values())))
        x_region = [((age_counts[a]/tot)*100.0 if tot>0 else 0) for a in age_labels]
    y_store  = [store_age_map.get(a,0) for a in age_labels]

    vmax = max(max(x_region or [0]), max(y_store or [0]), 1) * 1.1
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_region, y=y_store, mode="markers+text", text=age_labels, textposition="top center"))
    fig.add_trace(go.Scatter(x=[0, vmax], y=[0, vmax], mode="lines", line=dict(color="gray", dash="dot")))
    fig.update_layout(height=260, margin=dict(l=20,r=20,t=10,b=10),
                      xaxis_title="행정동 연령대 비중(%)", yaxis_title="매장 방문 비중(%)",
                      showlegend=False, xaxis_range=[0, vmax], yaxis_range=[0, vmax])
    return fig

def build_heatmap(tr_row, kind="flow"):
    # 간이 버전 (trade row 사용)
    if tr_row is None or (isinstance(tr_row, pd.Series) and tr_row.empty):
        return go.Figure()
    if kind == "flow":
        time_cols = ["시간대_00_06_유동인구_수","시간대_06_11_유동인구_수","시간대_11_14_유동인구_수",
                     "시간대_14_17_유동인구_수","시간대_17_21_유동인구_수","시간대_21_24_유동인구_수"]
        dow_cols  = ["월요일_유동인구_수","화요일_유동인구_수","수요일_유동인구_수","목요일_유동인구_수",
                     "금요일_유동인구_수","토요일_유동인구_수","일요일_유동인구_수"]
    else:
        time_cols = ["시간대_00~06_매출_금액","시간대_06~11_매출_금액","시간대_11~14_매출_금액",
                     "시간대_14~17_매출_금액","시간대_17~21_매출_금액","시간대_21~24_매출_금액"]
        dow_cols  = ["월요일_매출_금액","화요일_매출_금액","수요일_매출_금액","목요일_매출_금액",
                     "금요일_매출_금액","토요일_매출_금액","일요일_매출_금액"]
    time_labels = ["00-06시","06-11시","11-14시","14-17시","17-21시","21-24시"]
    dow_labels  = ["월","화","수","목","금","토","일"]

    tr_vals_time = [float(tr_row.get(c, 0) or 0) for c in time_cols]
    tr_vals_dow  = [float(tr_row.get(c, 0) or 0) for c in dow_cols]
    mat = np.outer(np.array(tr_vals_dow, dtype=float), np.array(tr_vals_time, dtype=float))
    m, s = float(np.nanmean(mat)), float(np.nanstd(mat))
    z = (mat - m)/s if s not in (0.0, np.nan) else mat*0
    fig = go.Figure(go.Heatmap(z=z, x=time_labels, y=dow_labels, colorscale="RdBu_r", zmid=0, colorbar=dict(title="Z")))
    fig.update_layout(height=350, margin=dict(l=20,r=20,t=10,b=10))
    return fig
