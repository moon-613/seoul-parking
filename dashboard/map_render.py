"""지도 렌더링 공용 모듈 — 나들이용 지도와 정책용 지도가 함께 쓴다.

원래 views/map.py 한 파일에 지표 10개가 모두 들어 있었다. 그런데 사이드바는
app.py에서 이미 '나들이 계획'과 '주차 정책'으로 나뉘어 있어서, 나들이 그룹에
있는 지도가 정책 지표까지 품고 있는 구조 불일치가 있었다.

그림 그리는 코드를 여기로 옮기고, 페이지 파일은 '어떤 지표를 누구에게
보여줄지'만 정한다. 지도 로직이 한 곳에만 있으므로 페이지를 나눠도 갈라지지 않는다.
"""
import plotly.express as px
import streamlit as st

from common import (
    ALL_TIMESLOT, SCALE_DEMAND, SCALE_DIV, SCALE_SEQ, SCALE_SUPPLY, STATE_COLOR,
    TIMESLOTS, WEEKDAYS, apply_filters, load_boundary, page_header,
    require_analysis, require_data, sidebar_filters, when_phrase, with_parking,
)

TRIP, POLICY = "🧭 나들이", "🏗️ 정책"

# 정적 지표의 산출 기준 시점. 정책 지도는 요일·시간대를 묻지 않으므로
# 어느 시점의 패널을 깔지 여기서 못박는다 (회귀 기준과 같은 토요일 오후).
BASIS_WEEKDAY = "토" if "토" in WEEKDAYS else WEEKDAYS[0]
BASIS_TIMESLOT = "오후" if "오후" in TIMESLOTS else TIMESLOTS[0]

# 지표 정의 — source가 None이면 패널에 이미 있는 컬럼, 아니면 분석 산출물에서 붙인다.
# static=True는 시간에 따라 변하지 않아 '편차 모드'를 쓸 수 없는 지표.
# group은 이 지표가 누구를 위한 것인지 — 페이지를 나누는 기준이자 라벨 접두사다.
METRICS = {
    # ── 주 사용자 (나들이) ─────────────────────────────────
    "공영주차 여유도 (천명당 주차면)": dict(col="slots_per_1k", scale=SCALE_SUPPLY, group=TRIP,
                                  hint="높을수록 여유", source=None, static=False),
    "혼잡도 (생활인구)": dict(col="living_pop", scale=SCALE_DEMAND, group=TRIP,
                        hint="높을수록 붐빔", source=None, static=False),
    "나들이 적합도 (PCA 지수)": dict(col="나들이적합도", scale=SCALE_SEQ, group=TRIP,
                             hint="놀거리와 주차를 함께 갖춘 정도", source="suitability", static=True),
    "20~30대 비중": dict(col="young_ratio", scale=SCALE_DEMAND, group=TRIP,
                      hint="젊은층이 몰리는 정도", source=None, static=False),
    "음식점 수": dict(col="store_food", scale=SCALE_DEMAND, group=TRIP,
                   hint="놀거리 밀집도", source=None, static=True),
    # ── 부 사용자 (확충 진단) ──────────────────────────────
    "실수요 대비 공급 (비아파트 100가구당 주차면)": dict(
        col="slots_per_100_nonapt", scale=SCALE_SEQ, group=POLICY,
        hint="낮을수록 실거주 가구에 비해 공영주차가 적음", source=None, static=True),
    "공급 상태 구분": dict(col="공급상태", scale=None, group=POLICY,
                     hint="확충 후보 · 불필요(아파트 밀집) · 0면",
                     source="real_demand", static=True, categorical=True),
    "공급 과부족 (생활인구 보정)": dict(col="z_residual", scale=SCALE_DIV, midpoint=0, group=POLICY,
                             hint="음수=같은 인구 규모 동네들의 평균보다 적음",
                             source="residual", static=True),
    "아파트 거주 비율": dict(col="apt_ratio", scale=SCALE_SEQ, group=POLICY,
                       hint="높을수록 부설주차장이 실수요를 흡수", source=None, static=True),
    "비아파트 가구 (공영주차 실수요)": dict(col="non_apt_households", scale=SCALE_DEMAND, group=POLICY,
                                hint="공영주차에 의존하는 가구 수", source=None, static=True),
}

TRIP_METRICS = {k: v for k, v in METRICS.items() if v["group"] == TRIP}
POLICY_METRICS = {k: v for k, v in METRICS.items() if v["group"] == POLICY}

LABELS = {"slots_per_1k": "천명당주차면", "living_pop": "생활인구",
          "parking_slots": "공영주차면", "store_food": "음식점수",
          "sgg_nm": "자치구", "z_residual": "공급 과부족", "slots_per_100_nonapt": "100가구당주차면",
          "young_ratio": "20~30대비중", "apt_ratio": "아파트비율",
          "non_apt_households": "비아파트가구", "나들이적합도": "적합도",
          "deviation": "동네평균대비(%)", "dong_mean": "동네평균", "공급상태": "상태"}


def render_map(metrics: dict, *, title: str, lead: str,
               time_aware: bool = True, group_labels: bool = False) -> None:
    """지도 페이지 한 장을 통째로 그린다.

    metrics       이 페이지가 보여줄 지표만 담은 dict (METRICS의 부분집합)
    time_aware    False면 요일·시간대를 묻지 않는다. 정적 지표만 있는 페이지용 —
                  사이드바 요일·시간대와 '표시 방식' 라디오가 통째로 사라진다.
    group_labels  드롭다운 항목 앞에 '🧭 나들이 ·' 같은 접두사를 붙인다.
                  한 페이지에 두 사용자의 지표가 섞여 있을 때만 의미가 있다.
    """
    df = require_data()
    if time_aware:
        f = sidebar_filters(df)
    else:
        # 자치구는 아래 상세 표에 쓰지만 요일·시간대는 이 페이지에서 의미가 없다
        f = sidebar_filters(df, need=("gu",))
        f["weekday"], f["timeslot"] = BASIS_WEEKDAY, BASIS_TIMESLOT
    d = apply_filters(df, f, apply_gu=False)   # 지도는 항상 서울 전체를 그린다
    boundary = load_boundary()

    page_header(title, lead)

    if not boundary:
        st.error("행정동 경계 파일이 없습니다.")
        st.code(".\\.venv\\Scripts\\python.exe -m src.collect.fetch_dong_boundary")
        st.stop()

    @st.fragment
    def _body() -> None:
        """지표·표시 방식·불투명도를 바꿀 때 이 블록만 다시 그린다.

        전에는 이 위젯들이 페이지 전체 rerun을 일으켰고, Streamlit은 전체 rerun
        마다 스크롤을 맨 위로 되돌린다. 지도를 내려다보며 지표를 바꾸면 화면이
        위로 튀어 방금 보던 곳을 다시 찾아 내려가야 했다.
        프래그먼트로 묶으면 이 안의 위젯은 이 함수만 재실행하므로 보던 위치가 그대로 남는다.

        사이드바(요일·시간대·자치구)는 지도 밖의 문구까지 바꾸므로 여기 넣지 않는다 —
        그쪽은 전체 rerun이 맞다.
        """
        if time_aware:
            c1, c2, c3 = st.columns([2, 2, 1])
        else:
            c1, c3 = st.columns([4, 1])

        metric_name = c1.selectbox(
            "지도에 표시할 값", list(metrics),
            format_func=(lambda n: f'{metrics[n]["group"]} · {n}') if group_labels else str,
        )
        spec = metrics[metric_name]
        col, scale, hint = spec["col"], spec["scale"], spec["hint"]
        source, is_static = spec["source"], spec["static"]
        is_categorical = spec.get("categorical", False)

        if time_aware:
            # 시간대가 '전체'면 비교 대상이 시간대가 아니라 요일이 된다.
            # 라디오 값은 "deviation"으로 고정하고 보이는 글자만 바꾼다 —
            # 선택지 문자열 자체를 바꾸면 조건을 옮길 때마다 선택이 풀린다.
            dev_label = ("이 요일의 편차" if f["timeslot"] == ALL_TIMESLOT
                         else "이 시간대의 편차")
            mode = c2.radio(
                "표시 방식", ["절대값", "deviation"], horizontal=True,
                format_func=lambda m: dev_label if m == "deviation" else m,
                help="절대값은 '어디가 여유로운가', 편차는 '이 동네에서 지금이 좋은 때인가'를 보여줍니다. "
                     "동네 간 순위는 시간대가 바뀌어도 거의 그대로라, 절대값 지도는 조건을 바꿔도 비슷해 보입니다.",
                disabled=is_static,
            )
            deviation = (mode == "deviation") and not is_static
        else:
            deviation = False
        opacity = c3.slider("불투명도", 0.3, 1.0, 0.75, 0.05)

        # 지도 위쪽에 글을 끼워 넣으면 지표를 바꿀 때마다 지도가 아래위로 밀린다.
        # (적합도를 고르면 '※ 정적 지표' 안내가 새로 생기면서 화면이 통째로 움직였다)
        # 그래서 안내문은 여기서 변수에만 담아 두고, 그리는 것은 지도 아래에서 한다.
        # 컨트롤 줄과 지도 사이에는 이제 아무것도 들어가지 않으므로 지도의 화면상
        # 위치가 지표와 무관하게 고정된다.
        static_note = warn_note = ""

        # 분석 산출물이 필요한 지표는 여기서 붙인다 (모두 시간과 무관한 정적 지표)
        plot_df = d
        if source:
            extra = require_analysis(source)
            if source == "real_demand":
                extra = extra.copy()
                # 지도용 단일 상태 컬럼. 뒤에 오는 조건이 앞을 덮는다.
                # '확충 불필요'를 맨 마지막에 두는 이유: 0면이면서 실수요도 없는 동이 4개 있는데
                # (잠실2동·가락1동·하계2동·둔촌1동) 이들을 '0면'으로 칠하면 가장 시급한 색이 되어
                # 정반대 신호를 준다. 지을 필요가 없다는 사실이 0면이라는 사실보다 우선한다.
                extra["공급상태"] = "보통"
                extra.loc[extra.판정_정주 == "공급부족", "공급상태"] = "확충 후보"
                extra.loc[extra.parking_slots == 0, "공급상태"] = "공영주차 0면"
                extra.loc[extra.확충필요성 == "불필요", "공급상태"] = "확충 불필요"
                cols = ["admi_cd", "공급상태"]
            elif source == "suitability":
                cols = ["admi_cd", "나들이적합도", "매력도지수_pct", "주차여유지수_pct"]
            else:
                cols = ["admi_cd", "z_residual", "expected_slots", "grade"]
            plot_df = d.merge(extra[cols], on="admi_cd", how="inner")
            # 정책 지도는 지표가 전부 정적이라 이 안내를 페이지 머리말에서 한 번만 한다
            if time_aware:
                static_note = ("※ 이 지표는 요일·시간대에 따라 변하지 않습니다. "
                               "회귀 기준 시점(토요일 오후)으로 산출한 값이며, 시점을 바꿔도 "
                               "동네 간 순위상관이 0.99 이상이라 결과가 거의 같습니다.")

        if col == "z_residual":
            warn_note = (
                "**이 지표를 그대로 '수요 대비 부족'으로 읽지 마세요.** 생활인구로 기대 공급을 "
                "보정하려 했으나 설명력이 R²=0.068로 낮아 보정이 거의 일어나지 않습니다. "
                "그 결과 이 값의 순위는 **공영주차면 수 자체의 순위와 0.96까지 일치**합니다. "
                "실거주 수요 대비 부족은 위의 **비아파트 100가구당 주차면**으로 보세요."
            )

        plot_df = plot_df.dropna(subset=[col]).copy()
        if plot_df.empty:
            st.warning("표시할 값이 없습니다.")
            return

        # ── 편차 모드: 그 동네의 전체 시간대 평균 대비 몇 %인지 ────────────
        if deviation:
            # 편차는 그 동네 평균 대비 비율이라 분모가 0이면 계산되지 않는다
            src = with_parking(df)
            dong_mean = src.groupby("adm_cd", observed=True)[col].mean().rename("dong_mean")
            plot_df = plot_df.merge(dong_mean, on="adm_cd", how="left")
            plot_df["deviation"] = (plot_df[col] / plot_df["dong_mean"] - 1) * 100
            plot_df = plot_df[plot_df["dong_mean"] > 0]

            color_col = "deviation"
            color_scale = SCALE_DIV
            midpoint = 0
            # 극단값이 색을 독점하지 않도록 상하위 5%로 범위를 자른다
            lim = max(abs(plot_df.deviation.quantile(0.05)), abs(plot_df.deviation.quantile(0.95)))
            color_range = (-lim, lim)
        else:
            color_col, color_scale = col, scale
            midpoint, color_range = spec.get("midpoint"), None

        hover = {
            "sgg_nm": True, "living_pop": ":,.0f", "parking_slots": ":,.0f",
            "slots_per_1k": ":.1f", "store_food": ":,.0f", "adm_cd": False,
        }
        for extra_col, fmt in [("z_residual", ":.2f"), ("나들이적합도", ":.1f"),
                               ("apt_ratio", ":.1%"), ("non_apt_households", ":,.0f"),
                               ("slots_per_100_nonapt", ":.2f")]:
            if extra_col in plot_df.columns and extra_col != col:
                hover[extra_col] = fmt
        if deviation:
            hover["deviation"] = ":+.0f"
            hover["dong_mean"] = ":.1f"

        common_kw = dict(
            geojson=boundary, locations="adm_cd", featureidkey="properties.adm_cd",
            hover_name="admi_nm", hover_data=hover,
            center={"lat": 37.5665, "lon": 126.978}, zoom=10.2,
            opacity=opacity, map_style="carto-positron", labels=LABELS,
        )

        if is_categorical:
            fig = px.choropleth_map(
                plot_df, color=color_col,
                color_discrete_map=STATE_COLOR,
                category_orders={col: list(STATE_COLOR)},
                **common_kw,
            )
            # 범주형은 컬러바 대신 범례가 그려진다. 지표를 바꿔도 색 설명이 같은 자리에
            # 있도록 연속형 컬러바와 같은 오른쪽 세로로 맞춘다.
            fig.update_layout(legend=dict(
                orientation="v", yanchor="top", y=1, xanchor="left", x=1.01, title=None,
            ))
        else:
            fig = px.choropleth_map(
                plot_df, color=color_col,
                color_continuous_scale=color_scale,
                color_continuous_midpoint=midpoint,
                range_color=color_range,
                **common_kw,
            )
        fig.update_layout(height=640, margin=dict(r=0, t=0, l=0, b=0))
        # key를 주면 지표를 바꿔도 같은 차트 컴포넌트를 다시 쓴다. key가 없으면
        # 새 컴포넌트로 갈아끼워지면서 높이가 잠깐 0이 되고, 그 순간 브라우저가
        # 스크롤을 위로 당긴다.
        st.plotly_chart(fig, use_container_width=True, key="map_chart")

        # 위에서 미뤄 둔 안내문 — 지도 아래에 그린다
        if warn_note:
            st.warning(warn_note, icon="⚠️")
        if static_note:
            st.caption(static_note)

        if deviation:
            st.caption(
                f"**{metric_name} — {dev_label}** · {when_phrase(f)}  \n"
                f"각 행정동의 **전체 요일·시간대 평균({len(WEEKDAYS) * len(TIMESLOTS)}개)을 100으로 놓고** "
                "지금이 몇 % 인지 표시합니다. "
                "**파란색 = 평소보다 여유, 빨간색 = 평소보다 빠듯.** 요일·시간대를 바꾸면 지도가 크게 달라집니다."
            )
            top = plot_df.nlargest(3, "deviation")
            bot = plot_df.nsmallest(3, "deviation")
            m1, m2 = st.columns(2)
            m1.success("**평소보다 여유** — " + ", ".join(
                f"{r.admi_nm} {r.deviation:+.0f}%" for r in top.itertuples()))
            m2.error("**평소보다 빠듯** — " + ", ".join(
                f"{r.admi_nm} {r.deviation:+.0f}%" for r in bot.itertuples()))
        elif time_aware:
            st.caption(f"**{metric_name}** — {hint} · 기준: {when_phrase(f)}")
            if not is_static:
                st.caption("💡 동네 간 순위는 시간대가 바뀌어도 거의 그대로라 이 지도는 조건을 바꿔도 비슷해 보입니다. "
                           f"시간대별 차이를 보려면 위에서 **‘{dev_label}’** 를 선택하세요.")
        else:
            st.caption(f"**{metric_name}** — {hint}")

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

        # 0면 동을 어디서 확인하라고 할지는 페이지마다 다르다. 이 페이지에 없는 지표를
        # 가리키면 끊어진 링크가 되므로, 각자 가진 지표 안에서만 안내한다.
        if any(m["col"] == "공급상태" for m in metrics.values()):
            where = "**공급 상태 구분**을 고르면 별도 색으로 구분됩니다."
        else:
            where = "**공영주차 여유도**를 고르면 값 0으로 표시됩니다."
        st.caption("공영주차가 0면인 행정동도 지도에서 빠지지 않습니다. " + where)

    _body()
