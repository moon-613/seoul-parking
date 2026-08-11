"""일별 추세 분석 -> reports/figures/daily_trend.png

패널은 56일을 요일×시간대로 평균내므로 날짜 축이 사라진다.
그 평균이 믿을 만한지 확인하려면 일별 원본을 봐야 한다.

확인하는 것
----------
  1. 요일별 8개 표본이 서로 비슷한가 (변동계수)
  2. 평일에 낀 공휴일이 평균을 왜곡하는가
  3. 6월 → 7월 추세 변화가 있는가
"""
from __future__ import annotations

import glob
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.utils.holidays import add_day_flags
from src.utils.logger import get_logger
from src.utils.plotstyle import use_korean_font
from src.utils.settings import DATA_RAW, ROOT_DIR

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

WD = ["월", "화", "수", "목", "금", "토", "일"]
COMMUTE_HOURS = (8, 9)      # 출근시간 — 휴일 판별에 민감
AFTERNOON_HOURS = (14, 17)  # 오후 — 나들이 시간대


def load_daily() -> pd.DataFrame:
    """일별 서울 전체 평균 (행정동 평균)."""
    files = sorted(glob.glob(str(DATA_RAW / "living_population" / "*.csv")))
    if not files:
        raise FileNotFoundError("생활인구 파일이 없습니다.")

    rows = []
    for f in files:
        d = pd.read_csv(f, usecols=["TMZON_PD_SE", "TOT_LVPOP_CO"])
        ymd = os.path.basename(f)[:8]
        dt = datetime.strptime(ymd, "%Y%m%d")
        rows.append({
            "date_id": ymd,
            "date": dt,
            "weekday": WD[dt.weekday()],
            "commute": d[d.TMZON_PD_SE.between(*COMMUTE_HOURS)].TOT_LVPOP_CO.mean(),
            "afternoon": d[d.TMZON_PD_SE.between(*AFTERNOON_HOURS)].TOT_LVPOP_CO.mean(),
        })

    t = add_day_flags(pd.DataFrame(rows), "date_id")
    logger.info(f"일별 데이터 {len(t)}일 ({t.date.min():%Y-%m-%d} ~ {t.date.max():%Y-%m-%d})")
    return t


def check_variance(t: pd.DataFrame) -> pd.DataFrame:
    """요일별 표본 변동. 공휴일 포함/제외를 나란히 본다."""
    def cv(sub: pd.DataFrame) -> pd.Series:
        g = sub.groupby("weekday", observed=True)["afternoon"].agg(["size", "mean", "std"])
        return (g["std"] / g["mean"] * 100).round(2)

    out = pd.DataFrame({
        "전체": cv(t),
        "공휴일 제외": cv(t[t.day_type != "공휴일"]),
    }).reindex(WD)
    out["개선"] = (out["전체"] - out["공휴일 제외"]).round(2)

    logger.info("요일별 변동계수(%) — 오후 생활인구")
    for wd, r in out.iterrows():
        mark = "  ← 공휴일 영향" if r["개선"] > 0.5 else ""
        logger.info(f"  {wd}  전체 {r['전체']:>5.2f}  제외 {r['공휴일 제외']:>5.2f}{mark}")
    return out


def compare_day_types(t: pd.DataFrame) -> pd.DataFrame:
    """평일 / 주말 / 공휴일 비교."""
    g = t.groupby("day_type", observed=True).agg(
        일수=("date", "size"),
        출근시간=("commute", "mean"),
        오후=("afternoon", "mean"),
    ).round(0)
    base = g.loc["평일", "출근시간"]
    g["평일대비_출근"] = ((g["출근시간"] / base - 1) * 100).round(1)

    logger.info("일 유형별 비교")
    logger.info(f"\n{g.to_string()}")
    return g


def monthly_trend(t: pd.DataFrame) -> pd.DataFrame:
    """6월 vs 7월 (공휴일 제외한 평일 기준)."""
    w = t[t.day_type == "평일"].copy()
    w["월"] = w.date.dt.month
    g = w.groupby("월").agg(일수=("date", "size"), 출근시간=("commute", "mean"),
                            오후=("afternoon", "mean")).round(0)
    diff = (g.loc[7, "오후"] / g.loc[6, "오후"] - 1) * 100
    logger.info(f"6월 → 7월 오후 생활인구 변화: {diff:+.1f}%")
    return g


def plot(t: pd.DataFrame, var: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), height_ratios=[2, 1])

    # ── 일별 시계열 ──
    ax = axes[0]
    colors = {"평일": "#4C78A8", "주말": "#54A24B", "공휴일": "#D62728"}
    for dt_name, sub in t.groupby("day_type", observed=True):
        ax.scatter(sub.date, sub.afternoon, s=42, label=dt_name,
                   color=colors[dt_name], zorder=3)
    ax.plot(t.date, t.afternoon, color="#BBBBBB", lw=1, zorder=1)

    for _, r in t[t.holiday_nm.notna()].iterrows():
        ax.annotate(r.holiday_nm, (r.date, r.afternoon), textcoords="offset points",
                    xytext=(0, -16), ha="center", fontsize=8.5, color="#D62728")

    wk = t[t.day_type == "평일"].afternoon.mean()
    we = t[t.day_type == "주말"].afternoon.mean()
    ax.axhline(wk, color="#4C78A8", ls="--", lw=1, alpha=0.7, label=f"평일 평균 {wk:,.0f}")
    ax.axhline(we, color="#54A24B", ls="--", lw=1, alpha=0.7, label=f"주말 평균 {we:,.0f}")
    ax.set_ylabel("오후 생활인구(동당 평균)")
    ax.set_title("일별 생활인구 추세 — 평일에 낀 공휴일은 주말 수준으로 떨어진다", pad=12)
    ax.legend(fontsize=9, ncol=5)
    ax.grid(alpha=0.3)

    # ── 요일별 변동계수 ──
    ax = axes[1]
    x = range(len(WD))
    ax.bar([i - 0.2 for i in x], var["전체"], width=0.4, label="공휴일 포함", color="#D62728")
    ax.bar([i + 0.2 for i in x], var["공휴일 제외"], width=0.4, label="공휴일 제외", color="#4C78A8")
    ax.set_xticks(list(x), WD)
    ax.set_ylabel("변동계수(%)")
    ax.set_title("요일별 표본 8개의 흔들림 — 낮을수록 평균이 믿을 만함", pad=10)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "daily_trend.png", dpi=150)
    plt.close(fig)
    logger.info("저장: daily_trend.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    t = load_daily()

    var = check_variance(t)
    types = compare_day_types(t)
    monthly_trend(t)
    plot(t, var)

    print("\n=== 일 유형별 (동당 평균 생활인구) ===")
    print(types.to_string())

    print("\n=== 공휴일 상세 ===")
    h = t[t.holiday_nm.notna()][["date", "weekday", "day_type", "holiday_nm", "commute", "afternoon"]]
    print(h.to_string(index=False, float_format="%.0f"))

    print("\n=== 요일별 변동계수(%) ===")
    print(var.to_string())


if __name__ == "__main__":
    main()
