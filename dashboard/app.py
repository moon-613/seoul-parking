"""탐색 페이지 — 선택한 요일·시간대의 공영주차 여유도와 혼잡도

실행: streamlit run dashboard/app.py
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (
    SCALE_SUPPLY, TIMESLOTS, TIMESLOT_LABEL, WEEKDAYS,
    apply_filters, page_header, require_data, scope_phrase, sidebar_filters,
)

st.set_page_config(page_title="서울 나들이 주차 대시보드", page_icon="🅿️", layout="wide")

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

line_src = df[df["weekday"] == f["weekday"]]
if f["gu"] != "전체":
    line_src = line_src[line_src["sgg_nm"] == f["gu"]]
if f["exclude_zero"]:
    line_src = line_src[line_src["has_parking"]]

seoul_line = df[df["weekday"] == f["weekday"]]
if f["exclude_zero"]:
    seoul_line = seoul_line[seoul_line["has_parking"]]

cur = line_src.groupby("timeslot", observed=True)["living_pop"].mean().reindex(TIMESLOTS)
ref = seoul_line.groupby("timeslot", observed=True)["living_pop"].mean().reindex(TIMESLOTS)
sel_i = TIMESLOTS.index(f["timeslot"])

fig = go.Figure()
# 자치구가 '전체'면 두 선의 값이 같아 빨간 선이 회색 점선을 덮는다.
# 비교 기준선은 특정 자치구를 골랐을 때만 그린다.
if f["gu"] != "전체":
    fig.add_trace(go.Scatter(x=TIMESLOTS, y=ref, name="서울 전체",
                             mode="lines+markers", line=dict(color="#B0B0B0", dash="dash")))
# 범례는 문장이 아니라 짧은 이름이라야 해서 리드 문장과 따로 만든다
scope_label = "서울 전체" if f["gu"] == "전체" else f["gu"]
fig.add_trace(go.Scatter(x=TIMESLOTS, y=cur, name=scope_label,
                         mode="lines+markers", line=dict(color="#D62728", width=3)))
# 선택 시간대는 노란 띠로만 표시한다
fig.add_vrect(x0=sel_i - 0.45, x1=sel_i + 0.45,
              fillcolor="#FFC107", opacity=0.30, line_width=0, layer="below")
fig.update_layout(height=400, margin=dict(t=10, b=10),
                  yaxis_title="평균 생활인구(명)", xaxis_title=None,
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, use_container_width=True)

if f["gu"] == "전체":
    st.caption(f"**빨간 선**이 서울 전체 평균입니다. **노란 배경**이 선택한 시간대({f['timeslot']})입니다. "
               "사이드바에서 자치구를 고르면 서울 평균과 비교하는 회색 점선이 함께 나옵니다.")
else:
    st.caption(f"**빨간 선**이 {f['gu']}, **회색 점선**이 서울 전체입니다. "
               f"**노란 배경**이 선택한 시간대({f['timeslot']})입니다.")

# ── 자치구별 여유도 ─────────────────────────────────────────────
st.subheader("자치구별 공영주차 여유도")

gu_med = (base.groupby("sgg_nm", observed=True)
          .agg(여유도=("slots_per_1k", "median"), 동수=("admi_nm", "size"))
          .reset_index())
gu_med["순위"] = gu_med["여유도"].rank(ascending=False).astype(int)

TOP_N = 10
show_all = st.session_state.get("gu_show_all", False)
plot_gu = gu_med if show_all else gu_med.nlargest(TOP_N, "여유도")
plot_gu = plot_gu.sort_values("여유도")   # 가로 막대는 큰 값이 위로 가도록

fig2 = px.bar(plot_gu, x="여유도", y="sgg_nm", orientation="h",
              color="여유도", color_continuous_scale=SCALE_SUPPLY,
              hover_data={"동수": True, "순위": True}, text="여유도")
fig2.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)

# 선택한 자치구가 화면에 있을 때만 표시 (상위 10 밖이면 아래 캡션으로 안내)
if f["gu"] != "전체" and f["gu"] in set(plot_gu["sgg_nm"]):
    fig2.add_annotation(x=plot_gu.loc[plot_gu["sgg_nm"] == f["gu"], "여유도"].iloc[0],
                        y=f["gu"], text="◀ 선택", showarrow=False,
                        xanchor="left", xshift=42,
                        font=dict(size=13, color="#D62728"))

# 막대 수에 비례해 높이를 잡는다. 부족하면 Plotly가 축 라벨을 솎아낸다.
fig2.update_layout(height=max(340, 28 * len(plot_gu)), margin=dict(t=10, b=10, r=60),
                   xaxis_title="1,000명당 공영주차면(중앙값)", yaxis_title=None,
                   coloraxis_showscale=False)
fig2.update_yaxes(tickmode="linear", dtick=1, tickfont=dict(size=12))
st.plotly_chart(fig2, use_container_width=True)

cap, btn = st.columns([3, 1])
with cap:
    if show_all:
        st.caption(f"자치구 {len(gu_med)}개 전체. 막대가 길수록 사람 대비 공영주차장이 넉넉합니다.")
    else:
        st.caption(f"여유도 상위 {TOP_N}개 자치구 (전체 {len(gu_med)}개). "
                   "막대가 길수록 사람 대비 공영주차장이 넉넉합니다.")
    if f["gu"] != "전체" and f["gu"] not in set(plot_gu["sgg_nm"]):
        rank = int(gu_med.loc[gu_med["sgg_nm"] == f["gu"], "순위"].iloc[0])
        st.caption(f"선택하신 **{f['gu']}**는 {len(gu_med)}개 중 **{rank}위**라 목록에 없습니다. "
                   "‘전체 보기’를 눌러 확인하세요.")
with btn:
    st.toggle("전체 보기", key="gu_show_all",
              help=f"상위 {TOP_N}개만 보여줍니다. 켜면 자치구 {len(gu_med)}개를 모두 표시합니다.")

st.divider()

# ── 동네 순위 ───────────────────────────────────────────────────
st.subheader("이 조건에서 주차가 넉넉한 / 빠듯한 동네")

cols = ["sgg_nm", "admi_nm", "living_pop", "slots_per_1k", "parking_slots", "store_food"]
names = {"sgg_nm": "자치구", "admi_nm": "행정동", "living_pop": "생활인구",
         "slots_per_1k": "천명당주차면", "parking_slots": "공영주차면", "store_food": "음식점수"}
fmt = {"생활인구": "{:,.0f}", "천명당주차면": "{:.1f}", "공영주차면": "{:,.0f}", "음식점수": "{:,.0f}"}

t1, t2 = st.columns(2)
with t1:
    st.markdown("**🟢 여유 TOP 10**")
    st.dataframe(d.nlargest(10, "slots_per_1k")[cols].rename(columns=names)
                 .style.format(fmt), use_container_width=True, hide_index=True)
with t2:
    st.markdown("**🔴 빠듯 TOP 10**")
    st.dataframe(d.nsmallest(10, "slots_per_1k")[cols].rename(columns=names)
                 .style.format(fmt), use_container_width=True, hide_index=True)

st.info(
    "**천명당주차면**은 그 시간대에 그 동네에 있는 사람 1,000명당 공영주차면 수입니다. "
    "주차면은 고정이고 사람 수가 시간에 따라 변하므로, **같은 동네도 시간대에 따라 값이 달라집니다.**",
    icon="💡",
)
