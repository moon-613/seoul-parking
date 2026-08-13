"""대시보드 공통 모듈 — 데이터 로딩, 사이드바 필터, 색상 규칙.

Streamlit 멀티페이지는 페이지마다 스크립트가 새로 실행되므로,
필터 선택값은 session_state에 저장해 페이지를 옮겨도 유지되게 한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# src 모듈은 위에서 sys.path를 잡은 뒤에야 임포트할 수 있다
from src.utils.timeslot import (  # noqa: E402
    get_recommend_exclude, get_timeslots, get_weekday_names, recommend_timeslots,
)

PROCESSED = ROOT / "data" / "processed"
PANEL_PATH = PROCESSED / "panel.csv"
BOUNDARY_PATH = ROOT / "data" / "external" / "dong_boundary.geojson"

# 정적 분석 산출물 — 대시보드에서 다시 계산하지 않고 그대로 읽는다.
# (필터를 바꿔도 값이 흔들리면 보고서 수치와 어긋나기 때문)
# 값은 (파일명, 재생성 스크립트). 없을 때 무엇을 돌려야 하는지 안내에 쓴다.
ANALYSIS_FILES = {
    "residual": ("dong_residual.csv", "residual"),          # 회귀 잔차·등급
    "real_demand": ("dong_real_demand.csv", "real_demand"),  # 실수요 진단
    "suitability": ("dong_suitability.csv", "suitability"),  # 나들이 적합도 지수
    "recommend": ("dong_recommend.csv", "recommend"),        # 추천/혼잡 등급
    "timeslot": ("dong_timeslot.csv", "timeslot_effect"),    # 동별 최적 시점
    "sgg": ("sgg_summary.csv", "district"),                  # 자치구 요약
}

# 요일·시간대 정의는 config/config.yaml 한 곳에서만 관리한다.
# 예전에는 여기에 값이 따로 박혀 있어 구간 설계를 바꾸면 대시보드가 어긋났다.
WEEKDAYS = get_weekday_names()
TIMESLOTS = [s["name"] for s in get_timeslots()]
TIMESLOT_LABEL = {s["name"]: f'{s["name"]} {s["label"]}' for s in get_timeslots()}

# 추천 후보에서 빠지는 시간대 (config.panel.recommend_exclude). 조회는 되지만
# '언제 가면 좋은가'의 답으로는 내밀지 않는다.
RECOMMEND_EXCLUDE = get_recommend_exclude()
RECOMMEND_TIMESLOTS = recommend_timeslots()

# 시간대 '전체' — 한 요일의 시간대를 모두 합쳐 본다.
# '하루 종일'이라고 쓰지 않는 이유: config가 심야(00~06시)를 분석 대상에서 빼고 있어
# 실제로는 6~24시다. 라벨에 구간을 박아 두어 오해를 막는다.
# 구간을 늘리거나 줄이면 이 값도 config를 따라 자동으로 바뀐다.
ALL_TIMESLOT = "전체"
DAY_SPAN = f'{get_timeslots()[0]["start"]}-{get_timeslots()[-1]["end"]}시'
TIMESLOT_LABEL[ALL_TIMESLOT] = f"{ALL_TIMESLOT} {DAY_SPAN}"
TIMESLOT_CHOICES = [ALL_TIMESLOT] + TIMESLOTS

# ── 색 팔레트 ─────────────────────────────────────────────────
# 회색·파랑을 바탕으로 두고 빨강은 경고에만 쓴다.
# 색은 '역할'로만 배정한다. 같은 색이 페이지마다 다른 뜻을 갖지 않도록 여기서만 정의한다.
#
# 역할이 셋뿐이다
#   크기(magnitude) -> 파랑 한 색상, 밝음→어두움          SCALE_SEQ
#   극성(polarity)  -> 빨강 ↔ 회색 ↔ 파랑                SCALE_DIV
#   상태(status)    -> 지도는 파랑 농도(진할수록 시급), 회색은 해당 없음   STATE_COLOR
#                      차트에서 한두 개를 짚어 경고할 때만 빨강            GRADE_COLOR
#
# 예전에는 RdYlGn(무지개 발산)·OrRd·Purples·Reds_r을 섞어 써서
# 한 화면에 빨강·노랑·초록·보라가 동시에 떴다. 무지개 발산은 중간값이
# 노란색이라 '기준선'으로 읽히지 않아 발산 인코딩으로 부적절하다.

INK = {
    "primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7", "surface": "#fcfcfb",
}

# 크기 — 값이 클수록 진하다. 의미의 좋고 나쁨은 범례가 말한다.
SCALE_SEQ = ["#eaf2fd", "#cde2fb", "#9ec5f4", "#6da7ec",
             "#3987e5", "#2a78d6", "#1c5cab", "#104281"]

# 극성 — 낮은 쪽(부족·빠듯) 빨강, 중간 회색, 높은 쪽(여유) 파랑.
# 중간을 회색으로 두어야 '기준선'이 눈에 잡힌다.
SCALE_DIV = [[0.0, "#8f1f1f"], [0.25, "#d03b3b"], [0.5, "#f0efec"],
             [0.75, "#5598e7"], [1.0, "#184f95"]]

ALERT = "#d03b3b"      # 조치가 필요한 것
ALERT_STRONG = "#8f1f1f"  # 더 시급한 것
NEUTRAL = "#898781"    # 해당 없음 / 조치 불필요
BACKDROP = "#dbe8f8"   # 조치 없음 (배경으로 물러남)
ACCENT = "#2a78d6"     # 주력 · 긍정
ACCENT_LIGHT = "#86b6ef"
ACCENT_DEEP = "#104281"   # 가장 진한 파랑 (SCALE_SEQ 끝) — 가장 시급한 것

# 공급 상태 (지도) — '보통'은 전경이 아니라 배경이라 팔레트 검증에서 제외했다
#
# 빨강 대신 파랑 농도로 시급도를 표현한다. 이 지도는 행정동 425개를 한 번에
# 칠하는데 확충 후보 52 + 0면 62 = 114개가 빨강이라 화면의 4분의 1이 경고색이
# 되어, 빨강이 '경고'가 아니라 그냥 '많은 색'으로 읽혔다. 다른 지도가 모두
# 파랑 순차 램프(SCALE_SEQ)를 쓰므로 여기서만 색상이 튀는 문제도 있었다.
# 진할수록 시급 — 회색은 램프 밖에 두어 '해당 없음'을 뜻한다.
STATE_COLOR = {
    "공영주차 0면": ACCENT_DEEP,
    "확충 후보": ACCENT,
    "보통": BACKDROP,
    "확충 불필요": NEUTRAL,
}

# 잔차 등급
GRADE_COLOR = {"공급부족": ALERT, "보통": INK["axis"], "공급여유": ACCENT}

# 나들이 등급 (코스추천)
COURSE_COLOR = {"⭐ 추천": ACCENT, "혼잡 주의": ALERT,
                "한산": ACCENT_LIGHT, "그 외": "#d5d4cc"}

# 이전 이름 유지 (지도 페이지가 참조) — 둘 다 크기 지표라 같은 순차 램프를 쓴다
SCALE_SUPPLY = SCALE_SEQ
SCALE_DEMAND = SCALE_SEQ


@st.cache_data
def load_panel() -> pd.DataFrame:
    if not PANEL_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(PANEL_PATH, dtype={"adm_cd": str, "admi_cd": str})
    df["timeslot"] = pd.Categorical(df["timeslot"], categories=TIMESLOTS, ordered=True)
    df["weekday"] = pd.Categorical(df["weekday"], categories=WEEKDAYS, ordered=True)
    return df


@st.cache_data
def load_residual() -> pd.DataFrame:
    """하위 호환용. 새 코드는 require_analysis('residual')을 쓴다."""
    return load_analysis("residual")


@st.cache_data
def load_analysis(key: str) -> pd.DataFrame:
    """정적 분석 산출물을 읽는다. 없으면 빈 DataFrame (페이지에서 안내 후 중단)."""
    filename, _ = ANALYSIS_FILES[key]
    path = PROCESSED / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})


def require_analysis(key: str) -> pd.DataFrame:
    """분석 결과가 없으면 어떤 스크립트를 돌려야 하는지 알려주고 멈춘다."""
    df = load_analysis(key)
    if df.empty:
        filename, script = ANALYSIS_FILES[key]
        st.error(
            f"`{filename}` 이 없습니다.\n\n"
            f"먼저 `python -m src.analysis.{script}` 를 실행하세요."
        )
        st.stop()
    return df


@st.cache_data
def load_boundary() -> dict:
    if not BOUNDARY_PATH.exists():
        return {}
    with open(BOUNDARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def require_data() -> pd.DataFrame:
    """패널이 없으면 안내하고 중단."""
    df = load_panel()
    if df.empty:
        st.error("분석 데이터가 없습니다. 아래를 먼저 실행하세요.")
        st.code(".\\.venv\\Scripts\\python.exe -m src.preprocess.build_panel --quarter 20261")
        st.stop()
    return df


def sidebar_filters(df: pd.DataFrame,
                    need: tuple[str, ...] = ("weekday", "timeslot", "gu")) -> dict:
    """페이지가 실제로 쓰는 필터만 그린다.

    전에는 세 개를 항상 띄웠는데, 동네 유형 페이지는 자치구를 쓰지 않고
    확충 우선순위 페이지는 요일·시간대를 쓰지 않는다.
    쓰지 않는 조건이 떠 있으면 바꿔도 화면이 안 변해 이용자가 혼란스럽다.
    선택값은 session_state에 남아 페이지를 옮겨도 유지된다.
    """
    st.sidebar.title("조회 조건")

    f = {"weekday": WEEKDAYS[0], "timeslot": TIMESLOTS[0], "gu": "전체"}

    if "weekday" in need:
        f["weekday"] = st.sidebar.selectbox(
            "요일", WEEKDAYS,
            index=WEEKDAYS.index(st.session_state.get("weekday", "토")),
            key="weekday",
        )
    if "timeslot" in need:
        cur_ts = st.session_state.get("timeslot", "오후")
        f["timeslot"] = st.sidebar.selectbox(
            "시간대", TIMESLOT_CHOICES,
            index=TIMESLOT_CHOICES.index(cur_ts if cur_ts in TIMESLOT_CHOICES else "오후"),
            format_func=lambda x: TIMESLOT_LABEL[x],
            key="timeslot",
        )
    if "gu" in need:
        gu_list = ["전체"] + sorted(df["sgg_nm"].dropna().unique())
        cur = st.session_state.get("gu", "전체")
        f["gu"] = st.sidebar.selectbox(
            "자치구", gu_list,
            index=gu_list.index(cur) if cur in gu_list else 0,
            key="gu",
        )

    st.sidebar.caption(
        f"기준: 생활인구 2026-06-02~07-27 (56일)\n\n"
        f"선택: **{when_phrase(f)}**"
    )
    return f


def when_phrase(f: dict) -> str:
    """선택한 시점을 사람 말로. '토요일 오후 15-18시' / '토요일 하루 전체(10-24시)'.

    시간대 '전체'를 TIMESLOT_LABEL로 그대로 풀면 '토요일 전체 10-24시'가 되어
    무엇이 전체인지(요일인지 시간대인지) 모호하다. 여기서 한 번만 다듬는다.
    """
    if f["timeslot"] == ALL_TIMESLOT:
        return f"{f['weekday']}요일 하루 전체({DAY_SPAN})"
    return f"{f['weekday']}요일 {TIMESLOT_LABEL[f['timeslot']]}"


def with_parking(df: pd.DataFrame) -> pd.DataFrame:
    """공영주차가 있는 동만 남긴다.

    0면 66개 동은 '숨겨야 할 결측'이 아니라 **이용자가 가장 먼저 알아야 할 사실**이다.
    (문정2동은 음식점 821개에 공영주차 0면이라 혼잡주의 1위 신촌동보다 사정이 나쁘다)
    그래서 지도·경고 목록에는 항상 넣고, 여기서 빼는 것은 다음 두 경우뿐이다.

      순위표    '빠듯 TOP 10'을 그대로 뽑으면 10개가 전부 0면 동이라 순위가 무의미해진다
      중앙값    0이 분포를 끌어내린다 (천명당주차면 중앙값 5.22 -> 6.49)

    예전에는 이 판단을 사이드바 체크박스 하나로 전역 처리했는데,
    지표마다 답이 달라 지도에서까지 66개가 사라지는 문제가 있었다.
    """
    return df[df["has_parking"]]


def scope_phrase(f: dict) -> str:
    """페이지 상단 리드 문장. 아래에 오는 결과를 이끄는 조건절 형태로 쓴다.

    사이드바의 '선택: ...' 표시와는 목적이 다르다.
    저쪽은 지금 무엇을 고른 상태인지 알리는 것이고, 이쪽은 결과로 이어지는 문장이다.
    자치구를 고르면 '가면', 전체면 '보면'으로 받아 두 경우의 어투를 맞춘다.
    """
    when = when_phrase(f)
    if f["gu"] == "전체":
        return f"{when}, 서울 전체를 보면"
    return f"{f['gu']}에 {when}에 가면"


@st.cache_data
def average_day(d: pd.DataFrame) -> pd.DataFrame:
    """한 요일의 시간대 전부를 행정동 1행으로 합친다 (시간대 '전체').

    비율은 평균내지 않고 인구를 평균낸 뒤 다시 계산한다.
    '천명당주차면'의 시간대별 평균과 '하루 평균 인구 천명당 주차면'은 다른 값인데
    (비율의 평균 != 평균의 비율), 이 지표가 뜻하는 바는 후자다.
    주차면은 고정이고 인구만 변하므로 분모만 평균내면 된다. young_ratio도 같은 이유.

    패널은 (행정동, 요일)마다 모든 시간대가 빠짐없이 있어 단순평균으로 충분하다.
    """
    MEAN = ["living_pop", "young_pop"]        # 시간에 따라 변하는 원자료
    DERIVED = ["slots_per_1k", "young_ratio"]  # 위에서 다시 계산할 비율
    keep = [c for c in d.columns if c not in MEAN + DERIVED + ["timeslot", "adm_cd"]]

    out = (d.groupby("adm_cd", observed=True, as_index=False)
             .agg({**{c: "first" for c in keep}, **{c: "mean" for c in MEAN}}))
    out["slots_per_1k"] = out["parking_slots"] / out["living_pop"] * 1000
    out["young_ratio"] = out["young_pop"] / out["living_pop"]
    out["timeslot"] = ALL_TIMESLOT
    return out[list(d.columns)]


def apply_filters(df: pd.DataFrame, f: dict, apply_gu: bool = True) -> pd.DataFrame:
    """선택 조건으로 패널을 자른다. 결과는 행정동 1개당 1행."""
    d = df[df["weekday"] == f["weekday"]]
    if f["timeslot"] == ALL_TIMESLOT:
        d = average_day(d)
    else:
        d = d[d["timeslot"] == f["timeslot"]].copy()
    if apply_gu and f["gu"] != "전체":
        d = d[d["sgg_nm"] == f["gu"]]
    return d


def mark_korean() -> None:
    """브라우저 자동 번역을 막는다.

    Streamlit은 <html lang="en">으로 내보내는데 내용은 한국어라,
    크롬이 '영어 페이지'로 보고 한국어로 번역하면서 멀쩡한 문구를 뭉갠다.
    ('시간대' -> '대처', '넉넉한/빠듯한 동네' -> '제거한/마치 같은 동네')

    st.markdown 안의 <script>는 실행되지 않으므로,
    iframe에서 부모 문서에 접근하는 components.html을 쓴다.
    """
    components.html(
        """
        <script>
        const doc = window.parent.document;
        doc.documentElement.lang = "ko";
        doc.documentElement.setAttribute("translate", "no");
        doc.documentElement.classList.add("notranslate");
        if (!doc.querySelector('meta[name="google"][content="notranslate"]')) {
            const m = doc.createElement("meta");
            m.name = "google";
            m.content = "notranslate";
            doc.head.appendChild(m);
        }
        </script>
        """,
        height=0,
    )


def page_header(title: str, desc: str) -> None:
    mark_korean()
    st.title(title)
    st.caption(desc)
