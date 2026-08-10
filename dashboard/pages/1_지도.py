"""지도 페이지 — 행정동 경계에 선택 조건의 값을 색으로 표시"""
import plotly.express as px
import streamlit as st

from common import (
    SCALE_DEMAND, SCALE_SUPPLY, TIMESLOT_LABEL,
    apply_filters, load_boundary, load_residual, page_header, require_data, sidebar_filters,
)

st.set_page_config(page_title="지도 | 서울 나들이 주차", page_icon="🗺️", layout="wide")

df = require_data()
f = sidebar_filters(df)
d = apply_filters(df, f, apply_gu=False)   # 지도는 항상 서울 전체를 그린다
boundary = load_boundary()

page_header("🗺️ 행정동 지도", "선택한 요일·시간대 기준으로 색이 바뀝니다. 마우스를 올리면 상세가 보입니다.")

if not boundary:
    st.error("행정동 경계 파일이 없습니다.")
    st.code(".\\.venv\\Scripts\\python.exe -m src.collect.fetch_dong_boundary")
    st.stop()

METRICS = {
    "공영주차 여유도 (천명당 주차면)": ("slots_per_1k", SCALE_SUPPLY, "높을수록 여유", False),
    "혼잡도 (생활인구)": ("living_pop", SCALE_DEMAND, "높을수록 붐빔", False),
    "20~30대 비중": ("young_ratio", SCALE_DEMAND, "젊은층이 몰리는 정도", False),
    "음식점 수": ("store_food", SCALE_DEMAND, "놀거리 밀집도", False),
    "공급 과부족 (회귀 잔차)": ("z_residual", "RdYlGn", "음수=기대보다 부족", True),
}

c1, c2 = st.columns([3, 1])
metric_name = c1.selectbox("지도에 표시할 값", list(METRICS))
col, scale, hint, from_residual = METRICS[metric_name]
opacity = c2.slider("불투명도", 0.3, 1.0, 0.75, 0.05)

# 회귀 잔차는 시간과 무관한 정적 지표라 별도 파일에서 가져온다
if from_residual:
    res = load_residual()
    if res.empty:
        st.error("잔차 분석 결과가 없습니다.")
        st.code(".\\.venv\\Scripts\\python.exe -m src.analysis.residual")
        st.stop()
    plot_df = d.merge(res[["adm_cd", "z_residual", "expected_slots", "grade"]], on="adm_cd", how="inner")
    st.caption("※ 회귀 잔차는 요일·시간대에 따라 거의 변하지 않습니다(순위상관 0.99 이상). "
               "토요일 오후를 기준으로 산출한 값입니다.")
else:
    plot_df = d

if f["gu"] != "전체":
    st.caption(f"사이드바에서 **{f['gu']}** 를 선택하셨습니다. 지도는 전체를 그리되 해당 자치구를 강조합니다.")

plot_df = plot_df.dropna(subset=[col])
if plot_df.empty:
    st.warning("표시할 값이 없습니다.")
    st.stop()

hover = {
    "sgg_nm": True, "living_pop": ":,.0f", "parking_slots": ":,.0f",
    "slots_per_1k": ":.1f", "store_food": ":,.0f", "adm_cd": False,
}
if from_residual:
    hover["z_residual"] = ":.2f"

fig = px.choropleth_map(
    plot_df,
    geojson=boundary,
    locations="adm_cd",
    featureidkey="properties.adm_cd",
    color=col,
    color_continuous_scale=scale,
    color_continuous_midpoint=0 if from_residual else None,
    hover_name="admi_nm",
    hover_data=hover,
    center={"lat": 37.5665, "lon": 126.978},
    zoom=10.2,
    opacity=opacity,
    map_style="carto-positron",
    labels={"slots_per_1k": "천명당주차면", "living_pop": "생활인구",
            "parking_slots": "공영주차면", "store_food": "음식점수",
            "sgg_nm": "자치구", "z_residual": "표준화잔차", "young_ratio": "20~30대비중"},
)
fig.update_layout(height=640, margin=dict(r=0, t=0, l=0, b=0))
st.plotly_chart(fig, use_container_width=True)

st.caption(f"**{metric_name}** — {hint} · 기준: {f['weekday']}요일 {TIMESLOT_LABEL[f['timeslot']]}")

# ── 선택 자치구 상세 ────────────────────────────────────────────
if f["gu"] != "전체":
    st.divider()
    st.subheader(f"{f['gu']} 행정동 상세")
    sub = plot_df[plot_df["sgg_nm"] == f["gu"]].sort_values(col, ascending=False)
    show = ["admi_nm", "living_pop", "parking_slots", "slots_per_1k", "store_food"]
    names = {"admi_nm": "행정동", "living_pop": "생활인구", "parking_slots": "공영주차면",
             "slots_per_1k": "천명당주차면", "store_food": "음식점수"}
    st.dataframe(
        sub[show].rename(columns=names).style.format(
            {"생활인구": "{:,.0f}", "공영주차면": "{:,.0f}", "천명당주차면": "{:.1f}", "음식점수": "{:,.0f}"}),
        use_container_width=True, hide_index=True,
    )

if f["exclude_zero"]:
    st.info("공영주차장이 0면인 행정동 66개는 지도에서 빠져 있습니다(회색). "
            "사이드바에서 '0면 동 제외'를 해제하면 포함됩니다.", icon="ℹ️")
