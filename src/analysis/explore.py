"""탐색적 분석 -> reports/figures/

산출물
------
  corr_heatmap.png      변수 간 피어슨 상관 (p-value 병기)
  weekday_timeslot.png  요일 × 시간대 생활인구 히트맵
  gu_distribution.png   자치구별 1,000명당 공영주차면 분포

주의: 공영주차면이 0인 행정동 66개는 민영 미개방 영향이 섞여 있어
      상관·분포 계산에서 제외한다 (has_parking=False).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.utils.logger import get_logger
from src.utils.plotstyle import use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR
from src.utils.timeslot import timeslot_order

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"

use_korean_font()

ANALYSIS_VARS = {
    "living_pop": "생활인구",
    "young_ratio": "20~30대비중",
    "parking_slots": "공영주차면",
    "slots_per_1k": "천명당주차면",
    "avg_fee_per_hour": "시간당요금",
    "store_food": "음식점수",
    "store_cafe": "카페수",
    "facility_cnt": "집객시설수",
    "resident_pop": "상주인구",
    "worker_pop": "직장인구",
}


def load_panel() -> pd.DataFrame:
    path = DATA_PROCESSED / "panel.csv"
    if not path.exists():
        raise FileNotFoundError("패널이 없습니다. build_panel.py를 먼저 실행하세요.")
    return pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})


def corr_with_pvalue(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = df.columns
    r = pd.DataFrame(np.eye(len(cols)), index=cols, columns=cols)
    p = pd.DataFrame(np.zeros((len(cols), len(cols))), index=cols, columns=cols)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            ok = df[[a, b]].dropna()
            if len(ok) < 3:
                r.loc[a, b] = r.loc[b, a] = np.nan
                p.loc[a, b] = p.loc[b, a] = np.nan
                continue
            rv, pv = stats.pearsonr(ok[a], ok[b])
            r.loc[a, b] = r.loc[b, a] = rv
            p.loc[a, b] = p.loc[b, a] = pv
    return r, p


def plot_corr(panel: pd.DataFrame) -> pd.DataFrame:
    """행정동 단위(토요일 오후 기준) 상관 히트맵."""
    d = panel[(panel.weekday == "토") & (panel.timeslot == "오후") & panel.has_parking]
    sub = d[list(ANALYSIS_VARS)].rename(columns=ANALYSIS_VARS)
    r, p = corr_with_pvalue(sub)

    fig, ax = plt.subplots(figsize=(9, 7.5))
    im = ax.imshow(r, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(r)), r.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(r)), r.index)

    for i in range(len(r)):
        for j in range(len(r)):
            v = r.iloc[i, j]
            if pd.isna(v):
                continue
            star = "*" if p.iloc[i, j] < 0.05 and i != j else ""
            ax.text(j, i, f"{v:.2f}{star}", ha="center", va="center",
                    fontsize=7.5, color="white" if abs(v) > 0.55 else "black")

    ax.set_title(f"변수 간 상관계수 (행정동 {len(d)}개, 토요일 오후)\n* p<0.05", pad=12)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "corr_heatmap.png", dpi=150)
    plt.close(fig)
    logger.info(f"저장: corr_heatmap.png (행정동 {len(d)}개)")
    return r


def plot_weekday_timeslot(panel: pd.DataFrame) -> pd.DataFrame:
    """요일 × 시간대 생활인구 (서울 평균 대비 지수)."""
    order = timeslot_order()
    piv = panel.pivot_table(index="weekday", columns="timeslot", values="living_pop", aggfunc="mean")
    piv = piv.reindex(index=["월", "화", "수", "목", "금", "토", "일"], columns=order)
    idx = piv / piv.values.mean() * 100

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(idx, cmap="YlOrRd")
    ax.set_xticks(range(len(order)), order)
    ax.set_yticks(range(len(idx)), idx.index)
    for i in range(idx.shape[0]):
        for j in range(idx.shape[1]):
            ax.text(j, i, f"{idx.iloc[i, j]:.1f}", ha="center", va="center", fontsize=9)
    ax.set_title("요일 × 시간대 생활인구 지수 (전체 평균=100)", pad=12)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "weekday_timeslot.png", dpi=150)
    plt.close(fig)
    logger.info("저장: weekday_timeslot.png")
    return idx


def plot_gu_distribution(panel: pd.DataFrame) -> pd.DataFrame:
    """자치구별 1,000명당 공영주차면 (토요일 오후)."""
    d = panel[(panel.weekday == "토") & (panel.timeslot == "오후") & panel.has_parking]
    med = d.groupby("sgg_nm")["slots_per_1k"].median().sort_values()

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.barh(med.index, med.values, color="#4C78A8")
    ax.set_xlabel("1,000명당 공영주차면 (중앙값)")
    ax.set_title("자치구별 공영주차 여유도 (토요일 오후)", pad=12)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "gu_distribution.png", dpi=150)
    plt.close(fig)
    logger.info("저장: gu_distribution.png")
    return med


def zero_parking_sensitivity(panel: pd.DataFrame) -> pd.DataFrame:
    """0면 66개 동을 넣고 뺀 상관계수 비교 (가설 1·3 민감도).

    상관·회귀에서 0면 동을 제외하는 것은 민영 미개방 영향이 섞여 있기 때문이지만,
    `slots_per_1k = 0`은 결측이 아니라 실제 값이므로 포함한 결과도 함께 제시해야
    "왜 뺐느냐"에 답할 수 있다.
    """
    d = panel[(panel.weekday == "토") & (panel.timeslot == "오후")]
    rows = []
    for a, label in [("living_pop", "생활인구"), ("store_food", "음식점수"),
                     ("store_cafe", "카페수"), ("young_ratio", "20~30대비중")]:
        ex = d[d.has_parking].dropna(subset=[a, "slots_per_1k"])
        inc = d.dropna(subset=[a, "slots_per_1k"])
        r_ex, p_ex = stats.pearsonr(ex[a], ex.slots_per_1k)
        r_in, p_in = stats.pearsonr(inc[a], inc.slots_per_1k)
        rows.append({"변수": label, "제외 r": r_ex, "제외 p": p_ex, "제외 n": len(ex),
                     "포함 r": r_in, "포함 p": p_in, "포함 n": len(inc)})
    return pd.DataFrame(rows).set_index("변수")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    logger.info(f"패널 {len(panel):,}행 / 행정동 {panel.admi_cd.nunique()}개")

    r = plot_corr(panel)
    idx = plot_weekday_timeslot(panel)
    med = plot_gu_distribution(panel)

    print("\n=== 가설 3 검증: 매력도 vs 1인당 공영주차면 ===")
    for v in ["음식점수", "카페수", "20~30대비중", "생활인구"]:
        print(f"  {v:12} vs 천명당주차면 : r = {r.loc[v, '천명당주차면']:+.3f}")

    sens = zero_parking_sensitivity(panel)
    print("\n=== 민감도: 공영주차 0면 66개 동을 포함하면 (천명당주차면과의 상관) ===")
    for v, row in sens.iterrows():
        flip = "  ← 부호 반전" if row["제외 r"] * row["포함 r"] < 0 else ""
        print(f"  {v:12} 제외 r={row['제외 r']:+.3f}(n={row['제외 n']:.0f})"
              f"   포함 r={row['포함 r']:+.3f}(n={row['포함 n']:.0f}){flip}")
    print("  → 결론은 유지되나(가설1 매우 약함·가설3 기각) 제외 시 음의 상관이 다소 강해 보임.")
    print("    보고서에는 제외 기준과 함께 이 표를 병기할 것.")

    print("\n=== 요일×시간대 지수 (전체=100) ===")
    print(idx.round(1).to_string())

    print("\n=== 자치구 공영주차 여유도 ===")
    print(f"  상위 3: {', '.join(f'{k}({v:.1f})' for k, v in med.tail(3)[::-1].items())}")
    print(f"  하위 3: {', '.join(f'{k}({v:.1f})' for k, v in med.head(3).items())}")


if __name__ == "__main__":
    main()
