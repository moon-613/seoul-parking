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
