"""코스 추천 페이지 — 놀거리 × 주차여유 사분면에서 추천 동네를 고르고,
   선택한 동네가 가장 여유로운 시간대를 찾는다.
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (
    TIMESLOTS, TIMESLOT_LABEL, WEEKDAYS,
    apply_filters, page_header, require_data, sidebar_filters,
)

st.set_page_config(page_title="코스 추천 | 서울 나들이 주차", page_icon="🎯", layout="wide")

df = require_data()
f = sidebar_filters(df)
d = apply_filters(df, f, apply_gu=False).dropna(subset=["store_food"])

page_header(
    "🎯 코스 추천 — 놀거리 많고 주차도 여유로운 동네",
    "오른쪽 위(놀거리↑ 주차여유↑)에 가까울수록 나들이하기 좋습니다.",
)

if d.empty:
    st.warning("조건에 맞는 데이터가 없습니다.")
    st.stop()

# ── 기준선 설정 ────────────────────────────────────────────────
c1, c2 = st.columns(2)
food_q = c1.slider("놀거리 기준선 (음식점 수 상위 %)", 10, 90, 50, 5,
                   help="이 값보다 음식점이 많은 동네를 '놀거리 많음'으로 봅니다")
park_q = c2.slider("주차 기준선 (천명당 주차면 상위 %)", 10, 90, 50, 5)

food_line = d["store_food"].quantile(1 - food_q / 100)
park_line = d["slots_per_1k"].quantile(1 - park_q / 100)

d = d.copy()
d["구분"] = "그 외"
d.loc[(d.store_food >= food_line) & (d.slots_per_1k >= park_line), "구분"] = "⭐ 추천"
d.loc[(d.store_food >= food_line) & (d.slots_per_1k < park_line), "구분"] = "혼잡 주의"
d.loc[(d.store_food < food_line) & (d.slots_per_1k >= park_line), "구분"] = "한산"

COLORS = {"⭐ 추천": "#2CA02C", "혼잡 주의": "#D62728", "한산": "#7F9FBF", "그 외": "#D9D9D9"}

st.markdown(f"#### {f['weekday']}요일 · {TIMESLOT_LABEL[f['timeslot']]}")

k1, k2, k3 = st.columns(3)
k1.metric("⭐ 추천 동네", f"{(d['구분'] == '⭐ 추천').sum()}개")
k2.metric("혼잡 주의", f"{(d['구분'] == '혼잡 주의').sum()}개")
k3.metric("전체 대상", f"{len(d)}개")

# ── 사분면 산점도 ──────────────────────────────────────────────
fig = px.scatter(
    d, x="store_food", y="slots_per_1k", color="구분",
    color_discrete_map=COLORS, size="living_pop", size_max=28,
    hover_name="admi_nm",
    hover_data={"sgg_nm": True, "living_pop": ":,.0f", "parking_slots": ":,.0f",
                "slots_per_1k": ":.1f", "store_food": ":,.0f", "구분": False},
    labels={"store_food": "음식점 수 (놀거리)", "slots_per_1k": "1,000명당 공영주차면 (여유)",
            "sgg_nm": "자치구", "living_pop": "생활인구", "parking_slots": "공영주차면"},
)
fig.add_vline(x=food_line, line_dash="dash", line_color="#888")
fig.add_hline(y=park_line, line_dash="dash", line_color="#888")
fig.add_annotation(x=d.store_food.max() * 0.92, y=d.slots_per_1k.max() * 0.95,
                   text="⭐ 놀거리↑ 주차↑", showarrow=False, font=dict(size=13, color="#2CA02C"))
fig.update_layout(height=560, margin=dict(t=20, b=10),
                  legend=dict(orientation="h", y=1.08))
fig.update_yaxes(range=[0, d.slots_per_1k.quantile(0.98) * 1.1])
st.plotly_chart(fig, use_container_width=True)
st.caption("원 크기는 생활인구입니다. 세로축은 상위 2%를 잘라 표시합니다.")

st.divider()

# ── 추천 랭킹 ──────────────────────────────────────────────────
st.subheader("⭐ 추천 동네 랭킹")
rec = d[d["구분"] == "⭐ 추천"].copy()
if rec.empty:
    st.warning("기준을 만족하는 동네가 없습니다. 위 슬라이더를 완화해보세요.")
else:
    # 놀거리·주차 각각 백분위로 환산해 합산
    rec["놀거리점수"] = rec.store_food.rank(pct=True) * 100
    rec["주차점수"] = rec.slots_per_1k.rank(pct=True) * 100
    rec["종합점수"] = (rec.놀거리점수 + rec.주차점수) / 2

    show = ["sgg_nm", "admi_nm", "store_food", "slots_per_1k", "parking_slots", "living_pop", "종합점수"]
    names = {"sgg_nm": "자치구", "admi_nm": "행정동", "store_food": "음식점수",
             "slots_per_1k": "천명당주차면", "parking_slots": "공영주차면", "living_pop": "생활인구"}
    st.dataframe(
        rec.nlargest(15, "종합점수")[show].rename(columns=names).style.format(
            {"음식점수": "{:,.0f}", "천명당주차면": "{:.1f}", "공영주차면": "{:,.0f}",
             "생활인구": "{:,.0f}", "종합점수": "{:.0f}"}),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ── 동네별 최적 시간대 ─────────────────────────────────────────
st.subheader("⏰ 이 동네, 언제 가면 가장 여유로울까")

dong_list = sorted(d["admi_nm"].unique())
default = rec.nlargest(1, "종합점수").admi_nm.iloc[0] if not rec.empty else dong_list[0]
dong = st.selectbox("행정동 선택", dong_list, index=dong_list.index(default))

prof = df[df["admi_nm"] == dong].pivot_table(
    index="weekday", columns="timeslot", values="slots_per_1k", observed=True
).reindex(index=WEEKDAYS, columns=TIMESLOTS)

fig2 = px.imshow(
    prof, text_auto=".1f", aspect="auto",
    color_continuous_scale="RdYlBu", origin="upper",
    labels=dict(x="시간대", y="요일", color="천명당주차면"),
)
fig2.update_layout(height=380, margin=dict(t=10, b=10))
st.plotly_chart(fig2, use_container_width=True)

best = prof.stack().idxmax()
worst = prof.stack().idxmin()
b1, b2 = st.columns(2)
b1.success(f"**가장 여유**: {best[0]}요일 {TIMESLOT_LABEL[best[1]]} — {prof.loc[best]:.1f}")
b2.error(f"**가장 빠듯**: {worst[0]}요일 {TIMESLOT_LABEL[worst[1]]} — {prof.loc[worst]:.1f}")

diff = (prof.loc[best] / prof.loc[worst] - 1) * 100
st.info(f"**{dong}**은 가장 빠듯한 때보다 가장 여유로운 때가 **{diff:.0f}% 넉넉**합니다. "
        f"같은 주차장인데 사람 수가 달라서 생기는 차이입니다.", icon="💡")
