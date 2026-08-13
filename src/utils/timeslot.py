"""패널 키(행정동 × 요일 × 시간대)의 요일/시간대 파생 로직."""
from __future__ import annotations

import pandas as pd

from src.utils.settings import get_config


def get_timeslots() -> list[dict]:
    return get_config()["panel"]["timeslots"]


def get_weekday_names() -> list[str]:
    return get_config()["panel"]["weekday_names"]


def hour_to_timeslot(hour: int) -> str | None:
    """0~23시를 config에 정의된 시간대 구간명으로 변환. 어느 구간에도 없으면 None(심야)."""
    for slot in get_timeslots():
        if slot["start"] <= hour < slot["end"]:
            return slot["name"]
    return None


def add_panel_keys(df: pd.DataFrame, date_col: str, hour_col: str) -> pd.DataFrame:
    """날짜/시간 컬럼으로부터 요일(weekday)과 시간대(timeslot) 컬럼을 추가.

    심야(어느 구간에도 속하지 않는 시간)는 제거된다.
    """
    out = df.copy()
    dates = pd.to_datetime(out[date_col], format="%Y%m%d", errors="coerce")

    weekday_names = get_weekday_names()
    out["weekday"] = dates.dt.weekday.map(lambda i: weekday_names[i] if pd.notna(i) else None)
    out["is_weekend"] = dates.dt.weekday >= 5
    out["timeslot"] = out[hour_col].astype(int).map(hour_to_timeslot)

    return out[out["timeslot"].notna()]


def timeslot_order() -> list[str]:
    """차트 정렬용 시간대 순서."""
    return [s["name"] for s in get_timeslots()]


def get_recommend_exclude() -> list[str]:
    """'언제 가면 좋은가' 추천에서 뺄 시간대 (config.panel.recommend_exclude)."""
    return get_config()["panel"].get("recommend_exclude", [])


def recommend_timeslots() -> list[str]:
    """최적 시점 후보가 되는 시간대만. 조회·집계용인 timeslot_order()와 구분해서 쓴다.

    아침(06-10)은 패널에는 있지만 여기서 빠진다 — 주차가 비는 건 사실이나
    나들이객이 실행할 수 없는 답이라 '가장 여유로운 때'로 내밀 수 없다.
    """
    drop = set(get_recommend_exclude())
    return [s for s in timeslot_order() if s not in drop]
