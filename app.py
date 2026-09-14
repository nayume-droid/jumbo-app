import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
        if "貸玉タイプ" in line or "客層" in line or "日付" in line or "タイプ" in line:
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
        elif "タイプ" in col and col != "貸玉タイプ": renames[col] = "タイプ"
        elif "種別" in col: renames[col] = "タイプ"
        elif "部門" in col: renames[col] = "タイプ"
        elif "客数" in col: renames[col] = "客数"
        elif "時間" in col: renames[col] = "時間"
        elif "イベント" in col: renames[col] = "イベント"
        elif "特記事項１" in col or "特記事項1" in col: renames[col] = "特記事項1"
        elif "特記事項２" in col or "特記事項2" in col: renames[col] = "特記事項2"
    df = df.rename(columns=renames)
    
    # 数値化
    if "客数" in df.columns:
        df["客数"] = pd.to_numeric(df["客数"], errors='coerce').fillna(0)

    # 日付データの正規化
    df["dt"] = pd.to_datetime(df["日付"], errors='coerce')
    df["日付_str"] = df["dt"].dt.strftime('%Y/%m/%d')
    df["年月_str"] = df["dt"].dt.strftime('%Y/%m')
    
    # ISO週の「月曜日の日付（YYYY/MM/DD）」を算出
    df["ISO週開始日"] = df["dt"].apply(
        lambda d: d.fromisocalendar(d.isocalendar().year, d.isocalendar().week, 1).strftime('%Y/%m/%d') if pd.notnull(d) else None
    )
    
    return df

# 選択された指標に応じた2軸折れ線グラフ描画関数
def create_selectable_dual_line_chart(df_attr, df_total, group_col, title, x_label, selected_metrics, is_avg=False):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    y_col = "平均客数" if is_avg else "客数"
    
    # 選択された客層属性を左軸（第1軸）に追加
    categories = df_attr["客層"].unique()
    for cat in categories:
        if cat in selected_metrics:
            sub_df = df_attr[df_attr["客層"] == cat]
            fig.add_trace(
                go.Scatter(
                    x=sub_df[group_col], y=sub_df[y_col], name=cat,
                    mode="lines+markers"
                ),
                secondary_y=False
            )
    
    # 「部門総客数」が選択されている場合、右軸（第2軸）に半透明の太いグリーン線で追加
    if "部門総客数" in selected_metrics and df_total is not None and not df_total.empty:
        fig.add_trace(
            go.Scatter(
                x=df_total[group_col], y=df_total[y_col], name="部門総客数",
                mode="lines",
                line=dict(color="rgba(76, 175, 80, 0.35)", width=8)
            ),
            secondary_y=True
        )
    
    # 軸ラベルの設定
    y_title_left = "平均客数(名/日)" if is_avg else "観測客数(名)"
    y_title_right = "総客数(名/日)" if is_avg else "総客数(名)"
    
    fig.update_layout(
        title=title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text=y_title_left, secondary_y=False)
    fig.update_yaxes(title_text=y_title_right, secondary_y=True, showgrid=False)
    
    return fig

# 最高値・最低値の折れ線グラフ描画関数
def create_selectable_min_max_chart(df_minmax, group_col, title, x_label, selected_metrics):
    fig = go.Figure()
    
    categories = df_minmax["客層"].unique()
    for cat in categories:
        if cat in selected_metrics:
            sub_df = df_minmax[df_minmax["客層"] == cat]
            fig.add_trace(
                go.Scatter(
                    x=sub_df[group_col], y=sub_df["最高値"], name=f"{cat} (最高)",
                    mode="lines+markers", line=dict(width=2)
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=sub_df[group_col], y=sub_df["最低値"], name=f"{cat} (最低)",
                    mode="lines+markers", line=dict(width=2, dash="dot")
                )
            )
        
    fig.update_layout(
        title=title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text="客数(名)")
    
    return fig

# 分析セクション共通描画関数
def render_analysis_section(attr_data, total_data, days_per_week, days_per_month, rate_label, selected_metrics, title_suffix=""):
    if not selected_metrics:
        st.warning("サイドバーの「グラフ表示項目の選択」で1つ以上の項目を選択してください。")
        return

    if attr_data.empty:
        st.warning("該当する観測データが存在しません。")
        return

    # 1. 日別推移
    st.markdown(f"#### 1. 日別推移 {title_suffix}")
    day_attr = attr_data.groupby(["日付_str", "客層"])["客数"].sum().reset_index()
    day_total = total_data.groupby("日付_str")["客数"].sum().reset_index() if total_data is not None and not total_data.empty else None

    fig_day = create_selectable_dual_line_chart(day_attr, day_total, "日付_str", f"{rate_label} 日別客数推移 {title_suffix}", "日付 (YYYY/MM/DD)", selected_metrics, is_avg=False)
    st.plotly_chart(fig_day, use_container_width=True)

    # 2. 週別推移
    st.markdown(f"#### 2. 週別推移（1日あたり平均客数） {title_suffix}")
    week_attr = attr_data.groupby(["ISO週開始日", "客層"])["客数"].sum().reset_index()
    week_attr = pd.merge(week_attr, days_per_week, on="ISO週開始日")
    week_attr["平均客数"] = (week_attr["客数"] / week_attr["営業日数"]).round(1)

    week_total = None
    if total_data is not None and not total_data.empty:
        week_total = total_data.groupby("ISO週開始日")["客数"].sum().reset_index()
        week_total = pd.merge(week_total, days_per_week, on="ISO週開始日")
        week_total["平均客数"] = (week_total["客数"] / week_total["営業日数"]).round(1)

    fig_week = create_selectable_dual_line_chart(week_attr, week_total, "ISO週開始日", f"{rate_label} 週別 1日あたり平均客数推移 {title_suffix}", "週開始日 (YYYY/MM/DD)", selected_metrics, is_avg=True)
    st.plotly_chart(fig_week, use_container_width=True)

    # 週毎 最高値・最低値
    day_attr_raw = attr_data.groupby(["日付_str", "ISO週開始日", "客層"])["客数"].sum().reset_index()
    week_minmax = day_attr_raw.groupby(["ISO週開始日", "客層"])["客数"].agg(最高値='max', 最低値='min').reset_index()

    fig_week_minmax = create_selectable_min_max_chart(week_minmax, "ISO週開始日", f"{rate_label} 週別 各客層の最高値・最低値推移 {title_suffix}", "週開始日 (YYYY/MM/DD)", selected_metrics)
    st.plotly_chart(fig_week_minmax, use_container_width=True)

    # 3. 月別推移
    st.markdown(f"#### 3. 月別推移（1日あたり平均客数） {title_suffix}")
    month_attr = attr_data.groupby(["年月_str", "客層"])["客数"].sum().reset_index()
    month_attr = pd.merge(month_attr, days_per_month, on="年月_str")
    month_attr["平均客数"] = (month_attr["客数"] / month_attr["営業日数"]).round(1)

    month_total = None
    if total_data is not None and not total_data.empty:
        month_total = total_data.groupby("年月_str")["客数"].sum().reset_index()
        month_total = pd.merge(month_total, days_per_month, on="年月_str")
        month_total["平均客数"] = (month_total["客数"] / month_total["営業日数"]).round(1)

    fig_month = create_selectable_dual_line_chart(month_attr, month_total, "年月_str", f"{rate_label} 月別 1日あたり平均客数推移 {title_suffix}", "年月 (YYYY/MM)", selected_metrics, is_avg=True)
    st.plotly_chart(fig_month, use_container_width=True)

    # 月毎 最高値・最低値
    day_attr_month_raw = attr_data.groupby(["日付_str", "年月_str", "客層"])["客数"].sum().reset_index()
    month_minmax = day_attr_month_raw.groupby(["年月_str", "客層"])["客数"].agg(最高値='max', 最低値='min').reset_index()

    fig_month_minmax = create_selectable_min_max_chart(month_minmax, "年月_str", f"{rate_label} 月別 各客層の最高値・最低値推移 {title_suffix}", "年月 (YYYY/MM)", selected_metrics)
    st.plotly_chart(fig_month_minmax, use_container_width=True)

try:
    df = load_data(SPREADSHEET_CSV_URL)

    # 右上にデータ再取得ボタン
    if st.sidebar.button("🔄 最新データに更新"):
        st.cache_data.clear()
        st.rerun()

    # --- 2. フィルター設定 ---
    st.sidebar.header("🔍 フィルター設定")
    
    # 期間選択
    min_date = df["dt"].min().date() if not df["dt"].dropna().empty else datetime.today().date()
    max_date = df["dt"].max().date() if not df["dt"].dropna().empty else datetime.today().date()

    date_range = st.sidebar.date_input(
        "表示対象の期間を選択",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="YYYY/MM/DD"
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = df[(df["dt"].dt.date >= start_date) & (df["dt"].dt.date <= end_date)].copy()
    else:
        filtered_df = df.copy()

    # --- イベント・特記事項フィルター ---
    st.sidebar.markdown("---")
    st.sidebar.header("🎉 イベント・特記事項フィルター")
    
    # イベント・特記事項1・特記事項2の3列から「なし」や空欄を除外したユニークな値リストを取得
    event_cols = [c for c in ["イベント", "特記事項1", "特記事項2"] if c in filtered_df.columns]
    
    unique_events = set()
    for c in event_cols:
        vals = filtered_df[c].dropna().astype(str).str.strip().unique()
        for v in vals:
            if v and v != "なし" and v != "nan" and v != "None":
                unique_events.add(v)
    
    sorted_events = sorted(list(unique_events))
    
    selected_events = st.sidebar.multiselect(
        "絞り込むイベント・特記事項を選択（複数選択可）",
        options=sorted_events,
        default=[],
        help="選択した項目が『イベント』『特記事項1』『特記事項2』のいずれかに含まれる日を抽出します。"
    )
    
    # イベント・特記事項によるフィルタリング（選択がある場合）
    if selected_events and event_cols:
        cond = pd.Series(False, index=filtered_df.index)
        for c in event_cols:
            cond |= filtered_df[c].astype(str).str.strip().isin(selected_events)
        filtered_df = filtered_df[cond].copy()

    # 表示項目の選択（マルチセレクトボタン）
    st.sidebar.markdown("---")
    st.sidebar.header("📊 属性グラフ表示項目の選択")
    all_metrics = ["常連", "準常連", "新規・流動", "専業", "部門総客数"]
    selected_metrics = st.sidebar.multiselect(
        "表示する属性項目を選択（複数選択可）",
        options=all_metrics,
        default=all_metrics
    )

    # タイプ別分析のON/OFF切り替え
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 20Sタイプ別比較")
    enable_type_analysis = st.sidebar.checkbox("タイプ別分析を表示（画面2分割）", value=False)
    
    selected_types = []
    if enable_type_analysis:
        all_types = ["ジャグラー", "AT", "ノーマル系"]
        selected_types = st.sidebar.multiselect(
            "対象タイプを選択（複数選択可）",
            options=all_types,
            default=all_types
        )

    # --- 3. メインコンテンツ（20S / 5S タブ） ---
    tab_20s, tab_5s = st.tabs(["🎰 20S分析", "🪙 5S分析"])

    # 営業日数集計用
    days_per_week = filtered_df.groupby("ISO週開始日")["日付_str"].nunique().reset_index().rename(columns={"日付_str": "営業日数"})
    days_per_month = filtered_df.groupby("年月_str")["日付_str"].nunique().reset_index().rename(columns={"日付_str": "営業日数"})

    # タイプに該当する列名を判定
    type_col_name = "タイプ" if "タイプ" in filtered_df.columns else "客層"

    for rate, tab in [("20S", tab_20s), ("5S", tab_5s)]:
        with tab:
            st.markdown(f"### {rate} 観測データ分析")
            target_df = filtered_df[filtered_df["貸玉タイプ"] == rate].copy()
            
            if target_df.empty:
                st.warning("選択された条件に該当するデータが存在しません。")
                continue

            # 20Sかつタイプ別分析がONの場合は画面を2分割
            if rate == "20S" and enable_type_analysis:
                col_left, col_right = st.columns(2)
                
                # 【左カラム】20S全体の客層属性分析
                with col_left:
                    st.subheader("👥 20S 全体 客層属性分析")
                    attr_data = target_df[~target_df["客層"].str.contains("総客", na=False)].copy()
                    total_data = target_df[target_df["客層"].str.contains("総客", na=False)].copy()
                    render_analysis_section(attr_data, total_data, days_per_week, days_per_month, rate, selected_metrics, title_suffix="(全体)")

                # 【右カラム】選択されたタイプのみに絞り込んだ客層属性分析
                with col_right:
                    type_str = "・".join(selected_types) if selected_types else "未選択"
                    st.subheader(f"🎰 タイプ限定 客層属性分析（{type_str}）")
                    
                    if not selected_types:
                        st.info("サイドバーで対象のタイプ（ジャグラー・AT・ノーマル系）を選択してください。")
                    else:
                        # 選択された「タイプ」で絞り込み
                        pattern = "|".join(selected_types)
                        filtered_by_type = target_df[target_df[type_col_name].astype(str).str.contains(pattern, na=False)].copy()
                        
                        if filtered_by_type.empty:
                            st.warning(f"選択されたタイプ（{type_str}）の観測データが存在しません。")
                        else:
                            # 絞り込んだデータの中から「客層属性」と「総客数」を切り分け
                            type_attr_data = filtered_by_type[~filtered_by_type["客層"].str.contains("総客", na=False)].copy()
                            type_total_data = filtered_by_type[filtered_by_type["客層"].str.contains("総客", na=False)].copy()
                            
                            render_analysis_section(
                                type_attr_data, type_total_data, days_per_week, days_per_month,
                                rate, selected_metrics, title_suffix=f"({type_str}限定)"
                            )
            else:
                # OFF時（または5Sタブ）は従来のフルサイズ1カラム表示
                attr_data = target_df[~target_df["客層"].str.contains("総客", na=False)].copy()
                total_data = target_df[target_df["客層"].str.contains("総客", na=False)].copy()
                render_analysis_section(attr_data, total_data, days_per_week, days_per_month, rate, selected_metrics)

    # --- 4. 元データ一覧 ---
    st.subheader("📋 観測データ一覧")
    st.dataframe(filtered_df.drop(columns=["dt"], errors="ignore"))

except Exception as e:
    st.error(f"エラーが発生しました: {e}")