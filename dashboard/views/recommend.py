"""코스 추천 페이지 — 놀거리 × 주차여유 사분면에서 추천 동네를 고르고,
   선택한 동네가 가장 여유로운 시간대를 찾는다.
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (
    COURSE_COLOR, INK, RECOMMEND_EXCLUDE, RECOMMEND_TIMESLOTS, SCALE_SEQ,
    TIMESLOTS, TIMESLOT_LABEL, WEEKDAYS, apply_filters, page_header,
    require_analysis, require_data, scope_phrase, sidebar_filters, with_parking,
)

df = require_data()
# 자치구는 사이드바에 두지 않는다. 이 페이지는 산점도도 랭킹도 서울 전체를 그리므로
# (apply_gu=False) 사이드바에서 고른 자치구가 화면을 바꾸지 않는데, scope_phrase는
# '강남구에 가면'이라고 말해 필터가 걸린 것처럼 보였다.
# 자치구를 고르는 자리는 아래 '언제 가면 좋을까'의 드롭다운 하나로 충분하다.
f = sidebar_filters(df, need=("weekday", "timeslot"))
suit = require_analysis("suitability")
d = apply_filters(df, f, apply_gu=False).dropna(subset=["store_food"])

page_header(
    "🎯 코스 추천 — 놀거리 많고 주차도 여유로운 동네",
    "오른쪽 위(놀거리↑ 주차여유↑)에 가까울수록 나들이하기 좋습니다.",
)

if d.empty:
    st.warning("조건에 맞는 데이터가 없습니다.")
    st.stop()

# ── 기준선 설정 ────────────────────────────────────────────────
# 백분위가 아니라 실제 값으로 받는다.
# 백분위('상위 X%')는 슬라이더를 오른쪽으로 밀수록 기준이 느슨해져 기준선이 왼쪽으로 갔다.
# 슬라이더와 화면 위의 선이 반대로 움직이는 셈이라 조작이 어긋났다.
# 실값으로 두면 슬라이더를 오른쪽으로 밀면 선도 오른쪽으로 가고 기준이 엄격해진다.
#
# 범위는 필터를 바꿔도 흔들리지 않게 패널 전체(모든 요일·시간대)에서 잡는다.
# 상위 5%는 극단값이라 슬라이더 눈금을 낭비하므로 95분위에서 끊는다.
_all = df[df["has_parking"]]
FOOD_MAX = int(round(_all["store_food"].quantile(0.95), -1))
PARK_MAX = float(round(_all["slots_per_1k"].quantile(0.95)))

c1, c2 = st.columns(2)
food_line = c1.slider(
    "놀거리 기준 — 음식점 수", 0, FOOD_MAX, 200, 20,
    help=f"이 개수 이상인 동네를 '놀거리 많음'으로 봅니다. "
         f"오른쪽으로 밀수록 기준이 엄격해집니다. (상위 5%인 {FOOD_MAX}개 초과는 눈금 밖)",
)
park_line = c2.slider(
    "주차 기준 — 1,000명당 공영주차면", 0.0, PARK_MAX, 6.0, 0.5,
    help="이 값 이상인 동네를 '주차 여유'로 봅니다. 오른쪽으로 밀수록 기준이 엄격해집니다.",
)

d = d.copy()
d["구분"] = "그 외"
d.loc[(d.store_food >= food_line) & (d.slots_per_1k >= park_line), "구분"] = "⭐ 추천"
d.loc[(d.store_food >= food_line) & (d.slots_per_1k < park_line), "구분"] = "혼잡 주의"
d.loc[(d.store_food < food_line) & (d.slots_per_1k >= park_line), "구분"] = "한산"

COLORS = COURSE_COLOR

st.markdown(f"#### {scope_phrase(f)}")

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
fig.add_vline(x=food_line, line_dash="dash", line_color=INK["muted"])
fig.add_hline(y=park_line, line_dash="dash", line_color=INK["muted"])
fig.add_annotation(x=d.store_food.max() * 0.92, y=d.slots_per_1k.max() * 0.95,
                   text="⭐ 놀거리↑ 주차↑", showarrow=False, font=dict(size=13, color=COURSE_COLOR["⭐ 추천"]))
fig.update_layout(height=560, margin=dict(t=20, b=10),
                  legend=dict(orientation="h", y=1.08))
fig.update_yaxes(range=[0, d.slots_per_1k.quantile(0.98) * 1.1])
st.plotly_chart(fig, use_container_width=True)
st.caption(f"점선이 위에서 정한 기준입니다 — 음식점 **{food_line:,}개** · 천명당 **{park_line:.1f}면**. "
           "오른쪽 위로 갈수록 나들이하기 좋습니다. 원 크기는 생활인구이고, 세로축은 상위 2%를 잘라 표시합니다.")

st.divider()

# ── 추천 랭킹 ──────────────────────────────────────────────────
st.subheader("⭐ 추천 동네 랭킹")
rec = d[d["구분"] == "⭐ 추천"].copy()
if rec.empty:
    st.warning("기준을 만족하는 동네가 없습니다. 위 슬라이더를 완화해보세요.")
else:
    # 순위는 대시보드에서 즉석 계산하지 않고 suitability.py가 만든 지수를 그대로 쓴다.
    # 예전에는 (놀거리 백분위 + 주차 백분위)/2 라는 임의 가중치를 여기서 계산했는데,
    # 기획서가 "임의 가중치가 아닌 PCA 기반"이라고 명시한 것과 어긋났고
    # 필터를 바꿀 때마다 값이 흔들려 보고서 수치와도 맞지 않았다.
    rec = rec.merge(
        suit[["admi_cd", "나들이적합도", "매력도지수_pct", "주차여유지수_pct"]],
        on="admi_cd", how="left")

    show = ["sgg_nm", "admi_nm", "나들이적합도", "매력도지수_pct", "주차여유지수_pct",
            "store_food", "parking_slots"]
    names = {"sgg_nm": "자치구", "admi_nm": "행정동", "나들이적합도": "적합도",
             "매력도지수_pct": "매력도", "주차여유지수_pct": "주차여유",
             "store_food": "음식점수", "parking_slots": "공영주차면"}
    st.dataframe(
        rec.nlargest(15, "나들이적합도")[show].rename(columns=names).style.format(
            {"적합도": "{:.1f}", "매력도": "{:.0f}", "주차여유": "{:.0f}",
             "음식점수": "{:,.0f}", "공영주차면": "{:,.0f}"}),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "**적합도**는 PCA로 뽑은 매력도 축(PC1 52.1%)과 주차 여유 축(PC2 39.2%)을 "
        "백분위로 환산해 **기하평균**한 값입니다. 한쪽만 높으면 점수가 크게 떨어집니다 — "
        "주차가 없으면 놀거리가 많아도 못 가고, 그 반대도 마찬가지이기 때문입니다."
    )

st.divider()

# ── 동네별 최적 시간대 ─────────────────────────────────────────
st.subheader("⏰ 이 동네, 언제 가면 가장 여유로울까")

# 자치구를 먼저 고르고 그 안의 행정동을 고른다 (424개를 한 줄에 늘어놓지 않기 위해)
if not rec.empty:
    top = rec.nlargest(1, "나들이적합도").iloc[0]
    default_gu, default_dong = top.sgg_nm, top.admi_nm
else:
    first = d.sort_values(["sgg_nm", "admi_nm"]).iloc[0]
    default_gu, default_dong = first.sgg_nm, first.admi_nm

# 다른 페이지에서 고른 자치구가 있으면 그것을 기본값으로 이어받는다.
# 이 페이지 사이드바에는 자치구가 없지만 선택값은 session_state에 남아 있어,
# 현황·지도에서 강남구를 보다 넘어오면 여기서도 강남구부터 열린다.
prev_gu = st.session_state.get("gu", "전체")
if prev_gu != "전체":
    default_gu = prev_gu

gu_list = sorted(d["sgg_nm"].dropna().unique())
s1, s2 = st.columns(2)

sel_gu = s1.selectbox("자치구", gu_list,
                      index=gu_list.index(default_gu) if default_gu in gu_list else 0)

dong_names = sorted(d.loc[d["sgg_nm"] == sel_gu, "admi_nm"].unique())
dong_list = ["전체"] + dong_names
dong_idx = dong_list.index(default_dong) if default_dong in dong_list else 0
dong = s2.selectbox("행정동", dong_list, index=dong_idx,
                    help=f"{sel_gu}에 행정동 {len(dong_names)}개가 있습니다. "
                         "'전체'를 고르면 이들의 평균을 봅니다.")

# '전체'면 자치구 안 행정동들의 평균, 아니면 해당 동 하나
if dong == "전체":
    src = df[df["sgg_nm"] == sel_gu]
    label = f"{sel_gu} 전체"
else:
    src = df[(df["sgg_nm"] == sel_gu) & (df["admi_nm"] == dong)]
    label = f"{sel_gu} {dong}"

# 0면 동은 요일·시간대와 무관하게 값이 0이라 '언제 가면 좋은가'를 못 낸다
src = with_parking(src)

prof = src.pivot_table(
    index="weekday", columns="timeslot", values="slots_per_1k", observed=True
).reindex(index=WEEKDAYS, columns=TIMESLOTS)

if prof.isna().all().all():
    st.warning(f"{label}에 표시할 데이터가 없습니다. 사이드바의 '0면 동 제외'를 해제해보세요.")
    st.stop()

fig2 = px.imshow(
    prof, text_auto=".1f", aspect="auto",
    color_continuous_scale=SCALE_SEQ, origin="upper",
    labels=dict(x="시간대", y="요일", color="천명당주차면"),
)
fig2.update_layout(height=380, margin=dict(t=10, b=10))
st.plotly_chart(fig2, use_container_width=True)

# 히트맵에는 아침(06-10)도 그대로 두되, '가장 여유로운 때'로는 고르지 않는다.
# 이 시간대는 주차가 실제로 비지만 사람이 없어서 비는 것이라, 나들이객에게
# "아침 7시에 가세요"는 실행할 수 없는 답이다. 제외 대상은 config에서 관리한다.
pick = prof[[c for c in prof.columns if c in RECOMMEND_TIMESLOTS]]
best = pick.stack().idxmax()
worst = pick.stack().idxmin()
b1, b2 = st.columns(2)
b1.success(f"**가장 여유**: {best[0]}요일 {TIMESLOT_LABEL[best[1]]} — {pick.loc[best]:.1f}")
b2.error(f"**가장 빠듯**: {worst[0]}요일 {TIMESLOT_LABEL[worst[1]]} — {pick.loc[worst]:.1f}")
if RECOMMEND_EXCLUDE:
    excluded = ", ".join(TIMESLOT_LABEL[t] for t in RECOMMEND_EXCLUDE)
    st.caption(f"위 표에는 **{excluded}** 도 함께 나오지만, 추천에서는 뺐습니다 — "
               "이 시간대는 주차가 비는 게 아니라 **사람이 없어서** 비는 것이라 "
               "나들이 시점으로는 쓸 수 없습니다.")

diff = (pick.loc[best] / pick.loc[worst] - 1) * 100
suffix = " (자치구 내 행정동 평균)" if dong == "전체" else ""
st.info(f"**{label}**{suffix}은 가장 빠듯한 때보다 가장 여유로운 때가 **{diff:.0f}% 넉넉**합니다. "
        f"같은 주차장인데 사람 수가 달라서 생기는 차이입니다.", icon="💡")
