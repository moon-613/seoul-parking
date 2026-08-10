"""공휴일 정의 — 평일에 낀 공휴일은 '보통의 평일'이 아니다.

수집 기간(2026-06-02 ~ 07-27)에 해당하는 공휴일:
  2026-06-03(수)  제9회 전국동시지방선거 — 임시공휴일
  2026-06-06(토)  현충일 — 토요일이라 이미 주말
  2026-07-17(금)  제헌절 — 2026년부터 공휴일 부활

데이터로도 독립 검증됨: 출근시간(08~09시) 생활인구가 평일 평균 24,505명인데
6/3은 23,286명, 7/17은 22,620명으로 주말 수준(23,070명)까지 떨어진다.

7/17이 금요일 공휴일이라 이어지는 7/18~19 주말도 평소보다 낮다(연휴 유출).
'평소 주말'과 구분하기 위해 연휴 주말도 표시한다.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

# 공휴일 (수집 기간 전후 여유 포함)
HOLIDAYS: dict[date, str] = {
    date(2026, 6, 3): "지방선거",
    date(2026, 6, 6): "현충일",
    date(2026, 7, 17): "제헌절",
    date(2026, 8, 15): "광복절",
}

# 공휴일과 붙어 연휴가 된 주말
LONG_WEEKEND: dict[date, str] = {
    date(2026, 7, 18): "제헌절 연휴",
    date(2026, 7, 19): "제헌절 연휴",
}


def is_holiday(d) -> bool:
    return _to_date(d) in HOLIDAYS


def holiday_name(d) -> str | None:
    dd = _to_date(d)
    return HOLIDAYS.get(dd) or LONG_WEEKEND.get(dd)


def _to_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, pd.Timestamp):
        return d
    return pd.Timestamp(d).date()


def day_type(d) -> str:
    """평일 / 주말 / 공휴일 3분류.

    공휴일은 요일과 무관하게 '공휴일'로 본다. 다만 토·일에 걸린 공휴일은
    어차피 주말이므로 '주말'로 둔다(현충일 6/6이 여기 해당).
    """
    ts = pd.Timestamp(d)
    weekend = ts.weekday() >= 5
    if is_holiday(ts) and not weekend:
        return "공휴일"
    return "주말" if weekend else "평일"


def add_day_flags(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """날짜 컬럼으로부터 day_type / is_holiday / holiday_nm 을 붙인다."""
    out = df.copy()
    dates = pd.to_datetime(out[date_col], format="%Y%m%d", errors="coerce")
    out["day_type"] = dates.map(day_type)
    out["is_holiday"] = dates.map(is_holiday)
    out["holiday_nm"] = dates.map(holiday_name)
    return out
