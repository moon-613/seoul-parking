"""확충 우선순위 페이지 — 부 사용자(자치구 주차 정책 담당자) 전용.

다른 페이지와 달리 요일·시간대 필터를 쓰지 않는다.
공영주차 확충은 '언제'가 아니라 '어디에'의 문제이고, 정주수요(비아파트 가구)는
시간에 따라 변하지 않기 때문이다. 사이드바 대신 자치구 선택만 둔다.

여기서 보여 주는 것
  ① 자치구 순위 — 실수요 100가구당 공영주차면 (규모를 나눠야 구끼리 비교된다)
  ② 확충 후보   — 정주수요 기준 공급부족 행정동
  ③ 판정 오류   — 생활인구만 보면 잘못 지목되는 곳 (예산이 잘못 갈 뻔한 지점)
  ④ 확충 불필요 — 비아파트 100가구 미만. 예산 배분에서 빼야 할 곳
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from common import ACCENT, ALERT, SCALE_SEQ, page_header, require_analysis, require_data

require_data()
rd = require_analysis("real_demand")
# 순위는 잔차가 아니라 직접 지표로 낸다.
# 잔차는 생활인구/비아파트 가구로 기대 공급을 보정한 값인데 설명력이 R²=0.004로 낮아
# 보정이 거의 일어나지 않는다(잔차 순위 ↔ 주차면수 순위 상관 0.997).
# 담당자에게는 "6,838가구에 1면"처럼 바로 읽히는 값이 정확하다.
rd = rd.merge(
    require_data()[["admi_cd", "slots_per_100_nonapt"]].drop_duplicates(),
    on="admi_cd", how="left")
sgg = require_analysis("sgg")

page_header(
    "🏗️ 공영주차장 확충 우선순위",
    "자치구 주차 정책 담당자용. **아파트를 제외한 실거주 가구**를 기준으로 "
    "확충이 필요한 곳과 필요 없는 곳을 구분합니다.",
)

st.info(
    "**왜 아파트를 빼나요?** 아파트는 부설주차장이 있어 공영주차 실수요가 낮습니다. "
    "생활인구만으로 대상지를 고르면 아파트 단지를 확충 대상으로 잘못 지목하게 됩니다.",
    icon="💡",
)

# ── 자치구 선택 ────────────────────────────────────────────────
gu_list = ["서울 전체"] + sorted(sgg["자치구"].tolist())
sel = st.selectbox("자치구", gu_list, index=0,
                   help="특정 구를 고르면 그 구의 행정동만 봅니다.")
scope = rd if sel == "서울 전체" else rd[rd.sgg_nm == sel]

# ── KPI ────────────────────────────────────────────────────────
cand = scope[scope.판정_정주 == "공급부족"]
skip = scope[scope.확충필요성 == "불필요"]
zero = scope[scope.parking_slots == 0]

k1, k2, k3, k4 = st.columns(4)
k1.metric("확충 후보", f"{len(cand)}개 동", help="정주수요 기준 공급부족 (표준화 잔차 ≤ -1)")
k2.metric("확충 불필요", f"{len(skip)}개 동", help="비아파트 100가구 미만 — 실수요가 사실상 없음")
k3.metric("공영주차 0면", f"{len(zero)}개 동")
k4.metric("대상 행정동", f"{len(scope)}개")

st.divider()

# ── ① 자치구 순위 ──────────────────────────────────────────────
st.subheader("① 자치구별 실수요 대비 공급")
st.caption("합계는 큰 구가 자동으로 상위에 오므로 **실수요 100가구당 주차면**으로 비교합니다.")

s = sgg.sort_values("실수요100가구당")
med = s["실수요100가구당"].median()
s = s.assign(구분=lambda x: x["실수요100가구당"].lt(med).map({True: "중앙값 미만", False: "중앙값 이상"}))

fig = px.bar(
    s, x="실수요100가구당", y="자치구", orientation="h", color="구분",
    color_discrete_map={"중앙값 미만": ALERT, "중앙값 이상": ACCENT},
    hover_data={"비아파트가구": ":,.0f", "공영주차면": ":,.0f",
                "확충후보": True, "확충불필요": True, "구분": False},
    labels={"실수요100가구당": "실수요 100가구당 공영주차면"},
)
fig.add_vline(x=med, line_dash="dash", line_color="#333",
              annotation_text=f"서울 중앙값 {med:.1f}", annotation_position="top")
if sel != "서울 전체":
    fig.add_annotation(x=s.loc[s.자치구 == sel, "실수요100가구당"].iloc[0], y=sel,
                       text="◀ 선택", showarrow=False, xanchor="left", font=dict(size=12))
fig.update_layout(height=620, margin=dict(t=30, b=10),
                  legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── ② 확충 후보 ────────────────────────────────────────────────
st.subheader(f"② 확충 후보 — {len(cand)}개 동")
if cand.empty:
    st.success(f"{sel}에는 정주수요 기준 공급부족 행정동이 없습니다.")
else:
    c1, c2 = st.columns([3, 2])
    with c1:
        top = cand.nsmallest(15, "slots_per_100_nonapt").sort_values(
            "slots_per_100_nonapt", ascending=False)
        figc = px.bar(
            top, x="non_apt_households", y="admi_nm", orientation="h",
            color="slots_per_100_nonapt", color_continuous_scale=SCALE_SEQ[::-1],
            hover_data={"sgg_nm": True, "parking_slots": ":,.0f",
                        "apt_ratio": ":.1%", "slots_per_100_nonapt": ":.2f"},
            labels={"non_apt_households": "비아파트 가구 수 (공영주차 실수요)",
                    "admi_nm": "", "slots_per_100_nonapt": "100가구당 주차면"},
        )
        figc.update_layout(height=520, margin=dict(t=20, b=10), coloraxis_showscale=False)
        st.plotly_chart(figc, use_container_width=True)
        st.caption("색이 진할수록 가구 수 대비 주차면이 적습니다. 막대 길이는 실수요 규모입니다.")
    with c2:
        show = cand.nsmallest(15, "slots_per_100_nonapt")[
            ["sgg_nm", "admi_nm", "non_apt_households", "parking_slots",
             "slots_per_100_nonapt", "apt_ratio"]]
        st.dataframe(
            show.rename(columns={"sgg_nm": "자치구", "admi_nm": "행정동",
                                 "non_apt_households": "비아파트가구",
                                 "parking_slots": "주차면",
                                 "slots_per_100_nonapt": "100가구당",
                                 "apt_ratio": "아파트비율"}).style.format(
                {"비아파트가구": "{:,.0f}", "주차면": "{:,.0f}",
                 "100가구당": "{:.2f}", "아파트비율": "{:.1%}"}),
            use_container_width=True, hide_index=True, height=520,
        )

st.divider()

# ── ③ 판정 오류 ────────────────────────────────────────────────
st.subheader("③ 생활인구만 보면 생기는 판정 오류")
st.caption("두 기준이 갈리는 곳입니다. **원인이 둘이라 정책 대응이 정반대**입니다.")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**🔻 확충 우선순위를 내려야 할 곳**")
    # 아파트가 실수요를 흡수한 두 경우를 합친다
    #   ① 검토대상이지만 정주 기준으로는 부족이 아닌 곳
    #   ② 애초에 확충 불필요인데 생활인구 기준으로는 부족으로 잡힌 곳
    fp = scope[scope.구분 == "유동만 부족(아파트 흡수형)"]
    fp_skip = scope[(scope.확충필요성 == "불필요") & (scope.판정_유동 == "공급부족")]
    merged = pd.concat([fp, fp_skip]).drop_duplicates(subset="admi_cd")
    if merged.empty:
        st.caption("해당 없음")
    else:
        st.dataframe(
            merged[["sgg_nm", "admi_nm", "non_apt_households", "apt_ratio", "parking_slots"]]
            .rename(columns={"sgg_nm": "자치구", "admi_nm": "행정동",
                             "non_apt_households": "비아파트가구",
                             "apt_ratio": "아파트비율", "parking_slots": "주차면"})
            .style.format({"비아파트가구": "{:,.0f}", "아파트비율": "{:.1%}", "주차면": "{:,.0f}"}),
            use_container_width=True, hide_index=True,
        )
        st.caption("생활인구로는 부족해 보이지만 **부설주차장이 실수요를 흡수**한 곳입니다.")

with col_b:
    st.markdown("**⏱ 거주자우선이 아닌 시간제로 풀 곳**")
    visit = scope[scope.구분 == "유동만 부족(방문객 수요형)"]
    if visit.empty:
        st.caption("해당 없음")
    else:
        st.dataframe(
            visit[["sgg_nm", "admi_nm", "non_apt_households", "apt_ratio", "parking_slots"]]
            .rename(columns={"sgg_nm": "자치구", "admi_nm": "행정동",
                             "non_apt_households": "비아파트가구",
                             "apt_ratio": "아파트비율", "parking_slots": "주차면"})
            .style.format({"비아파트가구": "{:,.0f}", "아파트비율": "{:.1%}", "주차면": "{:,.0f}"}),
            use_container_width=True, hide_index=True,
        )
        st.caption("아파트가 적은데도 생활인구 기준으로만 부족한 곳 — "
                   "**거주민보다 방문객 수요**가 큽니다.")

new_cand = scope[scope.구분 == "정주만 부족(누락)"]
if not new_cand.empty:
    st.markdown("**➕ 생활인구로는 놓쳤던 확충 후보**")
    st.dataframe(
        new_cand[["sgg_nm", "admi_nm", "non_apt_households", "parking_slots",
                  "slots_per_100_nonapt", "apt_ratio"]]
        .rename(columns={"sgg_nm": "자치구", "admi_nm": "행정동",
                         "non_apt_households": "비아파트가구", "parking_slots": "주차면",
                         "slots_per_100_nonapt": "100가구당", "apt_ratio": "아파트비율"})
        .style.format({"비아파트가구": "{:,.0f}", "주차면": "{:,.0f}",
                       "100가구당": "{:.2f}", "아파트비율": "{:.1%}"}),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ── ④ 확충 불필요 ──────────────────────────────────────────────
st.subheader(f"④ 확충 불필요 — {len(skip)}개 동")
if skip.empty:
    st.caption(f"{sel}에는 해당 동이 없습니다.")
else:
    st.warning(
        "비아파트 가구가 **100호 미만**이라 공영주차에 의존할 가구가 사실상 없습니다. "
        "예산 배분에서 제외하는 것이 맞습니다.",
        icon="⚠️",
    )
    st.dataframe(
        skip.sort_values("non_apt_households")[
            ["sgg_nm", "admi_nm", "households", "apartment", "non_apt_households", "parking_slots"]]
        .rename(columns={"sgg_nm": "자치구", "admi_nm": "행정동", "households": "일반가구",
                         "apartment": "아파트가구", "non_apt_households": "비아파트가구",
                         "parking_slots": "주차면"})
        .style.format({"일반가구": "{:,.0f}", "아파트가구": "{:,.0f}",
                       "비아파트가구": "{:,.0f}", "주차면": "{:,.0f}"}),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "임계값 100호 근거: 비아파트 가구를 정렬하면 40호와 101호 사이에 61호 격차가 있고, "
        "**41~100 어느 값을 잡아도 같은 동들이 분리**됩니다."
    )

st.divider()
st.caption(
    "정주수요 = 일반가구 − 아파트 가구 (인구주택총조사 2025). "
    "**순위는 '비아파트 100가구당 주차면'이라는 직접 지표로 냅니다.** "
    "확충 후보를 가려낸 기준(로그-로그 회귀의 표준화 잔차 ≤ −1)은 그대로지만, "
    "그 회귀의 설명력이 R² 0.004(유동수요 0.068)로 낮아 보정이 거의 일어나지 않습니다. "
    "**공영주차 배치가 어떤 수요 지표로도 설명되지 않는다**는 뜻이고, "
    "그래서 순위는 회귀를 거치지 않은 직접 지표로 제시하는 편이 정확합니다."
)
