import streamlit as st
import pandas as pd
import plotly.express as px
import io
import urllib.request
from datetime import datetime

st.set_page_config(page_title="ジャンボマックス浜乃木店 来客分析", layout="wide")

st.title("🎰 ジャンボマックス浜乃木店 来店者データ分析アプリ")

# --- 1. Googleスプレッドシート（Web公開CSV）のURL ---
SPREADSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ-szp-Gc5whMCl9dXuY0vmrTo-f8jDk-0RQ6htlQc34wXTpdOU_fCrIgd4wYbX2rrrmcnWSq69LOgC/pub?output=csv"

@st.cache_data(ttl=600)  # 10分ごとに自動更新
def load_data(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')

    lines = content.splitlines()
    
    # ヘッダー行を探索
    header_idx = 0
    for idx, line in enumerate(lines[:10]):
        if "貸玉タイプ" in line or "客層" in line or "日付" in line:
            header_idx = idx
            break

    csv_data = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data), on_bad_lines='skip')
    df.columns = [str(col).strip() for col in df.columns]
    
    # 列名修正
    renames = {}
    for col in df.columns:
        if "日付" in col: renames[col] = "日付"
        elif "曜日" in col: renames[col] = "曜日"
        elif "貸玉" in col: renames[col] = "貸玉タイプ"
        elif "客層" in col: renames[col] = "客層"
        elif "客数" in col: renames[col] = "客数"
        elif "時間" in col: renames[col] = "時間"
    df = df.rename(columns=renames)
    
    # 数値化
    if "客数" in df.columns:
        df["客数"] = pd.to_numeric(df["客数"], errors='coerce').fillna(0)

    # 日付データの正規化とISO週（週開始日：月曜日）の計算
    df["dt"] = pd.to_datetime(df["日付"], errors='coerce')
    
    # 各日付が属するISO週の「月曜日の日付（YYYY/MM/DD）」を算出
    df["ISO週開始日"] = df["dt"].apply(
        lambda d: d.fromisocalendar(d.isocalendar().year, d.isocalendar().week, 1).strftime('%Y/%m/%d') if pd.notnull(d) else None
    )
    
    return df

try:
    df = load_data(SPREADSHEET_CSV_URL)

    # 右上にデータ再取得ボタン
    if st.sidebar.button("🔄 最新データに更新"):
        st.cache_data.clear()
        st.rerun()

    # --- 2. フィルター設定（日付範囲選択） ---
    st.sidebar.header("🔍 フィルター設定")
    
    min_date = df["dt"].min().date() if not df["dt"].dropna().empty else datetime.today().date()
    max_date = df["dt"].max().date() if not df["dt"].dropna().empty else datetime.today().date()

    # YYYY/MM/DD から YYYY/MM/DD までの範囲選択入力
    date_range = st.sidebar.date_input(
        "表示対象の期間を選択",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="YYYY/MM/DD"
    )

    # 範囲指定の適用
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = df[(df["dt"].dt.date >= start_date) & (df["dt"].dt.date <= end_date)].copy()
    else:
        filtered_df = df.copy()

    # --- 3. ISO週ごとの客層属性推移分析 ---
    st.subheader("📅 週ごとの客層属性推移分析")
    
    # 合計行（20S総客・5S総客）を除外して純粋な客層属性のみ抽出
    attr_df = filtered_df[~filtered_df["客層"].str.contains("総客", na=False)].copy()

    tab1, tab2 = st.tabs(["🎰 20S客層属性推移", "🪙 5S客層属性推移"])

    with tab1:
        st.markdown("##### 20Sの客層属性（常連 / 準常連 / 新規・流動 / 専業）の週別変化")
        df_20s = attr_df[attr_df["貸玉タイプ"] == "20S"]
        
        # 週開始日 × 客層属性での合計
        summary_20s = df_20s.groupby(["ISO週開始日", "客層"])["客数"].sum().reset_index()

        fig_20s = px.line(
            summary_20s,
            x="ISO週開始日",
            y="客数",
            color="客層",
            markers=True,
            title="20S：週別の客層属性推移（横軸：週の開始日 YYYY/MM/DD）",
            labels={"客数": "延べ客数(名)", "ISO週開始日": "週開始日 (YYYY/MM/DD)"}
        )
        fig_20s.update_layout(hovermode="x unified")
        st.plotly_chart(fig_20s, use_container_width=True)

    with tab2:
        st.markdown("##### 5Sの客層属性（常連 / 準常連 / 新規・流動 / 専業）の週別変化")
        df_5s = attr_df[attr_df["貸玉タイプ"] == "5S"]
        
        # 週開始日 × 客層属性での合計
        summary_5s = df_5s.groupby(["ISO週開始日", "客層"])["客数"].sum().reset_index()

        fig_5s = px.line(
            summary_5s,
            x="ISO週開始日",
            y="客数",
            color="客層",
            markers=True,
            title="5S：週別の客層属性推移（横軸：週の開始日 YYYY/MM/DD）",
            labels={"客数": "延べ客数(名)", "ISO週開始日": "週開始日 (YYYY/MM/DD)"}
        )
        fig_5s.update_layout(hovermode="x unified")
        st.plotly_chart(fig_5s, use_container_width=True)

    # --- 4. 元データ一覧 ---
    st.subheader("📋 観測データ一覧")
    st.dataframe(filtered_df.drop(columns=["dt"], errors="ignore"))

except Exception as e:
    st.error(f"エラーが発生しました: {e}")