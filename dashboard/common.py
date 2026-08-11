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
from src.utils.timeslot import get_timeslots, get_weekday_names  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
PANEL_PATH = PROCESSED / "panel.csv"
RESIDUAL_PATH = PROCESSED / "dong_residual.csv"
BOUNDARY_PATH = ROOT / "data" / "external" / "dong_boundary.geojson"

# 정적 분석 산출물 — 대시보드에서 다시 계산하지 않고 그대로 읽는다.
# (필터를 바꿔도 값이 흔들리면 보고서 수치와 어긋나기 때문)
ANALYSIS_FILES = {
    "real_demand": "dong_real_demand.csv",     # real_demand.py — 실수요 진단
    "suitability": "dong_suitability.csv",     # suitability.py — 나들이 적합도 지수
    "recommend": "dong_recommend.csv",         # recommend.py   — 추천/혼잡 등급
    "timeslot": "dong_timeslot.csv",           # timeslot_effect.py — 동별 최적 시점
    "sgg": "sgg_summary.csv",                  # district.py    — 자치구 요약
}

# 요일·시간대 정의는 config/config.yaml 한 곳에서만 관리한다.
# 예전에는 여기에 값이 따로 박혀 있어 구간 설계를 바꾸면 대시보드가 어긋났다.
WEEKDAYS = get_weekday_names()
TIMESLOTS = [s["name"] for s in get_timeslots()]
TIMESLOT_LABEL = {s["name"]: f'{s["name"]} {s["label"]}' for s in get_timeslots()}

# 공영주차 여유도 색상 (낮음=빨강, 높음=파랑)
SCALE_SUPPLY = "RdYlBu"
SCALE_DEMAND = "OrRd"

GRADE_COLOR = {"공급부족": "#D62728", "보통": "#B0B0B0", "공급여유": "#2CA02C"}


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
    if not RESIDUAL_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(RESIDUAL_PATH, dtype={"adm_cd": str, "admi_cd": str})


@st.cache_data
def load_analysis(key: str) -> pd.DataFrame:
    """정적 분석 산출물을 읽는다. 없으면 빈 DataFrame (페이지에서 안내 후 중단)."""
    path = PROCESSED / ANALYSIS_FILES[key]
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})


def require_analysis(key: str, script: str) -> pd.DataFrame:
    """분석 결과가 없으면 어떤 스크립트를 돌려야 하는지 알려주고 멈춘다."""
    df = load_analysis(key)
    if df.empty:
        st.error(
            f"`{ANALYSIS_FILES[key]}` 가 없습니다.\n\n"
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


def sidebar_filters(df: pd.DataFrame) -> dict:
    """전 페이지 공통 사이드바. 선택값은 session_state로 유지된다."""
    st.sidebar.title("조회 조건")

    weekday = st.sidebar.selectbox(
        "요일", WEEKDAYS,
        index=WEEKDAYS.index(st.session_state.get("weekday", "토")),
        key="weekday",
    )
    timeslot = st.sidebar.selectbox(
        "시간대", TIMESLOTS,
        index=TIMESLOTS.index(st.session_state.get("timeslot", "오후")),
        format_func=lambda x: TIMESLOT_LABEL[x],
        key="timeslot",
    )

    gu_list = ["전체"] + sorted(df["sgg_nm"].dropna().unique())
    gu = st.sidebar.selectbox(
        "자치구", gu_list,
        index=gu_list.index(st.session_state.get("gu", "전체")) if st.session_state.get("gu", "전체") in gu_list else 0,
        key="gu",
    )

    st.sidebar.divider()
    exclude_zero = st.sidebar.checkbox(
        "공영주차장 0면 동 제외", value=st.session_state.get("exclude_zero", True),
        key="exclude_zero",
        help="공영주차장이 없는 66개 행정동은 민영 데이터 미개방 영향이 섞여 있어 "
             "기본적으로 제외합니다. 해제하면 분석에 포함됩니다.",
    )

    st.sidebar.caption(
        f"기준: 생활인구 2026-06-02~07-27 (56일)\n\n"
        f"선택: **{weekday}요일 {TIMESLOT_LABEL[timeslot]}**"
    )

    return {"weekday": weekday, "timeslot": timeslot, "gu": gu, "exclude_zero": exclude_zero}


def scope_phrase(f: dict) -> str:
    """페이지 상단 리드 문장. 아래에 오는 결과를 이끄는 조건절 형태로 쓴다.

    사이드바의 '선택: ...' 표시와는 목적이 다르다.
    저쪽은 지금 무엇을 고른 상태인지 알리는 것이고, 이쪽은 결과로 이어지는 문장이다.
    자치구를 고르면 '가면', 전체면 '보면'으로 받아 두 경우의 어투를 맞춘다.
    """
    when = f"{f['weekday']}요일 {TIMESLOT_LABEL[f['timeslot']]}"
    if f["gu"] == "전체":
        return f"{when}, 서울 전체를 보면"
    return f"{f['gu']}에 {when}에 가면"


def apply_filters(df: pd.DataFrame, f: dict, apply_gu: bool = True) -> pd.DataFrame:
    """선택 조건으로 패널을 자른다. 결과는 행정동 1개당 1행."""
    d = df[(df["weekday"] == f["weekday"]) & (df["timeslot"] == f["timeslot"])].copy()
    if apply_gu and f["gu"] != "전체":
        d = d[d["sgg_nm"] == f["gu"]]
    if f["exclude_zero"]:
        d = d[d["has_parking"]]
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
