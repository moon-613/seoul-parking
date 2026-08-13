"""탐색 페이지 — 선택한 요일·시간대의 공영주차 여유도와 혼잡도

실행: streamlit run dashboard/app.py
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (
    ACCENT, ACCENT_LIGHT, INK, SCALE_SUPPLY, TIMESLOTS, TIMESLOT_LABEL, WEEKDAYS,
    apply_filters, page_header, require_data, scope_phrase, sidebar_filters,
    with_parking,
)

df = require_data()
f = sidebar_filters(df)
d = apply_filters(df, f)

page_header(
    "🅿️ 어디로 언제 갈까 — 서울 공영주차 여유도",
    "생활인구(방문객 포함 체류인구) 대비 공영주차 공급을 요일·시간대별로 봅니다. "
    "※ 실시간 빈자리가 아니라 8주 평균 패턴입니다.",
)

if d.empty:
    st.warning("선택한 조건에 해당하는 행정동이 없습니다. 조건을 바꿔보세요.")
    st.stop()

# ── 비교 기준: 같은 시점의 서울 전체 ───────────────────────────────
base = apply_filters(df, f, apply_gu=False)

pop_sel, pop_all = d["living_pop"].mean(), base["living_pop"].mean()
slot_sel, slot_all = d["slots_per_1k"].median(), base["slots_per_1k"].median()
young_sel, young_all = d["young_ratio"].mean(), base["young_ratio"].mean()

st.markdown(f"#### {scope_phrase(f)}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("대상 행정동", f"{len(d):,}개",
          delta=None if f["gu"] == "전체" else f"서울 {len(base):,}개 중")
c2.metric("평균 생활인구", f"{pop_sel:,.0f}명",
          delta=f"{pop_sel - pop_all:+,.0f}명" if f["gu"] != "전체" else None,
          help="선택 조건 행정동의 평균 체류인구")
c3.metric("공영주차 여유도", f"{slot_sel:.1f}",
          delta=f"{slot_sel - slot_all:+.1f}" if f["gu"] != "전체" else None,
          help="1,000명당 공영주차면수(중앙값). 높을수록 여유")
c4.metric("20~30대 비중", f"{young_sel*100:.1f}%",
          delta=f"{(young_sel - young_all)*100:+.1f}%p" if f["gu"] != "전체" else None)

if f["gu"] == "전체":
    st.caption("자치구를 선택하면 서울 전체 대비 증감이 표시됩니다.")

st.divider()

# ── 시간대별 생활인구 ────────────────────────────────────────────
st.subheader("시간대별 생활인구")

# 생활인구는 주차장 유무와 무관한 지표라 0면 동도 그대로 쓴다
line_src = df[df["weekday"] == f["weekday"]]
if f["gu"] != "전체":
    line_src = line_src[line_src["sgg_nm"] == f["gu"]]
seoul_line = df[df["weekday"] == f["weekday"]]

cur = line_src.groupby("timeslot", observed=True)["living_pop"].mean().reindex(TIMESLOTS)
ref = seoul_line.groupby("timeslot", observed=True)["living_pop"].mean().reindex(TIMESLOTS)
# 시간대 '전체'는 이 차트의 가로축에 대응하는 칸이 없다 (축이 곧 시간대다).
# 이때는 강조 띠를 그리지 않는다 — 다섯 칸 전부가 선택된 셈이라 강조가 무의미하다.
sel_i = TIMESLOTS.index(f["timeslot"]) if f["timeslot"] in TIMESLOTS else None

fig = go.Figure()
# 자치구가 '전체'면 두 선의 값이 같아 파란 선이 회색 점선을 덮는다.
# 비교 기준선은 특정 자치구를 골랐을 때만 그린다.
if f["gu"] != "전체":
    fig.add_trace(go.Scatter(x=TIMESLOTS, y=ref, name="서울 전체",
                             mode="lines+markers", line=dict(color=INK["axis"], dash="dash")))
# 범례는 문장이 아니라 짧은 이름이라야 해서 리드 문장과 따로 만든다
scope_label = "서울 전체" if f["gu"] == "전체" else f["gu"]
fig.add_trace(go.Scatter(x=TIMESLOTS, y=cur, name=scope_label,
                         mode="lines+markers", line=dict(color=ACCENT, width=3)))
# 선택 시간대는 옅은 띠로만 표시한다
if sel_i is not None:
    fig.add_vrect(x0=sel_i - 0.45, x1=sel_i + 0.45,
                  fillcolor=ACCENT_LIGHT, opacity=0.35, line_width=0, layer="below")
fig.update_layout(height=400, margin=dict(t=10, b=10),
                  yaxis_title="평균 생활인구(명)", xaxis_title=None,
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, use_container_width=True)

band = (f"**옅은 배경**이 선택한 시간대({f['timeslot']})입니다. " if sel_i is not None
        else f"시간대를 **전체**로 두어 {len(TIMESLOTS)}개 시간대를 강조 없이 함께 봅니다. ")
if f["gu"] == "전체":
    st.caption("**파란 선**이 서울 전체 평균입니다. " + band
               + "사이드바에서 자치구를 고르면 서울 평균과 비교하는 회색 점선이 함께 나옵니다.")
else:
    st.caption(f"**파란 선**이 {f['gu']}, **회색 점선**이 서울 전체입니다. " + band)

# ── 자치구별 여유도 ─────────────────────────────────────────────
st.subheader("자치구별 공영주차 여유도")

# 중앙값은 0면 동을 빼고 낸다 (넣으면 5.22, 빼면 6.49로 분포가 눌린다)
gu_med = (with_parking(base).groupby("sgg_nm", observed=True)
          .agg(여유도=("slots_per_1k", "median"), 동수=("admi_nm", "size"))
          .reset_index())
gu_med["순위"] = gu_med["여유도"].rank(ascending=False).astype(int)

# 25개를 항상 다 그린다.
# 전에는 상위 10개만 보이고 '전체 보기' 토글을 아래에 뒀는데 세 가지가 어긋났다.
#   ① 토글은 켜고 끄는 '상태'를 뜻하는데 이건 '몇 개를 볼까'라는 범위 선택이었다
#   ② 컨트롤이 차트 아래라 누른 뒤 위를 다시 봐야 했다
#   ③ 이 차트의 목적은 '내 자치구가 어디쯤인가'인데, 상위 10 밖이면 클릭해야 보였다
# 서울 자치구는 25개로 고정이라 자를 만큼 많지 않다. 막대 높이를 줄여 한눈에 담는다.
plot_gu = gu_med.sort_values("여유도")   # 가로 막대는 큰 값이 위로 가도록

fig2 = px.bar(plot_gu, x="여유도", y="sgg_nm", orientation="h",
              color="여유도", color_continuous_scale=SCALE_SUPPLY,
              hover_data={"동수": True, "순위": True}, text="여유도")
fig2.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)

# 25개를 다 그리므로 선택한 자치구는 항상 화면에 있다
if f["gu"] != "전체":
    fig2.add_annotation(x=plot_gu.loc[plot_gu["sgg_nm"] == f["gu"], "여유도"].iloc[0],
                        y=f["gu"], text="◀ 선택", showarrow=False,
                        xanchor="left", xshift=42,
                        font=dict(size=13, color=ACCENT))

# 막대 수에 비례해 높이를 잡는다. 부족하면 Plotly가 축 라벨을 솎아낸다.
fig2.update_layout(height=max(340, 22 * len(plot_gu)), margin=dict(t=10, b=10, r=60),
                   xaxis_title="1,000명당 공영주차면(중앙값)", yaxis_title=None,
                   coloraxis_showscale=False)
fig2.update_yaxes(tickmode="linear", dtick=1, tickfont=dict(size=12))
st.plotly_chart(fig2, use_container_width=True)

caption = f"자치구 {len(gu_med)}개 전체. 막대가 길수록 사람 대비 공영주차장이 넉넉합니다."
if f["gu"] != "전체":
    rank = int(gu_med.loc[gu_med["sgg_nm"] == f["gu"], "순위"].iloc[0])
    caption += f" **{f['gu']}**는 {len(gu_med)}개 중 **{rank}위**입니다."
st.caption(caption)

st.divider()

# ── 동네 순위 ───────────────────────────────────────────────────
st.subheader("이 조건에서 주차가 넉넉한 / 빠듯한 동네")

cols = ["sgg_nm", "admi_nm", "living_pop", "slots_per_1k", "parking_slots", "store_food"]
names = {"sgg_nm": "자치구", "admi_nm": "행정동", "living_pop": "생활인구",
         "slots_per_1k": "천명당주차면", "parking_slots": "공영주차면", "store_food": "음식점수"}
fmt = {"생활인구": "{:,.0f}", "천명당주차면": "{:.1f}", "공영주차면": "{:,.0f}", "음식점수": "{:,.0f}"}

# 순위는 0면 동을 빼고 낸다. 넣으면 '빠듯 TOP 10'이 10개 모두 0면 동이라 순위가 안 된다.
# 대신 0면 동은 아래에 따로 세어 보여 준다 — 숨기는 게 아니라 분리하는 것.
ranked = with_parking(d)
zero_n = len(d) - len(ranked)

t1, t2 = st.columns(2)
with t1:
    st.markdown("**여유 TOP 10**")
    st.dataframe(ranked.nlargest(10, "slots_per_1k")[cols].rename(columns=names)
                 .style.format(fmt), use_container_width=True, hide_index=True,
                 height="content")
with t2:
    st.markdown("**빠듯 TOP 10**")
    st.dataframe(ranked.nsmallest(10, "slots_per_1k")[cols].rename(columns=names)
                 .style.format(fmt), use_container_width=True, hide_index=True,
                 height="content")

if zero_n:
    # 안내는 나들이객이 볼 수 있는 화면만 가리킨다. '공급 상태 구분'은 정책 담당자
    # 지도에만 있어서, 이 페이지에서 그쪽을 가리키면 끊어진 링크가 된다.
    st.warning(
        f"위 순위에는 **공영주차장이 아예 없는 {zero_n}개 동**이 빠져 있습니다 — "
        "넣으면 '빠듯 TOP 10'이 전부 0면 동이라 순위가 되지 않습니다. "
        "차로 가신다면 민영주차장을 찾아야 하는 동네입니다. "
        "🗺️ **지도**에서 **공영주차 여유도**를 고르면 이 동네들이 값 0으로 표시됩니다.",
        icon="⚠️",
    )

st.info(
    "**천명당주차면**은 그 시간대에 그 동네에 있는 사람 1,000명당 공영주차면 수입니다.  \n"
    "주차면은 고정이고 사람 수가 시간에 따라 변하므로, **같은 동네도 시간대에 따라 값이 달라집니다.**",
    icon="💡",
)
