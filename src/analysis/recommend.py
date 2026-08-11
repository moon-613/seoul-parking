"""가설 4 — 매력도와 주차 여유를 동시에 갖춘 추천 동네 -> data/processed/dong_recommend.csv

검증하는 것
----------
"가고 싶은 동네일수록 공영주차가 부족하다"가 전반적 경향이라면(가설 1·3),
**그 경향을 벗어나 둘 다 갖춘 동네가 실제로 존재하는가.** 존재한다면 그곳이 추천 대상이다.

왜 잔차만으로는 부족한가
---------------------
`residual.py`의 잔차는 '생활인구 대비 주차가 많은가'만 본다.
잔차가 큰 동네 중에는 애초에 갈 이유가 없는 곳(놀거리 없는 주거지)이 섞인다.
주차만 넉넉한 동네를 추천하면 서비스가 성립하지 않으므로 **매력도 조건을 함께 건다.**

두 축
----
  주차 여유 = residual.py의 표준화 잔차 z_residual (기대 대비 몇 배인지)
  매력도    = 음식점 + 카페 + 집객시설의 백분위 평균
              (절대 개수는 큰 동네가 독식하므로 순위로 환산)

추천 판정
--------
  z_residual >= +1.0 (config: recommend_residual_threshold) 이고
  매력도 백분위 >= 60  -> 추천
잔차 하위(<= -1.0)이면서 매력도가 높은 곳은 '혼잡 주의'로 따로 표시한다.
사람이 몰리는데 공영주차가 없는, 가장 시간을 버리기 쉬운 조합이기 때문이다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.utils.plotstyle import annotate_spread, use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR, get_config

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

APPEAL_VARS = ["store_food", "store_cafe", "facility_cnt"]
APPEAL_MIN = 60.0   # 매력도 백분위 하한


def load_joined() -> pd.DataFrame:
    """잔차 결과에 매력도 변수를 붙인다 (기준 시점은 residual.py와 동일)."""
    res_path = DATA_PROCESSED / "dong_residual.csv"
    if not res_path.exists():
        raise FileNotFoundError("잔차 결과가 없습니다. residual.py를 먼저 실행하세요.")
    res = pd.read_csv(res_path, dtype={"adm_cd": str, "admi_cd": str})

    cfg = get_config()["panel"]["regression_baseline"]
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    base = panel[(panel.weekday == cfg["weekday"]) & (panel.timeslot == cfg["timeslot"])]

    d = res.merge(base[["admi_cd", "store_cafe", "facility_cnt", "slots_per_1k"]],
                  on="admi_cd", how="left")
    logger.info(f"잔차 {len(res)}개 동에 매력도 결합 / 결측 {d[APPEAL_VARS].isna().any(axis=1).sum()}개")
    return d.dropna(subset=APPEAL_VARS)


def score(d: pd.DataFrame) -> pd.DataFrame:
    """매력도를 백분위 평균으로 환산하고 등급을 매긴다."""
    cfg = get_config()["imbalance_index"]
    lo = cfg["vulnerable_residual_threshold"]
    hi = cfg["recommend_residual_threshold"]

    d = d.copy()
    for c in APPEAL_VARS:
        d[f"pct_{c}"] = d[c].rank(pct=True) * 100
    d["appeal"] = d[[f"pct_{c}" for c in APPEAL_VARS]].mean(axis=1)
    d["parking_pct"] = d.z_residual.rank(pct=True) * 100

    d["등급"] = "그 외"
    d.loc[(d.z_residual >= hi) & (d.appeal >= APPEAL_MIN), "등급"] = "추천"
    d.loc[(d.z_residual <= lo) & (d.appeal >= APPEAL_MIN), "등급"] = "혼잡 주의"
    d.loc[(d.z_residual >= hi) & (d.appeal < APPEAL_MIN), "등급"] = "한산"

    # 추천 순위: 매력도와 주차 여유를 같은 비중으로
    d["종합점수"] = (d.appeal + d.parking_pct) / 2

    for k, v in d.등급.value_counts().items():
        logger.info(f"  {k}: {v}개 동")
    return d


def plot(d: pd.DataFrame) -> None:
    colors = {"추천": "#2CA02C", "혼잡 주의": "#D62728", "한산": "#7F9FBF", "그 외": "#D9D9D9"}
    cfg = get_config()["imbalance_index"]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))

    # ① 매력도 × 주차 여유 사분면
    ax = axes[0]
    for g in ["그 외", "한산", "혼잡 주의", "추천"]:
        sub = d[d.등급 == g]
        ax.scatter(sub.appeal, sub.z_residual, s=22, alpha=0.8, label=f"{g} ({len(sub)})",
                   color=colors[g], edgecolor="none")
    ax.axvline(APPEAL_MIN, color="#888", ls="--", lw=1)
    ax.axhline(cfg["recommend_residual_threshold"], color="#2CA02C", ls="--", lw=1)
    ax.axhline(cfg["vulnerable_residual_threshold"], color="#D62728", ls="--", lw=1)

    annotate_spread(ax, [(r.appeal, r.z_residual, r.admi_nm) for _, r
                         in d[d.등급 == "추천"].nlargest(6, "종합점수").iterrows()])
    annotate_spread(ax, [(r.appeal, r.z_residual, r.admi_nm) for _, r
                         in d[d.등급 == "혼잡 주의"].nlargest(4, "appeal").iterrows()],
                    color="#8B1A1A")

    ax.set_xlabel("매력도 백분위 (음식점·카페·집객시설)")
    ax.set_ylabel("공영주차 여유 (표준화 잔차)")
    ax.set_title(f"매력도 × 주차 여유 (행정동 {len(d)}개)")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(alpha=0.3)

    # ② 추천 동네 순위
    ax = axes[1]
    top = d[d.등급 == "추천"].nlargest(12, "종합점수").iloc[::-1]
    if top.empty:
        ax.text(0.5, 0.5, "추천 조건을 만족하는 동네가 없습니다", ha="center", va="center")
        ax.axis("off")
    else:
        y = np.arange(len(top))
        ax.barh(y - 0.2, top.appeal, height=0.4, color="#F58518", label="매력도")
        ax.barh(y + 0.2, top.parking_pct, height=0.4, color="#4C78A8", label="주차 여유")
        ax.set_yticks(y, [f"{r.sgg_nm} {r.admi_nm}" for _, r in top.iterrows()], fontsize=9)
        ax.set_xlabel("백분위 (100에 가까울수록 좋음)")
        ax.set_title("추천 동네 TOP 12")
        ax.legend(fontsize=9, loc="lower right")
        ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "recommend.png", dpi=150)
    plt.close(fig)
    logger.info("저장: recommend.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    d = score(load_joined())

    cols = ["adm_cd", "admi_cd", "sgg_nm", "admi_nm", "등급", "종합점수", "appeal",
            "parking_pct", "z_residual", "supply_ratio", "parking_slots", "expected_slots",
            "slots_per_1k", "living_pop", *APPEAL_VARS]
    dest = DATA_PROCESSED / "dong_recommend.csv"
    d[cols].sort_values("종합점수", ascending=False).to_csv(dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(d)}행)")

    plot(d)

    show = ["sgg_nm", "admi_nm", "appeal", "parking_pct", "종합점수",
            "parking_slots", "store_food", "living_pop"]
    rec = d[d.등급 == "추천"].nlargest(15, "종합점수")
    print(f"\n=== 추천 동네 TOP 15 (총 {(d.등급 == '추천').sum()}개) ===")
    print(rec[show].to_string(index=False, float_format="%.0f"))

    warn = d[d.등급 == "혼잡 주의"].nlargest(10, "appeal")
    print(f"\n=== 혼잡 주의 TOP 10 — 사람은 몰리는데 공영주차가 없는 곳 (총 {(d.등급 == '혼잡 주의').sum()}개) ===")
    print(warn[show].to_string(index=False, float_format="%.0f"))

    # 가설 4 판정: 두 조건을 동시에 만족하는 동네가 실제로 존재하는가
    n = (d.등급 == "추천").sum()
    print(f"\n=== 가설 4 판정 ===")
    print(f"  매력도 {APPEAL_MIN:.0f}백분위 이상 & 잔차 +1.0 이상 동시 만족: {n}개 동 "
          f"({n / len(d):.1%})")
    print(f"  -> {'지지' if n > 0 else '기각'}: 전반적 상충 관계에도 예외 지역이 "
          f"{'존재함' if n > 0 else '존재하지 않음'}")


if __name__ == "__main__":
    main()
