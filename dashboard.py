# dashboard.py
# -*- coding: utf-8 -*-
"""
대시보드 데이터 로직 및 시각화
"""
import io
import csv
import re
import numpy as np
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

import duckdb
from pathlib import Path 

from my_agent.utils.config import DUCKDB_PATH, USE_DUCKDB
# ==== THEME ====
THEME_MAIN  = "#7742e3"
THEME_DARK  = "#5b2fc7"
THEME_LIGHT = "#d9ccff"
THEME_LINE  = "#e6e0fb"
THEME_INK   = "#111827"
THEME_MUTED = "#6b7280"

# ========= 유틸리티 =========
def smart_read_csv(path, expect_cols=None, max_bytes=3_000_000):
    enc_candidates = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    seps = [",", "\t", "|", ";"]
    for enc in enc_candidates:
        for sep in seps:
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc, engine="python", quoting=csv.QUOTE_MINIMAL)
                if expect_cols and not set(expect_cols).issubset(df.columns):
                    continue
                return df, {"encoding": enc, "sep": sep}
            except Exception:
                pass
    raise RuntimeError(f"smart_read_csv 실패: {path}")

def to_month_robust(s):
    if pd.isna(s):
        return pd.NaT
    if isinstance(s, (pd.Timestamp, datetime)):
        return pd.Timestamp(s).to_period('M').to_timestamp()
    s = str(s).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 6:
        y, m = int(digits[:4]), int(digits[4:6])
        if 1 <= m <= 12:
            return pd.Timestamp(y, m, 1)
    dt = pd.to_datetime(s, errors="coerce")
    return pd.Timestamp(dt).to_period('M').to_timestamp() if pd.notna(dt) else pd.NaT

def ensure_dt(df):
    df["dt"] = df["기준년월"].apply(to_month_robust)
    return df

def clean_str(s):
    if pd.isna(s): return s
    return str(s).replace("\u200b", "").strip()

def clean_str_col(df, col):
    if col in df.columns:
        df[col] = df[col].map(clean_str)

def zscore(arr):
    arr = np.asarray(arr, dtype=float)
    m, sd = np.nanmean(arr), np.nanstd(arr)
    if (sd == 0) or np.isnan(sd): return np.zeros_like(arr)
    return (arr - m) / sd

def pct_rank(series, val):
    if series is None or pd.isna(val): return np.nan
    s = pd.Series(series, dtype="float64").dropna()
    if s.empty: return np.nan
    return (s < float(val)).mean() * 100.0

def as_pct(val):
    if pd.isna(val): return np.nan
    try:
        v = float(val)
        if 0 <= v <= 1.0: return v * 100.0
        return v
    except Exception:
        return np.nan

def as_pct_series(series):
    if series is None: return None
    return series.apply(as_pct)

# ========= 데이터 로드 =========
def load_all_data(franchise_csv, biz_area_csv):
    """대시보드용 데이터 로드 (DuckDB 우선)"""
    
    # ─────────────────────────────────────────
    # DuckDB 사용
    # ─────────────────────────────────────────
    if USE_DUCKDB:
        try:
            db_path = Path(DUCKDB_PATH).expanduser()
            if not db_path.exists():
                raise FileNotFoundError(f"DuckDB 파일 없음: {db_path}")
            
            con = duckdb.connect(str(db_path), read_only=True)
            
            # 전체 데이터 로드 (대시보드는 전체 데이터 필요)
            store = con.execute("SELECT * FROM franchise").fetchdf()
            trade = con.execute("SELECT * FROM biz_area").fetchdf()
            
            con.close()
            
            print(f"✅ DuckDB 로드 완료: franchise {len(store):,} rows, biz_area {len(trade):,} rows")
            
        except Exception as e:
            print(f"⚠️  DuckDB 로드 실패, CSV로 대체: {e}")
            # DuckDB 실패 시 CSV로 fallback
            store_need = ["기준년월", "가맹점_구분번호", "업종", "상권_지리"]
            trade_need = ["기준년월", "업종", "상권_지리"]
            store, _ = smart_read_csv(franchise_csv, expect_cols=store_need)
            trade, _ = smart_read_csv(biz_area_csv, expect_cols=trade_need)
            print(f"✅ CSV 로드 완료: franchise {len(store):,} rows, biz_area {len(trade):,} rows")
    
    # ─────────────────────────────────────────
    # CSV 사용 (USE_DUCKDB=False일 때)
    # ─────────────────────────────────────────
    else:
        store_need = ["기준년월", "가맹점_구분번호", "업종", "상권_지리"]
        trade_need = ["기준년월", "업종", "상권_지리"]
        store, _ = smart_read_csv(franchise_csv, expect_cols=store_need)
        trade, _ = smart_read_csv(biz_area_csv, expect_cols=trade_need)
        print(f"✅ CSV 로드 완료: franchise {len(store):,} rows, biz_area {len(trade):,} rows")
    
    # ─────────────────────────────────────────
    # 공통 전처리 (기존 코드 그대로)
    # ─────────────────────────────────────────
    store = ensure_dt(store)
    trade = ensure_dt(trade)
    
    # 문자열 정리
    for col in ["가맹점명", "업종", "상권_지리"]:
        clean_str_col(store, col)
    for col in ["업종", "상권_지리"]:
        clean_str_col(trade, col)
    
    # MCT_KEY 생성 (대시보드용 고유키)
    if "가맹점_구분번호" in store.columns and "가맹점명" in store.columns:
        store["MCT_KEY"] = (
            store["가맹점_구분번호"].astype(str) + "___" + 
            store["가맹점명"].astype(str)
        )
    
    return store, trade

# ========= 컨텍스트 계산 =========
def pick_latest_row(df, dt_target, upjong=None, key_col=None, key_val=None):
    q = df.copy()
    if upjong and "업종" in q.columns:
        q = q[q["업종"].astype(str) == str(upjong)]
    if key_col and key_col in q.columns:
        q = q[q[key_col].astype(str) == str(key_val)]
    if q.empty: return pd.Series(), "no_match"
    same = q[q["dt"] == dt_target]
    if not same.empty: return same.sort_values("dt").iloc[-1], "match_same_dt"
    past = q[q["dt"] < dt_target]
    if not past.empty: return past.sort_values("dt").iloc[-1], "fallback_past_dt"
    return q.sort_values("dt").iloc[-1], "fallback_latest"

def pick_peers(df, dt_target, upjong, trade_key):
    base = df[(df["업종"].astype(str) == str(upjong)) & (df["상권_지리"].astype(str) == str(trade_key))]
    if base.empty: return base, "no_peer"
    p = base[base["dt"] == dt_target]
    if not p.empty: return p, "same_dt"
    p = base[base["dt"] < dt_target]
    if not p.empty: return p.tail(9999), "past"
    return base.tail(9999), "latest"

def compute_context(store, trade, admin_dong, store_id):
    dfm = store[store["MCT_KEY"] == str(store_id)].copy()
    if dfm.empty: raise ValueError(f"매장 ID({store_id}) 데이터 없음.")
    latest_dt = dfm["dt"].dropna().max()
    cand = dfm[dfm["dt"] == latest_dt]
    row_now = cand.iloc[0]
    upjong = str(row_now.get("업종", ""))
    trade_key = str(row_now.get("상권_지리", ""))
    peers, _ = pick_peers(store, row_now["dt"], upjong, trade_key)
    if "MCT_KEY" in peers.columns:
        peers = peers[peers["MCT_KEY"] != row_now["MCT_KEY"]]
    tr_row, _ = pick_latest_row(trade, row_now["dt"], upjong, "상권_지리", trade_key)
    return dfm, row_now, peers, tr_row, None

# ========= 스타일 유틸 =========
def _apply_card_style(fig, height=196):
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=88, b=20),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )
    return fig

# ========= KPI 카드 =========
def build_kpi_figs(row_now, dfm, peers):
    def peer_series(col):
        if peers.empty or col not in peers.columns:
            return None
        return pd.to_numeric(peers[col], errors="coerce")

    def indicator_card(title, desc, cur, prev, peer_s, unit="%", higher_is_good=True):
        curp = as_pct(cur)
        prevp = as_pct(prev) if pd.notna(prev) else np.nan
        ps = as_pct_series(pd.to_numeric(peer_s, errors="coerce")) if peer_s is not None else None
        pctl = pct_rank(ps, curp) if ps is not None else np.nan
        upper = f"동일 상권·업종 대비 상위 {100 - pctl:.0f}% 위치" if pd.notna(pctl) else ""

        show_delta = pd.notna(prevp) and pd.notna(curp)
        # 색상
        if show_delta:
            delta_value = curp - prevp
            if delta_value > 0: value_color = "#10b981"
            elif delta_value < 0: value_color = "#dc2626"
            else: value_color = THEME_INK
        else:
            value_color = THEME_INK

        fig = go.Figure(go.Indicator(
            mode="number" + ("+delta" if show_delta else ""),
            value=float(curp) if pd.notna(curp) else 0.0,
            number={"valueformat": ",.1f", "suffix": f" {unit}",
                    "font": {"size": 42, "color": value_color}},
            delta=({"reference": float(prevp),
                    "relative": False, "valueformat": ",.1f", "suffix": f" {unit}",
                    "increasing": {"color": "#10b981"},
                    "decreasing": {"color": "#dc2626"}}
                   if show_delta else None),
            title={"text":
                   f"<b style='font-size:17px;color:{THEME_INK}'>{title}</b>"
                   f"<br><span style='font-size:12px;color:{THEME_MUTED};line-height:1.45'>{desc}</span>"
                   + (f"<br><span style='font-size:12px;color:{THEME_MUTED}'>{upper}</span>" if upper else "")
            }
        ))
        return _apply_card_style(fig, height=196)

    prev_dt = row_now["dt"] - pd.offsets.MonthBegin(1) if pd.notna(row_now["dt"]) else row_now["dt"]
    prev_row = dfm[dfm["dt"] == prev_dt].iloc[0] if not dfm[dfm["dt"] == prev_dt].empty else row_now

    cur_repeat   = row_now.get("단골손님_비중", np.nan)
    cur_delivery = row_now.get("배달매출_비중", np.nan)
    cur_ind_rev  = row_now.get("동일_업종_매출금액_비율", np.nan)
    cur_ind_cnt  = row_now.get("동일_업종_매출건수_비율", np.nan)

    kpis = []
    if pd.notna(cur_repeat):
        kpis.append(indicator_card("재방문율", "단골 비중",
                                   cur_repeat, prev_row.get("단골손님_비중", np.nan),
                                   peer_series("단골손님_비중"), "%"))
    if pd.notna(cur_delivery):
        kpis.append(indicator_card("배달 매출 비중", "총매출 중 배달이 차지하는 비중",
                                   cur_delivery, prev_row.get("배달매출_비중", np.nan),
                                   peer_series("배달매출_비중"), "%"))

    for t, v, ps_col in [
        ("업종대비 매출액 지수", cur_ind_rev, "동일_업종_매출금액_비율"),
        ("업종대비 건수 지수",   cur_ind_cnt, "동일_업종_매출건수_비율"),
    ]:
        if pd.notna(v):
            ps = peer_series(ps_col)
            pctl = pct_rank(pd.to_numeric(ps, errors="coerce") if ps is not None else None, float(v))
            upper = f"동일업종·동일상권 대비 상위 {100 - pctl:.0f}% 위치" if pd.notna(pctl) else ""
            fig = go.Figure(go.Indicator(
                mode="number",
                value=float(v),
                number={"valueformat": ",.1f", "font": {"size": 42, "color": THEME_INK}},
                title={"text":
                       f"<b style='font-size:17px;color:{THEME_INK}'>{t}</b>"
                       f"<br><span style='font-size:12px;color:{THEME_MUTED};line-height:1.45'>동일 업종 같은 달 평균 100 기준</span>"
                       f"<br><span style='font-size:12px;color:{THEME_MUTED}'>{upper}</span>"
                }
            ))
            kpis.append(_apply_card_style(fig, height=196))

    while len(kpis) < 4:
        dummy = go.Figure().add_annotation(text="데이터 없음", showarrow=False,
                                           font=dict(size=14, color=THEME_MUTED))
        kpis.append(_apply_card_style(dummy, height=196))
    return kpis[:4]

def build_top3_fig(row_now):
    top_names = [str(row_now.get("핵심고객_1순위","")), str(row_now.get("핵심고객_2순위","")), str(row_now.get("핵심고객_3순위",""))]
    top_vals  = [as_pct(row_now.get("핵심고객_1순위_비중",np.nan)),
                 as_pct(row_now.get("핵심고객_2순위_비중",np.nan)),
                 as_pct(row_now.get("핵심고객_3순위_비중",np.nan))]
    top_df = pd.DataFrame({"그룹": top_names, "비중(%)": top_vals}).dropna()
    if not top_df.empty:
        top_df = top_df.sort_values("비중(%)", ascending=True)
        vmax = float(top_df["비중(%)"].max() or 0.0)
        xr = [0, max(30.0, round(vmax * 1.15, 1))]
        fig = px.bar(top_df, x="비중(%)", y="그룹", orientation="h",
                     text="비중(%)", range_x=xr,
                     color_discrete_sequence=[THEME_MAIN])  # 보라
        fig.update_traces(texttemplate='%{text:.1f}%', textposition="outside", cliponaxis=False)
        fig.update_layout(
            margin=dict(l=16, r=54, t=10, b=12),
            xaxis_title="", yaxis_title="", height=228,
            paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        )
    else:
        fig = go.Figure().add_annotation(text="핵심고객 정보가 없습니다.", showarrow=False)
        fig.update_layout(margin=dict(l=16, r=16, t=10, b=10),
                          xaxis={"visible": False}, yaxis={"visible": False}, height=220)
    return fig


def build_pyramid(row_now, dn_row):
    age_labels = ["20대 이하","30대","40대","50대","60대 이상"]
    male_vals = [as_pct(row_now.get("남성_20대이하_고객_비중",0) or 0),
                 as_pct(row_now.get("남성_30대_고객_비중",0) or 0),
                 as_pct(row_now.get("남성_40대_고객_비중",0) or 0),
                 as_pct(row_now.get("남성_50대_고객_비중",0) or 0),
                 as_pct(row_now.get("남성_60대이상_고객_비중",0) or 0)]
    fem_vals  = [as_pct(row_now.get("여성_20대이하_고객_비중",0) or 0),
                 as_pct(row_now.get("여성_30대_고객_비중",0) or 0),
                 as_pct(row_now.get("여성_40대_고객_비중",0) or 0),
                 as_pct(row_now.get("여성_50대_고객_비중",0) or 0),
                 as_pct(row_now.get("여성_60대이상_고객_비중",0) or 0)]
    pyr_df = pd.DataFrame({"연령대": age_labels*2, "비중(%)": male_vals+fem_vals, "성별": ["남성"]*5 + ["여성"]*5})
    fig = px.bar(pyr_df, x="연령대", y="비중(%)", color="성별", barmode="group",
                 color_discrete_map={"남성": THEME_DARK, "여성": THEME_LIGHT})
    fig.update_layout(
        height=440,
        margin=dict(l=22, r=18, t=18, b=36),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    )
    return fig


def build_radar_and_minibars(row_now, peers):
    # 라벨 줄바꿈으로 클리핑 방지
    axes_cols = [("단골<br>비중(%)","단골손님_비중"),
                 ("신규<br>비중(%)","신규손님_비중"),
                 ("배달<br>비중(%)","배달매출_비중"),
                 ("거주고객<br>비중(%)","거주고객_비중"),
                 ("직장고객<br>비중(%)","직장고객_비중")]
    labels, r_store_vals, r_peer_vals = [], [], []
    hover_store, hover_peer = [], []

    def get_peer_series_percent(col_name):
        if (not peers.empty) and (col_name in peers.columns):
            return as_pct_series(pd.to_numeric(peers[col_name], errors="coerce"))
        return None

    for label, col in axes_cols:
        store_raw = as_pct(row_now.get(col, np.nan))
        peer_s = get_peer_series_percent(col)
        if pd.isna(store_raw) or (peer_s is None) or peer_s.dropna().empty:
            continue
        peer_mean = float(peer_s.dropna().mean())
        labels.append(label); r_store_vals.append(float(store_raw)); r_peer_vals.append(peer_mean)
        # hover 텍스트는 줄바꿈 없는 풀 라벨로
        plain = label.replace("<br>", " ")
        hover_store.append(f"{plain}<br>매장: {store_raw:.1f}%")
        hover_peer.append(f"{plain}<br>동일 상권·업종 평균: {peer_mean:.1f}%")

    radar_fig = go.Figure()
    if labels:
        radar_fig.add_trace(go.Scatterpolar(
            r=r_store_vals, theta=labels, name='매장',
            line=dict(color=THEME_DARK, width=2),
            fill='toself', fillcolor="rgba(119,66,227,0.18)",
            hovertext=hover_store, hoverinfo='text'
        ))
        radar_fig.add_trace(go.Scatterpolar(
            r=r_peer_vals, theta=labels, name='동일 상권·업종 평균',
            line=dict(color=THEME_LIGHT, width=2),
            fill='toself', fillcolor="rgba(217,204,255,0.25)",
            hovertext=hover_peer, hoverinfo='text'
        ))
        radar_fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0,100], tickvals=[0,25,50,75,100],
                                tickfont=dict(size=11)),
                angularaxis=dict(tickfont=dict(size=12),  # 라벨 글씨 조금 키움
                                 rotation=90,             # 위쪽에서 시작 → 좌우 클리핑 감소
                                 direction="clockwise")
            ),
            showlegend=True,
            margin=dict(l=56, r=56, t=26, b=62),  # 여백 넉넉히
            height=350,
            paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        )
    return radar_fig, None


def build_trend_24m(dfm):
    """24개월 트렌드 차트"""
    df24 = dfm.sort_values("dt").tail(24).copy()
    
    def nz(col):
        return (col in df24.columns) and (not df24[col].isna().all())
    
    def series_pct(col):
        s = pd.to_numeric(df24[col], errors="coerce")
        return s.apply(as_pct)
    
    fig = go.Figure()
    
    if nz("단골손님_비중"):
        fig.add_trace(go.Scatter(
            x=df24["dt"], y=series_pct("단골손님_비중"),
            mode="lines+markers", name="재방문율(단골손님_비중, %)", yaxis="y"
        ))
    
    if nz("배달매출_비중"):
        fig.add_trace(go.Scatter(
            x=df24["dt"], y=series_pct("배달매출_비중"),
            mode="lines+markers", name="배달 비중(배달매출_비중, %)", yaxis="y"
        ))
    
    if nz("동일_업종_매출금액_비율"):
        fig.add_trace(go.Scatter(
            x=df24["dt"], y=pd.to_numeric(df24["동일_업종_매출금액_비율"], errors="coerce"),
            mode="lines", name="업종대비 매출액 지수(=100 평균)", line=dict(dash="dot"), yaxis="y2"
        ))
    
    if nz("동일_업종_매출건수_비율"):
        fig.add_trace(go.Scatter(
            x=df24["dt"], y=pd.to_numeric(df24["동일_업종_매출건수_비율"], errors="coerce"),
            mode="lines", name="업종대비 건수 지수(=100 평균)", line=dict(dash="dot"), yaxis="y2"
        ))
    
    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis=dict(title="정규화 비율(%)", rangemode="tozero"),
        yaxis2=dict(title="지수(업종 평균=100)", overlaying="y", side="right", rangemode="tozero"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


# === gap bar 비활성화 =======================================
def build_gap_bar(row_now, peers):
    fig = go.Figure()
    fig.update_layout(height=10, margin=dict(l=0, r=0, t=0, b=0),
                      xaxis={"visible": False}, yaxis={"visible": False})
    return fig


def build_age_dev(row_now, dn_row):
    """연령대 편차 차트 (매장 방문 연령 vs 상권 연령 - 행정동 제거됨)"""
    fig = go.Figure()
    fig.add_annotation(
        text="연령대 편차 분석은 현재 비활성화되었습니다.",
        showarrow=False,
        font=dict(size=14, color="#666")
    )
    fig.update_layout(
        height=220,
        margin=dict(l=20, r=20, t=10, b=10),
        xaxis={"visible": False},
        yaxis={"visible": False}
    )
    return fig


def build_heatmap(tr_row, kind="flow"):
    """요일×시간 히트맵 (상권 기준, Z-정규화) — kind: 'flow' or 'sales'"""
    def _first_available(cols):
        for c in cols:
            if c in tr_row.index:
                return c
        return None

    def _collect(prefix_patterns):
        vals = []
        for patterns in prefix_patterns:
            c = _first_available(patterns)
            vals.append(float(tr_row.get(c, 0) if c else 0.0))
        return vals

    time_candidates_flow = [
        ("시간대_00_06_유동인구_수", "시간대_00~06_유동인구_수"),
        ("시간대_06_11_유동인구_수", "시간대_06~11_유동인구_수"),
        ("시간대_11_14_유동인구_수", "시간대_11~14_유동인구_수"),
        ("시간대_14_17_유동인구_수", "시간대_14~17_유동인구_수"),
        ("시간대_17_21_유동인구_수", "시간대_17~21_유동인구_수"),
        ("시간대_21_24_유동인구_수", "시간대_21~24_유동인구_수"),
    ]
    time_candidates_sales = [
        ("시간대_00_06_매출_금액", "시간대_00~06_매출_금액"),
        ("시간대_06_11_매출_금액", "시간대_06~11_매출_금액"),
        ("시간대_11_14_매출_금액", "시간대_11~14_매출_금액"),
        ("시간대_14_17_매출_금액", "시간대_14~17_매출_금액"),
        ("시간대_17_21_매출_금액", "시간대_17~21_매출_금액"),
        ("시간대_21_24_매출_금액", "시간대_21~24_매출_금액"),
    ]
    dow_candidates_flow = [
        ("월요일_유동인구_수",), ("화요일_유동인구_수",), ("수요일_유동인구_수",),
        ("목요일_유동인구_수",), ("금요일_유동인구_수",), ("토요일_유동인구_수",), ("일요일_유동인구_수",)
    ]
    dow_candidates_sales = [
        ("월요일_매출_금액",), ("화요일_매출_금액",), ("수요일_매출_금액",),
        ("목요일_매출_금액",), ("금요일_매출_금액",), ("토요일_매출_금액",), ("일요일_매출_금액",)
    ]

    if kind == "sales":
        tvals = _collect(time_candidates_sales)
        dvals = _collect(dow_candidates_sales)
        if sum(tvals) == 0 and sum(dvals) == 0:
            tvals = _collect(time_candidates_flow); dvals = _collect(dow_candidates_flow)
    else:
        tvals = _collect(time_candidates_flow)
        dvals = _collect(dow_candidates_flow)
        if sum(tvals) == 0 and sum(dvals) == 0:
            tvals = _collect(time_candidates_sales); dvals = _collect(dow_candidates_sales)

    time_labels = ["00-06시", "06-11시", "11-14시", "14-17시", "17-21시", "21-24시"]
    dow_labels  = ["월", "화", "수", "목", "금", "토", "일"]

    mat = np.outer(np.array(dvals, dtype=float), np.array(tvals, dtype=float))

    fig = go.Figure(go.Heatmap(
        z=zscore(mat), x=time_labels, y=dow_labels,
        colorscale="RdBu_r", zmid=0, colorbar=dict(title="Z")
    ))
    fig.update_layout(
        height=368,
        margin=dict(l=22, r=22, t=14, b=22),
        xaxis_title="시간대", yaxis_title="요일",
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    )
    return fig