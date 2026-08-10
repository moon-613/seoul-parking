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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PANEL_PATH = ROOT / "data" / "processed" / "panel.csv"
RESIDUAL_PATH = ROOT / "data" / "processed" / "dong_residual.csv"
BOUNDARY_PATH = ROOT / "data" / "external" / "dong_boundary.geojson"

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
TIMESLOTS = ["아침", "점심", "오후", "저녁밤"]
TIMESLOT_LABEL = {"아침": "아침 06-11시", "점심": "점심 11-14시",
                  "오후": "오후 14-18시", "저녁밤": "저녁밤 18-24시"}

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


def apply_filters(df: pd.DataFrame, f: dict, apply_gu: bool = True) -> pd.DataFrame:
    """선택 조건으로 패널을 자른다. 결과는 행정동 1개당 1행."""
    d = df[(df["weekday"] == f["weekday"]) & (df["timeslot"] == f["timeslot"])].copy()
    if apply_gu and f["gu"] != "전체":
        d = d[d["sgg_nm"] == f["gu"]]
    if f["exclude_zero"]:
        d = d[d["has_parking"]]
    return d


def page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
