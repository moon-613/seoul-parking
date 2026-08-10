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

# 시간에 따라 변하지 않는 지표는 편차 모드를 쓸 수 없다
STATIC_COLS = {"store_food", "z_residual"}

c1, c2, c3 = st.columns([2, 2, 1])
metric_name = c1.selectbox("지도에 표시할 값", list(METRICS))
col, scale, hint, from_residual = METRICS[metric_name]

mode = c2.radio(
    "표시 방식", ["절대값", "이 시간대의 편차"], horizontal=True,
    help="절대값은 '어디가 여유로운가', 편차는 '이 동네에서 지금이 좋은 때인가'를 보여줍니다. "
         "동네 간 순위는 시간대가 바뀌어도 거의 그대로라, 절대값 지도는 조건을 바꿔도 비슷해 보입니다.",
    disabled=col in STATIC_COLS,
)
opacity = c3.slider("불투명도", 0.3, 1.0, 0.75, 0.05)

deviation = (mode == "이 시간대의 편차") and col not in STATIC_COLS

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

plot_df = plot_df.dropna(subset=[col]).copy()
if plot_df.empty:
    st.warning("표시할 값이 없습니다.")
    st.stop()

# ── 편차 모드: 그 동네의 전체 시간대 평균 대비 몇 %인지 ────────────
if deviation:
    src = df[df["has_parking"]] if f["exclude_zero"] else df
    dong_mean = src.groupby("adm_cd", observed=True)[col].mean().rename("dong_mean")
    plot_df = plot_df.merge(dong_mean, on="adm_cd", how="left")
    plot_df["deviation"] = (plot_df[col] / plot_df["dong_mean"] - 1) * 100
    plot_df = plot_df[plot_df["dong_mean"] > 0]

    color_col = "deviation"
    color_scale = "RdBu"
    midpoint = 0
    # 극단값이 색을 독점하지 않도록 상하위 5%로 범위를 자른다
    lim = max(abs(plot_df.deviation.quantile(0.05)), abs(plot_df.deviation.quantile(0.95)))
    color_range = (-lim, lim)
else:
    color_col, color_scale, midpoint, color_range = col, scale, (0 if from_residual else None), None

hover = {
    "sgg_nm": True, "living_pop": ":,.0f", "parking_slots": ":,.0f",
    "slots_per_1k": ":.1f", "store_food": ":,.0f", "adm_cd": False,
}
if from_residual:
    hover["z_residual"] = ":.2f"
if deviation:
    hover["deviation"] = ":+.0f"
    hover["dong_mean"] = ":.1f"

fig = px.choropleth_map(
    plot_df,
    geojson=boundary,
    locations="adm_cd",
    featureidkey="properties.adm_cd",
    color=color_col,
    color_continuous_scale=color_scale,
    color_continuous_midpoint=midpoint,
    range_color=color_range,
    hover_name="admi_nm",
    hover_data=hover,
    center={"lat": 37.5665, "lon": 126.978},
    zoom=10.2,
    opacity=opacity,
    map_style="carto-positron",
    labels={"slots_per_1k": "천명당주차면", "living_pop": "생활인구",
            "parking_slots": "공영주차면", "store_food": "음식점수",
            "sgg_nm": "자치구", "z_residual": "표준화잔차", "young_ratio": "20~30대비중",
            "deviation": "동네평균대비(%)", "dong_mean": "동네평균"},
)
fig.update_layout(height=640, margin=dict(r=0, t=0, l=0, b=0))
st.plotly_chart(fig, use_container_width=True)

if deviation:
    st.caption(
        f"**{metric_name} — 이 시간대의 편차** · {f['weekday']}요일 {TIMESLOT_LABEL[f['timeslot']]}  \n"
        "각 행정동의 **전체 요일·시간대 평균(28개)을 100으로 놓고** 지금이 몇 % 인지 표시합니다. "
        "**파란색 = 평소보다 여유, 빨간색 = 평소보다 빠듯.** 요일·시간대를 바꾸면 지도가 크게 달라집니다."
    )
    top = plot_df.nlargest(3, "deviation")
    bot = plot_df.nsmallest(3, "deviation")
    m1, m2 = st.columns(2)
    m1.success("**평소보다 여유** — " + ", ".join(
        f"{r.admi_nm} {r.deviation:+.0f}%" for r in top.itertuples()))
    m2.error("**평소보다 빠듯** — " + ", ".join(
        f"{r.admi_nm} {r.deviation:+.0f}%" for r in bot.itertuples()))
else:
    st.caption(f"**{metric_name}** — {hint} · 기준: {f['weekday']}요일 {TIMESLOT_LABEL[f['timeslot']]}")
    if col not in STATIC_COLS:
        st.caption("💡 동네 간 순위는 시간대가 바뀌어도 거의 그대로라 이 지도는 조건을 바꿔도 비슷해 보입니다. "
                   "시간대별 차이를 보려면 위에서 **‘이 시간대의 편차’** 를 선택하세요.")

if f["gu"] != "전체":
    st.caption(f"※ 사이드바의 **{f['gu']}** 선택은 아래 상세 표에만 적용됩니다. 지도는 서울 전체를 그립니다.")

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
